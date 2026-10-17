"""Analyze a house: the verdict, both ROIs, scenarios, and the max offer.

Every number comes from the same tested code as the terminal report and the
Excel export. This page only reads your workbook; what-if changes apply on
screen and in the downloaded report, never to the file.
"""

import dataclasses
import math
import tempfile

import pandas as pd
import streamlit as st

from flip.batch import analyze_deals, deal_inputs, worst_months
from flip.charts import cost_chart, scenario_chart, sensitivity_chart
from flip.comps import suggested_arv
from flip.decision import add_verdicts, checklist_status, sensitivity
from flip.export import export_inputs
from flip.inputs import SAMPLE_BANNER, InputError, load_excel_inputs
from flip.scenarios import run_scenarios
from flip.tables import build_deals
from flip.ui import load_inputs, pct, peso, pick_house, uploaded_workbook, workbook_path

# --- Where the deals come from (chosen in the sidebar) ---

path = workbook_path()
try:
    temp = uploaded_workbook()
    if temp is not None:
        inputs = load_excel_inputs(temp)
    elif path.exists():
        inputs = load_inputs(str(path), path.stat().st_mtime)
    else:
        st.title("Flip Deal Analyzer")
        st.info(f"No workbook at `{path}`. Create one with `python -m flip.template`, "
                "or upload one in the sidebar.")
        st.stop()
except InputError as error:
    st.title("Flip Deal Analyzer")
    st.error("Your workbook has some problems to fix first:")
    st.code(str(error), language=None)
    st.stop()

settings = inputs.settings
with st.sidebar:
    st.subheader("Your criteria")
    st.caption("From the Settings sheet")
    st.markdown(
        f"- Safe account: **{settings.safe_rate:.1%}** a year\n"
        f"- Minimum profit: **{peso(settings.min_profit)}**\n"
        f"- Minimum yearly cash-on-cash: **{settings.min_yearly_return:.0%}**\n"
        f"- Price at or below the Stress max offer: "
        f"**{'yes' if settings.price_within_stress_max_offer else 'no'}**")

st.title("Flip Deal Analyzer")
if inputs.sample:
    st.warning(SAMPLE_BANNER, icon=":material/warning:")

# --- Pick a house, try what-ifs ---

houses = inputs.properties
deal_id = pick_house(houses, key="house")
if temp is None:
    st.page_link("views/edit.py", label="Edit this house: costs, loans, comps, checklist",
                 icon=":material/edit:")
house = houses[houses["deal_id"] == deal_id].iloc[0]


def number(value, default=0.0):
    return default if value is None or pd.isna(value) else float(value)


with st.expander("What-if: try different numbers (not saved to your workbook)"):
    a, b, c = st.columns(3)
    price = a.number_input("Purchase price (PHP)", min_value=0.0, step=10_000.0, format="%.0f",
                           value=number(house["purchase_price"]), key=f"price_{deal_id}")
    arv = b.number_input("Sale price after repair, ARV (PHP)", min_value=0.0, step=10_000.0,
                         format="%.0f", value=number(house["arv"]), key=f"arv_{deal_id}")
    monthly = c.number_input("Monthly holding cost (PHP)", min_value=0.0, step=500.0,
                             format="%.0f", value=number(house["monthly_holding_cost"]),
                             key=f"monthly_{deal_id}")
    a, b, c = st.columns(3)
    months = a.number_input("Holding months (likely)", min_value=0.0, step=1.0, format="%.0f",
                            value=number(house["holding_months"]), key=f"months_{deal_id}")
    worst_default = house.get("holding_months_worst")
    worst = b.number_input("Worst-case months (blank = +4 in Stress)", min_value=0.0, step=1.0,
                           format="%.0f", key=f"worst_{deal_id}",
                           value=None if worst_default is None or pd.isna(worst_default)
                           else float(worst_default))
    contingency = c.number_input("Contingency (% of renovation)", min_value=0.0,
                                 max_value=100.0, step=1.0, format="%.0f",
                                 value=number(house.get("contingency_rate")) * 100,
                                 key=f"contingency_{deal_id}")

