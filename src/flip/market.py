"""Market scan: where are foreclosures cheap compared with similar homes?

Reads a listings CSV (one row per listing: city, kind, price, floor area,
subdivision...) and summarizes price per sqm by city and kind.

Each foreclosure is compared like for like, in this order:
    1. resale listings in the same subdivision, of a similar size (floor
       area within 25%) and type (townhouse/rowhouse, attached, detached)
    2. new units in the same subdivision, same size and type rule (a
       ceiling: similar houses, new)
    3. the city's resale median
    4. the city's new-unit median. This one can only rule a house out:
       new units elsewhere in the city are often in pricier subdivisions,
       so being far below them proves little, but being close to even
       those prices means there is no room.
Foreclosures priced at or below 70% of what they were compared with pass
the quick screen from docs/how-to-use.md Step 2 and are listed as
candidates. Each also shows how many foreclosures are for sale in its
subdivision: when you resell, those are your competition.

Run `python -m flip.market data/market/cavite_listings.csv` to write
output/market_report.xlsx.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from flip.batch import file_notes, load_deals
from flip.pagibig import PROPERTY_NUMBER

SCREEN = 0.70             # foreclosure price per sqm / benchmark, at most
MIN_BENCHMARK = 3         # listings needed before a city median is used as a benchmark
MIN_SAME_SUBDIVISION = 2  # listings needed before a subdivision median is used
MIN_FLOOR_AREA = 25       # sqm; smaller is usually a lot area or a typo
PER_SQM_RANGE = (10_000, 150_000)  # outside this, treat the listing as a data error
KINDS = ["new", "resale", "foreclosed"]
# Like for like (also used by flip.draft to pick comps): floor area within 25%,
# and the same type group when both types are known.
AREA_TOLERANCE = 0.25
TYPE_GROUPS = {
    "townhouse": "row", "rowhouse": "row", "row house": "row",
    "single attached": "attached", "duplex": "attached", "double attached": "attached",
    "quadruplex": "attached", "single detached": "detached",
}

LOOK = "worth a closer look"
LITTLE_ROOM = "little room"
NO_FAIR = "no fair comparison: collect resale prices from its subdivision"
SCREEN_ORDER = {LOOK: 0, LITTLE_ROOM: 1, NO_FAIR: 2}

# Words that don't tell subdivisions apart: "The Westdale Villas" and
# "Westdale Villas Subdivision" are the same place.
NOISE_WORDS = {"the", "subdivision", "subd", "phase", "ph"}
NOT_A_NAME = re.compile(r"^(?:\d+[a-z]?|i{1,3}|iv|vi{0,3}|ix|x)$")  # 2, 2b, 2000, II, IV


def subdivision_key(name, city="") -> str:
    """A subdivision name reduced to the words that identify it, so the same
    place written two ways matches: "MICARA ESTATES TANZA PHASE 1" and
    "Micara Estates" (in Tanza) both become "micara estate". Phase numbers,
    the city's name, and plurals don't count."""
    text = "" if name is None or pd.isna(name) else str(name).lower()
    if re.sub(r"[^a-z]", "", text) == "nonsubdivision":
        return ""  # Pag-IBIG's label for a house outside any subdivision
    words_of = lambda value: re.sub(r"[^a-z0-9ñ ]", " ", value).split()
    city_words = set(words_of(str(city or "").lower()))
    words = []
    for word in words_of(text):
        if word in NOISE_WORDS or word in city_words or NOT_A_NAME.match(word):
            continue
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]  # "estates" -> "estate", "villas" -> "villa"
        words.append(word)
    return " ".join(words)


def same_subdivision(a: str, b: str) -> bool:
    """Do two subdivision keys name the same place? Equal keys match. A
    shorter key of 2+ words also matches a longer one that contains it
    ("golden horizon" matches "villa at golden horizon"); one word alone
    ("camella") is too general to match a longer name."""
    if not a or not b:
        return False
    if a == b:
        return True
    short, long = sorted((a, b), key=lambda k: len(k.split()))
    return len(short.split()) >= 2 and f" {short} " in f" {long} "


def type_group(value) -> str:
    """"townhouse" and "rowhouse" -> "row"; duplex, single attached... -> "attached"."""
    text = "" if value is None or pd.isna(value) else str(value).strip().lower()
    return TYPE_GROUPS.get(text, text)


def like_for_like(pool: pd.DataFrame, floor_area, group: str) -> pd.DataFrame:
    """Listings of a similar size and the same type group (or type unknown)."""
    if floor_area is not None and not pd.isna(floor_area):
        pool = pool[(pool["floor_area_sqm"] - floor_area).abs() <= AREA_TOLERANCE * floor_area]
    if group and "type" in pool:
        pool = pool[pool["type"].map(type_group).isin(["", group])]
    return pool


def load_listings(path) -> pd.DataFrame:
    """Read a listings CSV, skipping the # note lines at the top."""
    return load_deals(path)


