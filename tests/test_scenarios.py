"""Tests for scenario analysis and max offer. Every expected number is
calculated by hand from the anchor deal; the arithmetic is in the comments.
"""

import pytest

from flip.scenarios import SCENARIOS, apply_scenario, max_offer, run_scenarios

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


def test_base_is_the_deal_as_planned():
    r = run_scenarios(ANCHOR)["Base"]

    assert r["total_cost"] == money(3_895_800)
    assert r["net_profit"] == money(304_200)


def test_conservative():
    # ARV 4,200,000 x 0.95 = 3,990,000; renovation 450,000 x 1.10 = 495,000;
    # holding 6 + 2 = 8 months
    r = run_scenarios(ANCHOR)["Conservative"]

    assert r["renovation"] == money(495_000)
    assert r["interest"] == money(117_600)  # 1,960,000 x 9% x 8/12
    assert r["holding"] == money(120_000)  # 15,000 x 8
    assert r["selling"] == money(359_100)  # 3,990,000 x (3% + 6%)
    # 2,800,000 + 70,000 + 495,000 + 117,600 + 19,600 + 120,000 + 359,100
    assert r["total_cost"] == money(3_981_300)
    assert r["net_profit"] == money(8_700)  # 3,990,000 - 3,981,300
    # 840,000 + 70,000 + 495,000 + 117,600 + 19,600 + 120,000
    assert r["cash_invested"] == money(1_662_200)
    assert r["roi_on_total_cost"] == pytest.approx(8_700 / 3_981_300)  # ~0.22%
    assert r["cash_on_cash_roi"] == pytest.approx(8_700 / 1_662_200)  # ~0.52%


def test_stress():
    # ARV 4,200,000 x 0.90 = 3,780,000; renovation 450,000 x 1.25 = 562,500;
    # holding 6 + 4 = 10 months
    r = run_scenarios(ANCHOR)["Stress"]

    assert r["renovation"] == money(562_500)
    assert r["interest"] == money(147_000)  # 1,960,000 x 9% x 10/12
    assert r["holding"] == money(150_000)  # 15,000 x 10
    assert r["selling"] == money(340_200)  # 3,780,000 x (3% + 6%)
    # 2,800,000 + 70,000 + 562,500 + 147,000 + 19,600 + 150,000 + 340,200
    assert r["total_cost"] == money(4_089_300)
    assert r["net_profit"] == money(-309_300)  # 3,780,000 - 4,089,300
    # 840,000 + 70,000 + 562,500 + 147,000 + 19,600 + 150,000
    assert r["cash_invested"] == money(1_789_100)
    assert r["roi_on_total_cost"] == pytest.approx(-309_300 / 4_089_300)  # ~-7.56%
    assert r["cash_on_cash_roi"] == pytest.approx(-309_300 / 1_789_100)  # ~-17.29%


def test_apply_scenario_leaves_the_original_deal_unchanged():
    deal = dict(ANCHOR)
    apply_scenario(deal, SCENARIOS["Stress"])

    assert deal == ANCHOR


def test_max_offer_breaks_even_under_stress():
    # Under Stress, every peso of purchase price costs 1.0845 pesos:
    #   1 (price) + 0.025 (acquisition) + 0.70 x 9% x 10/12 (interest = 0.0525)
    #   + 0.70 x 1% (loan fee = 0.007)
    # Costs that don't depend on price: 562,500 + 150,000 + 340,200 = 1,052,700
    # Break even: 1.0845 x price = 3,780,000 - 1,052,700 = 2,727,300
    #   price = 2,727,300 / 1.0845 = ~2,514,799.45
    assert max_offer(ANCHOR) == pytest.approx(2_514_799.45, abs=1)


# Max offer = (ARV - costs that don't depend on price) - min profit,
# divided by what each peso of price costs in total:
#   Base:         ARV 4,200,000 - (450,000 + 90,000 + 378,000)  = 3,282,000
#                 per peso 1 + 0.025 + 0.70 x 9% x 6/12 + 0.007  = 1.0635
#   Conservative: ARV 3,990,000 - (495,000 + 120,000 + 359,100) = 3,015,900
#                 per peso 1 + 0.025 + 0.70 x 9% x 8/12 + 0.007  = 1.074
#   Stress:       ARV 3,780,000 - (562,500 + 150,000 + 340,200) = 2,727,300
#                 per peso 1 + 0.025 + 0.70 x 9% x 10/12 + 0.007 = 1.0845
@pytest.mark.parametrize("scenario, min_profit, expected", [
    ("Base", 0, 3_086_036.67),  # 3,282,000 / 1.0635
    ("Conservative", 0, 2_808_100.56),  # 3,015,900 / 1.074
    ("Base", 200_000, 2_897_978.37),  # 3,082,000 / 1.0635
    ("Conservative", 200_000, 2_621_880.82),  # 2,815,900 / 1.074
    ("Stress", 200_000, 2_330_382.66),  # 2,527,300 / 1.0845
])
def test_max_offer_for_each_scenario_and_profit_target(scenario, min_profit, expected):
    assert max_offer(ANCHOR, scenario, min_profit) == pytest.approx(expected, abs=1)


def test_max_offer_for_the_anchor_profit_is_the_anchor_price():
    # The anchor deal earns 304,200 at 2,800,000 in Base, so the highest
    # price that still earns 304,200 must be 2,800,000.
    assert max_offer(ANCHOR, "Base", min_profit=304_200) == pytest.approx(2_800_000, abs=1)


def test_max_offer_is_none_when_no_price_works():
    # Renovation of 5,000,000 (6,250,000 under Stress) exceeds the 3,780,000
    # Stress ARV on its own, so even a free property loses money.
    assert max_offer({**ANCHOR, "renovation_cost": 5_000_000}) is None
