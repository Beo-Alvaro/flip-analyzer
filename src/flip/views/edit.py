"""Edit a house: its details, renovation items, other costs, loan offers,
comps, and checklist.

Everything is saved together with one button, through flip.workbook
(checked, backed up, never while Excel has it open). Only what you changed is
written, and other houses' rows are never touched.
"""

import pandas as pd
import streamlit as st

from flip.analyzer import TAX_MODES
from flip.comps import KINDS, suggested_arv
from flip.editing import NUMBERS, PERCENT, from_editor, to_editor
from flip.inputs import CHECKLIST_STATUSES, REQUIRED, SHEETS, InputError
from flip.template import STANDARD_CHECKLIST
from flip.ui import load_inputs, peso, pick_house, uploaded_workbook, workbook_path
from flip.workbook import WorkbookBusy, save_house

TABLES = [  # (table, tab title, what goes in it)
    ("renovations", "Renovations",
     "Repair and improvement items, one per row. Use contractor quotes when you have them."),
    ("other_costs", "Other costs",
     "Up-front costs that aren't renovation: eviction and legal, unpaid dues and taxes."),
    ("loan_offers", "Loan offers",
     "One row per way to pay. Add a row named Cash with 0s to compare paying cash. With no "
     "rows, the analysis uses a 70% loan at 9% a year with a 1% fee (default terms)."),
    ("comps", "Comps",
     "Comparable listings, one per row. Only resale comps set the suggested ARV; new units "
     "are the ceiling, foreclosures the floor, and pasalo prices are left out. Every comp "
     "needs its floor area. Dates as YYYY-MM-DD."),
    ("checklist", "Checklist",
     "What to verify before bidding: open, done, or issue (say what in the note)."),
]
HOUSE_NUMBERS = [  # (column, label, number format, step)
    ("purchase_price", "Purchase price (PHP)", "%.0f", 10_000.0),
    ("arv", "ARV: sale price after repair (PHP)", "%.0f", 10_000.0),
    ("monthly_holding_cost", "Monthly holding cost (PHP)", "%.0f", 500.0),
    ("holding_months", "Months to sell (likely)", "%.0f", 1.0),
    ("holding_months_worst", "Worst-case months (optional)", "%.0f", 1.0),
    ("floor_area_sqm", "Floor area (sqm)", "%.2f", 1.0),
    ("contingency_rate", "Contingency (% of renovation)", "%.1f", 1.0),
    ("zonal_value", "Zonal value (PHP, optional)", "%.0f", 10_000.0),
    ("fair_market_value", "Fair market value (PHP, optional)", "%.0f", 10_000.0),
    ("income_tax_rate", "Income tax (% of profit, business mode)", "%.1f", 1.0),
    ("vat_rate", "VAT (% of sale price, business mode)", "%.1f", 1.0),
]
HOUSE_TEXTS = [("description", "Description"), ("city", "City"), ("barangay", "Barangay"),
               ("subdivision", "Subdivision"), ("type", "Type"), ("source_url", "Listing link")]
LABELS = {
    "item": "Item", "cost": "Cost (PHP)", "offer": "Offer",
    "loan_ratio": "Loan (% of price)", "annual_interest_rate": "Interest (% a year)",
    "loan_fee_rate": "Loan fee (% of loan)", "price_discount_rate": "Price discount (%)",
    "subdivision": "Subdivision", "link": "Link", "type": "Type",
    "floor_area_sqm": "Floor area (sqm)", "lot_area_sqm": "Lot area (sqm)",
    "price": "Price (PHP)", "condition": "Condition", "date_seen": "Date seen",
    "kind": "Kind", "date_listed": "Date listed", "status": "Status", "note": "Note",
}


def column_config(table: str, columns) -> dict:
    """How each column is edited: numbers, a list to pick from, or text."""
    required = set(REQUIRED[table]) - {"deal_id"}
    config = {}
    for column in columns:
        label, needed = LABELS.get(column, column), column in required
        if column in PERCENT:
            config[column] = st.column_config.NumberColumn(
                label, min_value=0.0, max_value=100.0, format="%.2f", required=needed)
        elif column in NUMBERS:
            config[column] = st.column_config.NumberColumn(
                label, min_value=0.0, required=needed,
                format="localized" if column in ("cost", "price") else "%.2f")
        elif column == "kind":
            config[column] = st.column_config.SelectboxColumn(label, options=KINDS)
        elif column == "status":
            config[column] = st.column_config.SelectboxColumn(label, options=CHECKLIST_STATUSES)
        else:
            config[column] = st.column_config.TextColumn(label, required=needed)
    return config


st.title("Edit a house")
path = workbook_path()
if uploaded_workbook() is not None:
    st.info("An uploaded workbook is only read. To edit, remove the upload in the sidebar and "
            "use the workbook at the path below it.")
    st.stop()
if not path.exists():
    st.info(f"No workbook at `{path}`. Create one with `python -m flip.template`, or start a "
            "deal on Market scan.")
    st.stop()
try:
    inputs = load_inputs(str(path), path.stat().st_mtime)
except InputError as error:
    st.error("Your workbook has some problems to fix first (in Excel):")
    st.code(str(error), language=None)
    st.stop()

