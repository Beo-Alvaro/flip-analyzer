"""Tests for the Market scan page, run headless with Streamlit's AppTest.
Every expected number is calculated by hand in the comments.
"""

import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from flip.batch import load_deals
from flip.inputs import load_excel_inputs
from flip.market import LITTLE_ROOM, LOOK, NO_FAIR
from flip.template import STANDARD_CHECKLIST, create_template
from flip.workbook import add_deal, save_house

APP = str(Path(__file__).parent.parent / "src" / "flip" / "app.py")
OPEN = "1st auction; batch B1; offers Dec. 1, 2099 12:00 AM - Dec. 5, 2099 11:59 PM"
CLOSED = "1st auction; batch B0; offers Jan. 1, 2020 12:00 AM - Jan. 5, 2020 11:59 PM"


def listing(kind, price, link, occupancy="", notes=""):
    return {"city": "Tanza", "subdivision": "Sunrise Homes", "type": "townhouse", "kind": kind,
            "price": price, "floor_area_sqm": 40, "occupancy": occupancy, "link": link,
            "price_basis": "minimum bid (1st auction)" if kind == "foreclosed" else "asking",
            "notes": notes}


# Sunrise Homes new units: 50,000 and 52,000 per sqm -> median 51,000
LISTINGS = [
    listing("new", 2_000_000, "n1"),
    listing("new", 2_080_000, "n2"),
    listing("foreclosed", 1_000_000, "pagibig:815200000000001", "unoccupied", OPEN),  # 49.0%
    listing("foreclosed", 1_100_000, "pagibig:815200000000002", "occupied", OPEN),    # 53.9%
    listing("foreclosed", 1_040_000, "pagibig:815200000000003", "unoccupied", CLOSED),  # 51.0%
    listing("foreclosed", 1_600_000, "pagibig:815200000000004", "unoccupied", OPEN),  # 78.4%
]


@pytest.fixture
def files(tmp_path):
    listings = tmp_path / "listings.csv"
    with listings.open("w", encoding="utf-8", newline="") as f:
        f.write("# Test listings\n")
        pd.DataFrame(LISTINGS).to_csv(f, index=False)
    return {"listings": listings, "workbook": create_template(tmp_path / "deals_input.xlsx")}


@pytest.fixture
def app(files):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()  # the Market scan page comes first
    at.sidebar.text_input(key="path").set_value(str(files["workbook"]))
    at.sidebar.text_input(key="listings_path").set_value(str(files["listings"])).run()
    return at


def table(at):
    return at.dataframe[0].value  # the page's one table: the foreclosures


def test_default_filters(app):
    assert not app.exception
    # Unoccupied, offer window not closed, screen "worth a closer look" or "no fair
    # comparison": only ...0001. (0002 is occupied, 0003's window closed, 0004 is
    # 40,000 / 51,000 = 78.4%: little room.)
    shown = table(app)
    assert list(shown["link"]) == ["pagibig:815200000000001"]
    assert shown["vs_benchmark"].iloc[0] == pytest.approx(25_000 / 51_000)


def test_filters_off(app):
    app.checkbox(key="unoccupied").uncheck()
    app.checkbox(key="hide_closed").uncheck()
    app.multiselect(key="screens").set_value([LOOK, LITTLE_ROOM, NO_FAIR]).run()

    # Candidates first, lowest ratio first: 25,000, 26,000, 27,500 per sqm / 51,000,
    # then 40,000 / 51,000 (little room)
    assert list(table(app)["link"]) == [f"pagibig:81520000000000{n}" for n in (1, 3, 2, 4)]


def start(app, arv=1_500_000, monthly=5_000):
    link = "pagibig:815200000000001"
    if arv is not None:
        app.number_input(key=f"arv_{link}").set_value(arv)
    if monthly is not None:
        app.number_input(key=f"monthly_{link}").set_value(monthly)
    app.button(key="add_deal").click().run()


def test_start_a_deal(app, files):
    start(app)

    assert "Added **TANZA-01**" in app.success[0].value
    inputs = load_excel_inputs(files["workbook"])
    house = inputs.properties.set_index("deal_id").loc["TANZA-01"]
    assert (house["purchase_price"], house["arv"], house["floor_area_sqm"]) == (
        1_000_000, 1_500_000, 40)
    assert (house["holding_months"], house["monthly_holding_cost"]) == (6, 5_000)
    assert house["contingency_rate"] == pytest.approx(0.10)
    assert (house["source_url"], house["subdivision"]) == ("pagibig:815200000000001",
                                                           "Sunrise Homes")
    assert house["description"] == "Sunrise Homes townhouse, Pag-IBIG 1st auction, unoccupied"
    checklist = inputs.checklist[inputs.checklist["deal_id"] == "TANZA-01"]
    assert list(checklist["item"]) == STANDARD_CHECKLIST
    assert len(list((files["workbook"].parent / "backups").iterdir())) == 1


