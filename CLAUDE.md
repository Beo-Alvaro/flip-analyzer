# House Flip Deal Analyzer

Portfolio project: evaluates whether a property is worth buying and its
expected profit and ROI. Stack: Python, pandas, Excel (openpyxl export).
Full background and decisions: docs/project-context.md — read it at the
start of a new session.

## How to work with me
- This is a learning project. Explain what you changed and why, in plain
  language, tied to this project's data.
- Propose a plan before multi-file changes.
- If my approach has a flaw for this project, say so directly.

## Calculation rules
- Report BOTH roi_on_total_cost and cash_on_cash_roi. Never a bare "ROI".
- cash_invested = down payment + acquisition + renovation + contingency
  + other costs + interest + loan fees + holding. Selling costs (and
  income tax in business mode) come out of sale proceeds.
- Down payment, acquisition, and the loan are based on the price paid:
  purchase_price x (1 - price_discount_rate).
- New analyze() inputs must default to "off" so the anchor deal stays
  at 304,200.
- Tests must assert hand-calculated numbers (see project-context.md),
  never values copied from the code's current output.

## Cost assumptions (Philippines, PHP; verify before changing)
- Capital gains tax 6%, seller pays; base is the highest of selling
  price, zonal value, or fair market value
- Documentary stamp tax 1.5%; transfer tax + registration ~1%
  (acquisition side, ~2.5% total)
- Broker commission 3% of selling price
- Business tax mode (habitual flipper): no CGT; income tax on positive
  profit and VAT on the sale at rates the user enters. Not hard-coded:
  the user confirms the rates with an accountant

## Data
- data/deals_input.xlsx: the user's real deals, entered in the Excel
  input workbook (created by `python -m flip.template`). Gitignored so
  real deals stay private. Comps are hand-collected from PH listing
  sites and entered on its Comps sheet (or a comps CSV via --comps)
- data/sample_deals.csv: SAMPLE data, must stay labeled as sample
  (one row per house; used by src/flip/batch.py)
- data/sample_properties.csv, sample_renovations.csv,
  sample_loan_offers.csv: SAMPLE data, must stay labeled as sample
  (split tables; used by src/flip/tables.py)
- Sample label = a "# SAMPLE DATA: ..." first line; tests enforce it