# House Flip Deal Analyzer

Portfolio project: evaluates whether a property is worth buying and its
expected profit and ROI. Stack: Python, pandas, Excel (openpyxl export).
Full background and decisions: docs/project-context.md — read it at the
start of a new session.

## How to work with me
- This is a learning project. Explain what you changed and why, in plain
  language, tied to this project's data.
- Do NOT write or change the formulas in src/flip/analyzer.py. If you
  find a bug there, explain it and let me fix it myself.
- Propose a plan before multi-file changes.
- If my approach has a flaw for this project, say so directly.

## Calculation rules
- Report BOTH roi_on_total_cost and cash_on_cash_roi. Never a bare "ROI".
- cash_invested = down payment + acquisition + renovation + interest
  + loan fees + holding. Selling costs come out of sale proceeds.
- Tests must assert hand-calculated numbers (see project-context.md),
  never values copied from the code's current output.

## Cost assumptions (Philippines, PHP; verify before changing)
- Capital gains tax 6%, seller pays; base is the highest of selling
  price, zonal value, or fair market value
- Documentary stamp tax 1.5%; transfer tax + registration ~1%
  (acquisition side, ~2.5% total)
- Broker commission 3% of selling price

## Data
- data/comps.csv: hand-collected comparables from PH listing sites
- data/sample_deals.csv: SAMPLE data, must stay labeled as sample