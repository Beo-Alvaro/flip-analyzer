"""Deals stored as separate tables: properties, renovation items, loan offers.

    properties:   one row per house (price, ARV, holding, zonal value)
    renovations:  one row per renovation item; a house can have many
    loan_offers:  one row per loan offer; a house can have several

build_deals() combines them into one row per house and loan offer, and
batch.analyze_deals() analyzes those rows with analyze().

Run `python -m flip.tables` to print the report for the sample tables.
"""

import argparse
import inspect

import pandas as pd

from flip.analyzer import analyze
from flip.batch import analyze_deals, deal_inputs
from flip.decision import Settings, add_verdicts, checklist_status, sensitivity

LOAN_COLUMNS = ["loan_ratio", "annual_interest_rate", "loan_fee_rate"]
DEFAULT_TERMS = "default terms"

# analyze()'s default inputs, e.g. {"loan_ratio": 0.70, ...}
ANALYZE_DEFAULTS = {
    name: p.default
    for name, p in inspect.signature(analyze).parameters.items()
    if p.default is not inspect.Parameter.empty
}


def check_deal_ids(properties: pd.DataFrame, table: pd.DataFrame, table_name: str) -> None:
    """Stop with an error if a table mentions a deal_id that isn't a property.

    Without this, a typo like SAMPLE-1 instead of SAMPLE-01 would make that
    row silently disappear when the tables are combined.
    """
    unknown = sorted(set(table["deal_id"]) - set(properties["deal_id"]))
    if unknown:
        raise ValueError(f"{table_name} has deal_id not found in properties: {', '.join(unknown)}")


def build_deals(properties: pd.DataFrame, renovations: pd.DataFrame,
                loan_offers: pd.DataFrame) -> pd.DataFrame:
    """Combine the three tables into one row per house and loan offer."""
    repeated = sorted(set(properties["deal_id"][properties["deal_id"].duplicated()]))
    if repeated:
        raise ValueError(f"properties lists a deal_id more than once: {', '.join(repeated)}")
    check_deal_ids(properties, renovations, "renovations")
    check_deal_ids(properties, loan_offers, "loan_offers")

    # 1. Add up each house's renovation items. A house with no items gets 0.
    totals = (
        renovations.groupby("deal_id")["cost"].sum()
        .reset_index().rename(columns={"cost": "renovation_cost"})
    )
    deals = properties.merge(totals, on="deal_id", how="left")
    deals["renovation_cost"] = deals["renovation_cost"].fillna(0)

    # 2. Pair each house with each of its loan offers: 3 offers = 3 rows.
    #    how="left" keeps houses with no offers; they get analyze()'s default
    #    loan terms, labeled so they are never mistaken for a real offer.
    deals = deals.merge(loan_offers, on="deal_id", how="left")
    no_offer = deals["offer"].isna()
    deals.loc[no_offer, "offer"] = DEFAULT_TERMS
    for column in LOAN_COLUMNS:
        deals.loc[no_offer, column] = ANALYZE_DEFAULTS[column]
    return deals