def clean(listings: pd.DataFrame) -> pd.DataFrame:
    """Normalize kinds, drop repeated links, and mark which rows can be used.

    Adds price_per_sqm, subdivision_key, usable (counted in medians), and
    excluded_reason.
    """
    df = listings.copy()
    df["kind"] = df["kind"].fillna("").astype(str).str.strip().str.lower().replace({"": "unknown"})
    reason = (df["kind_reason"] if "kind_reason" in df else pd.Series("", index=df.index))
    df.loc[reason.fillna("").astype(str).str.lower().str.contains("pasalo"), "kind"] = "pasalo"
    # The same property is often posted more than once: same link, or the same
    # city, kind, price, and floor area under different links. Count it once.
    # But different Pag-IBIG property numbers are different houses, even at the
    # same price and size (many units of one house model are for sale at once).
    df = df.drop_duplicates(subset="link", keep="first")
    df["property_number"] = df["link"].astype(str).str.extract(PROPERTY_NUMBER)[0].fillna("")
    df = df.drop_duplicates(subset=["city", "kind", "price", "floor_area_sqm", "property_number"],
                            keep="first")
    df = df.drop(columns="property_number").reset_index(drop=True)

    df["price_per_sqm"] = df["price"] / df["floor_area_sqm"]
    names = df["subdivision"] if "subdivision" in df else [""] * len(df)
    df["subdivision_key"] = [subdivision_key(n, c) for n, c in zip(names, df["city"])]
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
        elif ratio > SCREEN:
            row["screen"] = "foreclosures near benchmark: little room"
        elif row["benchmark"] == "resale":
            row["screen"] = "foreclosures look cheap: worth a closer look"
        else:  # far below a new-unit ceiling proves little: resale may be far lower
            row["screen"] = "cheaper than new units, but no resale prices to confirm"
        rows.append(row)
    return pd.DataFrame(rows)


def _benchmark(same: pd.DataFrame, city) -> tuple[str, int, float]:
    """(what it is, how many listings, median per sqm) for one foreclosure,
    from the same-subdivision listings and its city's summary row."""
    for kind, label in [("resale", "same subdivision: resale"),
                        ("new", "same subdivision: new (ceiling)")]:
        per_sqm = same.loc[same["kind"] == kind, "price_per_sqm"]
        if len(per_sqm) >= MIN_SAME_SUBDIVISION:
            return label, len(per_sqm), per_sqm.median()
    if city is not None:
        if city["resale_count"] >= MIN_BENCHMARK:
            return "city: resale", city["resale_count"], city["resale_median_per_sqm"]
        if city["new_count"] >= MIN_BENCHMARK:
            return "city: new (ceiling)", city["new_count"], city["new_median_per_sqm"]
    return "none", 0, float("nan")


DATE = re.compile(r"[A-Z][a-z]{2,3}\.? \d{1,2}, \d{4}")  # Oct. 16, 2026 or Sept. 5, 2026


def offer_window(notes) -> tuple[str, str]:
    """A Pag-IBIG row's offer window and, when the end is known, the day it
    closes (YYYY-MM-DD). The notes look like "1st auction; batch OPA1510115;
    offers Oct. 12, 2026 12:00 AM - Oct. 16, 2026 11:59 PM"; older imports
    have only the start date, so their closing day is blank."""
    found = re.search(r"offers (.+)$", "" if notes is None or pd.isna(notes) else str(notes))
    if not found:
        return "", ""
    window = found.group(1).strip()
    dates = DATE.findall(window)
    closes = ""
    if len(dates) >= 2:
        try:
            closes = pd.Timestamp(dates[-1].replace(".", "")).date().isoformat()
        except ValueError:
            pass
    return window, closes


def _screen(benchmark: str, ratio: float) -> str:
    if pd.isna(ratio):
        return NO_FAIR
    if ratio > SCREEN:
        return LITTLE_ROOM
    if benchmark == "city: new (ceiling)":
        return NO_FAIR  # cheaper than other subdivisions' new units proves little
    return LOOK


