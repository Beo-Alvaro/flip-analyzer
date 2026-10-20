# House Flip Deal Analyzer (Philippines)

**Find, price, and decide on Pag-IBIG foreclosures before you bid.**

A tool for house flippers in the Philippines. It screens every house on
Pag-IBIG's online auction against similar homes, helps you collect comps
and estimate the costs (renovation, holding, Philippine taxes), and tells
you whether a house meets your own rules, and the most you can bid without
losing money if things go badly.

![The verdict for a real Pag-IBIG townhouse](docs/images/readme/10-verdict.png)

*A real screening: a 42.5 sqm townhouse in Jade Residences, Imus, at
Pag-IBIG's ₱1,184,220 minimum bid (property number left out). With a
bare-shell renovation estimate and paying cash, it would earn ₱87,554, and
the most it could cost to survive a bad case is ₱998,182, below the minimum
bid. Verdict: don't bid, unless the unit turns out to be finished already.*

## Why I built this

In the United States, house flipping is an established business: investors
buy run-down or foreclosed houses, renovate them, and resell within months.
A whole industry supports it, including **"hard money" lenders**: private
lenders and specialized companies that make short-term loans based on a
property's value, often its value after repair, so a flipper can buy and
renovate with borrowed money. Flippers there also share rules of thumb, like
paying at most 70% of the after-repair value, minus the repairs.

In the Philippines, flipping is still small and informal. As far as I could
find, there is no financing built for it: buyers mostly pay cash or use
housing loans meant for people who will live in the house. Yet there is no
shortage of houses: Pag-IBIG auctions thousands of foreclosures, about
1,500 houses in Cavite alone.

So I wanted to answer one question: **can the flipping model work here,
with Philippine prices and costs?** That means Philippine taxes (6% capital
gains tax, about 2.5% transfer costs), Philippine listing habits (pasalo
posts, asking prices with no public record of sale prices), and Pag-IBIG's
auction rules. This tool does the screening a flipper would do, and is
honest about the answer.

## What it does for a flipper

| Step | What the tool does |
|---|---|
| **Find** | Imports every house on Pag-IBIG's [Online Public Auction](https://www.pagibigfundservices.com/OnlinePublicAuction/) (a browser snippet you run once a month) and screens each one **like for like**: against resale and new homes of a similar size and type in the **same subdivision** first. Shows how many foreclosures you would be competing with when you resell, and hides offers that have closed. |
| **Price** | One-click searches for comps (Facebook Marketplace and groups, the listing sites), drafts of the most similar listings it already has, and a **paste reader** that tells resale, new, pasalo, and foreclosed listings apart and fills in their numbers. Works out a **pasalo's real price** (cash-out + what is still owed, checked against the loan terms). Suggests an ARV from resale comps, with new units as the ceiling and foreclosures as the floor. |
| **Cost** | Renovation items with a contingency, holding costs, one-time costs (eviction, back dues), loan offers or cash, and Philippine costs: 6% capital gains tax on the highest of sale price, zonal value, or fair market value; about 2.5% buying costs; 3% broker. A business tax mode for habitual flippers. |
| **Decide** | A **verdict against your own rules** (minimum profit, minimum yearly return, a walk-away price), net profit and both ROIs, what happens if things go wrong (Conservative and Stress), your **walk-away bid** (max offer under Stress), break-even prices, which estimate matters most, and what-ifs. |
| **Keep track** | A due-diligence checklist per house, every number in one Excel workbook (checked and backed up on every save), and a downloadable Excel report. |

It runs on your own computer; your deals stay in a local Excel workbook.

