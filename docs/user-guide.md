# User guide: from a Pag-IBIG listing to a decision

This guide follows one real house through the app: a 42.5 sqm townhouse in
Jade Residences, Imus, at a Pag-IBIG auction (property number left out). It
takes you from the market scan to the verdict in ten steps.

For finding a listing and its comps by hand, with the Excel workbook, see
[how-to-use.md](how-to-use.md). New to a term? See the
[glossary](glossary.md).

> The analyzer checks a deal against your own rules. It is not investment
> advice, and its answers are only as good as the numbers you give it.

---

## 1. Install and start

Requires Python 3.11+. In the project folder:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[web]"
.venv\Scripts\python -m flip.template
.venv\Scripts\python -m flip.web
```

`flip.template` creates your workbook (`data/deals_input.xlsx`) once;
`flip.web` opens the app in your browser at http://localhost:8501. (On
macOS or Linux, use `.venv/bin/python`.) The app has three pages, in the
order of a deal: **Market scan**, **Edit a house**, **Analyze a house**.

## 2. Refresh Pag-IBIG's listings (once a month)

![Refresh Pag-IBIG listings](images/readme/01-refresh.png)

Pag-IBIG has no download button, so the app gives you a small snippet: open
the auction site, choose the region and province, paste the snippet into
the browser's console (F12), and it reads every city's listings and saves
them to a file (about 10 minutes for Cavite). Upload that file and press
**Import**. It only reads the pages; it never logs in or bids. Houses no
longer listed are removed, and each house keeps its offer window.

The first time, the browser blocks pasting into the console: type
`allow pasting`, press Enter, then paste again.

## 3. Screen the foreclosures

![Market scan: every foreclosure, screened](images/readme/02-market-scan.png)

Every foreclosure gets one of three results:

- **Worth a closer look**: at or below 70% of similar houses.
- **Little room**: close to what similar houses cost, even new ones. Skip.
- **No fair comparison**: cheaper than new units elsewhere in the city, but
  there is nothing similar to compare it with yet. Collect resale prices
  from its subdivision first.

Filter by city, unoccupied, open offers, price, and how many are for sale
in the same subdivision (your competition when you resell). Jade showed
*no fair comparison*: the only prices the data had were new units.

## 4. Start a deal

![Start a deal, with the ARV guide](images/readme/03-start-a-deal.png)

Pick the house; its price, size, and location are filled in. The **ARV
guide** puts the subdivision's own prices first: new Jade units cost about
₱43,480 per sqm (₱1,847,900 for this size), a *ceiling* for a renovated used
unit. The city's new-unit median (₱2,833,333 here) is labeled as only a
maximum, because those units are often in pricier subdivisions. **Add to my
workbook** also adds the standard checklist and a Cash offer, so no loan is
assumed.

## 5. Fill in the house

![Edit a house](images/readme/04-edit-house.png)

**Edit a house** has one tab per part of the deal: the house's numbers,
renovations, other costs, loan offers, comps, and the checklist. One **Save
changes** button saves only what you changed; the workbook is backed up
first, and nothing is saved while it is open in Excel.

**Monthly holding cost** is what the house costs you each month until it
sells: association dues, utilities, and property tax (divided by 12). Loan
interest is not part of it; the app works that out from your loan offers.

## 6. Find comps

![One-click searches](images/readme/06-find-comps.png)

**Find comps online** opens ready-made searches for the subdivision in your
own browser, where you are logged in. **Draft from the market data** lists
the most similar listings the app already has, to tick and add.

![Paste a listing](images/readme/07-paste-read.png)

**Paste listings** reads a post's text (or several, separated by a `---`
line). It says what kind of listing it looks like and shows the phrases that
gave it away, then fills in the numbers it found. Only the fields you
confirm are saved, never the pasted text, which can hold names and phone
numbers. It also keeps score of how often its guesses were right.

Check the **floor area** in particular: it is the house's space on all
floors, not the lot. A two-storey townhouse usually has more floor area than
lot area.

![Pasalo full price](images/readme/08-pasalo-price.png)

A **pasalo**'s listed price is only the cash-out. This Jade seller asked
₱1.1M cash-out and said ₱400,000 was left on the loan, but 81 more payments
of ₱17,000 at 24% a year come to about ₱679,075. The app shows both full
prices and records the more cautious one.

![Comps and the suggested ARV](images/readme/05-comps.png)

The **suggested ARV** is the median resale price per sqm × the house's floor
area. With one resale comp it warns you: 3 to 5 make a steadier estimate.
Update your ARV on the House tab once the comps are in.

## 7. Renovation and payment

![Renovation estimate](images/readme/09-renovations.png)

One row per item. Jade's ₱313,000 is a bare-shell estimate built from
Philippine contractor cost guides (marked *estimate*, to replace with
quotes); the app adds a 10% contingency. Add your loan offers next to the
Cash row to compare them; with no offers at all, the app assumes a 70% loan
at 9% and says so.

## 8. Read the verdict

![The verdict and the key figures](images/readme/10-verdict.png)

**Analyze a house** checks the deal against your Settings (by default: at
least ₱200,000 profit, a 15% yearly cash-on-cash return, and a price within
the Stress max offer):

- **Net profit**, **ROI on total cost** (is it a good deal?), and
  **cash-on-cash ROI** (is it a good use of my money?).
- **Stress profit**: if it sells 10% lower, renovation runs 25% over, and it
  takes your worst-case months.
- **Max offer (Stress)**: your walk-away bid. Jade's is ₱998,182, below the
  ₱1,184,220 minimum bid.
- **Break-even sale and purchase prices.**

## 9. Understand the risk

![If things go wrong, and what matters most](images/readme/11-charts.png)

**If things go wrong** shows the profit as planned and in two bad cases:
Jade goes from ₱87,554 to −₱42,960 (Conservative) and −₱190,688 (Stress).
**What matters most** shows which estimate swings the profit most: for Jade,
the sale price. Selling for 10% less turns the profit into a loss, so more
resale comps matter far more than getting the monthly dues exact. A
**What-if** panel tries other numbers without saving them.

## 10. Verify, then bid

Work through the house's checklist (title, occupants, dues, flood risk,
inspection...) and download the Excel report for your records. For Jade,
the numbers pass your rules only if the unit needs about ₱100,000 of work or
less, so the next step was its photos and a viewing, not a bid.
