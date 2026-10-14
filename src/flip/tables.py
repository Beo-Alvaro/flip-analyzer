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
from flip.batch import analyze_deals

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
                 analyzed: pd.DataFrame, suggestions: pd.DataFrame | None = None) -> None:
    """Print each house's renovation budget and its loan offers side by side.

    suggestions (from comps.suggested_arv) adds a line comparing your ARV
    with the ARV suggested by the house's comps.
    """
    for _, house in properties.iterrows():
        deal_id = house["deal_id"]
        print(f"{deal_id}  {house.get('description', '')}")

        if suggestions is not None:
            s = suggestions[suggestions["deal_id"] == deal_id].iloc[0]
            if pd.isna(s["suggested_arv"]):
                reason = "no comps" if s["comps_used"] == 0 else "no floor area"
                print(f"  ARV: yours {house['arv']:,.0f} | suggested: none ({reason})")
            else:
                print(f"  ARV: yours {house['arv']:,.0f} | suggested {s['suggested_arv']:,.0f} "
                      f"from {s['comps_used']} comps (median {s['median_price_per_sqm']:,.0f}/sqm)")

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
            print(f"    {label:<20}" + "".join(f"{v:>{width}}" for v in values))

        def loan(o):
            if o["loan_ratio"] == 0:
                return "none"
            return f"{o['loan_ratio'] * 100:g}% at {o['annual_interest_rate'] * 100:g}%"

        def fee(o):
            return "-" if o["loan_ratio"] == 0 else f"{o['loan_fee_rate'] * 100:g}%"

        def pesos(value):
            return "none" if pd.isna(value) else f"{value:,.0f}"

        rows = [o for _, o in offers.iterrows()]
        print(f"  {'Loan offers':<22}" + "".join(f"{o['offer']:>{width}}" for o in rows))
        row("Loan", [loan(o) for o in rows])
        row("Loan fee", [fee(o) for o in rows])
        row("Net profit", [pesos(o["net_profit"]) for o in rows])
        row("Cash invested", [pesos(o["cash_invested"]) for o in rows])
        row("ROI on total cost", [f"{o['roi_on_total_cost']:.2%}" for o in rows])
        row("Cash-on-cash ROI", [f"{o['cash_on_cash_roi']:.2%}" for o in rows])
        row("Stress profit", [pesos(o["stress_net_profit"]) for o in rows])
        row("Max offer (Stress)", [pesos(o["max_offer_stress"]) for o in rows])
        print()


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
                                         inputs.loan_offers))
    has_comps = inputs.comps is not None and not inputs.comps.empty
    suggestions = suggested_arv(inputs.properties, inputs.comps) if has_comps else None
    print_report(inputs.properties, inputs.renovations, analyzed, suggestions)
