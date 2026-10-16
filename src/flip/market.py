"""Market scan: where are foreclosures cheap compared with new and resale homes?

Reads a listings CSV (one row per listing: city, kind, price, floor area...)
and summarizes price per sqm by city and kind. Each city gets a benchmark:
the median resale price per sqm when there are at least 3 resale listings,
otherwise the median new-unit price per sqm (a ceiling, since a renovated
resale rarely sells for more than new). Foreclosures priced at or below
70% of their city's benchmark pass the quick screen from
docs/how-to-use.md Step 2 and are listed as candidates.

Run `python -m flip.market data/market/cavite_listings.csv` to write
output/market_report.xlsx.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from flip.batch import file_notes, load_deals

SCREEN = 0.70             # foreclosure price per sqm / benchmark, at most
MIN_BENCHMARK = 3         # listings needed before a median is used as a benchmark
MIN_FLOOR_AREA = 25       # sqm; smaller is usually a lot area or a typo
PER_SQM_RANGE = (10_000, 150_000)  # outside this, treat the listing as a data error
KINDS = ["new", "resale", "foreclosed"]


def load_listings(path) -> pd.DataFrame:
    """Read a listings CSV, skipping the # note lines at the top."""
    return load_deals(path)


def clean(listings: pd.DataFrame) -> pd.DataFrame:
    """Normalize kinds, drop repeated links, and mark which rows can be used.

    Adds price_per_sqm, usable (counted in medians), and excluded_reason.
    """
    df = listings.copy()
    df["kind"] = df["kind"].fillna("").astype(str).str.strip().str.lower().replace({"": "unknown"})
    reason = df["kind_reason"].fillna("").astype(str).str.lower() if "kind_reason" in df else ""
    df.loc[reason.str.contains("pasalo"), "kind"] = "pasalo"
    # The same property is often posted more than once: same link, or the same
    # city, kind, price, and floor area under different links. Count it once.
    df = df.drop_duplicates(subset="link", keep="first")
    df = df.drop_duplicates(subset=["city", "kind", "price", "floor_area_sqm"], keep="first")
    df = df.reset_index(drop=True)

    df["price_per_sqm"] = df["price"] / df["floor_area_sqm"]
    excluded = []
    for _, row in df.iterrows():
        if row["kind"] == "pasalo":
            excluded.append("pasalo: price is usually only the cash-out")
        elif row["kind"] not in KINDS:
            excluded.append("kind unknown")
        elif pd.isna(row["floor_area_sqm"]):
            excluded.append("no floor area")
        elif row["floor_area_sqm"] < MIN_FLOOR_AREA:
            excluded.append(f"floor area under {MIN_FLOOR_AREA} sqm")
        elif not PER_SQM_RANGE[0] <= row["price_per_sqm"] <= PER_SQM_RANGE[1]:
            excluded.append("price per sqm looks like a data error")
        else:
            excluded.append("")
    df["excluded_reason"] = excluded
    df["usable"] = df["excluded_reason"] == ""
    return df


def city_summary(listings: pd.DataFrame) -> pd.DataFrame:
    """One row per city: counts and median price per sqm by kind, the
    benchmark, the foreclosure ratio, and whether the city passes the screen."""
    usable = listings[listings["usable"]]
    rows = []
    for city, all_in_city in listings.groupby("city", sort=True):
        mine = usable[usable["city"] == city]
        row = {"city": city, "listings": len(all_in_city)}
        for kind in KINDS:
            per_sqm = mine[mine["kind"] == kind]["price_per_sqm"]
            row[f"{kind}_count"] = len(per_sqm)
            row[f"{kind}_median_per_sqm"] = per_sqm.median() if len(per_sqm) else float("nan")

        if row["resale_count"] >= MIN_BENCHMARK:
            row["benchmark"], row["benchmark_per_sqm"] = "resale", row["resale_median_per_sqm"]
        elif row["new_count"] >= MIN_BENCHMARK:
            row["benchmark"], row["benchmark_per_sqm"] = "new (ceiling)", row["new_median_per_sqm"]
        else:
            row["benchmark"], row["benchmark_per_sqm"] = "none", float("nan")

        ratio = row["foreclosed_median_per_sqm"] / row["benchmark_per_sqm"]
        row["foreclosed_vs_benchmark"] = ratio
        # Even 1-2 resale listings are a useful sanity check on a new-unit benchmark
        row["foreclosed_vs_resale"] = (row["foreclosed_median_per_sqm"]
                                       / row["resale_median_per_sqm"])
        if pd.isna(ratio):
            row["screen"] = "not enough data"
        elif ratio <= SCREEN:
            row["screen"] = "foreclosures look cheap: worth a closer look"
        else:
            row["screen"] = "foreclosures near benchmark: little room"
        rows.append(row)
    return pd.DataFrame(rows)


