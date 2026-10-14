"""Suggested ARV from comparable sales (comps).

For each house: work out each comp's price per sqm, take the median, and
multiply by the house's floor area. The median (the middle value) is used
instead of the average so one unusual comp, like a luxury unit, can't pull
the estimate up on its own.

The suggestion is shown next to the ARV you entered; it never replaces it.
"""

import math

import pandas as pd


def suggested_arv(properties: pd.DataFrame, comps: pd.DataFrame) -> pd.DataFrame:
    """One row per house: deal_id, comps_used, median_price_per_sqm, suggested_arv.

    suggested_arv is blank (NaN) when the house has no comps or no floor area.
    """
    per_sqm = comps.assign(price_per_sqm=comps["price"] / comps["floor_area_sqm"])
    stats = (
        per_sqm.groupby("deal_id")["price_per_sqm"]
        .agg(comps_used="count", median_price_per_sqm="median")
        .reset_index()
    )
    result = properties[["deal_id"]].merge(stats, on="deal_id", how="left")
    result["comps_used"] = result["comps_used"].fillna(0).astype(int)

    if "floor_area_sqm" in properties.columns:
        floor_area = properties["floor_area_sqm"].to_numpy(dtype=float)
    else:
        floor_area = math.nan
    result["suggested_arv"] = result["median_price_per_sqm"] * floor_area
    return result
