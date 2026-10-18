"""Market scan: refresh Pag-IBIG listings, screen every foreclosure, start a deal.

The screen is flip.market's (like-for-like comparison, the 70% rule). Starting
a deal adds the house to your workbook through flip.workbook (checked, backed
up, never while Excel has it open).
"""

import re
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from flip.inputs import InputError, load_excel_inputs
from flip.market import LITTLE_ROOM, LOOK, NO_FAIR, scan, workbook_comps
from flip.pagibig import import_opa, merge_into
from flip.template import STANDARD_CHECKLIST
from flip.ui import DEFAULT_LISTINGS, peso, uploaded_workbook, workbook_path
from flip.workbook import WorkbookBusy, add_deal, backup, check_not_open, next_deal_id

COLLECTOR = Path(__file__).resolve().parents[3] / "docs" / "pagibig-opa-collector.js"
SHORT = {LOOK: "Worth a closer look", LITTLE_ROOM: "Little room", NO_FAIR: "No fair comparison"}


@st.cache_data(show_spinner="Screening every foreclosure...")
def cached_scan(path: str, modified: float, workbook: str, workbook_modified: float):
    """Every usable foreclosure compared, and how many of your comps were used;
    cached until either file changes."""
    comps = workbook_comps(workbook) if workbook else None
    return scan(path, comps)[2], 0 if comps is None else len(comps)


def text(value) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


def label(house) -> str:
    return (f"{text(house['city'])} · {text(house['subdivision']) or 'no subdivision'} · "
            f"{peso(house['price'])} · {house['floor_area_sqm']:g} sqm · "
            f"{text(house['occupancy']) or 'occupancy unknown'} · {SHORT[house['screen']]}")


def arv_hint(house) -> str:
    """What the scan compared the house with, as a starting point for the ARV."""
    benchmark, per_sqm = text(house["benchmark"]), house["benchmark_per_sqm"]
    if pd.isna(per_sqm):
        return "No comparison yet: collect resale comps from its subdivision."
    size = per_sqm * house["floor_area_sqm"]
    if "resale" in benchmark:
        return (f"Resale comparison ({benchmark}): {peso(per_sqm)} per sqm, about {peso(size)} "
                "for this size.")
    return (f"New units ({benchmark}) cost about {peso(per_sqm)} per sqm, {peso(size)} for "
            "this size. That is a ceiling, not an ARV: a renovated resale usually sells "
            "for less.")


st.title("Market scan")
st.caption("Every foreclosure in your listings file, compared with similar houses. Asking "
           "prices and minimum bids, not sale prices: a first filter, not advice.")

with st.sidebar:
    st.header("Market data")
    listings_path = Path(st.text_input("Listings file", value=DEFAULT_LISTINGS,
                                       key="listings_path"))
    use_comps = st.checkbox("Also use the comps in my workbook", value=True, key="use_comps",
                            help="Your resale and new comps (not the SAMPLE examples) count "
                                 "as listings in their house's city, so each comp is typed once.")

# --- 0. Refresh Pag-IBIG's listings ---

with st.expander("Refresh Pag-IBIG listings (once a month)", icon=":material/sync:"):
    st.markdown(
        "1. Open Pag-IBIG's [Online Public Auction]"
        "(https://www.pagibigfundservices.com/OnlinePublicAuction/) and choose the region "
        "and province (e.g. REGION 4-A, CAVITE).\n"
        "2. Press F12, open the **Console** tab, paste the snippet below, and press Enter. "
        "It reads every city's listings (about 10 minutes for Cavite) and downloads "
        "`opa_listings.json`. It only reads; it never bids or logs in.\n"
        "3. Upload that file here, or move it to `data/market/`, and press **Import**.")
    if COLLECTOR.exists():
        st.code(COLLECTOR.read_text(encoding="utf-8"), language="javascript", height=240)
    uploaded = st.file_uploader("Collector file", type=["json"], key="opa_upload")
    opa_path = st.text_input("...or read it from this path", key="opa_path",
                             value="data/market/opa_listings.json")
    if st.button("Import into the listings file", key="opa_import", icon=":material/download:"):
        source = Path(opa_path)
        if uploaded is not None:
            source = Path(tempfile.gettempdir()) / "flip_opa_listings.json"
            source.write_bytes(uploaded.getvalue())
        try:
            if not source.exists():
                raise FileNotFoundError(f"No collector file at {source}.")
            imported = import_opa(source)
            if imported.empty:
                raise ValueError(f"No houses found in {source.name}. Is it the collector's file?")
            check_not_open(listings_path)
            saved = backup(listings_path) if listings_path.exists() else None
            added, replaced = merge_into(listings_path, imported)
        except (OSError, ValueError, WorkbookBusy) as error:
            st.error(str(error))
        else:
            vacant = int((imported["occupancy"] == "unoccupied").sum())
            st.success(f"Imported {len(imported)} house{'s' * (len(imported) != 1)} "
                       f"({vacant} unoccupied): {added} new, {replaced} updated."
                       + (f" The previous file is backed up at `{saved}`." if saved else ""))

