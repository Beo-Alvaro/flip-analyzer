"""Tests for comp quality: kinds, range, ceiling, floor, and warnings.
Expected numbers are calculated by hand; the arithmetic is in comments.
"""

import math

import pandas as pd
import pytest

from flip.comps import suggested_arv


def money(value):
    """Compare peso amounts to the centavo, ignoring float rounding noise."""
    return pytest.approx(value, abs=0.01)


HOUSE = pd.DataFrame({"deal_id": ["h"], "purchase_price": [2_800_000], "arv": [4_200_000],
                      "floor_area_sqm": [84]})


def comps(*rows):
    """Comps for house h: (kind, price, floor area[, date_listed])."""
    return pd.DataFrame([
        {"deal_id": "h", "subdivision": f"comp {i}", "kind": r[0], "price": r[1],
         "floor_area_sqm": r[2], "date_listed": r[3] if len(r) > 3 else None}
        for i, r in enumerate(rows, start=1)
    ])


RESALE = [("resale", 4_500_000, 90),    # 50,000/sqm
          ("resale", 5_200_000, 100),   # 52,000/sqm
          ("resale", 4_080_000, 85)]    # 48,000/sqm


def check(table, **kwargs):
    return suggested_arv(HOUSE, table, today="2026-10-15", **kwargs).iloc[0]


def test_each_kind_has_its_role():
    s = check(comps(*RESALE,
                    ("new", 3_100_000, 48),          # 64,583.33/sqm
                    ("foreclosed", 2_400_000, 80),   # 30,000/sqm
                    ("pasalo", 380_000, 48)))        # cash-out only: left out

    assert s["comps_used"] == 3
    assert s["low_price_per_sqm"] == money(48_000)
    assert s["median_price_per_sqm"] == money(50_000)
    assert s["high_price_per_sqm"] == money(52_000)
    assert s["suggested_arv"] == money(4_200_000)  # 50,000 x 84
    assert s["arv_low"] == money(4_032_000)  # 48,000 x 84
    assert s["arv_high"] == money(4_368_000)  # 52,000 x 84
    assert s["new_unit_ceiling"] == money(5_425_000)  # 3,100,000 / 48 x 84
    assert s["foreclosed_floor"] == money(2_520_000)  # 30,000 x 84
    assert any("1 pasalo comp(s) left out" in w for w in s["warnings"])


def test_only_new_units_gives_a_ceiling_but_no_suggestion():
    # San Pablo: 3 brand-new Manor Classic prices, a 51.65 sqm house, and an
    # ARV set to the new-unit median.
    house = pd.DataFrame({"deal_id": ["h"], "purchase_price": [2_607_210],
                          "arv": [3_335_729], "floor_area_sqm": [51.65]})
    table = comps(("new", 2_357_200, 48),      # 49,108.33/sqm
                  ("new", 3_100_000, 48),      # 64,583.33/sqm
                  ("new", 3_327_500, 45.85))   # 72,574.70/sqm
    s = suggested_arv(house, table, today="2026-10-15").iloc[0]

    assert s["comps_used"] == 0
    assert math.isnan(s["suggested_arv"])
    assert s["new_unit_ceiling"] == money(3_335_729.17)  # 64,583.33 x 51.65
    assert "no resale comps: the suggested ARV needs at least one" in s["warnings"]
    assert any("at or above the new-unit ceiling (3,335,729)" in w for w in s["warnings"])


def test_comps_without_a_kind_count_as_resale_with_a_warning():
    table = comps(*RESALE).drop(columns="kind")
    s = check(table)

    assert s["comps_used"] == 3
    assert s["suggested_arv"] == money(4_200_000)
    assert "3 comp(s) have no kind set and were counted as resale" in s["warnings"]


def test_few_comps_warning():
    s = check(comps(*RESALE[:2]))

    # Median of 50,000 and 52,000 is 51,000; x 84 = 4,284,000
    assert s["suggested_arv"] == money(4_284_000)
    assert "only 2 resale comp(s); 3 to 5 make a steadier estimate" in s["warnings"]


def test_outlier_warning():
    # Median of 48k, 50k, 52k, 150k is 51,000; 150,000 is over twice that
    s = check(comps(*RESALE, ("resale", 15_000_000, 100)))

    assert any(w.startswith("comp 4 (15,000,000) is far from the other comps")
               for w in s["warnings"])


def test_old_listing_warning():
    s = check(comps(("resale", 4_500_000, 90, "2025-02-27"),
                    ("resale", 5_200_000, 100, "2026-06-01"),
                    ("resale", 4_080_000, 85)))

    old = [w for w in s["warnings"] if "over a year ago" in w]
    assert old == ["comp 1 (4,500,000) was listed 2025-02, over a year ago"]


def test_suggested_arv_under_half_the_price():
    # Pasalo cash-outs entered as resale: 380,000 / 48 = 7,916.67/sqm, etc.
    s = check(comps(("resale", 380_000, 48), ("resale", 400_000, 52), ("resale", 350_000, 49)))

    assert any(w.startswith("suggested ARV is less than half the purchase price")
               for w in s["warnings"])


def test_arv_above_highest_comp():
    house = HOUSE.assign(arv=4_500_000)
    s = suggested_arv(house, comps(*RESALE), today="2026-10-15").iloc[0]

    assert "your ARV is above your highest resale comp (4,368,000)" in s["warnings"]
