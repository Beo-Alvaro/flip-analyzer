"""Tests for saving into the input workbook (flip.workbook)."""

from datetime import datetime

import pandas as pd
import pytest
from openpyxl import load_workbook

from flip.inputs import InputError, load_excel_inputs
from flip.template import STANDARD_CHECKLIST, create_template
from flip.workbook import WorkbookBusy, add_deal, backup, next_deal_id

HOUSE = {"deal_id": "TANZA-01", "description": "Test house", "purchase_price": 1_000_000,
         "arv": 1_500_000, "holding_months": 6, "monthly_holding_cost": 5_000,
         "floor_area_sqm": 40, "holding_months_worst": None, "city": "Tanza",
         "subdivision": "Sunrise Homes", "type": "townhouse",
         "source_url": "pagibig:815200000000001"}


@pytest.fixture
def workbook(tmp_path):
    return create_template(tmp_path / "deals_input.xlsx")


def test_add_deal(workbook):
    saved = add_deal(workbook, HOUSE, STANDARD_CHECKLIST)

    inputs = load_excel_inputs(workbook)
    assert list(inputs.properties["deal_id"]) == ["SAMPLE-01", "TANZA-01"]  # below the example
    house = inputs.properties.set_index("deal_id").loc["TANZA-01"]
    assert (house["purchase_price"], house["arv"], house["floor_area_sqm"]) == (
        1_000_000, 1_500_000, 40)
    assert (house["subdivision"], house["source_url"]) == ("Sunrise Homes",
                                                           "pagibig:815200000000001")
    assert pd.isna(house["holding_months_worst"])  # left blank
    mine = inputs.checklist[inputs.checklist["deal_id"] == "TANZA-01"]
    assert list(mine["item"]) == STANDARD_CHECKLIST
    assert set(mine["status"]) == {"open"}
    # The backup is the workbook as it was before the change
    assert saved.parent == workbook.parent / "backups"
    assert list(load_excel_inputs(saved).properties["deal_id"]) == ["SAMPLE-01"]


def test_column_notes_and_typing_checks_are_kept(workbook):
    add_deal(workbook, HOUSE)

    ws = load_workbook(workbook)["Properties"]
    assert ws["A1"].comment is not None
    assert ws.data_validations.dataValidation


def test_the_same_deal_id_is_refused(workbook):
    add_deal(workbook, HOUSE)

    with pytest.raises(InputError, match="already on the Properties sheet"):
        add_deal(workbook, {**HOUSE, "deal_id": "tanza-01"})


def test_a_bad_value_never_reaches_the_workbook(workbook):
    before = workbook.read_bytes()

    with pytest.raises(InputError, match="arv can't be negative"):
        add_deal(workbook, {**HOUSE, "arv": -1})
    assert workbook.read_bytes() == before
    assert not (workbook.parent / "backups").exists()
    assert not list(workbook.parent.glob(".saving-*"))


def test_open_in_excel_is_refused(workbook):
    (workbook.parent / f"~${workbook.name}").write_text("")  # Excel's lock file
    before = workbook.read_bytes()

    with pytest.raises(WorkbookBusy, match="open in Excel"):
        add_deal(workbook, HOUSE)
    assert workbook.read_bytes() == before


def test_next_deal_id():
    assert next_deal_id(["IMUS-01", "SANPABLO-01"], "Imus") == "IMUS-02"
    assert next_deal_id(["imus-01"], "Imus") == "IMUS-02"
    assert next_deal_id([], "Trece Martires") == "TRECE-MARTIRES-01"
    assert next_deal_id([], None) == "DEAL-01"


def test_backup_names(tmp_path):
    listings = tmp_path / "listings.csv"
    listings.write_text("city\n", encoding="utf-8")
    now = datetime(2026, 10, 17, 14, 30, 5)

    first, second = backup(listings, now), backup(listings, now)
    assert first.name == "listings-20261017-143005.csv"
    assert second.name == "listings-20261017-143005-2.csv"  # same second, not overwritten
    assert first.read_text(encoding="utf-8") == "city\n"
