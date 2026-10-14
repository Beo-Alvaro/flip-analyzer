"""Many deals at once: run analyze() on every row of a deals table.

Run `python -m flip.batch data/sample_deals.csv` to print the results.
"""

import argparse
import inspect

import pandas as pd

from flip.analyzer import analyze
from flip.scenarios import max_offer, run_scenarios

# Columns a deals file may use: one per analyze() input, read from its
# signature so this list never falls out of step with analyze().
INPUT_COLUMNS = list(inspect.signature(analyze).parameters)


def load_deals(path) -> pd.DataFrame:
    """Read a deals CSV. Lines starting with # are notes, like the SAMPLE label."""
    return pd.read_csv(path, comment="#")


def file_notes(path) -> list[str]:
    """The # note lines at the top of a deals file, e.g. the SAMPLE DATA label."""
    notes = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#"):
                break
            notes.append(line.rstrip("\n"))
    return notes


def deal_inputs(row: pd.Series) -> dict:
    """Turn one table row into analyze() inputs.

    Only columns that match an analyze() input are used, and blank cells
    are left out so analyze() falls back to its default (no zonal value,
    70% loan, PH tax rates). Blank cells arrive from pandas as NaN ("not a
    number"), not None. NaN never equals anything, so analyze()'s
    `is None` checks and max() would not treat it as "unknown".
    """
    return {
        column: row[column]
        for column in INPUT_COLUMNS
        if column in row.index and not pd.isna(row[column])
    }


def analyze_deals(deals: pd.DataFrame) -> pd.DataFrame:
    """Analyze every deal. Returns the deals table with result columns added.

    Besides analyze()'s results, each row gets:
        stress_net_profit: net profit if the Stress scenario happens
        max_offer_stress: highest price that still breaks even under Stress
                          (None if no price works)
    """
    results = []
    for _, row in deals.iterrows():
        inputs = deal_inputs(row)
        result = analyze(**inputs)
        result["stress_net_profit"] = run_scenarios(inputs)["Stress"]["net_profit"]
        result["max_offer_stress"] = max_offer(inputs)
        results.append(result)

    # "purchase" and "renovation" repeat the purchase_price and
    # renovation_cost input columns, so leave them out.
    results = pd.DataFrame(results, index=deals.index).drop(columns=["purchase", "renovation"])
    return pd.concat([deals, results], axis=1)


def print_deals(analyzed: pd.DataFrame) -> None:
    """Print a one-line summary per deal."""
    columns = {
        "deal_id": "Deal",
        "description": "Description",
        "purchase_price": "Price",
        "net_profit": "Net profit",
        "roi_on_total_cost": "ROI total cost",
        "cash_on_cash_roi": "Cash-on-cash",
        "stress_net_profit": "Stress profit",
        "max_offer_stress": "Max offer",
    }
    shown = analyzed[[c for c in columns if c in analyzed.columns]].rename(columns=columns)

    def pesos(value):
        return "none" if pd.isna(value) else f"{value:,.0f}"

    def percent(value):
        return f"{value:.2%}"

    print(shown.to_string(index=False, formatters={
        "Price": pesos,
        "Net profit": pesos,
        "ROI total cost": percent,
        "Cash-on-cash": percent,
        "Stress profit": pesos,
        "Max offer": pesos,
    }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze every deal in a CSV file.")
    parser.add_argument("path", nargs="?", default="data/sample_deals.csv",
                        help="deals CSV (default: data/sample_deals.csv)")
    args = parser.parse_args()

    for note in file_notes(args.path):
        print(note)
    print_deals(analyze_deals(load_deals(args.path)))
