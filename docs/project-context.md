# Project Context — House Flip Deal Analyzer

## Questions the analyzer answers
1. Is this property worth buying?
2. What are the expected net profit and ROI?

## Build order (decided)
1. Single-deal calculation: analyze() for one property  (done)
2. Scenario analysis: Base / Conservative / Stress (vary renovation cost,
   ARV, holding period) + max offer  (done)
3. Many deals in a pandas DataFrame, same logic across rows  (done:
   src/flip/batch.py runs analyze() per row; blank CSV cells use
   analyze()'s defaults)
4. Split into tables (done: src/flip/tables.py). Built as 3 tables, not
   the 5 first planned: properties, renovations (itemized budget, many
   per house), loan_offers (many per house, compared side by side).
   Holding costs and sale have one row per house, so they stay in
   properties. A house with no loan offers gets analyze()'s default terms,
   labeled "default terms". Unknown or repeated deal_ids are errors.
Excel export (done: src/flip/export.py). Writes values, not live Excel
formulas: Python is the tested source of truth and Excel is the report.
Sample inputs -> SAMPLE banner on every sheet + SAMPLE_ file name.
Output goes to output/ (gitignored).
Next: README.
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

## Scenarios (assumptions, defined in src/flip/scenarios.py)
| Scenario     | ARV  | Renovation | Holding   | Anchor net profit |
|--------------|------|------------|-----------|-------------------|
| Base         | as is| as is      | as is     | 304,200           |
| Conservative | -5%  | +10%       | +2 months | 8,700             |
| Stress       | -10% | +25%       | +4 months | -309,300          |

Purchase price is NOT varied: once signed it is known, the one number
the buyer decides. Instead, max offer = highest purchase price that
still breaks even under Stress. Anchor deal: ~2,514,799 vs 2,800,000
asking (the 70% rule gives 2,490,000 for comparison).

## Division of labor
- I decide: the cost waterfall, ROI definitions, assumptions; I review
  all calculation code
- Claude Code does: analyze() (written by Claude, reviewed by me), repo
  scaffolding, tests for edge cases, scenario runner, Excel export,
  README, git commits

## Known edge cases to handle
- Holding period overruns (interest + holding scale with months)
- CGT base can exceed the sale price if zonal value is higher
- 70%-of-ARV rule is a US heuristic: sanity check only, not a decision rule