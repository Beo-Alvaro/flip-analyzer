# House Flip Deal Analyzer (Philippines)

Decides whether a Philippine property is worth flipping, and the most you
should pay for it. Give it a purchase price, an expected sale price, a
renovation budget, and loan terms; it returns the full cost waterfall, net
profit, both ROIs, how the deal holds up when things go wrong, and a
walk-away price.

Built with Python, pandas, and openpyxl. All amounts are in PHP and the
costs follow Philippine rules: 6% capital gains tax on the highest of
selling price, zonal value, or fair market value; ~2.5% documentary stamp,
transfer tax, and registration; 3% broker commission.

## What it answers

| Question | Output |
|---|---|
| What will this flip earn? | Net profit, ROI on total cost, cash-on-cash ROI |
| Where does the money go? | Cost waterfall: price paid (after any payment-mode discount), acquisition, renovation, contingency, other costs (eviction, unpaid dues and tax, title), interest, loan fees, holding, selling, and income tax for business sellers |
| What if things go wrong? | Base, Conservative, and Stress scenarios; Stress uses each house's own worst-case months when given (an occupied foreclosure gets a longer Stress than a vacant house) |
| What's the most I should pay? | Max offer: highest price that still breaks even (or earns a target profit) under Stress |
| Which loan is better? | Loan offers side by side, including paying cash |
| Is my sale price realistic? | Suggested ARV from resale comps (median price per sqm x floor area) with a low–high range; new units shown as a ceiling, foreclosures as a floor, pasalo prices left out; warnings for old, odd, or too few comps |
| What does it need to sell for? | Break-even sale price and break-even purchase price |
| Which estimate matters most? | Profit when each input is 10% lower or higher, ranked by swing |
| Is it worth it vs. doing nothing? | Yearly ROI, and profit compared with a safe account at your rate |
| Does it meet my rules? | A verdict against your own criteria (minimum profit, minimum yearly return, max offer) and a due-diligence checklist per house |

## How to use

1. Start the web app (`python -m flip.web`). On **Market scan**, pick a
   foreclosure and press **Start a deal** (or find a listing yourself).
2. Find 3 to 5 comparable resale homes in its subdivision.
3. On **Edit a house**, add the comps, renovation items, and loan offers,
   and update the ARV (or do it in the Excel input workbook;
   `python -m flip.template` creates it).
4. On **Analyze a house**, read the verdict, key numbers, and charts; try
   what-ifs.
5. Download the Excel report.

**Full walkthrough with screenshots: [docs/how-to-use.md](docs/how-to-use.md)**

## Example: the anchor deal

Every calculation is tested against one hand-calculated deal: a
₱2,800,000 house, renovated for ₱450,000, held 6 months, sold for
₱4,200,000, with a 70% loan at 9%.

| Item | PHP |
|---|---|
| Purchase | 2,800,000 |
| Acquisition (2.5%) | 70,000 |
| Renovation | 450,000 |
| Interest (1,960,000 x 9% x 6/12) | 88,200 |
| Loan fees (1%) | 19,600 |
| Holding (15,000 x 6) | 90,000 |
| Selling (3% broker + 6% CGT) | 378,000 |
| **Total cost** | **3,895,800** |
| **Net profit** | **304,200** |
| Cash invested (own money only) | 1,557,800 |
| ROI on total cost | 7.81% |
| Cash-on-cash ROI | 19.53% |

It looks good until you ask what happens if things slip:

```
                                       Base   Conservative         Stress
ARV                               4,200,000      3,990,000      3,780,000
Renovation                          450,000        495,000        562,500
Holding months                            6              8             10
Net profit                          304,200          8,700       -309,300
ROI on total cost                     7.81%          0.22%         -7.56%
Cash-on-cash ROI                     19.53%          0.52%        -17.29%

Purchase price (asking)           2,800,000
Max offer: break even             3,086,037      2,808,101      2,514,799
Max offer: 200,000 profit         2,897,978      2,621,881      2,330,383
```

A 5% lower sale price, a 10% renovation overrun, and a 2-month delay take
the deal to break-even. To survive the Stress scenario, the offer should
be at most ₱2,514,799, about ₱285,000 below asking.

