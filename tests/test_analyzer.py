"""Tests for analyze(). Every expected number is calculated by hand.

The arithmetic is shown in comments so each value can be checked with a
calculator. Never replace an expected value with the code's output: if a
test fails, re-check the hand calculation and the code, then fix whichever
is wrong.
"""

import pytest

from flip.analyzer import analyze

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


def test_anchor_deal():
    r = analyze(**ANCHOR)

    assert r["purchase"] == money(2_800_000)
    assert r["acquisition"] == money(70_000)  # 2,800,000 x 2.5%
    assert r["renovation"] == money(450_000)
    assert r["interest"] == money(88_200)  # loan 1,960,000 x 9% x 6/12
    assert r["loan_fees"] == money(19_600)  # 1,960,000 x 1%
    assert r["holding"] == money(90_000)  # 15,000 x 6
    assert r["selling"] == money(378_000)  # 4,200,000 x (3% + 6%)
    assert r["total_cost"] == money(3_895_800)
    assert r["net_profit"] == money(304_200)  # 4,200,000 - 3,895,800
    # 840,000 down + 70,000 + 450,000 + 88,200 + 19,600 + 90,000
    assert r["cash_invested"] == money(1_557_800)
    assert r["roi_on_total_cost"] == pytest.approx(304_200 / 3_895_800)  # ~7.81%
    assert r["cash_on_cash_roi"] == pytest.approx(304_200 / 1_557_800)  # ~19.53%


def test_no_loan():
    # All cash: no interest, no loan fee, and the "down payment" is the full price.
    r = analyze(**{**ANCHOR, "loan_ratio": 0})

    assert r["interest"] == money(0)
    assert r["loan_fees"] == money(0)
    # 2,800,000 + 70,000 + 450,000 + 90,000 + 378,000
    assert r["total_cost"] == money(3_788_000)
    assert r["net_profit"] == money(412_000)  # 4,200,000 - 3,788,000
    # 2,800,000 + 70,000 + 450,000 + 90,000
    assert r["cash_invested"] == money(3_410_000)
    assert r["roi_on_total_cost"] == pytest.approx(412_000 / 3_788_000)  # ~10.88%
    assert r["cash_on_cash_roi"] == pytest.approx(412_000 / 3_410_000)  # ~12.08%


def test_twelve_month_hold():
    # Holding period overrun: interest and holding double, everything else stays.
    r = analyze(**{**ANCHOR, "holding_months": 12})

    assert r["interest"] == money(176_400)  # 1,960,000 x 9% x 12/12
    assert r["holding"] == money(180_000)  # 15,000 x 12
    # 2,800,000 + 70,000 + 450,000 + 176,400 + 19,600 + 180,000 + 378,000
    assert r["total_cost"] == money(4_074_000)
    assert r["net_profit"] == money(126_000)  # 4,200,000 - 4,074,000
    # 840,000 + 70,000 + 450,000 + 176,400 + 19,600 + 180,000
    assert r["cash_invested"] == money(1_736_000)
    assert r["roi_on_total_cost"] == pytest.approx(126_000 / 4_074_000)  # ~3.09%
    assert r["cash_on_cash_roi"] == pytest.approx(126_000 / 1_736_000)  # ~7.26%


def test_arv_below_cost_reports_a_loss():
    r = analyze(**{**ANCHOR, "arv": 3_500_000})

    assert r["selling"] == money(315_000)  # 3,500,000 x (3% + 6%)
    # 2,800,000 + 70,000 + 450,000 + 88,200 + 19,600 + 90,000 + 315,000
    assert r["total_cost"] == money(3_832_800)
    assert r["net_profit"] == money(-332_800)  # 3,500,000 - 3,832,800
    # Selling costs are not cash invested, so this matches the anchor deal.
    assert r["cash_invested"] == money(1_557_800)
    assert r["roi_on_total_cost"] == pytest.approx(-332_800 / 3_832_800)  # ~-8.68%
    assert r["cash_on_cash_roi"] == pytest.approx(-332_800 / 1_557_800)  # ~-21.36%


def test_cgt_uses_zonal_value_when_above_selling_price():
    r = analyze(**{**ANCHOR, "zonal_value": 4_800_000})

    # CGT 4,800,000 x 6% = 288,000; broker stays 4,200,000 x 3% = 126,000
    assert r["selling"] == money(414_000)
    assert r["total_cost"] == money(3_931_800)  # 3,895,800 - 378,000 + 414,000
    assert r["net_profit"] == money(268_200)  # 4,200,000 - 3,931,800
    assert r["cash_invested"] == money(1_557_800)
    assert r["roi_on_total_cost"] == pytest.approx(268_200 / 3_931_800)  # ~6.82%
    assert r["cash_on_cash_roi"] == pytest.approx(268_200 / 1_557_800)  # ~17.22%


def test_cgt_uses_highest_of_three_values():
    # Fair market value is the highest: 4,500,000 > zonal 4,300,000 > price 4,200,000
    r = analyze(**{**ANCHOR, "zonal_value": 4_300_000, "fair_market_value": 4_500_000})

    # CGT 4,500,000 x 6% = 270,000; broker 126,000
    assert r["selling"] == money(396_000)
    assert r["net_profit"] == money(286_200)  # 304,200 - (396,000 - 378,000)


def test_zonal_value_below_selling_price_does_not_lower_cgt():
    r = analyze(**{**ANCHOR, "zonal_value": 3_000_000})

    # CGT base stays at the 4,200,000 selling price: same as the anchor deal.
    assert r["selling"] == money(378_000)
    assert r["net_profit"] == money(304_200)
