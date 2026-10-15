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
Excel input workbook (done: src/flip/template.py, inputs.py, comps.py).
`python -m flip.template` creates data/deals_input.xlsx: Instructions,
Properties, Renovations, Loan offers, Comps sheets, a note on every
column, Excel typing checks. Data type cell (SAMPLE/REAL) drives the
SAMPLE banner; REAL with SAMPLE-* rows left in is an error. All inputs
(CSV or Excel) pass check_inputs(): blanks, text in number columns,
rates typed as 9 instead of 9%, negatives, unknown deal_ids, with
spreadsheet row numbers. Suggested ARV = median comp price per sqm x
floor area; shown next to the user's ARV, never replaces it.
Not modeled yet: loan prepayment penalties (would change analyze()).
README (done). Includes the Imus Pag-IBIG case study without the
address or property ID; delete that section if it shouldn't be public.

## Improvement plan (after an honest review: "good screener, not yet a
## decision tool")
Phase A (done, no analyze() changes): decision.py (break-even sale price
and purchase price, sensitivity ranking, yearly ROI = ROI x 12 / months,
simple not compounded; profit vs safe account; verdict vs Settings sheet;
checklist), comp kinds (resale counted; new = ceiling; foreclosed =
floor; pasalo left out) with range and warnings, workbook Checklist and
Settings sheets, `python -m flip.template --upgrade` keeps user data.
Settings defaults: safe rate 6%, min profit 200,000, min yearly
cash-on-cash 15%, price must be <= Stress max offer.
Phase B (done, approved by user): analyze() gained contingency_rate,
other_costs, price_discount_rate, tax_mode (capital_asset | business),
income_tax_rate, vat_rate; all default off. cash_invested now includes
contingency and other costs. Other costs sheet (summed per house like
renovations). holding_months_worst per house: Stress uses it,
Conservative goes halfway (scenarios.py worst_case_share). Business mode:
no CGT, selling = broker + VAT x ARV, income tax = rate x max(profit
before tax, 0), included in total cost but not cash invested. CWT is not
modeled (creditable, not a cost).
Applied to the user's deals: Imus legal 90,000 moved to Other costs, 10%
contingency, worst 24 months; San Pablo 10% contingency, worst 16 months.
Phase C (done): local web app, `python -m flip.web` (Streamlit 1.66 on
Python 3.15). app.py reads the workbook, never writes it; what-if inputs
(price, ARV, months, worst months, monthly cost, contingency) apply on
screen and in the downloaded report. charts.py: Altair charts with a
palette validated for colorblind safety and contrast on Streamlit's light
and dark backgrounds; every chart has a "See the numbers" table. Tested
headless with Streamlit AppTest (tests/test_app.py).
Still not modeled: loan prepayment penalty, amortizing loans.
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