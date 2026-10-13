# Glossary — House Flip Deal Analyzer

Plain-language definitions of the terms used in this project, explained
through the anchor deal (see project-context.md). All amounts are in PHP.

## The anchor deal

A single example property whose numbers were calculated by hand in
advance. It is the project's answer key: `analyze()` must reproduce these
numbers exactly, and every later feature is checked against it.

## Buying the property

| Term | Anchor deal | Meaning |
|---|---|---|
| Purchase price | 2,800,000 | What you pay the seller. |
| Acquisition costs | 70,000 | Government fees to transfer the title to you: documentary stamp tax (1.5%) plus transfer tax and registration (~1%), so ~2.5% of the price. |

## Financing (the loan)

| Term | Anchor deal | Meaning |
|---|---|---|
| Loan ratio | 70% | Share of the purchase price the bank lends: 2,800,000 × 70% = 1,960,000. |
| Down payment | 840,000 | The remaining 30% of the price, paid with your own money. |
| Interest | 88,200 | The bank's charge for lending, 9% per year. For 6 months: 1,960,000 × 9% × 6/12. |
| Loan fee | 19,600 | One-time 1% processing charge for setting up the loan. |
| Leverage | n/a | Using borrowed money to buy. It raises returns on your own cash, but it also magnifies losses, because the bank must be repaid even if the sale goes badly. |

## Renovating and holding

| Term | Anchor deal | Meaning |
|---|---|---|
| Renovation cost | 450,000 | Repairs and improvements. |
| ARV (After Repair Value) | 4,200,000 | The expected selling price after renovation. This is the most important estimate in the model. |
| Comps (comparables) | n/a | Similar renovated properties nearby, used to estimate ARV. Stored in `data/comps.csv`. |
| Holding period | 6 months | How long you own the property, from purchase to sale. |
| Holding costs | 90,000 | Ongoing costs of owning the property: utilities, association dues, real property tax, security. 15,000/month × 6. |

## Selling

| Term | Anchor deal | Meaning |
|---|---|---|
| Broker commission | 126,000 | 3% of the selling price, paid to the agent who sells the property. |
| Capital gains tax (CGT) | 252,000 | 6% tax paid by the seller on a property sale. |
| Zonal value | n/a | The BIR's (Bureau of Internal Revenue) official value per area. |
| Fair market value | n/a | The local assessor's value on the tax declaration. |
| CGT base | 4,200,000 | The amount CGT is charged on: the **highest** of selling price, zonal value, or fair market value. If zonal value is above your price, you pay tax on money you never received. |
| Selling costs | 378,000 | Broker commission + CGT. Paid out of the buyer's money at closing. |

## Results

| Term | Anchor deal | Meaning |
|---|---|---|
| Total cost | 3,895,800 | Everything spent, by you and the bank together: purchase + acquisition + renovation + interest + loan fees + holding + selling. |
| Net profit | 304,200 | ARV − total cost. |
| Cash invested | 1,557,800 | Your own money out of pocket: down payment + acquisition + renovation + interest + loan fees + holding. Selling costs are excluded because they come out of the sale proceeds. |
| ROI on total cost | ~7.81% | Net profit ÷ total cost. Answers: *is this a good deal?* |
| Cash-on-cash ROI | ~19.53% | Net profit ÷ cash invested. Answers: *is this a good use of my own money?* |

Both ROIs cover the whole holding period. They are not annual rates.

### Checking the profit by following the money

| Step | PHP |
|---|---|
| Buyer pays you | 4,200,000 |
| − Selling costs | −378,000 |
| − Repay the bank's loan | −1,960,000 |
| = Back in your hands | 1,862,000 |
| − Your cash invested | −1,557,800 |
| **= Net profit** | **304,200** |

## Analysis terms

| Term | Meaning |
|---|---|
| Edge case | An unusual input where code tends to break: no loan, a long holding period, a sale at a loss. |
| Scenario analysis | Running the same property under several outlooks. **Base** is the best guess, **Conservative** is somewhat worse, and **Stress** is a bad case (renovation overrun, lower ARV, longer hold). |
| 70% rule | A US rule of thumb: maximum purchase price = 70% × ARV − renovation. Anchor deal: 0.70 × 4,200,000 − 450,000 = 2,490,000, so the 2,800,000 price fails it. Used here only as a warning sign, not a decision rule, because PH costs differ from US costs. |

## Philippine tax note: capital vs. ordinary asset

The 6% CGT applies when the property is a **capital asset**, for example
an individual selling a property occasionally. If the seller is in the
business of flipping, the BIR treats the property as an **ordinary
asset** (like a store's inventory). The sale is then subject to regular
income tax with creditable withholding tax, and possibly VAT
(value-added tax), instead of CGT. This is why `cgt_rate` is an input
rather than a fixed number. Verify the treatment (RR 7-2003) before
relying on it.
