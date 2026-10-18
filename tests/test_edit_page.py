"""Tests for the Edit a house page, run headless with Streamlit's AppTest.
Expected numbers are the hand-calculated anchor deal (docs/project-context.md).
"""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from flip.inputs import load_excel_inputs
from flip.template import STANDARD_CHECKLIST, create_template
from flip.workbook import add_deal
from test_draft import LISTINGS as MARKET
from test_listing_text import DEVELOPER, PASALO, RESALE

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
    assert not at.warning  # an empty checklist is not an unsaved change
    at.button(key="checklist_add_TANZA-01_0").click().run()

    assert "Saved TANZA-01 (checklist added)" in at.success[0].value

    checklist = load_excel_inputs(workbook).checklist
    mine = checklist[checklist["deal_id"] == "TANZA-01"]
    assert list(mine["item"]) == STANDARD_CHECKLIST
    assert set(mine["status"]) == {"open"}


# --- Paste a listing (posts from tests/test_listing_text.py) ---

def test_paste_a_resale(workbook):
    at = open_edit(workbook)
    at.text_area(key="paste_SAMPLE-01_0").set_value(RESALE).run()
    assert any("Looks like **resale**" in i.value for i in at.info)
    assert at.button(key="p_add_SAMPLE-01_0").disabled  # the post has no floor area

    at.number_input(key="p_floor_SAMPLE-01_0").set_value(60).run()  # asked the seller
    at.button(key="p_add_SAMPLE-01_0").click().run()

    assert "Saved SAMPLE-01 (comp added)" in at.success[0].value
    comps = load_excel_inputs(workbook).comps
    assert len(comps[comps["deal_id"] == "SAMPLE-01"]) == 4  # the 3 examples + this one
    new = comps[comps["price"] == 2_500_000].iloc[0]
    assert (new["kind"], new["floor_area_sqm"], new["lot_area_sqm"]) == ("resale", 60, 36)
    # Resale comps per sqm: 48,000, 50,000, 52,000 and 2,500,000 / 60 = 41,667.
    # Median (48,000 + 50,000) / 2 = 49,000 x 84 sqm = 4,116,000
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Suggested ARV"] == "₱4,116,000"


def test_paste_a_pasalo(workbook):
    at = open_edit(workbook)
    at.text_area(key="paste_SAMPLE-01_0").set_value(PASALO).run()
    assert any("Looks like **pasalo**" in i.value for i in at.info)
    at.number_input(key="p_left_SAMPLE-01_0").set_value(81).run()  # 99 of 180 paid

    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Balance the loan terms imply"] == "₱679,075"  # see test_listing_text.py
    # 679,075 - 400,000 claimed
    assert any("differ by ₱279,075" in w.value for w in at.warning)

    at.button(key="p_add_SAMPLE-01_0").click().run()  # the cautious price is chosen first
    comps = load_excel_inputs(workbook).comps
    new = comps[comps["price"] == 1_500_000].iloc[0]  # 1,100,000 cash-out + 400,000
    assert (new["kind"], new["floor_area_sqm"]) == ("resale", 50)
    assert new["condition"] == ("bare (not finished); pasalo: cash-out + the seller's "
                                "balance figure, unconfirmed")


def test_paste_waits_for_other_changes(workbook):
    at = open_edit(workbook)
    at.number_input(key="arv_SAMPLE-01_0").set_value(4_300_000)
    at.text_area(key="paste_SAMPLE-01_0").set_value(RESALE)
    at.run()
    at.number_input(key="p_floor_SAMPLE-01_0").set_value(60).run()

    assert at.button(key="p_add_SAMPLE-01_0").disabled  # the ARV change isn't saved yet


def test_paste_several_posts(workbook):
    at = open_edit(workbook)
    at.text_area(key="paste_SAMPLE-01_0").set_value(f"{DEVELOPER}\n---\n{PASALO}\n---\n{RESALE}")
    at.run()
    assert any("3 posts" in i.value for i in at.info)

    # Only the pasalo post has both a price and a floor area, so only it is ticked
    at.button(key="batch_add_SAMPLE-01_0").click().run()

    assert "Saved SAMPLE-01 (comp added)" in at.success[0].value
    comps = load_excel_inputs(workbook).comps
    new = comps[comps["price"] == 1_500_000].iloc[0]  # 1,100,000 cash-out + 400,000 balance
    assert (new["kind"], new["floor_area_sqm"], new["lot_area_sqm"]) == ("resale", 50, 36)
    assert new["condition"] == ("bare (not finished); pasalo: cash-out + the seller's "
                                "balance figure, unconfirmed")
    log = pd.read_csv(workbook.parent / "paste_log.csv")
    assert (log.loc[0, "guessed_kind"], log.loc[0, "chosen_kind"]) == ("pasalo", "pasalo")
    assert list(log.loc[0, ["price_outcome", "floor_area_sqm_outcome",
                            "lot_area_sqm_outcome"]]) == ["kept", "kept", "kept"]


def test_the_reader_keeps_score(workbook):
    at = open_edit(workbook)
    at.text_area(key="paste_SAMPLE-01_0").set_value(RESALE).run()
    at.number_input(key="p_floor_SAMPLE-01_0").set_value(60).run()
    at.button(key="p_add_SAMPLE-01_0").click().run()

    # Kind guessed right; price and lot area read and kept; floor area typed in
    assert any("How the reader has done so far: Kind: right 1 of 1 (100%) · Price: found in "
               "1 of 1, kept as read 1 of 1 · Floor area: found in 0 of 1 · Lot area: found "
               "in 1 of 1, kept as read 1 of 1." in c.value for c in at.caption)


def test_draft_from_the_market_data(tmp_path):
    workbook = create_template(tmp_path / "deals_input.xlsx")
    add_deal(workbook, {"deal_id": "TANZA-01", "purchase_price": 1_201_368, "arv": 1_720_000,
                        "holding_months": 10, "monthly_holding_cost": 3_000,
                        "floor_area_sqm": 46.2, "source_url": "pagibig:999", "city": "Tanza",
                        "barangay": "Bucal", "subdivision": "Springtown Southgate",
                        "type": "townhouse"})
    listings = tmp_path / "listings.csv"
    MARKET.to_csv(listings, index=False)
    at = open_edit(workbook)
    at.session_state["listings_path"] = str(listings)
    at.switch_page(ANALYZE).run()
    at.session_state["current_deal"] = "TANZA-01"
    at.switch_page(EDIT).run()

    at.button(key="drafts_add_TANZA-01_0").click().run()  # all ticked by default

    assert "Saved TANZA-01 (5 drafted comps added)" in at.success[0].value
    comps = load_excel_inputs(workbook).comps
    # The same picks as tests/test_draft.py: 3 resale (closest place first), 2 new
    assert list(comps[comps["deal_id"] == "TANZA-01"]["link"]) == ["r1", "r2", "r3", "n3", "n2"]
    assert any("No similar listings in the market data for this house yet" in c.value
               for c in at.caption)  # all of them are comps now