## Case study: a real Pag-IBIG auction listing

A 92 sqm townhouse in Imus, Cavite, at a Pag-IBIG public auction: minimum
bid ₱2,267,730, occupied, title still under consolidation. Replacing each
guess with researched numbers, one at a time (cash purchase):

| Step | Change | Net profit |
|---|---|---|
| Start | All placeholder guesses | +543,577 |
| 1 | ARV from 4 resale comps (median ₱34,750/sqm x 92 sqm = ₱3,197,000) | -5,153 |
| 2 | Holding period 15 months (eviction case + renovation + sale) | -20,153 |
| 3 | Monthly holding cost ₱4,000 | -5,153 |
| 4 | Renovation ₱550,000 + legal costs for eviction ₱90,000 | **-115,153** |

The first ARV guess came from brand-new developer units; real resale comps
were 16% lower, and that single input erased the profit. At the minimum
bid the deal needs a sale price of at least ₱3,323,541 to break even, 4%
above what the comps support, or a purchase price of ₱2,155,385 or less.
The lesson: in flipping, the sale price estimate matters more than anything
else, and comps of the right kind (resale, same type, renovated) are what
make it believable.

*Comps were asking prices from public listings; costs are researched
estimates, not quotes. This is an analysis exercise, not investment advice.*

## Getting started

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -e ".[dev]"
python -m pytest
```

On Windows, PowerShell may refuse `activate` ("running scripts is disabled
on this system"). You don't need it: run the project's Python directly,
e.g. `.venv\Scripts\python -m flip.web`, and use `.venv\Scripts\python`
wherever this README says `python`.

### Analyze your own deals

1. Create the input workbook:
   ```bash
   python -m flip.template
   ```
   This makes `data/deals_input.xlsx` with sheets for Properties,
   Renovations, Loan offers, Comps, a due-diligence Checklist, and
   Settings (your criteria for a deal worth doing). Every column header
   has a note explaining what goes there and where to find it. It starts
   with the anchor deal as example rows. An older workbook can be brought
   up to date without losing data:
   `python -m flip.template --upgrade data/deals_input.xlsx`.
2. Replace the example rows with your properties and set **Data type** to
   REAL on the Instructions sheet.
3. Print the report, or export it to Excel:
   ```bash
   python -m flip.tables --input data/deals_input.xlsx
   python -m flip.export --input data/deals_input.xlsx
   ```

Typing mistakes are caught before anything is calculated, with the exact
row to fix:

```
Please fix these in your input:
  - Properties row 2 (SAMPLE-01): purchase_price must be a number, got '2.8M'
  - Loan offers row 2 (SAMPLE-01): annual_interest_rate is 9. Did you mean 9%? Type it as 9% or 0.09.
  - Comps row 2 (SAMPLE-1): deal_id SAMPLE-1 is not on the Properties sheet (typo?)
