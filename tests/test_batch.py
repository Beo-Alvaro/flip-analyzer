"""Tests for analyzing many deals at once. The expected numbers are the
same hand calculations as test_analyzer.py and test_scenarios.py; a table
of deals must give exactly the answers each deal gives on its own.
"""

import math

import pytest

import pandas as pd

from flip.batch import analyze_deals, file_notes, load_deals


def money(value):
    """Compare peso amounts to the centavo, ignoring float rounding noise."""
    return pytest.approx(value, abs=0.01)


# Hand-calculated deals. Columns not listed (interest rate, fees, tax rates)
# fall back to analyze()'s defaults, which match the anchor deal.
# Blank cells (NaN) are what pandas produces for an empty CSV cell.
DEALS = pd.DataFrame({
    "deal_id": ["anchor", "no_loan", "twelve_months", "arv_below_cost", "zonal_above"],
    "purchase_price": [2_800_000] * 5,
    "arv": [4_200_000, 4_200_000, 4_200_000, 3_500_000, 4_200_000],
    "renovation_cost": [450_000] * 5,
    "holding_months": [6, 6, 12, 6, 6],
    "monthly_holding_cost": [15_000] * 5,
    "loan_ratio": [0.70, 0, 0.70, 0.70, 0.70],
    "zonal_value": [math.nan, math.nan, math.nan, math.nan, 4_800_000],
})


@pytest.fixture
def analyzed():
    return analyze_deals(DEALS).set_index("deal_id")


@pytest.mark.parametrize("deal, net_profit, total_cost, cash_invested", [
    ("anchor", 304_200, 3_895_800, 1_557_800),
    ("no_loan", 412_000, 3_788_000, 3_410_000),
    ("twelve_months", 126_000, 4_074_000, 1_736_000),
    ("arv_below_cost", -332_800, 3_832_800, 1_557_800),
    ("zonal_above", 268_200, 3_931_800, 1_557_800),
])
def test_each_row_matches_its_hand_calculation(analyzed, deal, net_profit, total_cost,
                                                cash_invested):
    r = analyzed.loc[deal]

    assert r["net_profit"] == money(net_profit)
    assert r["total_cost"] == money(total_cost)
    assert r["cash_invested"] == money(cash_invested)
    assert r["roi_on_total_cost"] == pytest.approx(net_profit / total_cost)
    assert r["cash_on_cash_roi"] == pytest.approx(net_profit / cash_invested)


def test_anchor_row_gets_stress_profit_and_max_offer(analyzed):
    r = analyzed.loc["anchor"]

    assert r["stress_net_profit"] == money(-309_300)  # see test_scenarios.py
    assert r["max_offer_stress"] == pytest.approx(2_514_799.45, abs=1)  # 2,727,300 / 1.0845


def test_input_columns_are_kept(analyzed):
    assert analyzed.loc["zonal_above", "zonal_value"] == 4_800_000
    assert len(analyzed) == 5


def test_csv_with_sample_label_and_blank_cells(tmp_path):
    path = tmp_path / "deals.csv"
    path.write_text(
        "# SAMPLE DATA: test file\n"
        "deal_id,purchase_price,arv,renovation_cost,holding_months,"
        "monthly_holding_cost,zonal_value,fair_market_value\n"
        "anchor,2800000,4200000,450000,6,15000,,\n",
        encoding="utf-8",
    )

    assert file_notes(path) == ["# SAMPLE DATA: test file"]
    r = analyze_deals(load_deals(path)).iloc[0]
    # Blank zonal and fair market values: CGT on the 4,200,000 selling price
    assert r["selling"] == money(378_000)
    assert r["net_profit"] == money(304_200)