## How to use it

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[web]"
.venv\Scripts\python -m flip.template
.venv\Scripts\python -m flip.web
```

**Step-by-step guide with screenshots: [docs/user-guide.md](docs/user-guide.md)**,
following one real house from the market scan to the verdict. For finding a
listing and its comps by hand, see [docs/how-to-use.md](docs/how-to-use.md).

## A data science project

Behind the app is a small end-to-end data project: collecting messy
real-world listings, cleaning them, building features that make houses
comparable, screening with transparent rules, keeping a human in the loop
where judgment is needed, and validating every number.

| Stage | What it does here |
|---|---|
| **Collect** | A browser snippet that reads Pag-IBIG's auction site (1,538 Cavite properties in one run, 1,482 of them houses), public listings from FazWaz, and comps pasted from Facebook and listing sites. Sites that block automated reading are searched by hand, not scraped. |
| **Clean** | Removes repeated listings (same link, or the same city, kind, price, and size; but never two Pag-IBIG units with different property numbers), lots and condos, floor areas under 25 sqm, and prices per sqm outside ₱10,000–150,000. A pasalo's cash-out is converted to a full price or left out. |
| **Features** | Price per sqm; subdivision names matched across sources ("MICARA ESTATES TANZA PHASE 1" = "Micara Estates"); house type groups; a ±25% size window; how many foreclosures are for sale in each subdivision; offer windows. |
| **Screen** | Transparent rules instead of a black box: compare like for like (same subdivision, similar size and type, resale before new), let new units elsewhere in a city only rule a house *out*, and flag a house at or below 70% of a fair comparison. |
| **Human in the loop** | A rules-based reader classifies pasted listings. Every correction is logged, so its accuracy is measured, not assumed. |
| **Model** | A cost waterfall with Philippine taxes, three scenarios, a sensitivity ranking (tornado chart), break-even prices, and a walk-away bid found by binary search. |
| **Validate** | 247 automated tests, each checking hand-calculated numbers, never the code's own output, and the app tried on real listings. |

### What the data showed (Cavite, October 2026)

- **No foreclosure passed a fair comparison.** Of 1,170 screened houses,
  the 9 that had similar houses in their own subdivision were priced at
  85–115% of new units there: no room left for renovation, costs, and
  profit.
- **Resale prices, not foreclosures, are the bottleneck.** 598 houses had no
  fair comparison at all, because resale prices in their subdivisions simply
  aren't online.
- **Supply is concentrated.** Tanza (532 houses) and Naic (360) hold most of
  the Pag-IBIG stock; one Tanza subdivision had 137 units for sale at once.
  A flipper there would resell against the seller's own cheaper stock.
- **The sale price decides every deal.** In both real screenings below,
  the after-repair value moved the profit more than any other input, and the
  first guess, taken from new-unit prices, was too high.

So far the answer to the question above is: **rarely, at Pag-IBIG's
minimum bids.** The houses that might work are those already in good
condition, where the renovation is small.

## Two real screenings

**Jade Residences, Imus** (the house in the user guide): 42.5 sqm, minimum
bid ₱1,184,220, unoccupied. As a bare shell needing about ₱313,000 of work,
it earns ₱87,554 paying cash and loses ₱190,688 if things go badly; the
walk-away bid is ₱998,182. It meets the rules only if it needs about
₱100,000 of work or less.

**An occupied townhouse in Imus**: 92 sqm, minimum bid ₱2,267,730, title
still under consolidation. Replacing each guess with researched numbers, one
at a time (cash purchase):

| Step | Change | Net profit |
|---|---|---|
| Start | All placeholder guesses | +543,577 |
| 1 | ARV from 4 resale comps (median ₱34,750/sqm x 92 sqm = ₱3,197,000) | -5,153 |
| 2 | Holding period 15 months (eviction case + renovation + sale) | -20,153 |
| 3 | Monthly holding cost ₱4,000 | -5,153 |
| 4 | Renovation ₱550,000 + legal costs for eviction ₱90,000 | **-115,153** |

The first ARV guess came from brand-new developer units; real resale comps
were 16% lower, and that single input erased the profit.

## The math, checked by hand

Every calculation is tested against one hand-calculated deal: a ₱2,800,000
house, renovated for ₱450,000, held 6 months, sold for ₱4,200,000, with a
70% loan at 9%.

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
the deal to break-even. To survive the Stress scenario, the offer should be
at most ₱2,514,799, about ₱285,000 below asking. (The US 70% rule of thumb
would say ₱2,490,000.)

## Honest limits

- **Listing prices are asking prices.** The Philippines has no public record
  of actual sale prices, so comps run a little high.
- **Costs are estimates until they are quotes.** The renovation figures from
  cost guides are ballpark (roughly ±25–30%); inspect and get a contractor's
  quote before bidding.
- **A pasalo's balance is an estimate** from the stated terms; the lender's
  statement of account is the real number.
- **The market data is only as fresh as your last collector run.** Sites
  that block automated reading (Facebook, Lamudi, OnePropertee) are searched
  by you, not scraped.
- **Business tax mode uses rates you enter.** By default a sale is taxed as
  a capital asset (6% CGT). A habitual flipper may be taxed as a business
  instead (income tax and possibly VAT); confirm the rates with an
  accountant. Creditable withholding tax is not modeled.
- **Interest is simple interest on the full loan.** Real loans amortize, and
  prepayment penalties are not modeled.
- **The verdict checks your rules; it doesn't decide for you.** This is a
  learning project, not investment advice.

## For developers

### Setup and tests

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

### Without the web app

The workbook can be filled in Excel and every report run from the terminal:

```bash
python -m flip.template                                  # create data/deals_input.xlsx
python -m flip.template --upgrade data/deals_input.xlsx  # add new sheets and columns, keep data
python -m flip.tables --input data/deals_input.xlsx      # print each house's report
python -m flip.export --input data/deals_input.xlsx      # write the Excel report
```

Every column header in the workbook has a note explaining it. Replace the
SAMPLE rows with your houses and set **Data type** to REAL on the
Instructions sheet. Typing mistakes are caught before anything is
calculated, with the exact row to fix:

```
Please fix these in your input:
  - Properties row 2 (SAMPLE-01): purchase_price must be a number, got '2.8M'
  - Loan offers row 2 (SAMPLE-01): annual_interest_rate is 9. Did you mean 9%? Type it as 9% or 0.09.
  - Comps row 2 (SAMPLE-1): deal_id SAMPLE-1 is not on the Properties sheet (typo?)