what_if = {
    "purchase_price": price, "arv": arv, "monthly_holding_cost": monthly,
    "holding_months": months, "contingency_rate": contingency / 100,
    "holding_months_worst": math.nan if worst is None else worst,
}
properties = houses.copy()
row = properties["deal_id"] == deal_id
blank_means = {"contingency_rate": 0.0}  # a blank cell and the form's 0% are the same
changed = False
for column, value in what_if.items():
    old = properties.loc[row, column].iloc[0] if column in properties else math.nan
    if pd.isna(old):
        old = blank_means.get(column, math.nan)
    if pd.isna(old) != pd.isna(value) or (not pd.isna(old) and abs(float(old) - value) > 1e-9):
        changed = True
    properties[column] = properties[column].astype(float) if column in properties else math.nan
    properties.loc[row, column] = value
inputs = dataclasses.replace(inputs, properties=properties)
house = properties[row].iloc[0]
if changed:
    st.info("What-if numbers in use for this house. Your workbook is unchanged; the "
            "downloaded report includes them.", icon=":material/science:")

# --- Analyze this house ---

deals = build_deals(inputs.properties, inputs.renovations, inputs.loan_offers, inputs.other_costs)
analyzed = add_verdicts(analyze_deals(deals[deals["deal_id"] == deal_id], settings.safe_rate),
                        settings, inputs.checklist)
offer = st.radio("Loan offer", list(analyzed["offer"]), horizontal=True, key=f"offer_{deal_id}")
o = analyzed[analyzed["offer"] == offer].iloc[0]

verdict, _, checklist_note = o["verdict"].partition(" | ")
if verdict.startswith("Meets"):
    st.success(f"**Meets your criteria.** Checked against your Settings; it is not advice "
               "to buy.", icon=":material/check_circle:")
else:
    reasons = verdict.removeprefix("Fails: ").split("; ")
    st.error("**Fails your criteria** (checked against your Settings; not advice):\n\n"
             + "\n".join(f"- {r}" for r in reasons), icon=":material/cancel:")

cols = st.columns(3)
cols[0].metric("Net profit", peso(o["net_profit"]))
cols[1].metric("ROI on total cost", pct(o["roi_on_total_cost"]),
               help="Net profit / total cost. Is this a good deal?")
cols[2].metric("Cash-on-cash ROI", pct(o["cash_on_cash_roi"]),
               help="Net profit / your own cash. Is this a good use of my money?")
cols = st.columns(3)
cols[0].metric("Yearly cash-on-cash ROI", pct(o["yearly_cash_on_cash_roi"]),
               help="Cash-on-cash ROI x 12 / holding months")
cols[1].metric(f"vs {settings.safe_rate:.0%} safe account", f"{o['profit_vs_safe']:+,.0f}",
               help="Net profit minus what your cash would earn safely over the same months")
cols[2].metric("Stress profit", peso(o["stress_net_profit"]))
cols = st.columns(3)
cols[0].metric("Max offer (Stress)", peso(o["max_offer_stress"]),
               help="Highest price that still breaks even if the Stress scenario happens")
cols[1].metric("Break-even sale price", peso(o["break_even_arv"]))
cols[2].metric("Break-even purchase price", peso(o["break_even_price"]))

# --- Charts, each with its numbers underneath ---

theme = getattr(st.context, "theme", None)
dark = bool(theme is not None and theme.type == "dark")
inputs_o = deal_inputs(o)
scenarios = run_scenarios(inputs_o, worst_months(o))
scenario_table = pd.DataFrame({"scenario": list(scenarios),
                               "net_profit": [r["net_profit"] for r in scenarios.values()]})
table = sensitivity(inputs_o)

left, right = st.columns(2)
with left:
    st.subheader("If things go wrong")
    st.caption("Net profit as planned (Base), somewhat worse, and badly worse (Stress)")
    st.altair_chart(scenario_chart(scenario_table, dark), width="stretch", height=320)
    with st.expander("See the numbers"):
        st.dataframe(scenario_table.assign(net_profit=scenario_table["net_profit"].map(peso)),
                     hide_index=True)
with right:
    st.subheader("What matters most")
    st.caption("Profit when each input is 10% lower or higher; the dark line is the plan")
    st.altair_chart(sensitivity_chart(table, o["net_profit"], dark), width="stretch",
                    height=320)
    with st.expander("See the numbers"):
        st.dataframe(table.assign(**{c: table[c].map(peso) for c in
                                     ["profit_if_lower", "profit_if_higher", "swing"]}),
                     hide_index=True)

