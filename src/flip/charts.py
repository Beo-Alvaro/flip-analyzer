"""Charts for the web app (Altair).

Colors come from a validated palette: each pair below passed the colorblind
(CVD) separation, normal-vision, lightness, chroma, and 3:1 contrast checks
against Streamlit's light (#ffffff) and dark (#0e1117) backgrounds. Dark
mode uses its own steps of the same hues, not an automatic flip.
"""

import altair as alt
import pandas as pd

PALETTE = {
    "light": {"blue": "#2a78d6", "orange": "#eb6834", "red": "#e34948",
              "ink": "#52514e", "rule": "#898781"},
    "dark": {"blue": "#3987e5", "orange": "#d95926", "red": "#e66767",
             "ink": "#c3c2b7", "rule": "#898781"},
}

PESOS = ",.0f"


def _colors(dark: bool) -> dict:
    return PALETTE["dark" if dark else "light"]


def scenario_chart(scenarios: pd.DataFrame, dark: bool = False) -> alt.Chart:
    """Net profit per scenario, blue for a profit and red for a loss.

    scenarios: columns scenario, net_profit (in Base, Conservative, Stress order).
    """
    c = _colors(dark)
    data = scenarios.assign(result=scenarios["net_profit"].map(
        lambda v: "Profit" if v >= 0 else "Loss"))
    order = list(scenarios["scenario"])
    base = alt.Chart(data).encode(
        x=alt.X("scenario:N", sort=order, title=None, axis=alt.Axis(labelAngle=0)),
    )
    # Headroom past the longest bar so its label never meets the axis labels
    low = min(scenarios["net_profit"].min(), 0) * 1.2
    high = max(scenarios["net_profit"].max(), 0) * 1.2
    bars = base.mark_bar(cornerRadiusEnd=4, size=36).encode(
        y=alt.Y("net_profit:Q", title="Net profit (PHP)", axis=alt.Axis(format="~s"),
                scale=alt.Scale(domain=[low, high] if low < high else [-1, 1])),
        color=alt.Color("result:N", scale=alt.Scale(domain=["Profit", "Loss"],
                                                    range=[c["blue"], c["red"]]),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("scenario:N", title="Scenario"),
                 alt.Tooltip("net_profit:Q", title="Net profit", format=PESOS)],
    )
    # Direct labels: just three bars, above a profit and below a loss
    above = base.mark_text(dy=-8, color=c["ink"]).encode(
        y="net_profit:Q", text=alt.Text("net_profit:Q", format=PESOS),
    ).transform_filter(alt.datum.net_profit >= 0)
    below = base.mark_text(dy=12, color=c["ink"]).encode(
        y="net_profit:Q", text=alt.Text("net_profit:Q", format=PESOS),
    ).transform_filter(alt.datum.net_profit < 0)
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=c["rule"]).encode(y="y:Q")
    return (bars + zero + above + below).properties(height=300)


def sensitivity_chart(table: pd.DataFrame, base_profit: float, dark: bool = False) -> alt.Chart:
    """What matters most: bars from the as-planned profit to the profit with
    each input 10% lower (blue) and 10% higher (orange), biggest swing on top.

    table: columns input, profit_if_lower, profit_if_higher (sorted by swing).
    """
    c = _colors(dark)
    order = list(table["input"])
    long = pd.concat([
        pd.DataFrame({"input": table["input"], "case": "Input 10% lower",
                      "profit": table["profit_if_lower"]}),
        pd.DataFrame({"input": table["input"], "case": "Input 10% higher",
                      "profit": table["profit_if_higher"]}),
    ])
    long["as_planned"] = base_profit
    long["change"] = long["profit"] - base_profit
    bars = alt.Chart(long).mark_bar(cornerRadius=4, size=16).encode(
        y=alt.Y("input:N", sort=order, title=None, axis=alt.Axis(labelLimit=200)),
        x=alt.X("profit:Q", title="Net profit (PHP)", axis=alt.Axis(format="~s")),
        x2="as_planned:Q",
        color=alt.Color("case:N",
                        scale=alt.Scale(domain=["Input 10% lower", "Input 10% higher"],
                                        range=[c["blue"], c["orange"]]),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("input:N", title="Input"), alt.Tooltip("case:N", title="Case"),
                 alt.Tooltip("profit:Q", title="Net profit", format=PESOS),
                 alt.Tooltip("change:Q", title="Change vs plan", format="+,.0f")],
    )
    planned = alt.Chart(pd.DataFrame({"x": [base_profit]})).mark_rule(
        color=c["ink"], strokeWidth=2).encode(
        x="x:Q", tooltip=[alt.Tooltip("x:Q", title="As planned", format=PESOS)])
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=c["rule"]).encode(x="x:Q")
    return (zero + bars + planned).properties(height=260)


def cost_chart(costs: pd.DataFrame, dark: bool = False) -> alt.Chart:
    """Costs on top of the price paid, largest first, in one color.

    costs: columns cost, amount (zero amounts are left out).
    """
    c = _colors(dark)
    data = costs[costs["amount"] > 0]
    return alt.Chart(data).mark_bar(cornerRadiusEnd=4, size=16, color=c["blue"]).encode(
        y=alt.Y("cost:N", sort="-x", title=None, axis=alt.Axis(labelLimit=200)),
        x=alt.X("amount:Q", title="PHP", axis=alt.Axis(format="~s")),
        tooltip=[alt.Tooltip("cost:N", title="Cost"),
                 alt.Tooltip("amount:Q", title="Amount", format=PESOS)],
    ).properties(height=max(120, 28 * len(data)))
