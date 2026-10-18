"""Tests for keeping score of the listing reader (flip.paste_log)."""

from datetime import date

import pytest

from flip.listing_text import read_listing, suggested_comp
from flip.paste_log import entry, log_entries, outcome, reader_scores
from test_listing_text import RESALE


@pytest.mark.parametrize("found, saved, expected", [
    (2_500_000, 2_500_000, "kept"),
    (2_500_000, 2_400_000, "changed"),
    (None, 60, "added"),
    (None, None, "missing"),
    (36, None, "changed"),  # found but you cleared it
])
def test_outcome(found, saved, expected):
    assert outcome(found, saved) == expected


def test_entry():
    found = read_listing(RESALE)
    saved = {"price": 2_500_000, "floor_area_sqm": 60, "lot_area_sqm": 50}

    assert entry("IMUS-02", found, suggested_comp(found), "resale", saved,
                 today=date(2026, 10, 18)) == {
        "date": "2026-10-18", "deal_id": "IMUS-02", "guessed_kind": "resale",
        "chosen_kind": "resale", "signs": "resale: clean title, updated tax, cash basis",
        "price_outcome": "kept",            # read 2,500,000, saved 2,500,000
        "floor_area_sqm_outcome": "added",  # not in the post: typed 60
        "lot_area_sqm_outcome": "changed",  # read 36, the seller said 50
    }


def row(guessed, chosen, price, floor, lot):
    return {"date": "2026-10-18", "deal_id": "X", "guessed_kind": guessed, "chosen_kind": chosen,
            "signs": "", "price_outcome": price, "floor_area_sqm_outcome": floor,
            "lot_area_sqm_outcome": lot}


def test_reader_scores(tmp_path):
    path = tmp_path / "paste_log.csv"
    assert reader_scores(path) == []  # nothing pasted yet

    log_entries(path, [row("resale", "resale", "kept", "added", "kept"),
                       row("pasalo", "pasalo", "kept", "kept", "kept")])
    log_entries(path, [row("new", "resale", "changed", "added", "missing"),
                       row("unsure", "new", "kept", "kept", "missing")])

    assert len(path.read_text(encoding="utf-8").splitlines()) == 5  # one header, 4 rows
    # Kind right 2 of 4 (resale, pasalo); unsure once.
    # Price found 4 times (kept 3); floor area found 2 times (kept 2); lot area found 2 (kept 2)
    assert reader_scores(path) == [
        "Kind: right 2 of 4 (50%), unsure on 1",
        "Price: found in 4 of 4, kept as read 3 of 4",
        "Floor area: found in 2 of 4, kept as read 2 of 2",
        "Lot area: found in 2 of 4, kept as read 2 of 2",
    ]
