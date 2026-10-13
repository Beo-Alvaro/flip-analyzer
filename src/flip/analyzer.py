"""Single-deal analysis: cost waterfall, net profit, and both ROIs.

Terms are defined in docs/glossary.md. The anchor deal in
docs/project-context.md is the hand-calculated reference for this function.
"""


def analyze(
    purchase_price: float,
    arv: float,
    renovation_cost: float,
    holding_months: int,
    monthly_holding_cost: float,
    loan_ratio: float = 0.70,
    annual_interest_rate: float = 0.09,
    loan_fee_rate: float = 0.01,
    acquisition_rate: float = 0.025,
    broker_rate: float = 0.03,
    cgt_rate: float = 0.06,
    zonal_value: float | None = None,
    fair_market_value: float | None = None,
) -> dict:
    """Analyze one flip deal. All amounts in PHP; rates as decimals (9% = 0.09).

    Args:
        purchase_price: Price paid to the seller.
        arv: After Repair Value, the expected selling price.
        renovation_cost: Total repair and improvement cost.
        holding_months: Months from purchase to sale.
        monthly_holding_cost: Utilities, dues, property tax, security per month.
        loan_ratio: Share of purchase_price borrowed (0 = no loan).
        annual_interest_rate: Yearly interest rate on the loan.
        loan_fee_rate: One-time loan processing fee, as a share of the loan.
        acquisition_rate: DST + transfer tax + registration, as a share of
            purchase_price.
        broker_rate: Broker commission, as a share of the selling price.
        cgt_rate: Capital gains tax rate.
        zonal_value: BIR zonal value, if known.
        fair_market_value: Assessor's fair market value, if known.

    Returns:
        A dict with these keys:
            purchase, acquisition, renovation, interest, loan_fees,
            holding, selling: each cost line of the waterfall
            total_cost: sum of all cost lines
            net_profit: ARV minus total cost
            cash_invested: own money out of pocket (excludes selling costs)
            roi_on_total_cost: net profit relative to total cost
            cash_on_cash_roi: net profit relative to cash invested
    """
    # Financing: the bank lends a share of the purchase price; you pay the rest.
    loan = purchase_price * loan_ratio
    down_payment = purchase_price - loan

    # Cost lines, in the order they happen
    acquisition = purchase_price * acquisition_rate
    interest = loan * annual_interest_rate * holding_months / 12
    loan_fees = loan * loan_fee_rate
    holding = monthly_holding_cost * holding_months

    # CGT is charged on the highest of selling price, zonal value, and fair
    # market value. Unknown values count as 0, so the selling price wins.
    if zonal_value is None:
        zonal_value = 0
    if fair_market_value is None:
        fair_market_value = 0
    cgt_base = max(arv, zonal_value, fair_market_value)
    selling = arv * broker_rate + cgt_base * cgt_rate

    total_cost = (
        purchase_price + acquisition + renovation_cost
        + interest + loan_fees + holding + selling
    )
    net_profit = arv - total_cost

    # Own money out of pocket. Selling costs are excluded: they are paid
    # from the buyer's money at closing.
    cash_invested = (
        down_payment + acquisition + renovation_cost
        + interest + loan_fees + holding
    )

    return {
        "purchase": purchase_price,
        "acquisition": acquisition,
        "renovation": renovation_cost,
        "interest": interest,
        "loan_fees": loan_fees,
        "holding": holding,
        "selling": selling,
        "total_cost": total_cost,
        "net_profit": net_profit,
        "cash_invested": cash_invested,
        "roi_on_total_cost": net_profit / total_cost,
        "cash_on_cash_roi": net_profit / cash_invested,
    }
