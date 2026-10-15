"""Suggested ARV from comparable sales (comps), and how far to trust it.

Each comp has a kind:
    resale      someone selling an existing home outright: the best comp
    new         a brand-new developer unit: shown as a ceiling, since a
                renovated resale rarely sells for more than new
    foreclosed  a bank or Pag-IBIG property: shown as an as-is floor
    pasalo      a loan takeover: left out, because the listed price is
                usually only the cash-out, not the house's price
Comps with no kind are counted as resale, with a warning to set it.

The suggested ARV is the median price per sqm of the resale comps x the
house's floor area. The median (the middle value) is used instead of the
average so one unusual comp can't pull the estimate up on its own. The
suggestion is shown next to the ARV you entered; it never replaces it.
"""

import math
from datetime import date

import pandas as pd

KINDS = ["resale", "new", "foreclosed", "pasalo"]
OLD_LISTING_DAYS = 365
FEW_COMPS = 3


def _describe(comp) -> str:
    """A short name for a comp in warnings: its subdivision and price."""
    place = comp.get("subdivision")
    place = "comp" if place is None or pd.isna(place) else str(place)
    return f"{place} ({comp['price']:,.0f})"


def suggested_arv(properties: pd.DataFrame, comps: pd.DataFrame, today=None) -> pd.DataFrame:
    """One row per house: the comp-based ARV check.

    Columns:
        comps_used: resale comps (and comps with no kind) in the estimate
        low/median/high_price_per_sqm: their range per sqm
        suggested_arv: median per sqm x floor area (blank without comps or area)
        arv_low, arv_high: the range x floor area
        new_unit_ceiling: median of new comps x floor area
        foreclosed_floor: median of foreclosed comps x floor area
        warnings: list of plain-language warnings
    """
    today = pd.Timestamp(today or date.today())
    comps = comps.copy()
    if "kind" in comps.columns:
        comps["kind"] = comps["kind"].fillna("").astype(str).str.strip().str.lower()
    else:
        comps["kind"] = ""
    comps["price_per_sqm"] = comps["price"] / comps["floor_area_sqm"]

    rows = []
    for _, house in properties.iterrows():
        mine = comps[comps["deal_id"] == house["deal_id"]]
        area = house.get("floor_area_sqm", math.nan)
        area = math.nan if area is None or pd.isna(area) else float(area)
        used = mine[mine["kind"].isin(["resale", ""])]
        per_sqm = used["price_per_sqm"]
        median = per_sqm.median() if len(per_sqm) else math.nan
        warnings = []

        unset = int((used["kind"] == "").sum())
        if unset:
            warnings.append(f"{unset} comp(s) have no kind set and were counted as resale")
        pasalo = mine[mine["kind"] == "pasalo"]
        if len(pasalo):
            warnings.append(f"{len(pasalo)} pasalo comp(s) left out: a pasalo price is "
                            "usually the cash-out, not the house's price. Enter the total "
                            "contract price and set kind to new or resale")
        if 0 < len(used) < FEW_COMPS:
            warnings.append(f"only {len(used)} resale comp(s); 3 to 5 make a steadier estimate")
        if len(mine) and not len(used):
            warnings.append("no resale comps: the suggested ARV needs at least one")
        for _, comp in used.iterrows():
            if comp["price_per_sqm"] < 0.5 * median or comp["price_per_sqm"] > 2 * median:
                warnings.append(f"{_describe(comp)} is far from the other comps "
                                f"({comp['price_per_sqm']:,.0f}/sqm vs median {median:,.0f})")
        if "date_listed" in mine.columns:
            for _, comp in mine.iterrows():
                listed = comp["date_listed"]
                if not pd.isna(listed) and (today - pd.Timestamp(listed)).days > OLD_LISTING_DAYS:
                    warnings.append(f"{_describe(comp)} was listed "
                                    f"{pd.Timestamp(listed):%Y-%m}, over a year ago")

        def times_area(kind):
            prices = mine[mine["kind"] == kind]["price_per_sqm"]
            return prices.median() * area if len(prices) else math.nan

        suggestion = median * area
        ceiling = times_area("new")
        price = house.get("purchase_price", math.nan)
        arv = house.get("arv", math.nan)
        if not pd.isna(suggestion) and not pd.isna(price) and suggestion < 0.5 * price:
            warnings.append("suggested ARV is less than half the purchase price: check your "
                            "comps (a pasalo cash-out is not a full price)")
        if not pd.isna(ceiling) and not pd.isna(arv) and arv >= 0.98 * ceiling:
            warnings.append(f"your ARV is at or above the new-unit ceiling ({ceiling:,.0f}): a "
                            "renovated resale rarely sells for more than a brand-new unit")
        high = per_sqm.max() * area if len(per_sqm) else math.nan
        if not pd.isna(high) and not pd.isna(arv) and arv > high:
            warnings.append(f"your ARV is above your highest resale comp ({high:,.0f})")

        rows.append({
            "deal_id": house["deal_id"],
            "comps_used": len(used),
            "low_price_per_sqm": per_sqm.min() if len(per_sqm) else math.nan,
            "median_price_per_sqm": median,
            "high_price_per_sqm": per_sqm.max() if len(per_sqm) else math.nan,
            "suggested_arv": suggestion,
            "arv_low": per_sqm.min() * area if len(per_sqm) else math.nan,
            "arv_high": high,
            "new_unit_ceiling": ceiling,
            "foreclosed_floor": times_area("foreclosed"),
            "warnings": warnings,
        })
    return pd.DataFrame(rows)