def test_the_new_deal_is_analyzed(app):
    start(app)
    app.switch_page("views/analyze.py").run()
    app.selectbox(key="house").set_value("TANZA-01").run()

    # No loan offers, so the default terms: 70% loan at 9% a year, 1% fee.
    # Acquisition 2.5% x 1,000,000 = 25,000; interest 700,000 x 9% x 6/12 = 31,500;
    # loan fee 7,000; holding 6 x 5,000 = 30,000; selling (3% + 6%) x 1,500,000 = 135,000.
    # Total cost 1,228,500 -> net profit 1,500,000 - 1,228,500 = 271,500.
    # Cash invested: 300,000 down + 25,000 + 31,500 + 7,000 + 30,000 = 393,500.
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Net profit"] == "₱271,500"
    assert metrics["ROI on total cost"] == "22.10%"  # 271,500 / 1,228,500
    assert metrics["Cash-on-cash ROI"] == "69.00%"  # 271,500 / 393,500


def test_arv_and_monthly_cost_are_required(app, files):
    before = files["workbook"].read_bytes()
    start(app, arv=None, monthly=None)

    assert "Please enter the ARV and the monthly holding cost" in app.error[0].value
    assert files["workbook"].read_bytes() == before


def test_workbook_open_in_excel(app, files):
    (files["workbook"].parent / f"~${files['workbook'].name}").write_text("")
    before = files["workbook"].read_bytes()
    start(app)

    assert "open in Excel" in app.error[0].value
    assert files["workbook"].read_bytes() == before


def test_import_collector_file(app, files, tmp_path):
    card = {"id": "815200000000009", "name": "SUNRISE HOMES", "type": "Town House",
            "dates": "Dec. 1, 2099 12:00 AM - Dec. 5, 2099 11:59 PM", "batch": "B1",
            "occupancy": "Unoccupied", "lot": "36 sqm", "floor": "40 sqm",
            "price": "₱1,200,000", "sale": "1st auction", "city": "TANZA"}
    collected = tmp_path / "opa_listings.json"
    collected.write_text(json.dumps([card]), encoding="utf-8")
    app.text_input(key="opa_path").set_value(str(collected))
    app.button(key="opa_import").click().run()

    assert "Imported 1 house (1 unoccupied): 1 new, 0 updated." in app.success[0].value
    assert "pagibig:815200000000009" in set(load_deals(files["listings"])["link"])
    assert len(list((tmp_path / "backups").iterdir())) == 1
    # 1,200,000 / 40 = 30,000 per sqm; 30,000 / 51,000 = 58.8%: also worth a closer look
    assert list(table(app)["link"]) == ["pagibig:815200000000001", "pagibig:815200000000009"]


def test_workbook_comps_are_used(app, files):
    add_deal(files["workbook"], {"deal_id": "TANZA-01", "purchase_price": 1_000_000,
                                 "arv": 1_500_000, "holding_months": 6,
                                 "monthly_holding_cost": 5_000, "city": "Tanza"})
    save_house(files["workbook"], "TANZA-01", tables={"Comps": [
        {"deal_id": "TANZA-01", "subdivision": "Sunrise Homes", "kind": "resale",
         "price": 1_600_000, "floor_area_sqm": 40},   # 40,000 per sqm
        {"deal_id": "TANZA-01", "subdivision": "Sunrise Homes", "kind": "resale",
         "price": 1_680_000, "floor_area_sqm": 40}]})  # 42,000 per sqm
    app.run()

    row = table(app).iloc[0]
    # Resale in the same subdivision now comes first: median 41,000 per sqm;
    # 25,000 / 41,000 = 61.0%
    assert row["benchmark"] == "same subdivision: resale"
    assert row["vs_benchmark"] == pytest.approx(25_000 / 41_000)
    assert any("Includes 2 resale and new comps" in c.value for c in app.caption)

    app.sidebar.checkbox(key="use_comps").uncheck().run()
    assert table(app).iloc[0]["benchmark"] == "same subdivision: new (ceiling)"
