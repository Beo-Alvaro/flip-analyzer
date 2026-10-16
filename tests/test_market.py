"""Tests for the market scan. Every expected number is calculated by hand;
the arithmetic is in the comments.
"""

import math

import pandas as pd
import pytest
from openpyxl import load_workbook

from flip.market import candidates, city_summary, clean, write_report


def money(value):
    return pytest.approx(value, abs=0.01)


def listing(city, kind, price, floor, link, reason=""):
    return {"city": city, "kind": kind, "kind_reason": reason, "price": price,
            "floor_area_sqm": floor, "link": link}


# City A: 3 resale listings, so resale is the benchmark.
# City B: no resale but 3 new listings, so new is the benchmark (a ceiling).
# City C: only 1 new listing: not enough data for a benchmark.
LISTINGS = pd.DataFrame([
    listing("A", "new", 2_000_000, 40, "a1"),          # 50,000/sqm
    listing("A", "new", 2_200_000, 40, "a2"),          # 55,000/sqm
    listing("A", "resale", 1_600_000, 40, "a3"),       # 40,000/sqm
    listing("A", "resale", 1_760_000, 40, "a4"),       # 44,000/sqm
    listing("A", "resale", 1_920_000, 40, "a5"),       # 48,000/sqm
    listing("A", "foreclosed", 1_200_000, 40, "a6"),   # 30,000/sqm
    listing("A", "foreclosed", 1_400_000, 40, "a7"),   # 35,000/sqm
    listing("B", "new", 2_000_000, 40, "b1"),          # 50,000/sqm
    listing("B", "new", 1_920_000, 40, "b3"),          # 48,000/sqm
    listing("B", "new", 2_080_000, 40, "b4"),          # 52,000/sqm
    listing("B", "foreclosed", 1_200_000, 40, "b2"),   # 30,000/sqm
    listing("C", "new", 2_000_000, 40, "c1"),          # 50,000/sqm, but alone
    listing("C", "foreclosed", 800_000, 40, "c2"),     # 20,000/sqm
    # Rows that must not count in the medians:
    listing("A", "foreclosed", 500_000, 20, "x1"),               # floor area under 25
    listing("A", "new", 8_000_000, 40, "x2"),                    # 200,000/sqm: data error
    listing("A", "resale", 400_000, 48, "x3", reason="PASALO"),  # pasalo cash-out
    listing("A", "", 2_000_000, 40, "x4"),                       # kind unknown
    listing("A", "foreclosed", 1_000_000, math.nan, "x5"),       # no floor area
    listing("A", "new", 2_000_000, 40, "a1"),                    # repeated link
    listing("A", "foreclosed", 1_200_000, 40, "a6-again"),       # same as a6, other link
])


@pytest.fixture
def cleaned():
    return clean(LISTINGS)


def test_exclusions_and_repeats(cleaned):
    reasons = cleaned.set_index("link")["excluded_reason"]

    assert len(cleaned) == 18  # 20 rows minus the repeated link and the repeated a6
    assert "a6-again" not in reasons
    assert reasons["x1"] == "floor area under 25 sqm"
    assert reasons["x2"] == "price per sqm looks like a data error"
    assert reasons["x3"].startswith("pasalo")
    assert reasons["x4"] == "kind unknown"
    assert reasons["x5"] == "no floor area"
    assert cleaned["usable"].sum() == 13


def test_city_with_enough_resale_uses_resale_as_benchmark(cleaned):
    a = city_summary(cleaned).set_index("city").loc["A"]

    assert a["new_median_per_sqm"] == money(52_500)  # (50,000 + 55,000) / 2
    assert a["resale_median_per_sqm"] == money(44_000)  # middle of 40k, 44k, 48k
    assert a["foreclosed_median_per_sqm"] == money(32_500)  # (30,000 + 35,000) / 2
    assert a["benchmark"] == "resale"
    # 32,500 / 44,000 = 73.9%: above 70%, so the city as a whole doesn't pass
    assert a["foreclosed_vs_benchmark"] == pytest.approx(32_500 / 44_000)
    assert a["foreclosed_vs_resale"] == pytest.approx(32_500 / 44_000)
    assert a["screen"] == "foreclosures near benchmark: little room"


def test_city_without_resale_uses_new_units(cleaned):
    b = city_summary(cleaned).set_index("city").loc["B"]

    assert b["benchmark"] == "new (ceiling)"
    assert b["benchmark_per_sqm"] == money(50_000)  # middle of 48k, 50k, 52k
    assert b["foreclosed_vs_benchmark"] == pytest.approx(0.60)  # 30,000 / 50,000
    assert math.isnan(b["foreclosed_vs_resale"])  # no resale listings
    assert b["screen"] == "foreclosures look cheap: worth a closer look"


def test_one_listing_is_not_a_benchmark(cleaned):
    c = city_summary(cleaned).set_index("city").loc["C"]

    assert c["benchmark"] == "none"
    assert c["screen"] == "not enough data"


def test_candidates(cleaned):
    picks = candidates(cleaned, city_summary(cleaned))

    # b2: 30,000 / 50,000 = 60%; a6: 30,000 / 44,000 = 68.2%; a7 (79.5%) fails;
    # c2 has no benchmark. Best (lowest) first.
    assert list(picks["link"]) == ["b2", "a6"]
    assert list(picks["vs_benchmark"]) == [pytest.approx(0.60), pytest.approx(30_000 / 44_000)]
    assert picks.loc[1, "vs_resale"] == pytest.approx(30_000 / 44_000)


def test_report_workbook(tmp_path):
    path = tmp_path / "listings.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("# Test listings\n")
        LISTINGS.to_csv(f, index=False)
    wb = load_workbook(write_report(path, tmp_path / "market.xlsx"))

    assert wb.sheetnames == ["About", "City summary", "Candidates", "All listings"]
    headers = [c.value for c in wb["City summary"][1]]
    b = dict(zip(headers, [c.value for c in wb["City summary"][3]]))
    assert (b["City"], b["Benchmark"]) == ("B", "new (ceiling)")
    assert b["Foreclosed vs benchmark"] == pytest.approx(0.60)
    assert wb["Candidates"].max_row == 3  # header + 2 candidates