if not listings_path.exists():
    st.info(f"No listings file at `{listings_path}`.")
    st.stop()

# --- 1. Every foreclosure, screened ---

workbook = workbook_path()
comps_from = workbook if use_comps and uploaded_workbook() is None and workbook.exists() else None
try:
    compared, comps_used = cached_scan(str(listings_path), listings_path.stat().st_mtime,
                                       str(comps_from or ""),
                                       comps_from.stat().st_mtime if comps_from else 0.0)
except InputError:  # the workbook needs fixing first: scan without its comps
    compared, comps_used = cached_scan(str(listings_path), listings_path.stat().st_mtime, "", 0.0)
    st.caption("Your workbook has problems to fix (see Analyze a house), so its comps "
               "aren't used here yet.")
st.subheader("Foreclosures")
if comps_used:
    st.caption(f"Includes {comps_used} resale and new comps from your workbook.")
left, middle, right = st.columns(3)
cities = left.multiselect("City", sorted(compared["city"].dropna().unique()), key="cities",
                          placeholder="All cities")
screens = middle.multiselect("Screen result", list(SHORT), default=[LOOK, NO_FAIR],
                             format_func=SHORT.get, key="screens")
max_price = right.number_input("Highest price (PHP)", min_value=0.0, step=100_000.0,
                               format="%.0f", value=None, key="max_price")
left, middle, right = st.columns(3)
unoccupied = left.checkbox("Unoccupied only", value=True, key="unoccupied")
hide_closed = middle.checkbox(
    "Hide closed offers", value=True, key="hide_closed",
    help="Hides houses whose offer window has closed, using the closing day the collector "
         "saves. Rows imported without one stay listed.")
max_supply = right.number_input(
    "Max for sale in subdivision", min_value=1, step=1, value=None, key="max_supply",
    help="Foreclosures listed in the same subdivision. When you resell, they are your "
         "competition.")

view = compared[compared["screen"].isin(screens)]
if cities:
    view = view[view["city"].isin(cities)]
if max_price is not None:
    view = view[view["price"] <= max_price]
if unoccupied:
    view = view[view["occupancy"] == "unoccupied"]
if hide_closed and "offer_closes" in view:
    view = view[~((view["offer_closes"] != "") & (view["offer_closes"] < date.today().isoformat()))]
if max_supply is not None:
    view = view[~(view["foreclosures_in_subdivision"] > max_supply)]

st.caption(f"{len(view)} of {len(compared)} foreclosures match. Screen: at or below 70% of "
           "similar houses is worth a closer look; no fair comparison means collect resale "
           "prices from that subdivision first.")
shown = view.assign(screen=view["screen"].map(SHORT))
columns = {
    "city": "City", "subdivision": "Subdivision", "type": "Type", "price": "Price (PHP)",
    "price_basis": "Price basis", "floor_area_sqm": "Floor sqm", "price_per_sqm": "Per sqm",
    "screen": "Screen", "vs_benchmark": "vs benchmark", "benchmark": "Compared with",
    "foreclosures_in_subdivision": "For sale in subdivision", "occupancy": "Occupancy",
    "offer_window": "Offer window", "link": "Link",
}
st.dataframe(
    shown[[c for c in columns if c in shown]], hide_index=True, key="foreclosures",
    column_config={
        **{c: st.column_config.Column(name) for c, name in columns.items()},
        "price": st.column_config.NumberColumn("Price (PHP)", format="localized"),
        "price_per_sqm": st.column_config.NumberColumn("Per sqm", format="localized"),
        "vs_benchmark": st.column_config.NumberColumn("vs benchmark", format="percent"),
    })

# --- 2. Start a deal from one of them ---