def compare_foreclosures(listings: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """Every usable foreclosure: what it was compared with, the ratio, the
    screen result, and how many foreclosures are for sale in its
    subdivision. Candidates first, best (lowest ratio) first."""
    by_city = summary.set_index("city")
    usable = listings[listings["usable"]]
    others = usable[usable["kind"] != "foreclosed"]
    all_foreclosed = listings[listings["kind"] == "foreclosed"]  # supply counts every one
    foreclosed = usable[usable["kind"] == "foreclosed"].copy()

    def in_subdivision(table, city, key):
        in_city = table[table["city"] == city]
        match = [same_subdivision(key, k) for k in in_city["subdivision_key"]]
        return in_city.loc[pd.Series(match, index=in_city.index, dtype=bool)]

    # Many foreclosures are the same house model, so each comparison is worked out once
    supply, benchmarks, looked_up = {}, {}, []
    for _, house in foreclosed.iterrows():
        city, key = house["city"], house["subdivision_key"]
        group, area = type_group(house.get("type")), house["floor_area_sqm"]
        if (city, key) not in supply:  # every foreclosure there competes when you resell
            supply[(city, key)] = (len(in_subdivision(all_foreclosed, city, key)) if key
                                   else float("nan"))
        if (city, key, group, area) not in benchmarks:
            same = like_for_like(in_subdivision(others, city, key), area, group)
            city_row = by_city.loc[city] if city in by_city.index else None
            benchmarks[(city, key, group, area)] = _benchmark(same, city_row)
        looked_up.append((*benchmarks[(city, key, group, area)], supply[(city, key)]))
    for i, column in enumerate(["benchmark", "benchmark_listings", "benchmark_per_sqm",
                                "foreclosures_in_subdivision"]):
        foreclosed[column] = [values[i] for values in looked_up]
    foreclosed["vs_benchmark"] = foreclosed["price_per_sqm"] / foreclosed["benchmark_per_sqm"]
    foreclosed["vs_resale"] = (foreclosed["price_per_sqm"]
                               / foreclosed["city"].map(by_city["resale_median_per_sqm"]))
    foreclosed["screen"] = [_screen(b, r) for b, r in
                            zip(foreclosed["benchmark"], foreclosed["vs_benchmark"])]
    foreclosed["order"] = foreclosed["screen"].map(SCREEN_ORDER)
    if "notes" in foreclosed:
        windows = [offer_window(n) for n in foreclosed["notes"]]
        foreclosed["offer_window"] = [w for w, _ in windows]
        foreclosed["offer_closes"] = [c for _, c in windows]
    columns = ["city", "barangay", "subdivision", "type", "price", "price_basis",
               "floor_area_sqm", "price_per_sqm", "benchmark", "benchmark_listings",
               "benchmark_per_sqm", "vs_benchmark", "vs_resale", "screen",
               "foreclosures_in_subdivision", "occupancy", "date_listed", "offer_window",
               "offer_closes", "link"]
    return (foreclosed.sort_values(["order", "vs_benchmark", "city"])
            [[c for c in columns if c in foreclosed]].reset_index(drop=True))


def candidates(compared: pd.DataFrame) -> pd.DataFrame:
    """The foreclosures that pass the screen (from compare_foreclosures)."""
    return compared[compared["screen"] == LOOK].reset_index(drop=True)


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
        ("Benchmark (each foreclosure)",
         f"Compared like for like, in this order: resale listings in the same subdivision, "
         f"then new units in the same subdivision (at least {MIN_SAME_SUBDIVISION} "
         f"listings each, floor area within {AREA_TOLERANCE:.0%} and the same type group: "
         f"townhouse/rowhouse, attached, or detached); then the city's resale median, "
         f"then its new-unit median (at "
         f"least {MIN_BENCHMARK} listings each). The Benchmark listings column shows how "
         "many listings the median came from: few listings are shaky."),
        ("Same subdivision", "Names match after ignoring case, phase numbers, 'The', "
                             "'Subdivision', the city's name, and plurals, so 'Micara "
                             "Estates Tanza Phase 1' matches 'Micara Estates'. A general name "
                             "of 2+ words matches its sections ('Golden Horizon' matches "
                             "'Villas at Golden Horizon')."),
        ("Benchmark (city)", f"Median resale price per sqm when a city has at least "
                             f"{MIN_BENCHMARK} resale listings; otherwise the median new-unit "
                             "price per sqm, which is a ceiling."),
        ("Why a ceiling only rules out",
         "New units elsewhere in the city are often in pricier subdivisions. A foreclosure "
         f"far below them may still be close to what its own subdivision resells for, so "
         f"it is not a candidate ('no fair comparison'). But a foreclosure above "
         f"{SCREEN:.0%} of even those prices has little room."),
        ("Foreclosed vs resale", "Shown whenever a city has any resale listings, even 1 or 2, "
                                 "as a sanity check."),
        ("Repeated listings", "The same property posted more than once (same link, or the "
                              "same city, kind, price, and floor area) is counted once. "
                              "Pag-IBIG units with different property numbers are different "
                              "houses, even at the same price and size."),
        ("Screen", f"A foreclosure at or below {SCREEN:.0%} of its benchmark leaves room for "
                   "renovation, buying and selling costs, and a profit in the best case (see "
                   "docs/how-to-use.md Step 2). It is a first filter, not a verdict: analyze "
                   "each candidate with its own comps."),
        ("Foreclosures for sale in subdivision",
         "How many foreclosures (including this one) are listed in the same subdivision. "
         "When you resell, you compete with them, and buyers can get them at the bank's "
         "price."),
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


def scan(path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """The market scan of a listings CSV: (cleaned listings, city summary,
    every foreclosure compared)."""
    listings = clean(load_listings(path))
    summary = city_summary(listings)
    return listings, summary, compare_foreclosures(listings, summary)


def write_report(path, output) -> Path:
    """Build the market report workbook from a listings CSV."""
    from flip.export import write_workbook  # the same formatting as the deal report

    listings, summary, compared = scan(path)
    order = ["city", "kind", "kind_reason", "barangay", "subdivision", "type", "price",
             "price_basis", "floor_area_sqm", "price_per_sqm", "lot_area_sqm", "year_built",
             "date_listed", "occupancy", "excluded_reason", "source", "link", "collected"]
    sheets = {
        "About": about_table(path, file_notes(path), listings),
        "City summary": summary,
        "Candidates": candidates(compared),
        "Foreclosures": compared,
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
