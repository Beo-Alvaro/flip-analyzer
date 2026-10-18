"""Import Pag-IBIG's official listings into the market scan data.

Two formats:

1. The Online Public Auction site (current). Pag-IBIG now lists properties
   only at https://www.pagibigfundservices.com/OnlinePublicAuction/. The
   browser snippet in docs/pagibig-opa-collector.js reads every listing for
   a province (all three tabs: 1st auction, 2nd auction, negotiated sale)
   and saves them as a JSON file. Then:

       python -m flip.pagibig data/market/opa_cavite.json

2. Auction list PDFs (older; Pag-IBIG published these until about 2024):

       python -m flip.pagibig LIST.pdf

Every house in the province (default Cavite) is added to
data/market/cavite_listings.csv as a foreclosed listing with its price,
floor and lot area, and whether it is occupied. Lots, condos, and parking
slots are skipped. A property already in the file (same Pag-IBIG property
number) is replaced by the new row. After a collector import, earlier
auction rows for the same cities that are no longer listed (sold or
withdrawn) are removed.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from flip.batch import file_notes, load_deals

PROPERTY_NUMBER = re.compile(r"\b(\d{15})\b")
NUMBER = re.compile(r"\d[\d,]*\.\d+|\d[\d,]*")
SKIP_TYPES = ("LOT ONLY", "CONDOMINIUM", "COMMERCIAL")
TYPES = {  # as written in the list -> as used in the market data
    "TOWNHOUSE": "townhouse", "TOWN HOUSE": "townhouse", "ROWHOUSE": "rowhouse",
    "ROW HOUSE": "rowhouse", "SINGLE ATTACHED": "single attached",
    "SINGLE DETACHED": "single detached", "DUPLEX": "duplex", "QUADRUPLEX": "quadruplex",
}
CITY_NAMES = {"Dasmariñas": "Dasmarinas", "Gen. Mariano Alvarez": "GMA",
              "General Mariano Alvarez": "GMA"}
ROMAN = re.compile(r"\b(?:I{2,3}|IV|VI{0,3}|IX|X)\b", re.IGNORECASE)


def _last_number(cell) -> float | None:
    """The last number in a cell (stray text from page stamps is ignored)."""
    found = NUMBER.findall(str(cell or ""))
    return float(found[-1].replace(",", "")) if found else None


def _location_text(cell) -> str:
    """The address, starting from the first line that looks like one ("X - Y")."""
    lines = str(cell or "").splitlines()
    for i, line in enumerate(lines):
        if " - " in line:
            return " ".join(lines[i:]).strip()
    return " ".join(lines).strip()


def _city(name: str) -> str:
    name = name.strip()
    name = re.sub(r"^City of ", "", name)
    if name != "Cavite City":
        name = re.sub(r" City$", "", name)
    return CITY_NAMES.get(name, name)


def parse_row(cells: list) -> dict | None:
    """One table row from the list -> one listing, or None if it isn't a house.

    Expected columns: item no., property number, location, type, title no.,
    lot area, floor area, minimum bid, appraisal date, required income, remarks.
    """
    if len(cells) < 11:
        return None
    number = PROPERTY_NUMBER.search(str(cells[1] or ""))
    if not number:
        return None  # header or section title row
    kind_text = " ".join(str(cells[3] or "").upper().split())
    if any(skip in kind_text for skip in SKIP_TYPES):
        return None
    house_type = next((v for k, v in TYPES.items() if k in kind_text), kind_text.lower())

    location = _location_text(cells[2])
    parts = [p.strip() for p in location.split(" - ")]
    place = [p.strip() for p in parts[-1].split(",")]
    barangay = re.sub(r"^Brgy\.?\s*", "", place[0]) if len(place) >= 3 else ""
    city = _city(place[-2]) if len(place) >= 2 else ""
    province = place[-1] if place else ""

    remarks = " ".join(str(cells[10] or "").split())
    if "UNOCCUPIED" in remarks.upper():
        occupancy = "unoccupied"
    elif "OCCUPIED" in remarks.upper():
        occupancy = "occupied"
    else:
        occupancy = ""

    return {
        "city": city,
        "province": province,
        "barangay": barangay,
        "subdivision": parts[0] if len(parts) > 1 else "",
        "type": house_type,
        "kind": "foreclosed",
        "kind_reason": "Pag-IBIG",
        "price": _last_number(cells[7]),
        "price_basis": "minimum bid",
        "floor_area_sqm": _last_number(cells[6]),
        "lot_area_sqm": _last_number(cells[5]),
        "occupancy": occupancy,
        "notes": remarks,
        "link": f"pagibig:{number.group(1)}",
    }


OPA_SOURCE = "pagibigfundservices.com Online Public Auction"
OPA_SALES = {"1st auction": "minimum bid (1st auction)",
             "2nd auction": "minimum bid (2nd auction)",
             "negotiated sale": "selling price (negotiated sale)"}


def _opa_type(text: str) -> str | None:
    """OPA property type -> market type, or None for lots, condos, parking."""
    t = text.upper()
    if any(skip in t for skip in ("LOT ONLY", "CONDOMINIUM", "PARKING")):
        return None
    for start, name in [("TOWN", "townhouse"), ("ROW", "rowhouse"), ("DUPLEX", "duplex"),
                        ("DOUBLE ATTACHED", "double attached"),
                        ("SINGLE ATTACHED", "single attached"),
                        ("SINGLE DETACHED", "single detached"), ("QUADRUPLEX", "quadruplex")]:
        if t.startswith(start):
            return name
    return text.lower()


def parse_opa_card(card: dict) -> dict | None:
    """One Online Public Auction card (as saved by the collector snippet) ->
    one listing, or None if it isn't a house."""
    house_type = _opa_type(card.get("type", ""))
    if house_type is None or not PROPERTY_NUMBER.search(card.get("id", "")):
        return None
    # "CITY OF DASMARIÑAS" -> "Dasmariñas" -> "Dasmarinas"; "GEN. MARIANO ALVAREZ" -> "GMA"
    city = re.sub(r"^CITY OF ", "", card.get("city", "").strip().upper()).title()
    city = CITY_NAMES.get(city, city)
    occupancy = card.get("occupancy", "").lower()
    start = re.match(r"([A-Z][a-z]{2,3})\.? (\d{1,2}), (\d{4})", card.get("dates", ""))
    listed = ""
    if start:
        try:
            listed = pd.Timestamp(f"{start.group(1)} {start.group(2)}, {start.group(3)}").date().isoformat()
        except ValueError:
            pass
    sale = card.get("sale", "")
    return {
        "city": city,
        "barangay": "",
        # "BELVEDERE TOWNE II" -> "Belvedere Towne II" (title() alone gives "Ii")
        "subdivision": ROMAN.sub(lambda m: m.group(0).upper(), card.get("name", "").strip().title()),
        "type": house_type,
        "kind": "foreclosed",
        "kind_reason": "Pag-IBIG",
        "price": _last_number(card.get("price")),
        "price_basis": OPA_SALES.get(sale, "minimum bid"),
        "floor_area_sqm": _last_number(card.get("floor")),
        "lot_area_sqm": _last_number(card.get("lot")),
        "occupancy": "unoccupied" if occupancy.startswith("unoccupied") else
                     "occupied" if occupancy.startswith("occupied") else "",
        "date_listed": listed,
        "notes": f"{sale}; batch {card.get('batch', '')}; offers {card.get('dates', '')}".strip(),
        "link": f"pagibig:{card['id']}",
        "source": OPA_SOURCE,
        "collected": date.today().isoformat(),
    }