st.subheader("Start a deal")
if view.empty:
    st.info("No foreclosures match the filters.")
    st.stop()

pick = st.selectbox("House", list(view.index), format_func=lambda i: label(view.loc[i]),
                    key="pick")
house = view.loc[pick]
path = workbook_path()
if uploaded_workbook() is not None:
    st.info("Starting a deal saves into the workbook at the path in the sidebar. Remove the "
            "uploaded workbook to use it.")
    st.stop()
if not path.exists():
    st.info(f"No workbook at `{path}`. Create one with `python -m flip.template`.")
    st.stop()
try:
    taken = list(load_excel_inputs(path).properties["deal_id"])
except InputError as error:
    st.error("Your workbook has some problems to fix first:")
    st.code(str(error), language=None)
    st.stop()

link = text(house["link"])
sale = re.search(r"\(([^)]+)\)", text(house["price_basis"]))
st.caption("Fill in what you know now; you can change everything later in the workbook. "
           "The ARV is your first guess: comps check it on the Analyze page.")
with st.form(f"start_{link}"):
    left, right = st.columns(2)
    deal_id = left.text_input("deal_id", value=next_deal_id(taken, house["city"]),
                              key=f"deal_id_{link}")
    description = right.text_input("Description", key=f"description_{link}", value=", ".join(p for p in [
        f"{text(house['subdivision'])} {text(house['type'])}".strip(),
        f"Pag-IBIG {sale.group(1)}" if sale else "", text(house["occupancy"])] if p))
    left, middle, right = st.columns(3)
    price = left.number_input("Purchase price (PHP)", min_value=0.0, step=10_000.0,
                              format="%.0f", value=float(house["price"]), key=f"price_{link}")
    arv = middle.number_input("ARV: sale price after repair (PHP)", min_value=0.0,
                              step=10_000.0, format="%.0f", value=None, help=arv_hint(house),
                             key=f"arv_{link}")
    monthly = right.number_input(
        "Monthly holding cost (PHP)", min_value=0.0, step=500.0, format="%.0f", value=None,
        help="Association dues, utilities, and property tax per month while you own it.",
        key=f"monthly_{link}")
    left, middle, right = st.columns(3)
    months = left.number_input("Months to sell (likely)", min_value=1, step=1, value=6,
                               key=f"months_{link}")
    worst = middle.number_input(
        "Worst-case months (optional)", min_value=1, step=1, value=None,
        help="If eviction or title transfer drags on. Blank: Stress adds 4 months.",
        key=f"worst_{link}")
    contingency = right.number_input("Contingency (% of renovation)", min_value=0.0,
                                     max_value=100.0, step=1.0, format="%.0f", value=10.0,
                                     key=f"contingency_{link}")
    checklist = st.checkbox(f"Add the {len(STANDARD_CHECKLIST)} standard checklist items "
                            "(title, occupants, dues...)", value=True, key=f"checklist_{link}")
    submitted = st.form_submit_button("Add to my workbook", icon=":material/add_home:",
                                      key="add_deal")

if submitted:
    missing = [name for name, value in [("ARV", arv), ("monthly holding cost", monthly)]
               if value is None]
    if missing:
        st.error(f"Please enter the {' and the '.join(missing)}.")
        st.stop()
    row = {
        "deal_id": deal_id.strip(), "description": description.strip(),
        "purchase_price": price, "arv": arv, "holding_months": months,
        "monthly_holding_cost": monthly, "floor_area_sqm": float(house["floor_area_sqm"]),
        "source_url": link, "contingency_rate": contingency / 100,
        "holding_months_worst": worst, "city": text(house["city"]),
        "barangay": text(house.get("barangay")), "subdivision": text(house["subdivision"]),
        "type": text(house["type"]),
    }
    try:
        saved = add_deal(path, row, STANDARD_CHECKLIST if checklist else ())
    except WorkbookBusy as error:
        st.error(str(error))
    except InputError as error:
        st.error("Not saved. The workbook would have these problems:")
        st.code(str(error), language=None)
    else:
        st.session_state["current_deal"] = row["deal_id"]  # the other pages start on it
        st.success(f"Added **{row['deal_id']}** to `{path}`. The previous version is backed "
                   f"up at `{saved}`. Next: add its comps, renovation items, and loan "
                   "offers, then analyze it.", icon=":material/check_circle:")
        st.page_link("views/edit.py", label="Fill in the rest", icon=":material/edit:")
