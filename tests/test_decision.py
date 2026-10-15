"""Tests for decision support: break-even, what matters most, yearly return,
the safe alternative, and the verdict. Every expected number is calculated
by hand from the anchor deal; the arithmetic is in the comments.
"""

import pandas as pd
import pytest

from flip.batch import analyze_deals
from flip.decision import (Settings, break_even_arv, break_even_price, checklist_status,
                           safe_earnings, sensitivity, verdict, yearly_return)

# Anchor deal from docs/project-context.md
ANCHOR = dict(
    purchase_price=2_800_000,
    arv=4_200_000,
    renovation_cost=450_000,
    holding_months=6,
    monthly_holding_cost=15_000,
    loan_ratio=0.70,
    annual_interest_rate=0.09,
    loan_fee_rate=0.01,
    acquisition_rate=0.025,
    broker_rate=0.03,
    cgt_rate=0.06,
)


def money(value):
    """Compare peso amounts to the centavo, ignoring float rounding noise."""
    return pytest.approx(value, abs=0.01)


def analyzed_row(**changes):
    """The anchor deal (with changes) as one analyze_deals() row."""
    deal = {"deal_id": "anchor", **ANCHOR, **changes}
    return analyze_deals(pd.DataFrame([deal])).iloc[0]


# --- Break-even ---

def test_break_even_sale_price():
    # Costs except selling: 3,895,800 - 378,000 = 3,517,800.
    # Selling is 9% of the sale price, so 91% of it must cover 3,517,800.
    assert break_even_arv(ANCHOR) == pytest.approx(3_517_800 / 0.91, abs=0.02)  # 3,865,714.29


def test_break_even_sale_price_with_zonal_value_above_it():
    # Zonal 4,800,000: CGT is a fixed 6% x 4,800,000 = 288,000 below that price,
    # and only the 3% broker fee moves with the sale price.
    # 0.97 x ARV = 3,517,800 + 288,000 = 3,805,800
    expected = 3_805_800 / 0.97  # 3,923,505.15, below 4,800,000 so CGT stays fixed
    assert break_even_arv({**ANCHOR, "zonal_value": 4_800_000}) == pytest.approx(expected, abs=0.02)


def test_break_even_purchase_price():
    # 3,282,000 / 1.0635 (see test_scenarios.py)
    assert break_even_price(ANCHOR) == pytest.approx(3_086_036.67, abs=1)


# --- What matters most ---

def test_sensitivity_ranks_inputs_by_swing():
    table = sensitivity(ANCHOR).set_index("input")

    # ARV +/-10% = +/-420,000; 91% of it reaches profit: +/-382,200
    assert table.loc["Sale price (ARV)", "profit_if_lower"] == money(-78_000)
    assert table.loc["Sale price (ARV)", "profit_if_higher"] == money(686_400)
    # Price +/-280,000, and each peso costs 1.0635: +/-297,780
    assert table.loc["Purchase price", "swing"] == money(595_560)
    assert table.loc["Renovation", "swing"] == money(90_000)  # 2 x 45,000
    # +/-0.6 months: interest 1,960,000 x 9% x 0.6/12 = 8,820 + holding 9,000
    assert table.loc["Holding months", "swing"] == money(35_640)
    assert table.loc["Monthly holding cost", "swing"] == money(18_000)  # 2 x 1,500 x 6
    # 9% +/- 0.9 points: 1,960,000 x 0.9% x 6/12 = 8,820
    assert table.loc["Interest rate", "swing"] == money(17_640)
    assert list(table.index) == ["Sale price (ARV)", "Purchase price", "Renovation",
                                 "Holding months", "Monthly holding cost", "Interest rate"]


# --- Yearly return and the safe alternative ---

def test_yearly_return_is_simple_not_compounded():
    assert yearly_return(0.10, 6) == pytest.approx(0.20)  # 10% in 6 months
    assert yearly_return(0.10, 12) == pytest.approx(0.10)
    assert yearly_return(0.10, 18) == pytest.approx(0.10 * 12 / 18)
    assert yearly_return(0.10, 0) is None


def test_anchor_yearly_returns_and_safe_account():
    r = analyzed_row()

    assert r["yearly_cash_on_cash_roi"] == pytest.approx(304_200 / 1_557_800 * 2)  # ~39.06%
    assert r["yearly_roi_on_total_cost"] == pytest.approx(304_200 / 3_895_800 * 2)  # ~15.62%
    # 1,557,800 x 6% x 6/12 = 46,734
    assert r["safe_earnings"] == money(46_734)
    assert r["profit_vs_safe"] == money(257_466)  # 304,200 - 46,734


def test_safe_earnings():
    assert safe_earnings(1_000_000, 12, 0.06) == money(60_000)
    assert safe_earnings(1_000_000, 3, 0.06) == money(15_000)


# --- Verdict ---

def test_anchor_fails_only_the_max_offer_rule():
    # 2,800,000 - 2,514,799.45 = 285,200.55 above the Stress max offer
    assert verdict(analyzed_row(), Settings()) == (
        "Fails: price is 285,201 above the max offer under Stress (2,514,799)")


def test_anchor_meets_criteria_without_the_max_offer_rule():
    settings = Settings(price_within_stress_max_offer=False)

    assert verdict(analyzed_row(), settings) == "Meets your criteria"


def test_twelve_month_hold_fails_several_rules():
    # Profit 126,000; yearly cash-on-cash 126,000 / 1,736,000 = 7.26%.
    # Safe account: 1,736,000 x 6% x 12/12 = 104,160 < 126,000, so that one passes.
    # Stress (16 months): each peso of price costs 1 + 0.025 + 0.70 x 9% x 16/12
    # + 0.007 = 1.116; other costs 562,500 + 240,000 + 340,200 = 1,142,700;
    # max offer = (3,780,000 - 1,142,700) / 1.116 = 2,363,172.04
    assert verdict(analyzed_row(holding_months=12), Settings()) == (
        "Fails: profit 126,000 is below your minimum 200,000; "
        "yearly cash-on-cash return 7.3% is below your minimum 15%; "
        "price is 436,828 above the max offer under Stress (2,363,172)")


def test_a_loss_earns_less_than_the_safe_account():
    # Loss 332,800, and the safe account would have earned 46,734 on 1,557,800
    text = verdict(analyzed_row(arv=3_500_000), Settings())

    assert "earns 379,534 less than a 6% safe account" in text


CHECKLIST = pd.DataFrame({
    "deal_id": ["anchor"] * 4,
    "item": ["Title", "Occupants", "Flood risk", "Inspection"],
    "status": ["done", "issue", "open", "DONE"],
    "note": [None, "2 families living there", None, None],
})


def test_checklist_status():
    c = checklist_status("anchor", CHECKLIST)

    assert (c["done"], c["open"]) == (2, 1)  # status is not case-sensitive
    assert c["issues"] == ["Occupants: 2 families living there"]


def test_verdict_notes_the_checklist():
    settings = Settings(price_within_stress_max_offer=False)

    assert verdict(analyzed_row(), settings, CHECKLIST) == (
        "Meets your criteria | checklist: 1 open, 1 issue(s)")
    other = CHECKLIST.assign(deal_id="other")
    assert verdict(analyzed_row(), settings, other) == (
        "Meets your criteria | checklist not started")
