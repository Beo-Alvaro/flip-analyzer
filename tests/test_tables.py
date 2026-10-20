"""Tests for the split tables: itemized renovations and loan offer comparison.
Every expected number is calculated by hand; the arithmetic is in comments.
"""

import pandas as pd
import pytest

from flip.batch import analyze_deals, file_notes, load_deals
from flip.tables import build_deals


def money(value):
    """Compare peso amounts to the centavo, ignoring float rounding noise."""
    return pytest.approx(value, abs=0.01)


# Anchor deal, split into tables
PROPERTIES = pd.DataFrame({
    "deal_id": ["anchor"],
    "purchase_price": [2_800_000],
    "arv": [4_200_000],
    "holding_months": [6],
    "monthly_holding_cost": [15_000],
})

RENOVATIONS = pd.DataFrame({
    "deal_id": ["anchor"] * 6,
    "item": ["Roof", "Kitchen", "Bathroom", "Electrical", "Paint", "Flooring"],
    "cost": [90_000, 120_000, 80_000, 70_000, 60_000, 30_000],  # total 450,000
})

LOAN_OFFERS = pd.DataFrame({
    "deal_id": ["anchor"] * 3,
    "offer": ["Bank A", "Bank B", "Cash"],
    "loan_ratio": [0.70, 0.80, 0],
    "annual_interest_rate": [0.09, 0.10, 0],
    "loan_fee_rate": [0.01, 0.015, 0],
})


@pytest.fixture
def offers():
    analyzed = analyze_deals(build_deals(PROPERTIES, RENOVATIONS, LOAN_OFFERS))
    return analyzed.set_index("offer")


def test_renovation_items_add_up(offers):
    # 90,000 + 120,000 + 80,000 + 70,000 + 60,000 + 30,000
    assert offers.loc["Bank A", "renovation_cost"] == money(450_000)


def test_one_row_per_loan_offer(offers):
    assert list(offers.index) == ["Bank A", "Bank B", "Cash"]


def test_bank_a_is_the_anchor_deal(offers):
    r = offers.loc["Bank A"]

    assert r["net_profit"] == money(304_200)
    assert r["cash_invested"] == money(1_557_800)


def test_bank_b():
    # Loan 2,800,000 x 80% = 2,240,000; down payment 560,000
    # Interest 2,240,000 x 10% x 6/12 = 112,000; loan fee 2,240,000 x 1.5% = 33,600
    analyzed = analyze_deals(build_deals(PROPERTIES, RENOVATIONS, LOAN_OFFERS))
    r = analyzed.set_index("offer").loc["Bank B"]

    assert r["interest"] == money(112_000)
    assert r["loan_fees"] == money(33_600)
    # 2,800,000 + 70,000 + 450,000 + 112,000 + 33,600 + 90,000 + 378,000
    assert r["total_cost"] == money(3_933_600)
    assert r["net_profit"] == money(266_400)  # 4,200,000 - 3,933,600
    # 560,000 + 70,000 + 450,000 + 112,000 + 33,600 + 90,000
    assert r["cash_invested"] == money(1_315_600)
    assert r["roi_on_total_cost"] == pytest.approx(266_400 / 3_933_600)  # ~6.77%
    assert r["cash_on_cash_roi"] == pytest.approx(266_400 / 1_315_600)  # ~20.25%
    # Stress: interest 2,240,000 x 10% x 10/12 = 186,666.67
    # 2,800,000 + 70,000 + 562,500 + 186,666.67 + 33,600 + 150,000 + 340,200
    #   = 4,142,966.67; 3,780,000 - 4,142,966.67
    assert r["stress_net_profit"] == money(-362_966.67)


def test_cash_offer_is_the_no_loan_deal(offers):
    r = offers.loc["Cash"]

    assert r["net_profit"] == money(412_000)
    assert r["cash_invested"] == money(3_410_000)


