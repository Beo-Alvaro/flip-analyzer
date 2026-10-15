"""Decision support: break-even points, what matters most, yearly return,
the safe alternative, and the go/no-go verdict.

Nothing here changes the cost formulas. Every number is found by calling
analyze() (or max_offer()) with different inputs.
"""

import inspect
from dataclasses import dataclass

import pandas as pd

from flip.analyzer import analyze
from flip.scenarios import max_offer


@dataclass
class Settings:
    """Your criteria for a deal worth doing (the Settings sheet)."""
    safe_rate: float = 0.06            # yearly rate you could earn safely instead
    min_profit: float = 200_000        # smallest net profit worth the work and risk
    min_yearly_return: float = 0.15    # smallest yearly cash-on-cash return
    price_within_stress_max_offer: bool = True  # price must be <= max offer under Stress


# --- Break-even points ---

def break_even_arv(inputs: dict) -> float | None:
    """Lowest sale price (ARV) at which the deal stops losing money.

    Binary search, like max_offer(): profit rises with the sale price, so
    keep halving the range until it's accurate to the centavo. None if no
    sale price is high enough (selling costs of 100% or more).
    """
    def profit_at(arv):
        return analyze(**{**inputs, "arv": arv})["net_profit"]

    low, high = 0.0, max(inputs["arv"], 1.0)
    while profit_at(high) < 0:
        high *= 2
        if high > 1e12:
            return None
    while high - low > 0.01:
        middle = (low + high) / 2
        if profit_at(middle) >= 0:
            high = middle
        else:
            low = middle
    return high


def break_even_price(inputs: dict) -> float | None:
    """Highest purchase price at which the deal still breaks even as planned."""
    return max_offer(inputs, "Base", 0)


# --- What matters most ---

# Inputs varied by sensitivity(), with the label shown in reports
SENSITIVITY_INPUTS = {
    "arv": "Sale price (ARV)",
    "purchase_price": "Purchase price",
    "renovation_cost": "Renovation",
    "holding_months": "Holding months",
    "monthly_holding_cost": "Monthly holding cost",
    "annual_interest_rate": "Interest rate",
}


def sensitivity(inputs: dict, change: float = 0.10) -> pd.DataFrame:
    """Profit when each input is 10% lower and 10% higher, biggest swing first.

    The swing is the gap between those two profits. The top row is the
    number most worth getting right before you buy.
    """
    rows = []
    for name, label in SENSITIVITY_INPUTS.items():
        value = inputs.get(name, inspect.signature(analyze).parameters[name].default)
        lower = analyze(**{**inputs, name: value * (1 - change)})["net_profit"]
        higher = analyze(**{**inputs, name: value * (1 + change)})["net_profit"]
        rows.append({"input": label, "profit_if_lower": lower,
                     "profit_if_higher": higher, "swing": abs(higher - lower)})
    return (pd.DataFrame(rows).sort_values("swing", ascending=False, kind="stable")
            .reset_index(drop=True))


# --- Yearly return and the safe alternative ---

def yearly_return(roi: float, months: float) -> float | None:
    """A return over the holding period, stated per year: roi x 12 / months.

    Simple, not compounded: 19.53% over 6 months is 39.06% per year. This
    makes a 6-month and an 18-month flip comparable, and matches how a
    savings rate is quoted. None if there is no holding period.
    """
    if not months or months <= 0:
        return None
    return roi * 12 / months


def safe_earnings(cash_invested: float, months: float, safe_rate: float) -> float:
    """What the same cash would earn in a safe account over the same months."""
    return cash_invested * safe_rate * months / 12


# --- Go/no-go ---

def checklist_status(deal_id, checklist: pd.DataFrame | None) -> dict:
    """Done / open counts and issue notes for one deal's checklist items."""
    if checklist is None:
        return {"started": False, "done": 0, "open": 0, "issues": []}
    mine = checklist[checklist["deal_id"] == deal_id]
    status = mine["status"].fillna("open").astype(str).str.strip().str.lower()
    issues = []
    for (_, item), item_status in zip(mine.iterrows(), status):
        if item_status == "issue":
            note = item.get("note")
            issues.append(f"{item['item']}: {note}" if not pd.isna(note) else str(item["item"]))
    return {"started": not mine.empty, "done": int((status == "done").sum()),
            "open": int((status == "open").sum()), "issues": issues}


def verdict(row: pd.Series, settings: Settings, checklist: pd.DataFrame | None = None) -> str:
    """'Meets your criteria' or 'Fails: <reasons>' for one analyzed deal row.

    This checks the deal against criteria you set; it is not advice to buy.
    """
    fails = []
    if row["net_profit"] < settings.min_profit:
        fails.append(f"profit {row['net_profit']:,.0f} is below your minimum "
                     f"{settings.min_profit:,.0f}")
    yearly = row["yearly_cash_on_cash_roi"]
    if yearly is None or pd.isna(yearly) or yearly < settings.min_yearly_return:
        shown = "unknown" if yearly is None or pd.isna(yearly) else f"{yearly:.1%}"
        fails.append(f"yearly cash-on-cash return {shown} is below your minimum "
                     f"{settings.min_yearly_return:.0%}")
    if row["profit_vs_safe"] < 0:
        fails.append(f"earns {-row['profit_vs_safe']:,.0f} less than a "
                     f"{settings.safe_rate:.0%} safe account")
    if settings.price_within_stress_max_offer:
        offer = row["max_offer_stress"]
        if offer is None or pd.isna(offer):
            fails.append("no purchase price breaks even under Stress")
        elif row["purchase_price"] - offer > 0.5:  # ignore centavo rounding
            fails.append(f"price is {row['purchase_price'] - offer:,.0f} above the max "
                         f"offer under Stress ({offer:,.0f})")

    text = "Meets your criteria" if not fails else "Fails: " + "; ".join(fails)
    if checklist is not None:
        c = checklist_status(row["deal_id"], checklist)
        if not c["started"]:
            text += " | checklist not started"
        elif c["open"] or c["issues"]:
            text += f" | checklist: {c['open']} open, {len(c['issues'])} issue(s)"
    return text


def add_verdicts(analyzed: pd.DataFrame, settings: Settings,
                 checklist: pd.DataFrame | None = None) -> pd.DataFrame:
    """The analyzed table with a verdict column added."""
    result = analyzed.copy()
    result["verdict"] = [verdict(row, settings, checklist) for _, row in analyzed.iterrows()]
    return result