def print_report(properties: pd.DataFrame, renovations: pd.DataFrame,
                 analyzed: pd.DataFrame, suggestions: pd.DataFrame | None = None,
                 settings: Settings | None = None,
                 checklist: pd.DataFrame | None = None) -> None:
    """Print each house's report: ARV check, renovation budget, loan offers
    side by side, verdict, what matters most, and checklist.

    suggestions (from comps.suggested_arv) adds the ARV check against comps.
    """
    settings = settings or Settings()
    for _, house in properties.iterrows():
        deal_id = house["deal_id"]
        print(f"{deal_id}  {house.get('description', '')}")

        if suggestions is not None:
            print_arv_check(house, suggestions[suggestions["deal_id"] == deal_id].iloc[0])

        print("  Renovation budget")
        items = renovations[renovations["deal_id"] == deal_id]
        if items.empty:
            print("    (no items)")
        item_width = max([30] + [len(str(name)) + 2 for name in items["item"]])
        for _, item in items.iterrows():
            print(f"    {item['item']:<{item_width}}{item['cost']:>12,.0f}")
        print(f"    {'Total':<{item_width}}{items['cost'].sum():>12,.0f}")
        print()

        offers = analyzed[analyzed["deal_id"] == deal_id]
        width = max([15] + [len(str(name)) + 2 for name in offers["offer"]])

        def row(label, values):
            print(f"    {label:<24}" + "".join(f"{v:>{width}}" for v in values))

        def loan(o):
            if o["loan_ratio"] == 0:
                return "none"
            return f"{o['loan_ratio'] * 100:g}% at {o['annual_interest_rate'] * 100:g}%"

        def fee(o):
            return "-" if o["loan_ratio"] == 0 else f"{o['loan_fee_rate'] * 100:g}%"

        def pesos(value):
            return "none" if value is None or pd.isna(value) else f"{value:,.0f}"

        def percent(value):
            return "-" if value is None or pd.isna(value) else f"{value:.2%}"

        rows = [o for _, o in offers.iterrows()]
        print(f"  {'Loan offers':<26}" + "".join(f"{o['offer']:>{width}}" for o in rows))
        row("Loan", [loan(o) for o in rows])
        row("Loan fee", [fee(o) for o in rows])
        row("Net profit", [pesos(o["net_profit"]) for o in rows])
        row("Cash invested", [pesos(o["cash_invested"]) for o in rows])
        row("ROI on total cost", [percent(o["roi_on_total_cost"]) for o in rows])
        row("Cash-on-cash ROI", [percent(o["cash_on_cash_roi"]) for o in rows])
        row("Yearly ROI on total cost", [percent(o["yearly_roi_on_total_cost"]) for o in rows])
        row("Yearly cash-on-cash ROI", [percent(o["yearly_cash_on_cash_roi"]) for o in rows])
        row(f"vs {settings.safe_rate:.0%} safe account",
            [f"{o['profit_vs_safe']:+,.0f}" for o in rows])
        row("Stress profit", [pesos(o["stress_net_profit"]) for o in rows])
        row("Max offer (Stress)", [pesos(o["max_offer_stress"]) for o in rows])
        row("Break-even sale price", [pesos(o["break_even_arv"]) for o in rows])
        row("Break-even price", [pesos(o["break_even_price"]) for o in rows])
        print()

        if "verdict" in offers.columns:
            print("  Verdict (against your Settings)")
            for o in rows:
                print(f"    {o['offer']}: {o['verdict']}")
            print()

        if rows:
            first = rows[0]
            table = sensitivity(deal_inputs(first))
            print(f"  What matters most ({first['offer']}): profit if each input is "
                  "10% lower / higher")
            for _, s in table.iterrows():
                print(f"    {s['input']:<24}{s['profit_if_lower']:>14,.0f}"
                      f"{s['profit_if_higher']:>14,.0f}")
            print()

        if checklist is not None:
            c = checklist_status(deal_id, checklist)
            if not c["started"]:
                print("  Checklist: not started (add this house's items on the Checklist sheet)")
            else:
                print(f"  Checklist: {c['done']} done, {c['open']} open, "
                      f"{len(c['issues'])} issue(s)")
                for issue in c["issues"]:
                    print(f"    ! {issue}")
            print()


def print_arv_check(house: pd.Series, s: pd.Series) -> None:
    """Your ARV next to what the comps suggest, plus any warnings."""
    if pd.isna(s["suggested_arv"]):
        reason = ("no floor area" if s["comps_used"] and pd.isna(house.get("floor_area_sqm"))
                  else "no resale comps")
        line = f"  ARV: yours {house['arv']:,.0f} | suggested: none ({reason})"
    else:
        line = (f"  ARV: yours {house['arv']:,.0f} | suggested {s['suggested_arv']:,.0f} "
                f"(range {s['arv_low']:,.0f} to {s['arv_high']:,.0f}) from "
                f"{s['comps_used']} resale comps")
    print(line)
    extras = []
    if not pd.isna(s["new_unit_ceiling"]):
        extras.append(f"new-unit ceiling {s['new_unit_ceiling']:,.0f}")
    if not pd.isna(s["foreclosed_floor"]):
        extras.append(f"foreclosed floor {s['foreclosed_floor']:,.0f}")
    if extras:
        print("       " + " | ".join(extras))
    for warning in s["warnings"]:
        print(f"    ! {warning}")


if __name__ == "__main__":
    import sys

    from flip.comps import suggested_arv
    from flip.inputs import SAMPLE_BANNER, InputError, load_csv_inputs, load_excel_inputs

    parser = argparse.ArgumentParser(description="Renovation budgets and loan offer comparison.")
    parser.add_argument("--input", help="Excel input workbook (from python -m flip.template); "
                                        "replaces the CSV options")
    parser.add_argument("--properties", default="data/sample_properties.csv")
    parser.add_argument("--renovations", default="data/sample_renovations.csv")
    parser.add_argument("--loan-offers", default="data/sample_loan_offers.csv")
    parser.add_argument("--comps", help="optional comps CSV")
    args = parser.parse_args()

    try:
        if args.input:
            inputs = load_excel_inputs(args.input)
        else:
            inputs = load_csv_inputs(args.properties, args.renovations, args.loan_offers,
                                     args.comps)
    except InputError as error:
        sys.exit(str(error))

    if inputs.sample:
        print(SAMPLE_BANNER)
        print()
    analyzed = analyze_deals(build_deals(inputs.properties, inputs.renovations,
                                         inputs.loan_offers), inputs.settings.safe_rate)
    analyzed = add_verdicts(analyzed, inputs.settings, inputs.checklist)
    has_comps = inputs.comps is not None and not inputs.comps.empty
    suggestions = suggested_arv(inputs.properties, inputs.comps) if has_comps else None
    print_report(inputs.properties, inputs.renovations, analyzed, suggestions,
                 inputs.settings, inputs.checklist)