# Max offer under Stress: (3,780,000 - 562,500 - 150,000 - 340,200) = 2,727,300,
# divided by what each peso of price costs (1 + 0.025 acquisition + interest + fee):
@pytest.mark.parametrize("offer, expected", [
    ("Bank A", 2_514_799.45),  # 1 + 0.025 + 0.70 x 9% x 10/12 + 0.70 x 1%   = 1.0845
    ("Bank B", 2_471_126.55),  # 1 + 0.025 + 0.80 x 10% x 10/12 + 0.80 x 1.5% = 1.103667
    ("Cash", 2_660_780.49),  # 1 + 0.025                                   = 1.025
])
def test_max_offer_per_loan_offer(offers, offer, expected):
    assert offers.loc[offer, "max_offer_stress"] == pytest.approx(expected, abs=1)


def test_house_without_loan_offers_gets_labeled_default_terms():
    no_offers = LOAN_OFFERS.iloc[0:0]  # same columns, no rows
    analyzed = analyze_deals(build_deals(PROPERTIES, RENOVATIONS, no_offers))

    assert list(analyzed["offer"]) == ["default terms"]
    assert analyzed.loc[0, "loan_ratio"] == 0.70
    assert analyzed.loc[0, "net_profit"] == money(304_200)  # default terms = anchor terms


def test_cash_only_offers_read_as_whole_numbers():
    # Excel stores Cash's 0 / 0 / 0 as whole numbers, so pandas reads the loan
    # columns as integers. With every house on such offers there is no blank to
    # make them decimals, and filling in the 70% default must still work.
    cash = pd.DataFrame({"deal_id": ["anchor"], "offer": ["Cash"], "loan_ratio": [0],
                         "annual_interest_rate": [0], "loan_fee_rate": [0]})
    analyzed = analyze_deals(build_deals(PROPERTIES, RENOVATIONS, cash))
    assert analyzed.loc[0, "net_profit"] == money(412_000)  # as the Cash row above

    properties = pd.concat([PROPERTIES, PROPERTIES.assign(deal_id="second")],
                           ignore_index=True)
    analyzed = analyze_deals(build_deals(properties, RENOVATIONS, cash)).set_index("deal_id")
    assert (analyzed.loc["second", "offer"], analyzed.loc["second", "loan_ratio"]) == (
        "default terms", 0.70)
    assert analyzed.loc["second", "net_profit"] == money(754_200)  # anchor terms, no items


def test_house_without_renovation_items_has_zero_renovation():
    no_items = RENOVATIONS.iloc[0:0]
    analyzed = analyze_deals(build_deals(PROPERTIES, no_items, LOAN_OFFERS))
    r = analyzed.set_index("offer").loc["Bank A"]

    assert r["renovation_cost"] == 0
    assert r["total_cost"] == money(3_445_800)  # 3,895,800 - 450,000
    assert r["net_profit"] == money(754_200)  # 4,200,000 - 3,445,800


def test_typo_in_deal_id_is_an_error():
    typo = pd.DataFrame({"deal_id": ["anchr"], "item": ["Roof"], "cost": [90_000]})

    with pytest.raises(ValueError, match="anchr"):
        build_deals(PROPERTIES, typo, LOAN_OFFERS)


def test_repeated_property_is_an_error():
    repeated = pd.concat([PROPERTIES, PROPERTIES])

    with pytest.raises(ValueError, match="more than once"):
        build_deals(repeated, RENOVATIONS, LOAN_OFFERS)


def test_hash_inside_a_value_is_kept(tmp_path):
    path = tmp_path / "renovations.csv"
    path.write_text("# SAMPLE DATA: test\ndeal_id,item,cost\nanchor,Bathroom #2,80000\n",
                    encoding="utf-8")

    assert load_deals(path).loc[0, "item"] == "Bathroom #2"


@pytest.mark.parametrize("path", [
    "data/sample_properties.csv",
    "data/sample_renovations.csv",
    "data/sample_loan_offers.csv",
])
def test_sample_files_are_labeled_sample(path):
    assert any("SAMPLE DATA" in note for note in file_notes(path))


def test_sample_anchor_renovation_items_add_up_to_450000():
    renovations = load_deals("data/sample_renovations.csv")

    assert renovations[renovations["deal_id"] == "SAMPLE-01"]["cost"].sum() == 450_000