def candidates(listings: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """Usable foreclosures at or below 70% of their city's benchmark, best first."""
    by_city = summary.set_index("city")
    foreclosed = listings[listings["usable"] & (listings["kind"] == "foreclosed")].copy()
    foreclosed["benchmark"] = foreclosed["city"].map(by_city["benchmark"])
    foreclosed["benchmark_per_sqm"] = foreclosed["city"].map(by_city["benchmark_per_sqm"])
    foreclosed["vs_benchmark"] = foreclosed["price_per_sqm"] / foreclosed["benchmark_per_sqm"]
    foreclosed["vs_resale"] = (foreclosed["price_per_sqm"]
                               / foreclosed["city"].map(by_city["resale_median_per_sqm"]))
    picked = foreclosed[foreclosed["vs_benchmark"] <= SCREEN]
    columns = ["city", "barangay", "subdivision", "type", "price", "price_basis",
               "floor_area_sqm", "price_per_sqm", "benchmark", "benchmark_per_sqm",
               "vs_benchmark", "vs_resale", "occupancy", "date_listed", "link"]
    return (picked.sort_values("vs_benchmark")[[c for c in columns if c in picked]]
            .reset_index(drop=True))


def about_table(path, notes: list[str], listings: pd.DataFrame) -> pd.DataFrame:
    rows = [
        ("Generated", date.today().isoformat()),
        ("Source file", str(path)),
        ("Data notes", " ".join(n.lstrip("# ") for n in notes) or "-"),
        ("Listings", f"{len(listings)} after removing repeated links; "
                     f"{int(listings['usable'].sum())} usable for medians"),
        ("Price per sqm", "Price / floor area. Asking prices (minimum bids for Pag-IBIG), "
                          "not sale prices."),
        ("Kinds", "new = developer unit (pre-selling, RFO, promo, reservation); resale = "
                  "owner selling an existing home; foreclosed = bank or Pag-IBIG; pasalo = "
                  "loan takeover (left out: price is usually only the cash-out); unknown = "
                  "not clear from the listing (left out)."),
        ("Benchmark", f"Median resale price per sqm when a city has at least {MIN_BENCHMARK} "
                      f"resale listings; otherwise the median new-unit price per sqm (with at "
                      f"least {MIN_BENCHMARK} new listings), which is a ceiling: a renovated "
                      "resale rarely sells for more than new. Fewer listings: not enough data."),
        ("Foreclosed vs resale", "Shown whenever a city has any resale listings, even 1 or 2, "
                                 "as a sanity check: a new-unit benchmark can be pushed up by "
                                 "premium projects."),
        ("Repeated listings", "The same property posted more than once (same link, or the "
                              "same city, kind, price, and floor area) is counted once."),
        ("Screen", f"A foreclosure at or below {SCREEN:.0%} of its city's benchmark leaves "
                   "room for renovation, buying and selling costs, and a profit in the best "
                   "case (see docs/how-to-use.md Step 2). It is a first filter, not a "
                   "verdict: analyze each candidate with its own comps."),
        ("Left out of medians", f"Unknown kind, pasalo, no floor area, floor area under "
                                f"{MIN_FLOOR_AREA} sqm, or price per sqm outside "
                                f"{PER_SQM_RANGE[0]:,}-{PER_SQM_RANGE[1]:,} (likely data "
                                "errors). They stay on the All listings sheet with the reason."),
        ("Limits", "A sample of each site's first result pages, not every listing. Some "
                   "sites block automated reading, so they are missing. Listing text decides "
                   "the kind and can be wrong. Medians from few listings are shaky: check "
                   "the counts."),
    ]
    return pd.DataFrame(rows, columns=["Topic", "Details"])


def write_report(path, output) -> Path:
    """Build the market report workbook from a listings CSV."""
    from flip.export import write_workbook  # the same formatting as the deal report

    listings = clean(load_listings(path))
    summary = city_summary(listings)
    picks = candidates(listings, summary)
    order = ["city", "kind", "kind_reason", "barangay", "subdivision", "type", "price",
             "price_basis", "floor_area_sqm", "price_per_sqm", "lot_area_sqm", "year_built",
             "date_listed", "occupancy", "excluded_reason", "source", "link", "collected"]
    sheets = {
        "About": about_table(path, file_notes(path), listings),
        "City summary": summary,
        "Candidates": picks,
        "All listings": listings[[c for c in order if c in listings]],
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_workbook(sheets, output, sample=False)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Price per sqm by city: new, resale, foreclosed.")
    parser.add_argument("path", help="listings CSV, e.g. data/market/cavite_listings.csv")
    parser.add_argument("--output", default="output/market_report.xlsx")
    args = parser.parse_args()
    try:
        print(f"Wrote {write_report(args.path, args.output)}")
    except PermissionError as error:
        sys.exit(f"Can't write {error.filename}. If it is open in Excel, close it and run again.")