```

### Market data from the terminal

```bash
python -m flip.pagibig data/market/opa_listings.json     # import the collector's file
python -m flip.market data/market/cavite_listings.csv --output output/cavite_market.xlsx --workbook data/deals_input.xlsx
python -m flip.draft TANZA-01                            # draft comps for one house
```

- `flip.pagibig` imports the file saved by
  [docs/pagibig-opa-collector.js](docs/pagibig-opa-collector.js): every
  house with its price, floor and lot area, occupancy, sale type, and offer
  window. Lots, condos, and parking slots are skipped; a property already in
  the file is replaced, and houses no longer listed are removed (only for
  cities in the new file, so a run that stopped early can't wipe out the
  rest). Older PDF lists import the same way.
- `flip.market` writes the market report: medians per city by kind, a
  **Foreclosures** sheet with each house's like-for-like comparison, and the
  **Candidates**. `--workbook` adds the resale and new comps you entered.
  `data/market/cavite_listings.csv` holds about 1,500 public Cavite listings
  (FazWaz plus every Pag-IBIG house), facts and links only.
- `flip.draft` adds the most similar listings to a house's comps, marked
  DRAFT (same subdivision, then barangay, then city; floor area within 25%;
  same type group; up to 5 resale, 2 new, 2 foreclosed).

### Other commands

| Command | What it does |
|---|---|
| `python -m flip.scenarios --min-profit 300000` | Anchor deal scenarios and max offers |
| `python -m flip.batch data/sample_deals.csv` | Many deals from one CSV, one row per house |
| `python -m flip.tables` | Renovation budgets and loan offers from the sample CSV tables |
| `python -m flip.export` | Excel workbook from the sample CSV tables |

### Project layout

```
src/flip/
  analyzer.py      analyze(): cost waterfall, net profit, both ROIs for one deal
  scenarios.py     Base / Conservative / Stress, max offer
  batch.py         analyze() across every row of a pandas DataFrame
  tables.py        properties + renovation items + loan offers -> one row per offer
  decision.py      break-even, what matters most, yearly ROI, safe account, verdict
  comps.py         suggested ARV from comparable sales, by kind, with warnings
  market.py        like-for-like screen of every foreclosure; candidates
  pagibig.py       import Pag-IBIG's listings (Online Public Auction JSON or PDF)
  draft.py         draft comps for a house from the market data
  find_comps.py    one-click comp searches
  listing_text.py  read a pasted listing: kind, numbers, pasalo full price
  paste_log.py     keep score of the listing reader's guesses
  inputs.py        load CSV or Excel input, check it for typing mistakes
  template.py      create the Excel input workbook
  workbook.py      save into the workbook safely: checked, backed up
  editing.py       the Edit page's conversions (rates as %, dates as text)
  export.py        write the formatted Excel report
  app.py           the web app (Streamlit): views/market.py, views/edit.py,
                   views/analyze.py; ui.py has shared pieces; web.py starts it
  charts.py        web app charts, colorblind-safe in light and dark mode
