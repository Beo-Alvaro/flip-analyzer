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
from flip.pagibig import import_opa, merge_into, remove_unlisted
from flip.template import STANDARD_CHECKLIST
from flip.ui import DEFAULT_LISTINGS, DEFAULT_LOAN, peso, uploaded_workbook, workbook_path
from flip.workbook import WorkbookBusy, add_deal, backup, check_not_open, next_deal_id

COLLECTOR = Path(__file__).resolve().parents[3] / "docs" / "pagibig-opa-collector.js"
SHORT = {LOOK: "Worth a closer look", LITTLE_ROOM: "Little room", NO_FAIR: "No fair comparison"}
CASH_OFFER = {"offer": "Cash", "loan_ratio": 0.0, "annual_interest_rate": 0.0, "loan_fee_rate": 0.0}


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


def listings(n) -> str:
    return f"{int(n)} listing" + ("s" if int(n) != 1 else "")


def arv_guide(house) -> list[str]:
    """What the house's price could be compared with, closest first: resale and
    new units of a similar size in its own subdivision, then the city's median
    (for new units only a maximum: they are often in pricier subdivisions)."""
    area, place = house["floor_area_sqm"], text(house["subdivision"]) or "this subdivision"
    lines = []
    for kind, words in [("resale", "the best guide, though asking prices run a little high"),
                        ("new", "a ceiling: a renovated used unit usually sells for less")]:
        n, per_sqm = house.get(f"subdivision_{kind}_listings"), house.get(f"subdivision_{kind}_per_sqm")
        if n and not pd.isna(per_sqm):
            name = "Resale" if kind == "resale" else "New units"
            lines.append(f"**{name} in {place}** ({listings(n)} of a similar size): "
                         f"{peso(per_sqm)} per sqm, about **{peso(per_sqm * area)}** for this "
                         f"size. That's {words}.")
    benchmark, per_sqm = text(house["benchmark"]), house["benchmark_per_sqm"]
    if benchmark.startswith("city") and not pd.isna(per_sqm):
        if "new" in benchmark:
            lines.append(f"New units elsewhere in the city: {peso(per_sqm)} per sqm (about "
                         f"{peso(per_sqm * area)}). Only a maximum, since they are often in "
                         "pricier subdivisions: **don't use it as the ARV**.")
        else:
            lines.append(f"Resale elsewhere in the city: {peso(per_sqm)} per sqm (about "
                         f"{peso(per_sqm * area)}), a rough guide.")
    return lines or ["No comparison yet: collect resale comps from its subdivision."]


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
            removed = remove_unlisted(listings_path, imported)  # sold or withdrawn since
        except (OSError, ValueError, WorkbookBusy) as error:
            st.error(str(error))
        else:
            vacant = int((imported["occupancy"] == "unoccupied").sum())
            st.success(f"Imported {len(imported)} house{'s' * (len(imported) != 1)} "
                       f"({vacant} unoccupied): {added} new, {replaced} updated."
                       + (f" {removed} no longer listed (sold or withdrawn) were removed."
                          if removed else "")
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
shown = view.assign(screen=view["screen"].map(SHORT),
                   price_per_sqm=view["price_per_sqm"].round(0))  # whole pesos
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
st.caption("**ARV guide**  \n" + "  \n".join(arv_guide(house)))
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
                              step=10_000.0, format="%.0f", value=None,
                              help="What it should sell for after renovation: see the ARV "
                                   "guide above.",
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
    cash = st.checkbox("Add a Cash offer (no loan)", value=True, key=f"cash_{link}",
                       help=f"Without any loan offer, the analysis assumes {DEFAULT_LOAN}. "
                            "Add your real loan offers on Edit a house.")
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
        saved = add_deal(path, row, STANDARD_CHECKLIST if checklist else (),
                         [CASH_OFFER] if cash else ())
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