```

### The web app (no terminal needed after starting it)

```bash
pip install -e ".[web]"
python -m flip.web
```

It opens in your browser at http://localhost:8501 with three pages, in
the order of the deal cycle:

- **Market scan**: import Pag-IBIG's listings (the collector snippet and
  steps are on the page), filter every screened foreclosure (city, screen
  result, unoccupied, offer window still open, how many are for sale in
  the subdivision), and **Start a deal**: the house's price, floor area,
  and location go into your workbook along with the standard checklist.
  The resale and new comps in your workbook count as listings too, so
  every comp you add makes the scan fairer for its whole subdivision.
- **Edit a house**: its numbers (price, ARV, months, holding cost...) and
  tables for renovation items, other costs, loan offers, comps, and the
  checklist, with the suggested ARV updating as you type comps. One
  **Save changes** button saves only what you changed; **Discard** undoes.
  **Paste a listing** (on the Comps tab) reads a post's text: it suggests
  resale, new, pasalo, or foreclosed and shows the phrases that say so,
  fills in the price, floor and lot area, and condition it finds, and for a
  pasalo works out the full price (cash-out + what is still owed, checked
  against the loan terms). Only the fields you confirm are saved, never the
  pasted text.
- **Analyze a house**: pick a house and a loan offer to see the verdict,
  the key numbers, charts of the scenarios, what matters most, and where
  the money goes, the ARV check, costs, and the checklist. A **What-if**
  panel tries different numbers on screen without touching your workbook,
  and the sidebar downloads the Excel report.

It uses `data/deals_input.xlsx` (an uploaded workbook is only read). The
app saves only when you press a save button, and every save is checked
with the same rules as the reports, refused while the file is open in
Excel, and backed up first to a `backups` folder next to the file (kept
out of git). Stop it with Ctrl+C.

### Market scan: where are foreclosures cheap?

```bash
python -m flip.market data/market/cavite_listings.csv --output output/cavite_market.xlsx
```

Reads a CSV of listings (city, kind, price, floor area, subdivision...)
and writes a workbook with the median price per sqm of **new**,
**resale**, and **foreclosed** homes per city, and a **Foreclosures**
sheet that compares each foreclosure like for like: with resale, then
new, listings of a similar size and type in the **same subdivision**,
then with the city's resale median. New units elsewhere in the city can
only rule a house out (they are often in pricier subdivisions). Each
row also shows how many foreclosures are for sale in its subdivision:
your competition when you resell. Those at or below 70% of a fair
comparison go to the **Candidates** sheet; "no fair comparison" means
collect resale prices from that subdivision first.
`data/market/cavite_listings.csv` holds about 1,500 public Cavite listings
collected in October 2026 (FazWaz plus every Pag-IBIG house); add rows you
find yourself and run it again. Add `--workbook data/deals_input.xlsx` to
also use the resale and new comps you entered for your houses (the web
app does this by default).

### Keep it current: import Pag-IBIG's listings

Pag-IBIG now lists foreclosures only on its
[Online Public Auction](https://www.pagibigfundservices.com/OnlinePublicAuction/)
site (it stopped publishing PDF lists). Once a month:

1. Open the site, choose the region and province (e.g. REGION 4-A, CAVITE).
2. Press F12, open the Console tab, paste
   [docs/pagibig-opa-collector.js](docs/pagibig-opa-collector.js), and press
   Enter. It reads every city's 1st auction, 2nd auction, and negotiated sale
   listings (about 10 minutes for Cavite, pausing between pages) and
   downloads `opa_listings.json`. It only reads; it never bids or logs in.
3. Move the file to `data/market/` and import it:

```bash
python -m flip.pagibig data/market/opa_listings.json
```

Every house is added with its price, floor and lot area, occupancy, and sale
type; lots, condos, and parking slots are skipped, and a property already in
the file is replaced by the new row. Older PDF lists can be imported the same
way (`python -m flip.pagibig LIST.pdf`). Rebuild the market report afterwards.

### Draft comps for a house

```bash
python -m flip.draft TANZA-01
```

Fill in the house's `city` (and `barangay`, `subdivision`, `type` if known)
on the Properties sheet first. The most similar listings from the market
data (same subdivision, then barangay, then city; floor area within 25%;
same type) are added to the Comps sheet marked DRAFT: up to 5 resale, 2
new, and 2 foreclosed. Check each one before relying on it.

### Other commands

| Command | What it does |
|---|---|
| `python -m flip.scenarios --min-profit 300000` | Anchor deal scenarios and max offers |
| `python -m flip.batch data/sample_deals.csv` | Many deals from one CSV, one row per house |
| `python -m flip.tables` | Renovation budgets and loan offers from the sample CSV tables |
| `python -m flip.export` | Excel workbook from the sample CSV tables |

The Excel export has sheets for About (assumptions and definitions),
Summary (with break-even points, yearly ROI, safe-account comparison, and
the verdict), Cost waterfall, Scenarios, Sensitivity, ARV check, and the
inputs. Pesos are formatted, losses are red, and sample data carries a
SAMPLE banner on every sheet.

## Project layout

```
src/flip/
  analyzer.py    analyze(): cost waterfall, net profit, both ROIs for one deal
  scenarios.py   Base / Conservative / Stress, max offer
  batch.py       analyze() across every row of a pandas DataFrame
  tables.py      properties + renovation items + loan offers -> one row per offer
  decision.py    break-even, what matters most, yearly ROI, safe account, verdict
  comps.py       suggested ARV from comparable sales, by kind, with warnings
  market.py      like-for-like screen of every foreclosure; candidates
  pagibig.py     import Pag-IBIG's listings (Online Public Auction JSON or PDF)
  draft.py       draft comps for a house from the market data
  inputs.py      load CSV or Excel input, check it for typing mistakes
  template.py    create the Excel input workbook
  workbook.py    save into the workbook safely: checked, backed up
  editing.py     the Edit page's conversions (rates as %, dates as text)
  listing_text.py  read a pasted listing: kind, numbers, pasalo full price
  export.py      write the formatted Excel report
  app.py         the web app (Streamlit): views/market.py, views/edit.py,
                 views/analyze.py; ui.py has shared pieces; web.py starts it
  charts.py      web app charts, colorblind-safe in light and dark mode
