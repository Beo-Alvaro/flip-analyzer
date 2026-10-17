"""Pieces shared by the web app's pages (src/flip/views)."""

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from flip.inputs import load_excel_inputs

DEFAULT_WORKBOOK = "data/deals_input.xlsx"
DEFAULT_LISTINGS = "data/market/cavite_listings.csv"


def peso(value) -> str:
    """Pesos with the sign first: -₱309,300."""
    if value is None or pd.isna(value):
        return "none"
    return f"-₱{-value:,.0f}" if round(value) < 0 else f"₱{abs(value):,.0f}"


def pct(value) -> str:
    return "-" if value is None or pd.isna(value) else f"{value:.2%}"


@st.cache_data(show_spinner=False)
def load_inputs(path: str, modified: float):
    """Load the workbook; cached until the file changes (its modified time)."""
    return load_excel_inputs(path)


def pick_house(properties: pd.DataFrame, key: str) -> str:
    """The House dropdown. It starts on the house you last picked on any page
    (or just started on Market scan), then remembers your choice."""
    ids = list(properties["deal_id"])
    names = dict(zip(ids, properties["description"] if "description" in properties else ids))
    current = st.session_state.get("current_deal")
    choice = st.selectbox(
        "House", ids, index=ids.index(current) if current in ids else 0, key=key,
        format_func=lambda d: f"{d}  ·  {'' if pd.isna(names.get(d)) else names.get(d)}")
    st.session_state["current_deal"] = choice
    return choice


def workbook_path() -> Path:
    """The workbook named in the sidebar."""
    return Path(st.session_state.get("path") or DEFAULT_WORKBOOK)


def uploaded_workbook() -> Path | None:
    """The workbook uploaded in the sidebar, saved to a temporary file, if any.
    An uploaded workbook is only read: saving goes to the path in the sidebar."""
    uploaded = st.session_state.get("upload")
    if uploaded is None:
        return None
    temp = Path(tempfile.gettempdir()) / "flip_uploaded_input.xlsx"
    temp.write_bytes(uploaded.getvalue())
    return temp
