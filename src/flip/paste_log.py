"""Keep score of how well the listing reader (flip.listing_text) guesses.

Each comp you add from a pasted post adds one row to a small CSV next to your
workbook (data/paste_log.csv, kept out of git): what the reader guessed and
what you saved, for the kind, price, floor area, and lot area. The pasted text
is never stored. reader_scores() turns the rows into plain sentences.

Outcomes per number:
    kept     the reader found it and you saved it unchanged
    changed  the reader found it and you saved something else
    added    the reader found nothing and you typed it in
    missing  neither the post nor you had it
"""

import csv
from datetime import date
from pathlib import Path

import pandas as pd

FIELDS = {"price": "Price", "floor_area_sqm": "Floor area", "lot_area_sqm": "Lot area"}
COLUMNS = (["date", "deal_id", "guessed_kind", "chosen_kind", "signs"]
           + [f"{field}_outcome" for field in FIELDS])


def _blank(value) -> bool:
    return value is None or bool(pd.isna(value))


def outcome(found, saved) -> str:
    if _blank(found):
        return "missing" if _blank(saved) else "added"
    if _blank(saved):
        return "changed"
    return "kept" if abs(float(found) - float(saved)) < 0.5 else "changed"


def entry(deal_id, found: dict, suggested: dict, chosen_kind: str, saved: dict,
          today: date | None = None) -> dict:
    """One log row. found: from read_listing(); suggested: from suggested_comp();
    saved: the comp row that was saved."""
    return {
        "date": (today or date.today()).isoformat(), "deal_id": deal_id,
        "guessed_kind": found["kind"] or "unsure", "chosen_kind": chosen_kind,
        "signs": "; ".join(f"{kind}: {', '.join(phrases)}"
                           for kind, phrases in found["signs"].items()),
        **{f"{field}_outcome": outcome(suggested.get(field), saved.get(field))
           for field in FIELDS},
    }


def log_entries(path, entries: list[dict]) -> None:
    """Append rows to the log, creating it with a header the first time."""
    path = Path(path)
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            writer.writeheader()
        writer.writerows(entries)


def reader_scores(path) -> list[str]:
    """How the reader has done so far, as short sentences (none before the first row)."""
    path = Path(path)
    if not path.exists():
        return []
    log = pd.read_csv(path, dtype=str).fillna("")
    if log.empty:
        return []
    n = len(log)
    right = int((log["guessed_kind"] == log["chosen_kind"]).sum())
    unsure = int((log["guessed_kind"] == "unsure").sum())
    lines = [f"Kind: right {right} of {n} ({right / n:.0%})"
             + (f", unsure on {unsure}" if unsure else "")]
    for field, name in FIELDS.items():
        outcomes = log[f"{field}_outcome"]
        found = int(outcomes.isin(["kept", "changed"]).sum())
        kept = int((outcomes == "kept").sum())
        lines.append(f"{name}: found in {found} of {n}"
                     + (f", kept as read {kept} of {found}" if found else ""))
    return lines
