"""Save changes into the Excel input workbook, safely.

The web app writes your workbook only through this module. Every save:

    1. refuses while the workbook is open in Excel (Excel keeps a ~$ lock
       file next to it),
    2. writes the change to a copy and loads the copy with the same checks
       every report runs (flip.inputs), so a bad value never reaches your file,
    3. copies the current workbook into a backups folder next to it,
    4. then replaces the workbook with the checked copy.

Rows are added below the last used row, by column name, so the column order
in your workbook doesn't matter.
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from flip.inputs import InputError, load_excel_inputs


class WorkbookBusy(RuntimeError):
    """The file is open in Excel, so it can't be saved now."""


def check_not_open(path) -> None:
    """Raise WorkbookBusy if Excel has the file open (it keeps a ~$ lock file)."""
    path = Path(path)
    if path.with_name("~$" + path.name).exists():
        raise WorkbookBusy(f"{path.name} is open in Excel. Close it there, then try again.")


def backup(path, now: datetime | None = None) -> Path:
    """Copy a file into a backups folder next to it, named with the date and time."""
    path = Path(path)
    folder = path.parent / "backups"
    folder.mkdir(exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    target, n = folder / f"{path.stem}-{stamp}{path.suffix}", 1
    while target.exists():  # two saves in the same second
        n += 1
        target = folder / f"{path.stem}-{stamp}-{n}{path.suffix}"
    shutil.copy2(path, target)
    return target


def next_deal_id(existing, city) -> str:
    """The city in capitals and the next free number: IMUS-02 if IMUS-01 is taken."""
    base = re.sub(r"[^A-Z0-9]+", "-", str(city or "").upper()).strip("-") or "DEAL"
    taken = {str(d).strip().upper() for d in existing}
    n = 1
    while f"{base}-{n:02d}" in taken:
        n += 1
    return f"{base}-{n:02d}"


def _blank(value) -> bool:
    if isinstance(value, str):
        return value.strip() == ""
    return value is None or bool(pd.isna(value))


def _append(ws, rows: list[dict]) -> None:
    """Write rows below the sheet's last used row, matching keys to the header row."""
    headers = {cell.value: cell.column for cell in ws[1] if cell.value is not None}
    unknown = sorted({key for row in rows for key in row} - set(headers))
    if unknown:
        raise InputError(f"{ws.title} has no column {', '.join(unknown)}. Add it with "
                         "python -m flip.template --upgrade data/deals_input.xlsx")
    last = max((cell.row for row in ws.iter_rows(min_row=2) for cell in row
                if cell.value is not None), default=1)
    for offset, values in enumerate(rows, start=1):
        for key, value in values.items():
            if not _blank(value):
                ws.cell(row=last + offset, column=headers[key], value=value)


def save_changes(path, changes) -> Path:
    """Apply changes(openpyxl workbook), check the result, back up, and save.

    Returns the backup's path. If the checks fail, InputError explains why and
    the workbook is left as it was.
    """
    path = Path(path)
    check_not_open(path)
    wb = load_workbook(path)
    changes(wb)
    draft = path.with_name(f".saving-{path.name}")
    wb.save(draft)
    try:
        load_excel_inputs(draft)  # the same checks the reports and the app run
    except Exception:
        draft.unlink(missing_ok=True)
        raise
    saved = backup(path)
    try:
        os.replace(draft, path)
    except PermissionError as error:
        draft.unlink(missing_ok=True)
        raise WorkbookBusy(f"Can't save {path.name}: it is open in another program. "
                           "Close it, then try again.") from error
    return saved


def add_deal(path, house: dict, checklist_items=()) -> Path:
    """Add a house to the Properties sheet, plus its checklist items (status open).

    house: column name -> value, e.g. deal_id, purchase_price, arv... Returns
    the backup's path.
    """
    check_not_open(path)
    deal_id = str(house.get("deal_id") or "").strip()
    if not deal_id:
        raise InputError("Please fix these in your input:\n  - deal_id is blank")
    current = load_excel_inputs(path)  # a workbook with problems is fixed first
    if deal_id.upper() in {str(d).strip().upper() for d in current.properties["deal_id"]}:
        raise InputError(f"Please fix these in your input:\n  - {deal_id} is already on the "
                         "Properties sheet; choose another deal_id")

    def changes(wb):
        _append(wb["Properties"], [{**house, "deal_id": deal_id}])
        if checklist_items and "Checklist" in wb.sheetnames:
            _append(wb["Checklist"], [{"deal_id": deal_id, "item": item, "status": "open"}
                                      for item in checklist_items])

    return save_changes(path, changes)
