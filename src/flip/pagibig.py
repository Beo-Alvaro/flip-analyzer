"""Import Pag-IBIG's official auction lists (PDF) into the market scan data.

Pag-IBIG publishes each auction batch ("tranche") as a PDF on
www.pagibigfund.gov.ph under Properties for sale; Cavite is in the NCR
branch tranches. Download the current one in your browser, then run:

    python -m flip.pagibig LIST.pdf --into data/market/cavite_listings.csv

Every house in the chosen province (default Cavite) is added as a
foreclosed listing with its minimum bid, floor and lot area, and whether
it is occupied. Lots and condominiums are skipped. A property already in
the file (same Pag-IBIG property number) is replaced by the official row.
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
    with path.open("w", encoding="utf-8", newline="") as f:
        if notes:
            f.write("\n".join(notes) + "\n")
        merged.to_csv(f, index=False)
    return len(imported) - replaced, replaced


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import a Pag-IBIG auction list (PDF).")
    parser.add_argument("pdf", help="the auction list downloaded from pagibigfund.gov.ph")
    parser.add_argument("--province", default="Cavite")
    parser.add_argument("--into", default="data/market/cavite_listings.csv",
                        help="listings CSV to add to (default: data/market/cavite_listings.csv)")
    args = parser.parse_args()

    rows, first_text = read_tables(args.pdf)
    tranche, listed = list_details(first_text)
    imported = import_rows(rows, args.province, tranche, listed)
    if imported.empty:
        sys.exit(f"No {args.province} houses found in {args.pdf}. Is it a Pag-IBIG auction list?")
    added, replaced = merge_into(args.into, imported)
    occupied = int((imported["occupancy"] == "occupied").sum())
    print(f"{tranche or 'List'} ({listed or 'date not found'}): {len(imported)} {args.province} "
          f"houses ({occupied} occupied, {len(imported) - occupied} not). "
          f"{added} new, {replaced} replaced in {args.into}")
