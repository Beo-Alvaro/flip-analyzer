"""Tests for reading pasted listings (flip.listing_text).

The three posts are real Jade Residences (Imus) listings the user pasted in
October 2026, with the agent's name and phone number replaced and the
resale's block, lot, and street removed.
"""

from datetime import date

import pytest

from flip.listing_text import classify, loan_balance, money, payments_left, read_listing

DEVELOPER = """JADE RESIDENCES RE-OPEN UNITS!
Malagasang, Imus City, Cavite
Only 10 units are available, so now's the perfect time to secure your future home!
💰 Total Contract Price: ₱2,124,000
Flexible Payment Details:
✅ Loanable Amount: ₱1,522,000
✅ Total Downpayment: ₱602,000
📅 Payable in 24 months
💳 Monthly Downpayment: ₱24,875
🏦 Estimated Monthly Amortization: ₱9,927
📊 Required Monthly Salary: ₱27,000
Interested? I'd be happy to assist you!
📩 Message me now to reserve your unit and schedule your FREE site viewing!
Agent Name
📱0900-000-0000"""

PASALO = """🏠 HOUSE & LOT FOR SALE
📍 Property Details
• Location: JADE RESIDENCE imus
• Property Type: House and Lot
• Lot Area: 36 sqm
• Floor Area: 50 sqm
bare type
💰 Payment Details
. Bank Finance
• Start of Monthly Amortization: August 16, 2018
. 17k monthly
• Remaining Term: Based on 180 months (15 years)
• Interest Rate: 24%
💵 Selling Price / Terms
• Cash Out: ₱1.1m
• Remaining Balance: ₱400k plus (to be assumed by the buyer)
Khit 2gives ok lng po"""

RESALE = """•Address : Jade residences, malagasang, imus cavite
•Two storey residence with balcony
•Price : 2.5 million
•Cash basis
•Lot area :36  sq. Mtr.
•2 bedrooms
•1 toilet & bath
•Clean title
•Updated tax"""


@pytest.mark.parametrize("text, expected", [
    ("₱2,124,000", 2_124_000), ("1.1m", 1_100_000), ("₱400k plus", 400_000),
    ("2.5 million", 2_500_000), ("PHP 1,184,220.50", 1_184_220.50), ("no amount", None),
])
def test_money(text, expected):
    assert money(text) == expected


def test_developer_post():
    found = read_listing(DEVELOPER)

    assert found["kind"] == "new"
    assert {"total contract price", "re-open", "reserve your", "site viewing"} <= set(
        found["signs"]["new"])
    assert found["price"] == 2_124_000  # the TCP, not the loanable amount
    assert found["monthly"] == 9_927  # the amortization, not the monthly downpayment
    assert found["floor_area_sqm"] is None  # the post doesn't say: ask the seller


def test_pasalo_post():
    found = read_listing(PASALO)

    assert found["kind"] == "pasalo"
    assert {"cash out", "remaining balance", "assumed by the buyer"} <= set(found["signs"]["pasalo"])
    assert (found["lot_area_sqm"], found["floor_area_sqm"]) == (36, 50)
    assert (found["cash_out"], found["balance"]) == (1_100_000, 400_000)
    assert found["monthly"] == 17_000  # "17k monthly", not the 16 in "August 16"
    assert found["annual_rate"] == 0.24
    assert found["term_months"] == 180
    assert found["payments_started"] == date(2018, 8, 16)
    assert found["condition"] == "bare (not finished)"
    assert found["price"] is None  # "Selling Price / Terms" is a heading


def test_resale_post():
    found = read_listing(RESALE)

    assert found["kind"] == "resale"
    assert set(found["signs"]["resale"]) == {"clean title", "updated tax", "cash basis"}
    assert (found["price"], found["lot_area_sqm"]) == (2_500_000, 36)
    assert found["floor_area_sqm"] is None


def test_lot_and_house_written_together():
    found = read_listing("Jade Residences 50/60 lot/hse sqm, clean title")
    assert (found["lot_area_sqm"], found["floor_area_sqm"]) == (50, 60)


def test_unsure_and_whole_words():
    assert classify("House for sale in Imus")[0] == ""  # no signs either way
    assert read_listing("Villa 36 sqm")["lot_area_sqm"] is None  # "la" inside "villa"


def test_payments_left():
    # Started 2018-08-16: 8 years x 12 + 2 months (Aug to Oct) + October's = 99 made
    assert payments_left(date(2018, 8, 16), 180, date(2026, 10, 18)) == 81
    assert payments_left(date(2018, 8, 16), 180, date(2026, 10, 15)) == 82  # Oct not due yet
    assert payments_left(date(2010, 1, 1), 120, date(2026, 10, 18)) == 0  # paid off


def test_loan_balance():
    assert loan_balance(17_000, 0.0, 81) == 1_377_000  # no interest: 81 x 17,000
    # 2% a month: 17,000 / 1.02 = 16,666.67, plus 17,000 / 1.02^2 = 16,339.87
    assert loan_balance(17_000, 0.24, 2) == pytest.approx(33_006.54, abs=0.01)
    # The Jade pasalo: 81 payments of 17,000 at 2% a month.
    # 1.02^81 = 4.972948, so (1 - 1/4.972948) / 0.02 = 39.9456; x 17,000 = 679,075
    assert loan_balance(17_000, 0.24, 81) == pytest.approx(679_075, abs=2)
    assert loan_balance(17_000, 0.24, 0) == 0
