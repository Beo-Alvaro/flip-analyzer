"""Tests for the web app, run headless with Streamlit's AppTest.
Expected numbers are the hand-calculated anchor deal (docs/project-context.md).
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from flip.template import create_template

APP = str(Path(__file__).parent.parent / "src" / "flip" / "app.py")


@pytest.fixture
def app(tmp_path):
    workbook = create_template(tmp_path / "deals_input.xlsx")
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.text_input(key="path").set_value(str(workbook)).run()
    return at


def metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


def test_no_workbook_explains_how_to_make_one(tmp_path):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.text_input(key="path").set_value(str(tmp_path / "missing.xlsx")).run()

    assert not at.exception
    assert "python -m flip.template" in at.info[0].value


def test_anchor_deal_numbers(app):
    assert not app.exception
    assert "SAMPLE DATA" in app.warning[0].value
    assert not app.info  # no what-if note until something is changed
    assert metric(app, "Net profit") == "₱304,200"
    assert metric(app, "ROI on total cost") == "7.81%"  # 304,200 / 3,895,800
    assert metric(app, "Cash-on-cash ROI") == "19.53%"  # 304,200 / 1,557,800
    assert metric(app, "Yearly cash-on-cash ROI") == "39.06%"  # x 12 / 6
    assert metric(app, "vs 6% safe account") == "+257,466"  # 304,200 - 46,734
    assert metric(app, "Stress profit") == "-₱309,300"
    assert metric(app, "Max offer (Stress)") == "₱2,514,799"
    assert metric(app, "Break-even sale price") == "₱3,865,714"  # 3,517,800 / 0.91
    assert metric(app, "Suggested ARV") == "₱4,200,000"  # 50,000 x 84


def test_verdict_lists_the_reasons(app):
    assert "price is 285,201 above the max offer under Stress" in app.error[0].value


def test_other_loan_offer(app):
    app.radio(key="offer_SAMPLE-01").set_value("Bank B").run()

    assert metric(app, "Net profit") == "₱266,400"  # see test_tables.py
    assert metric(app, "Cash-on-cash ROI") == "20.25%"  # 266,400 / 1,315,600


def test_what_if_changes_the_numbers_but_not_the_workbook(app, tmp_path):
    workbook = tmp_path / "deals_input.xlsx"
    before = workbook.read_bytes()
    app.number_input(key="price_SAMPLE-01").set_value(2_514_799.45).run()

    # At the Stress max offer, Stress breaks even and the price rule passes
    assert metric(app, "Stress profit") == "₱0"
    assert "What-if numbers in use" in app.info[0].value
    assert workbook.read_bytes() == before  # the app never writes the workbook
