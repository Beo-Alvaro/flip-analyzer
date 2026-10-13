# Project Context — House Flip Deal Analyzer

## Questions the analyzer answers
1. Is this property worth buying?
2. What are the expected net profit and ROI?

## Build order (decided)
1. Single-deal calculation: analyze() for one property  <- current step
2. Scenario analysis: Base / Conservative / Stress (vary purchase price,
   renovation cost, ARV, holding period)
3. Many deals in a pandas DataFrame, same logic across rows
4. Split into tables: properties, renovations, financing, holding_costs, sale
Reason: the calculation decides which fields the tables need.

## Cost waterfall
Total Cost = Purchase + Acquisition + Renovation + Interest + Loan fees
             + Holding + Selling
Net Profit = ARV - Total Cost
ROI on total cost = Net Profit / Total Cost
Cash-on-cash ROI  = Net Profit / Cash invested

## Anchor deal (hand-calculated; use as the first test)
Inputs: purchase 2,800,000 | ARV 4,200,000 | renovation 450,000
        6 months holding at 15,000/month | loan 70% of purchase at 9%/yr
        loan fee 1% | acquisition 2.5% | broker 3% | CGT 6%

| Item                  | PHP        |
|-----------------------|------------|
| Purchase              | 2,800,000  |
| Acquisition (2.5%)    | 70,000     |
| Renovation            | 450,000    |
| Interest (6 mo)       | 88,200     |
| Loan fees             | 19,600     |
| Holding               | 90,000     |
| Selling (3% + 6%)     | 378,000    |
| **Total cost**        | 3,895,800  |
| **Net profit**        | 304,200    |
| Cash invested         | 1,557,800  |
| ROI on total cost     | ~7.81%     |
| Cash-on-cash ROI      | ~19.53%    |

## Division of labor
- I write: analyze(), the cost waterfall, ROI definitions
- Claude Code does: repo scaffolding, tests for edge cases (no loan,
  12-month hold, ARV below cost), scenario runner, Excel export,
  README, git commits

## Known edge cases to handle
- Holding period overruns (interest + holding scale with months)
- CGT base can exceed the sale price if zonal value is higher
- 70%-of-ARV rule is a US heuristic: sanity check only, not a decision rule