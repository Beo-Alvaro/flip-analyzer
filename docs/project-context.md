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
Single web app for the whole cycle (user chose option A: the app saves
into deals_input.xlsx, Excel stays the source of truth). Phase 1 done:
app.py is now a router (st.navigation) with views/market.py (refresh
Pag-IBIG via the collector file, filter the screened foreclosures, Start
a deal) and views/analyze.py (the former app, still read-only, what-ifs
never saved). Every save goes through flip.workbook: refused while Excel's
~$ lock file exists, written to a copy that must pass load_excel_inputs,
original backed up to a backups/ folder next to it (gitignored), then
replaced. Offer windows: notes carry the collector's full date text;
offer_closes is blank for rows imported with only a start date.
Phase 2 done: views/edit.py (Edit a house): House tab (Properties
fields) + data editors for Renovations, Other costs, Loan offers, Comps
(live suggested ARV), Checklist (standard items prefilled when empty).
flip.editing converts rates to % and dates to text and back, so untouched
tables round-trip unchanged (verified on the real workbook: one edited
cell = one changed cell). One Save writes only changed fields and tables
via workbook.save_house; a house's rows are replaced in place and other
houses' cells are kept as they were. Formulas in the tables block saving
(openpyxl can't recalculate them). The House picker follows you across
pages (session key current_deal).
Phase 3 done: flip.listing_text reads a pasted post (kind from the
how-to-use signs, pasalo first; labeled amounts only right after their
label; areas as whole words; "50/60 lot/hse"); payments_left + loan_balance
(present value of the payments left, annual rate / 12) give a pasalo's full
price. Edit page Comps tab: Paste a listing; Add as a comp saves at once,
so it waits for other unsaved changes; a pasalo is recorded as resale at the
chosen full price (default the lower, more cautious one) with a condition
note. The pasted text is never saved. Comps feed the scan without copying:
market.comps_as_listings (resale and new only, city from the house, SAMPLE
deals skipped) via scan(path, extra); the Market page includes them by
default, the CLI with --workbook.
Comp-finding helpers (user-approved recommendation: semi-automated, since
the resale-rich sites block automated reading or need a login): Comps tab
panels Find comps online (flip.find_comps: Facebook Marketplace/posts
and Google site: searches, opened in the user's own browser), Draft from
the market data (draft.new_drafts + comp_row; the flip.draft CLI now
saves through flip.workbook too), and Paste listings (several posts split
on a --- line, reviewed as rows). flip.paste_log keeps score per added
pasted comp (guessed vs chosen kind; price/floor/lot kept, changed, added,
missing) in data/paste_log.csv (gitignored, no listing text); the page
shows the scores. Checklist: no longer auto-prefilled (it counted as an
unsaved change forever and blocked adding comps); an "Add the 8 standard
items" button saves them instead.
Collector verified by the user 2026-10-18: 1,538 properties, 1,482 houses
(477 unoccupied), every row with its offer closing date.
Jade (IMUS-02) lessons, fixed 2026-10-18: (1) the Start-a-deal hint showed
the city's new-unit median (66,667/sqm, P2,833,333 for 42.5 sqm) and it was
typed in as the ARV; the form now shows a visible ARV guide built from new
compare_foreclosures columns subdivision_{resale,new}_{listings,per_sqm}
(similar size and type, even 1 listing), city figure labeled a maximum.
(2) A house with no loan offers silently got 70% at 9%: Start a deal now
adds a Cash offer (tick box), and Analyze shows a note on default terms
(text built from analyze()'s defaults). (3) pagibig.remove_unlisted drops
earlier OPA rows no longer listed, only for cities in the new file.
Jade verdict with a bare-shell estimate (P313,000, 11 items marked
estimate): fails (profit 23,311 on loan / 87,554 cash); passes only if the
unit needs about P100,000 or less. Decision rests on the unit's condition.

## Market scan (flip.market)
data/market/cavite_listings.csv: ~340 public listings collected
2026-10-16 (FazWaz city pages for new/resale; ForeclosurePhilippines
page 1 and acquiredassets.info for Pag-IBIG; other pages and Lamudi/Dot
Property/OnePropertee block automated reading). Facts and links only.
Rules: repeats removed (same link, or same city/kind/price/floor area);
unknown kind, pasalo, no floor area, floor < 25 sqm, or price per sqm
outside 10,000-150,000 left out of medians. Benchmark = resale median if
>= 3 resale, else new median if >= 3 new (a ceiling), else none.
Candidates = foreclosures <= 70% of their city's benchmark.
Automation (user-approved options 1 and 2): flip.pagibig imports
Pag-IBIG's official tranche PDFs (pdfplumber; 11 columns: item, property
number, location "Subdivision - Blk/Lot - Brgy. X, City, Province", type,
TCT, lot area, floor area, minimum bid, appraisal date, GMI, remarks);
links stored as "pagibig:<property number>"; replaces rows for the same
property number. Tested on SPB 321 (Apr 2024): 195 Cavite houses.
Pag-IBIG has since STOPPED publishing PDFs; listings are only on the
Online Public Auction site (pagibigfundservices.com/OnlinePublicAuction),
searchable one city at a time, 10 cards per page, three tabs (1st auction,
2nd auction, negotiated sale), no export. docs/pagibig-opa-collector.js is
a console snippet the user runs there (reads only, paced); flip.pagibig
imports its JSON. Its occupancy/floor filters don't apply via script, so it
collects everything and the import skips lots/condos.
flip.draft drafts comps into the Comps sheet from the market data using
new Properties columns city/barangay/subdivision/type. Scraping sites that
block automated reading was ruled out.
Finding: online Cavite listings are mostly developer units (8 confirmed
resales of ~300); Tanza and Trece Martires foreclosures sit at 74-81% of
new-unit prices (little room); Imus, Dasmarinas, Bacoor look cheaper vs
new units but much less so vs their few resales (70-79%).
OPA import 2026-10-17: 1,159 Cavite houses (375 unoccupied; 389 1st
auction, 171 2nd auction, 599 negotiated sale). Supply is concentrated
(Tanza 532, Naic 360; Westdale Villas alone 137). Flaw found: most cities
have < 3 resales, so the benchmark falls back to the new-unit median from
pricier subdivisions, and the screen flags 469 "candidates". Same-
subdivision checks (where they exist) show foreclosures at 72-109% of
other listings.
Fix (user-approved): each foreclosure is compared like for like:
same-subdivision resale, then same-subdivision new (>= 2 listings,
floor area within 25%, same type group, rules shared with flip.draft),
then city resale (>= 3), then city new, which can only rule out (a
ceiling from pricier subdivisions proves nothing when far below it).
Subdivision names match after dropping case, phase numbers, "The",
"Subdivision", the city's name, plurals; a 2+ word name matches its
sections. Distinct Pag-IBIG property numbers are never merged as repeats
(25 Westdale units share one price). Foreclosures sheet + supply column.
Result 2026-10-17: 0 candidates; 572 little room (incl. all 9 with a
same-subdivision comparison, 85-115% of new); 598 no fair comparison
(133 of them unoccupied): the next step there is hand-collected resale
prices per subdivision.
Resale search 2026-10-17 (Lumina Tanza, Palmerston, Jade Residences,
Pagsikat Place): no confirmed owner resale on readable sites; only
developer prices and pasalo posts (resales are on Facebook/Lamudi/
OnePropertee, which block automated reading). Added 4 developer prices
(new) and 6 Lumina FazWaz feed listings (unknown: seller type not stated).
By hand: Pagsikat minimum bids 1.27-1.30M exceed the developer's 1.2M new
44 sqm unit (skip); Jade 42.5 sqm 2nd-auction bid 1,184,220 = 64% of the
developer's RFO price per sqm (only lead; needs resale prices).
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