def import_opa(path) -> pd.DataFrame:
    """Read a JSON file saved by docs/pagibig-opa-collector.js."""
    import json

    cards = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(cards, dict):
        cards = cards.get("rows", [])
    return pd.DataFrame([p for p in (parse_opa_card(c) for c in cards) if p])


def read_tables(path) -> tuple[list[list], str]:
    """All table rows in the PDF, plus page 1's text (for the tranche and date)."""
    import pdfplumber

    rows = []
    with pdfplumber.open(path) as pdf:
        first_text = pdf.pages[0].extract_text() or ""
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend(table)
    return rows, first_text


def list_details(first_page_text: str) -> tuple[str, str]:
    """The tranche name (e.g. SPB 321) and the invitation date (YYYY-MM-DD)."""
    tranche = re.search(r"\b(SPB|OPA|NS)\s*\d+\b", first_page_text)
    found = re.search(r"\b([A-Z][a-z]+ \d{1,2}, \d{4})\b", first_page_text)
    listed = ""
    if found:
        try:
            listed = pd.Timestamp(found.group(1)).date().isoformat()
        except ValueError:
            pass
    return (tranche.group(0) if tranche else ""), listed


def import_rows(rows: list[list], province: str = "Cavite", tranche: str = "",
                listed: str = "") -> pd.DataFrame:
    """Turn table rows into market listings for one province."""
    parsed = [parse_row(r) for r in rows]
    houses = [p for p in parsed if p and p["province"].lower() == province.lower()]
    df = pd.DataFrame(houses)
    if df.empty:
        return df
    df["date_listed"] = listed
    df["source"] = f"pagibigfund.gov.ph {tranche}".strip()
    df["collected"] = date.today().isoformat()
    return df.drop(columns="province")