tests/             hand-calculated tests for every module
data/              SAMPLE data (made up, labeled as such) and public market data
docs/
  user-guide.md        the app, step by step, with screenshots
  how-to-use.md        finding a listing and its comps by hand
  glossary.md          every finance term, explained with the anchor deal
  project-context.md   build order, decisions, and assumptions
```

### Design decisions

- **Tests use hand-calculated numbers, never the code's own output.** Each
  test shows its arithmetic in comments so it can be checked with a
  calculator. A test that copies the code's output would pass even when the
  code is wrong.
- **Both ROIs, always.** ROI on total cost answers "is this a good deal?";
  cash-on-cash ROI answers "is this a good use of my money?". They can
  point in different directions: a bigger loan raises cash-on-cash ROI
  while lowering profit and making losses worse.
- **One calculation, reused everywhere.** Scenarios, batch analysis, loan
  comparisons, max offer, the web app, and the Excel export all call the
  same `analyze()`, so a fix in one place fixes every report.
- **Excel holds values, not formulas.** Python is the tested source of
  truth; rewriting the math as Excel formulas would create a second,
  untested copy.
- **The web app saves only through one guarded path** (`workbook.py`): it
  refuses while Excel has the file open, writes a copy that must pass the
  same input checks as the reports, backs up the original, then replaces
  it. What-if numbers are never saved.
- **Like for like before cheap.** A foreclosure is compared with similar
  houses in its own subdivision first. New units elsewhere in a city can
  only rule a house out, never in: they are often in pricier subdivisions.
- **Median, not average, for comps,** so one unusual listing can't pull the
  ARV estimate up on its own. Only resale comps count; new units and
  foreclosures bound the estimate instead, and pasalo prices are converted
  to a full price or left out.
- **Max offer by binary search over `analyze()`** instead of a separate
  formula, so it stays correct if the cost model changes.
- **Yearly ROI is simple, not compounded** (ROI x 12 / months), matching
  how a savings rate is quoted, so a deal can be compared with a safe
  account.
- **Purchase price is not a scenario variable.** Once you sign, it is the
  one number you decide. The uncertainty is in sale price, renovation, and
  time; the max offer turns that into a price to bid toward.
- **Private data stays private.** Real deals (`data/deals_input.xlsx`), its
  backups, and the reader's score log are gitignored; pasted listing text is
  never stored; sample files carry a `# SAMPLE DATA` line that tests
  enforce.

## Terms

New to the finance terms (ARV, cash-on-cash ROI, zonal value, comps,
pasalo)? See [docs/glossary.md](docs/glossary.md).
