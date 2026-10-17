"""Tests for the Edit page's conversions (flip.editing)."""

import math
from datetime import date

import pandas as pd
import pytest

from flip.editing import from_editor, to_editor

LOANS = pd.DataFrame([
    {"deal_id": "IMUS-01", "offer": "Bank A", "loan_ratio": 0.70, "annual_interest_rate": 0.09,
     "loan_fee_rate": 0.01, "price_discount_rate": math.nan},
    {"deal_id": "OTHER-01", "offer": "Cash", "loan_ratio": 0.0, "annual_interest_rate": 0.0,
     "loan_fee_rate": 0.0, "price_discount_rate": 0.05},
])
COMPS = pd.DataFrame([
    {"deal_id": "imus-01 ", "subdivision": "Jade", "price": 2_500_000, "floor_area_sqm": 60.0,
     "kind": "Resale", "date_listed": pd.Timestamp("2026-10-01"), "date_seen": "Oct 2026",
     "condition": math.nan},
])


def test_rates_are_shown_as_percentages():
    shown = to_editor(LOANS, "IMUS-01")

    assert list(shown.columns) == ["offer", "loan_ratio", "annual_interest_rate",
                                   "loan_fee_rate", "price_discount_rate"]
    assert len(shown) == 1  # only this house's rows
    assert (shown.loc[0, "loan_ratio"], shown.loc[0, "annual_interest_rate"],
            shown.loc[0, "loan_fee_rate"]) == (70, 9, 1)  # 0.09 x 100 = 9, not 9.000000000000002


def test_rates_go_back_to_fractions():
    [offer] = from_editor(to_editor(LOANS, "IMUS-01"), "IMUS-01")

    assert offer == {"deal_id": "IMUS-01", "offer": "Bank A", "loan_ratio": 0.7,
                     "annual_interest_rate": 0.09, "loan_fee_rate": 0.01,
                     "price_discount_rate": None}


def test_dates_kinds_and_blank_text():
    shown = to_editor(COMPS, "IMUS-01")  # the deal_id matches despite case and a space
    assert shown.loc[0, "date_listed"] == "2026-10-01"
    assert shown.loc[0, "kind"] == "resale"
    assert shown.loc[0, "condition"] is None  # a blank text column stays text

    [comp] = from_editor(shown, "IMUS-01")
    assert comp["date_listed"] == date(2026, 10, 1)
    assert comp["date_seen"] == "Oct 2026"  # not YYYY-MM-DD: kept as typed
    assert (comp["price"], comp["floor_area_sqm"]) == (2_500_000, 60)


def test_blank_rows_are_dropped():
    edited = pd.DataFrame({"item": ["Kitchen", None, "  "], "cost": [120_000.0, math.nan, None]})

    assert from_editor(edited, "IMUS-01") == [
        {"deal_id": "IMUS-01", "item": "Kitchen", "cost": 120_000}]


@pytest.mark.parametrize("table", [LOANS, COMPS])
def test_an_untouched_table_round_trips(table):
    once = from_editor(to_editor(table, "IMUS-01"), "IMUS-01")
    again = from_editor(to_editor(pd.DataFrame(once), "IMUS-01"), "IMUS-01")
    assert once == again
