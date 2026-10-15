"""Single-deal analysis: cost waterfall, net profit, and both ROIs.

Terms are defined in docs/glossary.md. The anchor deal in
docs/project-context.md is the hand-calculated reference for this function.
Every newer input defaults to "off" (0, or capital_asset), so the anchor
deal's numbers never change.
"""

TAX_MODES = ["capital_asset", "business"]


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
    contingency_rate: float = 0.0,
    other_costs: float = 0.0,
    price_discount_rate: float = 0.0,
    tax_mode: str = "capital_asset",
    income_tax_rate: float = 0.0,
    vat_rate: float = 0.0,
) -> dict:
    """Analyze one flip deal. All amounts in PHP; rates as decimals (9% = 0.09).

    Args:
        purchase_price: Price agreed with the seller (the listed price or your bid).
        arv: After Repair Value, the expected selling price.
        renovation_cost: Total repair and improvement cost.
        holding_months: Months from purchase to sale.
        monthly_holding_cost: Utilities, dues, property tax, security per month.
        loan_ratio: Share of the price paid borrowed (0 = no loan).
        annual_interest_rate: Yearly interest rate on the loan.
        loan_fee_rate: One-time loan processing fee, as a share of the loan.
        acquisition_rate: DST + transfer tax + registration, as a share of
            the price paid.
        broker_rate: Broker commission, as a share of the selling price.
        cgt_rate: Capital gains tax rate (capital_asset mode only).
        zonal_value: BIR zonal value, if known.
        fair_market_value: Assessor's fair market value, if known.
        contingency_rate: Extra share of renovation set aside for surprises.
        other_costs: Up-front costs outside renovation: eviction and legal,
            unpaid dues and property tax, title transfer.
        price_discount_rate: Discount on purchase_price for the payment mode,
            e.g. a Pag-IBIG cash discount. You pay purchase_price x (1 - rate).
        tax_mode: "capital_asset" (CGT on the sale, a final tax) or
            "business" (no CGT; income tax on profit, plus VAT on the sale).
        income_tax_rate: Business mode: tax rate on positive profit.
        vat_rate: Business mode: VAT as a share of the selling price.

    Returns:
        A dict with these keys:
            purchase, acquisition, renovation, contingency, other_costs,
            interest, loan_fees, holding, selling, income_tax: each cost
            line of the waterfall
            price_discount: amount taken off purchase_price
            total_cost: sum of all cost lines
            net_profit: ARV minus total cost
            cash_invested: own money out of pocket (excludes selling costs
                and income tax, which are paid out of the sale)
            roi_on_total_cost: net profit relative to total cost
            cash_on_cash_roi: net profit relative to cash invested
    """
    if tax_mode not in TAX_MODES:
        raise ValueError(f"tax_mode must be one of {TAX_MODES}, got {tax_mode!r}")

    # Price actually paid, after any payment-mode discount
    price_discount = purchase_price * price_discount_rate
    price_paid = purchase_price - price_discount

    # Financing: the bank lends a share of the price paid; you pay the rest.
    loan = price_paid * loan_ratio
    down_payment = price_paid - loan

    # Cost lines, in the order they happen
    acquisition = price_paid * acquisition_rate
    contingency = renovation_cost * contingency_rate
    interest = loan * annual_interest_rate * holding_months / 12
    loan_fees = loan * loan_fee_rate
    holding = monthly_holding_cost * holding_months

    if tax_mode == "capital_asset":
        # CGT is charged on the highest of selling price, zonal value, and fair
        # market value. Unknown values count as 0, so the selling price wins.
        if zonal_value is None:
            zonal_value = 0
        if fair_market_value is None:
            fair_market_value = 0
        cgt_base = max(arv, zonal_value, fair_market_value)
        selling = arv * broker_rate + cgt_base * cgt_rate
    else:
        # Business seller: no CGT; VAT (if any) is a share of the sale.
        selling = arv * broker_rate + arv * vat_rate

    costs_before_tax = (
        price_paid + acquisition + renovation_cost + contingency + other_costs
        + interest + loan_fees + holding + selling
    )
    # Business mode: income tax on profit, only when there is a profit.
    # In capital_asset mode the CGT above is the final tax.
    profit_before_tax = arv - costs_before_tax
    income_tax = income_tax_rate * max(profit_before_tax, 0) if tax_mode == "business" else 0

    total_cost = costs_before_tax + income_tax
    net_profit = arv - total_cost

    # Own money out of pocket. Selling costs and income tax are excluded:
    # they are paid from the buyer's money at closing.
    cash_invested = (
        down_payment + acquisition + renovation_cost + contingency + other_costs
        + interest + loan_fees + holding
    )

    return {
        "purchase": price_paid,
        "price_discount": price_discount,
        "acquisition": acquisition,
        "renovation": renovation_cost,
        "contingency": contingency,
        "other_costs": other_costs,
        "interest": interest,
        "loan_fees": loan_fees,
        "holding": holding,
        "selling": selling,
        "income_tax": income_tax,
        "total_cost": total_cost,
        "net_profit": net_profit,
        "cash_invested": cash_invested,
        "roi_on_total_cost": net_profit / total_cost,
        "cash_on_cash_roi": net_profit / cash_invested,
    }
