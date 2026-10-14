"""Scenario analysis: one deal under Base, Conservative, and Stress outlooks.

Run `python -m flip.scenarios` to print the anchor deal's scenarios.
"""

from flip.analyzer import analyze

# How much each scenario worsens the deal. These are assumptions:
# change them here and every scenario result and max offer follows.
#   arv_change:        -0.05 = sells for 5% less than the expected ARV
#   renovation_change:  0.10 = renovation runs 10% over budget
#   extra_months:          2 = holding period runs 2 months longer
SCENARIOS = {
    "Base": {"arv_change": 0.00, "renovation_change": 0.00, "extra_months": 0},
    "Conservative": {"arv_change": -0.05, "renovation_change": 0.10, "extra_months": 2},
    "Stress": {"arv_change": -0.10, "renovation_change": 0.25, "extra_months": 4},
}


def apply_scenario(deal: dict, scenario: dict) -> dict:
    """Return a copy of the deal's inputs with the scenario's changes applied."""
    adjusted = dict(deal)
    adjusted["arv"] = deal["arv"] * (1 + scenario["arv_change"])
    adjusted["renovation_cost"] = deal["renovation_cost"] * (1 + scenario["renovation_change"])
    adjusted["holding_months"] = deal["holding_months"] + scenario["extra_months"]
    return adjusted


def run_scenarios(deal: dict) -> dict:
    """Analyze the deal under every scenario: {scenario name: analyze() result}."""
    return {name: analyze(**apply_scenario(deal, s)) for name, s in SCENARIOS.items()}


def max_offer(deal: dict, scenario: str = "Stress", min_profit: float = 0) -> float | None:
    """Highest purchase price that still earns min_profit under the scenario.

    By default: the most you can pay and still break even if the Stress
    scenario happens. Uses binary search, like guessing a number between
    1 and 100: try the middle price, keep the half that contains the
    answer, and repeat until accurate to the centavo.

    Returns None if no price works, not even 0.
    """
    adjusted = apply_scenario(deal, SCENARIOS[scenario])

    def profit_at(price):
        return analyze(**{**adjusted, "purchase_price": price})["net_profit"]

    if profit_at(0) < min_profit:
        return None

    low = 0.0
    high = max(adjusted["arv"], 1.0)
    while profit_at(high) >= min_profit:  # make sure the answer is below high
        high *= 2
    while high - low > 0.01:
        middle = (low + high) / 2
        if profit_at(middle) >= min_profit:
            low = middle
        else:
            high = middle
    return low


def print_scenarios(deal: dict, min_profit: float = 200_000) -> None:
    """Print the deal's scenarios side by side, plus max offers.

    Shows two max offers per scenario: the most you can pay to break even,
    and the most you can pay to still earn min_profit.
    """
    results = run_scenarios(deal)
    inputs = {name: apply_scenario(deal, s) for name, s in SCENARIOS.items()}

    def row(label, values, fmt):
        cells = (f"{'none':>15}" if v is None else f"{v:>15{fmt}}" for v in values)
        print(f"{label:<28}" + "".join(cells))

    print(f"{'':<28}" + "".join(f"{name:>15}" for name in SCENARIOS))
    row("ARV", [inputs[n]["arv"] for n in SCENARIOS], ",.0f")
    row("Renovation", [inputs[n]["renovation_cost"] for n in SCENARIOS], ",.0f")
    row("Holding months", [inputs[n]["holding_months"] for n in SCENARIOS], "d")
    row("Total cost", [results[n]["total_cost"] for n in SCENARIOS], ",.0f")
    row("Cash invested", [results[n]["cash_invested"] for n in SCENARIOS], ",.0f")
    row("Net profit", [results[n]["net_profit"] for n in SCENARIOS], ",.0f")
    row("ROI on total cost", [results[n]["roi_on_total_cost"] for n in SCENARIOS], ".2%")
    row("Cash-on-cash ROI", [results[n]["cash_on_cash_roi"] for n in SCENARIOS], ".2%")

    print()
    print(f"{'Purchase price (asking)':<28}{deal['purchase_price']:>15,.0f}")
    row("Max offer: break even", [max_offer(deal, n) for n in SCENARIOS], ",.0f")
    row(f"Max offer: {min_profit:,.0f} profit",
        [max_offer(deal, n, min_profit) for n in SCENARIOS], ",.0f")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scenarios for the anchor deal.")
    parser.add_argument("--min-profit", type=float, default=200_000,
                        help="profit target for the second max offer (default 200,000)")
    args = parser.parse_args()

    # Anchor deal from docs/project-context.md
    print_scenarios(dict(
        purchase_price=2_800_000,
        arv=4_200_000,
        renovation_cost=450_000,
        holding_months=6,
        monthly_holding_cost=15_000,
    ), min_profit=args.min_profit)
