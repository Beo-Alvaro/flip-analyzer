"""Tests for the Edit a house page, run headless with Streamlit's AppTest.
Expected numbers are the hand-calculated anchor deal (docs/project-context.md).
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from flip.inputs import load_excel_inputs
from flip.template import STANDARD_CHECKLIST, create_template
from flip.workbook import add_deal

APP = str(Path(__file__).parent.parent / "src" / "flip" / "app.py")
EDIT, ANALYZE = "views/edit.py", "views/analyze.py"


@pytest.fixture
def workbook(tmp_path):
    return create_template(tmp_path / "deals_input.xlsx")


def open_edit(workbook):
    at = AppTest.from_file(APP, default_timeout=60)
    at.switch_page(EDIT).run()
    at.sidebar.text_input(key="path").set_value(str(workbook)).run()
    return at


def test_nothing_changed_means_nothing_to_save(workbook):
    at = open_edit(workbook)

    assert not at.exception
    # Every table of the example house (renovations, loan offers with rates, comps,
    # checklist) shown and read back unchanged: no unsaved changes
    assert at.button(key="save_house").disabled
    assert not at.warning


def test_change_the_arv_and_analyze(workbook):
    at = open_edit(workbook)
    at.number_input(key="arv_SAMPLE-01_0").set_value(4_300_000)
    at.run()
    assert "Unsaved changes: House" in at.warning[0].value

    at.button(key="save_house").click().run()

    assert "Saved SAMPLE-01 (House)" in at.success[0].value
    house = load_excel_inputs(workbook).properties.set_index("deal_id").loc["SAMPLE-01"]
    assert house["arv"] == 4_300_000
    assert len(list((workbook.parent / "backups").iterdir())) == 1
    assert at.button(key="save_house").disabled  # saved: nothing left to save

    at.switch_page(ANALYZE).run()
    # ARV +100,000; selling costs +9% of it = +9,000; net profit 304,200 + 91,000
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Net profit"] == "₱395,200"


def test_discard(workbook):
    at = open_edit(workbook)
    at.number_input(key="arv_SAMPLE-01_0").set_value(4_300_000)
    at.run()
    at.button(key="discard_house").click().run()

    assert at.number_input(key="arv_SAMPLE-01_1").value == 4_200_000
    assert at.button(key="save_house").disabled


def test_open_in_excel(workbook):
    at = open_edit(workbook)
    (workbook.parent / f"~${workbook.name}").write_text("")
    before = workbook.read_bytes()
    at.number_input(key="arv_SAMPLE-01_0").set_value(4_300_000)
    at.run()
    at.button(key="save_house").click().run()

    assert "open in Excel" in at.error[0].value
    assert workbook.read_bytes() == before


def test_a_new_house_gets_the_standard_checklist(workbook):
    add_deal(workbook, {"deal_id": "TANZA-01", "purchase_price": 1_000_000,
                        "arv": 1_500_000, "holding_months": 6,
                        "monthly_holding_cost": 5_000, "floor_area_sqm": 40})
    at = open_edit(workbook)  # on the first house, SAMPLE-01
    at.switch_page(ANALYZE).run()
    at.session_state["current_deal"] = "TANZA-01"  # what Start a deal does
    at.switch_page(EDIT).run()

    assert at.selectbox(key="edit_house").value == "TANZA-01"  # the page follows
    assert "Unsaved changes: Checklist" in at.warning[0].value
    at.button(key="save_house").click().run()

    checklist = load_excel_inputs(workbook).checklist
    mine = checklist[checklist["deal_id"] == "TANZA-01"]
    assert list(mine["item"]) == STANDARD_CHECKLIST
    assert set(mine["status"]) == {"open"}