tests/           hand-calculated tests for every module
data/            SAMPLE data (made up, labeled as such)
docs/
  glossary.md          every finance term, explained with the anchor deal
  project-context.md   build order, decisions, and assumptions
```

## Design decisions

- **Tests use hand-calculated numbers, never the code's own output.** Each
  test shows its arithmetic in comments so it can be checked with a
  calculator. A test that copies the code's output would pass even when the
  code is wrong.
- **Both ROIs, always.** ROI on total cost answers "is this a good deal?";
  cash-on-cash ROI answers "is this a good use of my money?". They can
  point in different directions: a bigger loan raises cash-on-cash ROI
  while lowering profit and making losses worse.
- **One calculation, reused everywhere.** Scenarios, batch analysis, loan
  comparisons, max offer, and the Excel export all call the same
  `analyze()`, so a fix in one place fixes every report.
- **Excel shows values, not formulas.** Python is the tested source of
  truth; rewriting the math as Excel formulas would create a second,
  untested copy. The web app follows the same rule: it calls the same
  functions, and its tests check the same hand-calculated numbers.
- **The web app never writes your workbook.** What-if changes live on
  screen and in the downloaded report only.
- **Max offer by binary search over `analyze()`** instead of a separate
  formula, so it stays correct if the cost model changes.
- **Median, not average, for comps,** so one unusual listing can't pull the
  ARV estimate up on its own. Only resale comps count; new units and
  foreclosures bound the estimate instead, and pasalo prices are left out
  because they are usually only the cash-out.
- **Yearly ROI is simple, not compounded** (ROI x 12 / months), matching
  how a savings rate is quoted, so a deal can be compared with a safe
  account.
- **The verdict checks your rules; it doesn't decide for you.** Minimum
  profit, minimum yearly return, and the max-offer rule live on the
  Settings sheet.
- **Purchase price is not a scenario variable.** Once you sign, it is the
  one number you decide. The uncertainty is in sale price, renovation, and
  time; the max offer turns that into a price to negotiate toward.
- **Sample data is always labeled.** Sample files carry a `# SAMPLE DATA`
  line, reports repeat it, and tests enforce it, so made-up numbers can't
  pass as real ones. Real deals (`data/deals_input.xlsx`) are gitignored.

## Limitations

- **Comps are asking prices,** usually higher than final sale prices.
- **Business tax mode uses rates you enter.** By default a sale is taxed
  as a capital asset (6% CGT). A habitual flipper may be taxed as a
  business instead (income tax and possibly VAT); the tool supports that
  per house, but the rates are inputs to confirm with an accountant, not
  built-in rules. Creditable withholding tax is not modeled.
- **Interest is simple interest on the full loan.** Real bank loans usually
  amortize, and loan prepayment penalties are not modeled.
- **Holding, renovation, contingency, and other costs are estimates**
  until replaced with real quotes.
- This is a learning project, not investment advice.

## Terms

New to the finance terms (ARV, cash-on-cash ROI, zonal value, comps)?
See [docs/glossary.md](docs/glossary.md).

## How this was built

A learning and portfolio project, built with
[Claude Code](https://claude.com/claude-code). I set the scope, the cost
waterfall and ROI definitions, the Philippine cost assumptions, and the
hand-calculated anchor deal, and reviewed the calculation code; Claude Code
wrote most of the implementation and tests.
