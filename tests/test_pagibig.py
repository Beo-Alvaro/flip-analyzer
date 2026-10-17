"""Tests for importing Pag-IBIG auction lists. The rows are copied from a
real list (NCR branch tranche SPB 321, April 2024), including one scrambled
by a mirror site's page stamp and one whose address wraps onto two lines.
"""

import pandas as pd
import pytest

from flip.batch import file_notes, load_deals
from flip.pagibig import import_rows, list_details, merge_into, parse_row

HEADER = ["ITEM\nNO", "PROPERTY NUMBER", "", "TYPE", "TCT/CCT NO.", "LOT\nAREA", "FLOOR\nAREA",
          "MINIMUM BID\nPRICE", "APPRAISAL\nDATE", "REQUIRED GROSS\nMONTHLY INCOME", "REMARKS"]
SECTION = ["SINGLE ATTACHED - BATANGAS, BULACAN, CAVITE, LAGUNA and RIZAL"] + [None] * 10
ELISA = ["26", "815202307130071",
         "Elisa Homes - Phase-3 Blk-36 Lot-5 - Brgy. Molino IV, Bacoor City, Cavite",
         "SINGLE ATTACHED", "T-248220", "120.00", "74.00", "4,235,400.00", "03/14/2023",
         "75,495.39", "Occupied - Occupant Undisclosed - For\nTitle Consolidation"]
SCRAMBLED = ["h\n28", "ttp\n815202309280024",
             "s://www.forecl\nVilla Apolonia - Phase-2 Blk-34 Lot-23 - Brgy. Ibayo Silangan, Naic, Cavite",
             "osu\nSINGLE ATTACHED", "re\nT-616140", "p\n61.75", "hi\n52.00", "lip\n905,650.00",
             "pi\n08/31/2023", "nes\n16,143.08",
             ".com\nOccupied - Occupant Undisclosed - For\nTitle Consolidation"]
UNOCCUPIED_TOWNHOUSE = ["5", "815202402140017",
                        "Pagsibol Village East - Blk-2 Lot-9 - Brgy. Sabang, Naic, Cavite",
                        "TOWNHOUSE", "T-1", "54.00", "45.50", "1,532,000.00", "01/02/2024",
                        "27,307.31", "UNOCCUPIED - For Title Consolidation"]
WRAPPED_LAGUNA = ["21", "815202112290299",
                  "South Fairway Homes Classic - Phase-4 Blk-77\nLot-21 - Brgy. Landayan, City of San Pedro, Laguna",
                  "TOWNHOUSE", "T-341872", "75.00", "40.00", "585,000.00", "02/17/2024",
                  "10,427.54", "Occupied - Occupant Undisclosed"]
CONDO = ["1", "815202402260040",
         "Tanza Garden Heights - Bldg-H 4th-Floor Unit-412 - Brgy. Punta I, Tanza, Cavite",
         "CONDOMINIUM", "057-2020000372", "0.00", "25.00", "1,007,300.00", "12/13/2023",
         "17,954.98", "UNOCCUPIED - For Title Consolidation"]
LOT = ["20", "815202402130051",
       "Villa Philomena Homes - Blk-8 Lot-20 - Brgy. De La Paz, City of Binan, Laguna",
       "LOT ONLY", "T-581498", "116.00", "0.00", "531,280.00", "09/19/2023", "9,469.99",
       "UNOCCUPIED"]


def test_header_and_section_rows_are_skipped():
    assert parse_row(HEADER) is None
    assert parse_row(SECTION) is None


def test_house_row():
    r = parse_row(ELISA)

    assert (r["city"], r["barangay"], r["subdivision"]) == ("Bacoor", "Molino IV", "Elisa Homes")
    assert r["type"] == "single attached"
    assert (r["price"], r["floor_area_sqm"], r["lot_area_sqm"]) == (4_235_400, 74, 120)
    assert r["occupancy"] == "occupied"
    assert r["link"] == "pagibig:815202307130071"
    assert (r["kind"], r["price_basis"]) == ("foreclosed", "minimum bid")


def test_row_scrambled_by_a_page_stamp():
    r = parse_row(SCRAMBLED)

    assert (r["city"], r["subdivision"], r["type"]) == ("Naic", "Villa Apolonia", "single attached")
    assert (r["price"], r["floor_area_sqm"], r["lot_area_sqm"]) == (905_650, 52, 61.75)
    assert r["link"] == "pagibig:815202309280024"


def test_unoccupied_and_wrapped_address():
    assert parse_row(UNOCCUPIED_TOWNHOUSE)["occupancy"] == "unoccupied"
    r = parse_row(WRAPPED_LAGUNA)
    assert (r["city"], r["province"], r["barangay"]) == ("San Pedro", "Laguna", "Landayan")


def test_condos_and_lots_are_skipped():
    assert parse_row(CONDO) is None
    assert parse_row(LOT) is None


@pytest.mark.parametrize("written, expected", [
    ("City of Dasmariñas", "Dasmarinas"),
    ("City of General Trias", "General Trias"),
    ("Gen. Mariano Alvarez", "GMA"),
    ("Cavite City", "Cavite City"),
])
def test_city_names_match_the_market_data(written, expected):
    row = ELISA.copy()
    row[2] = f"Some Homes - Blk-1 Lot-1 - Brgy. Somewhere, {written}, Cavite"
    assert parse_row(row)["city"] == expected


def test_import_keeps_one_province():
    df = import_rows([HEADER, SECTION, ELISA, SCRAMBLED, WRAPPED_LAGUNA, CONDO, LOT],
                     "Cavite", "SPB 321", "2024-04-12")

    assert list(df["link"]) == ["pagibig:815202307130071", "pagibig:815202309280024"]
    assert set(df["source"]) == {"pagibigfund.gov.ph SPB 321"}
    assert set(df["date_listed"]) == {"2024-04-12"}


def test_list_details():
    text = "INVITATION TO BID\nApril 12, 2024\n...\nSPB 321 293 April 22 - 26, 2024"
    assert list_details(text) == ("SPB 321", "2024-04-12")


def test_merge_replaces_the_same_property(tmp_path):
    path = tmp_path / "listings.csv"
    path.write_text(
        "# Test listings\n"
        "city,kind,price,floor_area_sqm,link\n"
        "Bacoor,foreclosed,4000000,74,https://example.com/advert/pag-ibig-815202307130071-elisa/\n"
        "Imus,new,2000000,40,https://example.com/new-unit\n",
        encoding="utf-8")
    imported = import_rows([ELISA, SCRAMBLED], "Cavite", "SPB 321", "2024-04-12")

    assert merge_into(path, imported) == (1, 1)  # Elisa replaced, Villa Apolonia added
    merged = load_deals(path)
    assert file_notes(path) == ["# Test listings"]
    assert len(merged) == 3
    elisa = merged[merged["link"] == "pagibig:815202307130071"].iloc[0]
    assert elisa["price"] == 4_235_400  # the official minimum bid replaced the old row