note = st.session_state.pop("edit_saved", None)
if note:
    st.success(note, icon=":material/check_circle:")

deal_id = pick_house(inputs.properties, key="edit_house")
st.page_link("views/analyze.py", label="Analyze this house", icon=":material/calculate:")
version = st.session_state.get("edit_version", 0)  # bumped after a save or discard


def key(name: str) -> str:
    return f"{name}_{deal_id}_{version}"


house_before = to_editor(inputs.properties, deal_id)  # one row; rates as percentages
row = house_before.iloc[0]
tabs = st.tabs(["House"] + [title for _, title, _ in TABLES])

# --- The house itself ---

house_now = {}
with tabs[0]:
    st.caption("The numbers the analysis starts from. Update the ARV once your comps are in.")
    columns = st.columns(3)
    fields = [f for f in HOUSE_NUMBERS if f[0] in row.index]
    for i, (column, label, number_format, step) in enumerate(fields):
        value = row[column]
        house_now[column] = columns[i % 3].number_input(
            label, min_value=0.0, max_value=100.0 if column in PERCENT else None, step=step,
            format=number_format, value=None if pd.isna(value) else float(value),
            key=key(column))
    if "tax_mode" in row.index:
        modes = ["", *TAX_MODES]
        current = row["tax_mode"] if row["tax_mode"] in modes else ""
        house_now["tax_mode"] = columns[len(fields) % 3].selectbox(
            "Tax mode", modes, index=modes.index(current), key=key("tax_mode"),
            format_func=lambda m: m or "capital asset (6% CGT; the default)")
    columns = st.columns(2)
    for i, (column, label) in enumerate(t for t in HOUSE_TEXTS if t[0] in row.index):
        house_now[column] = columns[i % 2].text_input(label, value=row[column] or "",
                                                      key=key(column))

# --- Its tables ---

before, now = {}, {}
for (table, title, explanation), tab in zip(TABLES, tabs[1:]):
    with tab:
        rows = getattr(inputs, table)
        if rows is None:
            st.info(f"Your workbook has no {SHEETS[table]} sheet. Add it with "
                    "`python -m flip.template --upgrade data/deals_input.xlsx`.")
            continue
        st.caption(explanation)
        shown = to_editor(rows, deal_id)
        before[table] = from_editor(shown, deal_id)
        if table == "checklist" and shown.empty:
            shown = pd.DataFrame({column: pd.Series([None] * len(STANDARD_CHECKLIST), dtype=object)
                                  for column in shown.columns})
            shown["item"], shown["status"] = STANDARD_CHECKLIST, "open"
            st.caption("The standard items are filled in for you; press Save to keep them.")
        edited = st.data_editor(shown, num_rows="dynamic", hide_index=True, width="stretch",
                                column_config=column_config(table, shown.columns), key=key(table))
        now[table] = from_editor(edited, deal_id)

        if table == "comps":  # the ARV check, live as you type
            usable = [c for c in now["comps"]
                      if isinstance(c.get("price"), (int, float))
                      and isinstance(c.get("floor_area_sqm"), (int, float))
                      and c["floor_area_sqm"] > 0]
            area = house_now.get("floor_area_sqm")
            if usable and area:
                check = suggested_arv(pd.DataFrame([{"deal_id": deal_id, "floor_area_sqm": area}]),
                                      pd.DataFrame(usable)).iloc[0]
                left, middle, right = st.columns(3)
                left.metric("Suggested ARV", peso(check["suggested_arv"]),
                            help=f"Median of {check['comps_used']} resale comps per sqm x "
                                 f"{area:g} sqm")
                middle.metric("Your ARV (House tab)", peso(house_now.get("arv")))
                right.metric("New-unit ceiling", peso(check["new_unit_ceiling"]))
                for warning in check["warnings"]:
                    st.warning(warning, icon=":material/warning:")

# --- Save ---

house_new = from_editor(pd.DataFrame([house_now]), deal_id)[0]
house_old = from_editor(house_before[list(house_now)], deal_id)[0]
changed_house = {c: v for c, v in house_new.items() if c != "deal_id" and v != house_old.get(c)}
titles = dict((table, title) for table, title, _ in TABLES)
changed_tables = [table for table in now if now[table] != before[table]]
changed = (["House"] if changed_house else []) + [titles[t] for t in changed_tables]

st.divider()
if changed:
    st.warning(f"Unsaved changes: {', '.join(changed)}", icon=":material/edit_note:")
buttons = st.container(horizontal=True)
save = buttons.button("Save changes", type="primary", disabled=not changed, key="save_house",
                      icon=":material/save:")
discard = buttons.button("Discard changes", disabled=not changed, key="discard_house")
if discard:
    st.session_state["edit_version"] = version + 1
    st.rerun()
if save:
    try:
        saved = save_house(path, deal_id, changed_house or None,
                           {SHEETS[t]: now[t] for t in changed_tables})
    except WorkbookBusy as error:
        st.error(str(error))
    except InputError as error:
        st.error("Not saved. The workbook would have these problems:")
        st.code(str(error), language=None)
    else:
        st.session_state["edit_saved"] = (f"Saved {deal_id} ({', '.join(changed)}). The previous "
                                          f"version is backed up at `{saved}`.")
        st.session_state["edit_version"] = version + 1
        st.rerun()
