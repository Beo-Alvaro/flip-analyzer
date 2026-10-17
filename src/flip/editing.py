"""Turn one house's workbook rows into what the Edit page shows, and back.

The page shows rates as percentages (9 for 9%) and dates as text
(2025-02-27); the workbook stores rates as fractions (0.09) and dates as
dates. to_editor() and from_editor() convert both ways, so a table nobody
touched round-trips to exactly the same rows and is not saved again.
"""

import re
from datetime import date, datetime

import pandas as pd

from flip.inputs import ABOVE_ZERO, NOT_NEGATIVE, RATES

PERCENT = RATES                     # shown as 9, stored as 0.09
DATES = ["date_seen", "date_listed"]  # shown as 2025-02-27 text
NUMBERS = set(RATES + NOT_NEGATIVE + ABOVE_ZERO)
CHOICES = ["kind", "status"]        # picked from a list; the checks ignore case
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _blank(value) -> bool:
    if isinstance(value, str):
        return not value.strip()
    return value is None or bool(pd.isna(value))


def _date_text(value):
    if _blank(value):
        return None
    if isinstance(value, (datetime, date)):  # pandas Timestamps are datetimes too
        return value.strftime("%Y-%m-%d")
    return str(value)


def to_editor(table: pd.DataFrame | None, deal_id: str) -> pd.DataFrame:
    """One house's rows, without the deal_id column, ready for st.data_editor."""
    if table is None:
        return pd.DataFrame()
    ids = table["deal_id"].astype(str).str.strip().str.upper()
    shown = table[ids == str(deal_id).strip().upper()].drop(columns="deal_id")
    shown = shown.reset_index(drop=True).copy()
    for column in shown.columns:
        values = shown[column]
        if column in PERCENT:
            shown[column] = (values.astype(float) * 100).round(6)
        elif column in NUMBERS:
            shown[column] = values.astype(float)
        elif column in DATES:
            shown[column] = pd.Series([_date_text(v) for v in values], dtype=object)
        else:  # text, even when every cell is blank (pandas would read it as numbers)
            text = [None if _blank(v) else str(v).strip() for v in values]
            if column in CHOICES:
                text = [t if t is None else t.lower() for t in text]
            shown[column] = pd.Series(text, dtype=object)
    return shown


def from_editor(edited: pd.DataFrame, deal_id: str) -> list[dict]:
    """The rows to save: blank rows dropped, rates back to fractions, dates
    typed as YYYY-MM-DD back to dates, and the deal_id added."""
    rows = []
    for _, row in edited.iterrows():
        values = {}
        for column, value in row.items():
            if _blank(value):
                value = None
            elif column in PERCENT:
                value = round(float(value) / 100, 8)
            elif column in NUMBERS:
                value = float(value)
                value = int(value) if value.is_integer() else value
            elif column in DATES and ISO_DATE.match(str(value).strip()):
                value = date.fromisoformat(str(value).strip())
            elif isinstance(value, str):
                value = value.strip()
            values[column] = value
        if any(v is not None for v in values.values()):
            rows.append({"deal_id": deal_id, **values})
    return rows