def merge_into(listings_path, imported: pd.DataFrame) -> tuple[int, int]:
    """Add imported rows to a listings CSV, replacing rows for the same
    Pag-IBIG property number. Returns (added, replaced)."""
    path = Path(listings_path)
    notes = file_notes(path) if path.exists() else []
    existing = load_deals(path) if path.exists() else pd.DataFrame()
    numbers = set(imported["link"].str.removeprefix("pagibig:"))

    def same_property(link) -> bool:
        found = PROPERTY_NUMBER.search(str(link))
        return bool(found and found.group(1) in numbers)

    keep = ~existing["link"].map(same_property) if not existing.empty else []
    replaced = int((~keep).sum()) if not existing.empty else 0
    merged = pd.concat([existing[keep] if not existing.empty else existing, imported],
                       ignore_index=True)
    _write(path, notes, merged)
    return len(imported) - replaced, replaced


def remove_unlisted(listings_path, imported: pd.DataFrame) -> int:
    """After importing a full Online Public Auction collection: remove earlier
    auction rows that are no longer listed (sold or withdrawn). Returns how
    many were removed.

    Only cities in the new collection are cleaned, so a collector run that
    stopped early can't wipe out the cities it never reached. Other sources'
    rows are never removed.
    """
    path = Path(listings_path)
    if imported.empty or not path.exists():
        return 0
    notes, existing = file_notes(path), load_deals(path)
    if existing.empty or "source" not in existing:
        return 0
    gone = ((existing["source"] == OPA_SOURCE) & existing["city"].isin(set(imported["city"]))
            & ~existing["link"].isin(set(imported["link"])))
    if gone.any():
        _write(path, notes, existing[~gone])
    return int(gone.sum())


def _write(path: Path, notes: list[str], listings: pd.DataFrame) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        if notes:
            f.write("\n".join(notes) + "\n")
        listings.to_csv(f, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Pag-IBIG listings (OPA JSON or PDF).")
    parser.add_argument("file", help="JSON saved by docs/pagibig-opa-collector.js, or an "
                                     "auction list PDF")
    parser.add_argument("--province", default="Cavite", help="for PDFs (default: Cavite)")
    parser.add_argument("--into", default="data/market/cavite_listings.csv",
                        help="listings CSV to add to (default: data/market/cavite_listings.csv)")
    args = parser.parse_args()

    if args.file.lower().endswith(".json"):
        imported, label = import_opa(args.file), "Online Public Auction"
    else:
        rows, first_text = read_tables(args.file)
        tranche, listed = list_details(first_text)
        imported = import_rows(rows, args.province, tranche, listed)
        label = f"{tranche or 'List'} ({listed or 'date not found'})"
    if imported.empty:
        sys.exit(f"No houses found in {args.file}. Is it a Pag-IBIG listing file?")
    added, replaced = merge_into(args.into, imported)
    removed = remove_unlisted(args.into, imported) if args.file.lower().endswith(".json") else 0
    occupied = int((imported["occupancy"] == "occupied").sum())
    print(f"{label}: {len(imported)} houses ({occupied} occupied, "
          f"{len(imported) - occupied} not). {added} new, {replaced} replaced in {args.into}"
          + (f"; {removed} no longer listed, removed" if removed else ""))