costs = pd.DataFrame({
    "cost": ["Acquisition", "Renovation", "Contingency", "Other costs", "Interest",
             "Loan fees", "Holding", "Selling", "Income tax"],
    "amount": [o["acquisition"], o["renovation_cost"], o["contingency"], o["other_costs"],
               o["interest"], o["loan_fees"], o["holding"], o["selling"], o["income_tax"]],
})
st.subheader("Where the money goes, on top of the price")
st.caption(f"Price paid {peso(o['purchase'])}; total cost {peso(o['total_cost'])}")
st.altair_chart(cost_chart(costs, dark), width="stretch",
                height=60 + 32 * int((costs["amount"] > 0).sum()))
with st.expander("See the numbers"):
    st.dataframe(costs.assign(amount=costs["amount"].map(peso)), hide_index=True)

# --- Loan offers side by side ---

st.subheader("Loan offers compared")
st.dataframe(pd.DataFrame({
    "Offer": analyzed["offer"],
    "Net profit": analyzed["net_profit"].map(peso),
    "Cash invested": analyzed["cash_invested"].map(peso),
    "ROI on total cost": analyzed["roi_on_total_cost"].map(pct),
    "Cash-on-cash ROI": analyzed["cash_on_cash_roi"].map(pct),
    "Yearly cash-on-cash": analyzed["yearly_cash_on_cash_roi"].map(pct),
    "Stress profit": analyzed["stress_net_profit"].map(peso),
    "Max offer (Stress)": analyzed["max_offer_stress"].map(peso),
    "Verdict": analyzed["verdict"].map(lambda v: v.partition(" | ")[0]),
}), hide_index=True)

# --- Sale price check against comps ---

if inputs.comps is not None and not inputs.comps.empty:
    st.subheader("Is the sale price realistic?")
    s = suggested_arv(inputs.properties, inputs.comps).set_index("deal_id").loc[deal_id]
    cols = st.columns(4)
    cols[0].metric("Your ARV", peso(house["arv"]))
    cols[1].metric("Suggested ARV", peso(s["suggested_arv"]),
                   help=f"Median of {s['comps_used']} resale comps per sqm x floor area"
                        + ("" if pd.isna(s["arv_low"]) else
                           f"; range {peso(s['arv_low'])} to {peso(s['arv_high'])}"))
    cols[2].metric("New-unit ceiling", peso(s["new_unit_ceiling"]))
    cols[3].metric("Foreclosed floor", peso(s["foreclosed_floor"]))
    for warning in s["warnings"]:
        st.warning(warning, icon=":material/warning:")
    with st.expander("Comps for this house"):
        st.dataframe(inputs.comps[inputs.comps["deal_id"] == deal_id], hide_index=True)

# --- Costs and checklist ---

left, right = st.columns(2)
with left:
    st.subheader("Renovation and other costs")
    items = inputs.renovations[inputs.renovations["deal_id"] == deal_id][["item", "cost"]]
    if o["contingency"] > 0:
        items = pd.concat([items, pd.DataFrame(
            {"item": [f"Contingency ({house['contingency_rate']:.0%})"],
             "cost": [o["contingency"]]})])
    if inputs.other_costs is not None:
        items = pd.concat([items, inputs.other_costs[
            inputs.other_costs["deal_id"] == deal_id][["item", "cost"]]])
    st.dataframe(items.assign(cost=items["cost"].map(peso)), hide_index=True)
with right:
    st.subheader("Due-diligence checklist")
    if inputs.checklist is None:
        st.caption("No Checklist sheet in this workbook.")
    else:
        c = checklist_status(deal_id, inputs.checklist)
        mine = inputs.checklist[inputs.checklist["deal_id"] == deal_id]
        if not c["started"]:
            st.caption("Not started: add this house's items on the Checklist sheet.")
        else:
            st.caption(f"{c['done']} done, {c['open']} open, {len(c['issues'])} issue(s)")
            st.dataframe(mine[[col for col in ["item", "status", "note"] if col in mine]]
                         .fillna(""), hide_index=True)

# --- Download the full report ---

with st.sidebar:
    st.subheader("Excel report")
    with tempfile.TemporaryDirectory() as folder:
        report = export_inputs(inputs, folder)
        st.download_button("Download the Excel report", report.read_bytes(),
                           file_name=report.name, icon=":material/download:",
                           mime="application/vnd.openxmlformats-officedocument."
                                "spreadsheetml.sheet")
    st.caption("All houses, with any what-if numbers shown here.")
