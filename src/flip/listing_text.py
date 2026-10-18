"""Read a pasted listing: what kind it is, and the numbers in it.

Listings on Facebook and listing sites are free text. read_listing() looks
for the signs from docs/how-to-use.md ("how to spot a resale") and pulls out
the numbers it can find. Everything it returns is a suggestion to check;
the pasted text itself is never saved.

For a pasalo (the buyer takes over the seller's loan), the listed price is
only the cash-out. The full price is cash-out + what is still owed, and
loan_balance() checks the seller's balance figure against the loan terms.
"""

import re
from datetime import date

import pandas as pd

# Phrases that give a listing's kind away, as in docs/how-to-use.md
SIGNS = {
    "pasalo": ["pasalo", "assume balance", "assumed by the buyer", "to be assumed",
               "assumption of", "cash out", "cash-out", "cashout", "remaining balance"],
    "foreclosed": ["foreclosed", "acquired asset", "minimum bid", "bank-owned", "ropa"],
    "new": ["total contract price", "tcp", "reservation fee", "reserve your", "downpayment",
            "down payment", "pre-selling", "preselling", "ready for occupancy", "rfo",
            "re-open", "reopen", "site viewing", "tripping", "required monthly salary",
            "required income", "gmi", "in-house financing"],
    "resale": ["clean title", "title in my name", "own name", "updated tax", "tax paid",
               "fully paid", "cash basis", "direct owner", "owner selling", "selling my",
               "renovated", "with improvements"],
}
TYPES = [("single detached", "single detached"), ("single attached", "single attached"),
         ("quadruplex", "quadruplex"), ("duplex", "duplex"), ("town house", "townhouse"),
         ("townhouse", "townhouse"), ("row house", "rowhouse"), ("rowhouse", "rowhouse")]
CONDITIONS = [("brand new", "brand new"), ("renovated", "renovated"),
              ("fully furnished", "furnished"), ("furnished", "furnished"),
              ("bare", "bare (not finished)")]
AMOUNT = r"(?:₱|php|p)?\s*(\d[\d,]*(?:\.\d+)?)\s*(million|mil|m|k)?\b"
SQM = r"\s*(?:sq\.?\s*m|sqm|square)"
SCALE = {"k": 1_000, "m": 1_000_000, "mil": 1_000_000, "million": 1_000_000}


def money(text: str) -> float | None:
    """₱2,124,000 -> 2124000; 1.1m -> 1100000; 400k -> 400000; 2.5 million -> 2500000."""
    found = re.search(AMOUNT, str(text).lower())
    if not found:
        return None
    return float(found.group(1).replace(",", "")) * SCALE.get(found.group(2) or "", 1)


def _has(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", text) is not None


def classify(text: str) -> tuple[str, dict[str, list[str]]]:
    """The kind the text points to ("" when unsure) and the phrases found per kind.

    A pasalo sign wins: its price is only the cash-out even when the post also
    sounds like an owner selling. Then foreclosed. Then new or resale, by
    which has more signs.
    """
    lower = text.lower()
    found = {kind: [p for p in phrases if _has(lower, p)] for kind, phrases in SIGNS.items()}
    if found["pasalo"]:
        kind = "pasalo"
    elif found["foreclosed"]:
        kind = "foreclosed"
    elif len(found["new"]) != len(found["resale"]):
        kind = "new" if len(found["new"]) > len(found["resale"]) else "resale"
    else:
        kind = ""
    return kind, {k: v for k, v in found.items() if v}


def _labeled(lines: list[str], labels: list[str]) -> float | None:
    """The first amount written right after one of the labels ("Cash Out: ₱1.1m").
    Only separators may come between: in "Start of amortization: August 16, 2018"
    the 16 is not an amount."""
    for label in labels:
        pattern = re.compile(r"(?<![a-z])" + re.escape(label) + r"(?![a-z])[\s:=\-–(]*"
                             + AMOUNT)
        for line in lines:
            found = pattern.search(line)
            if found:
                return float(found.group(1).replace(",", "")) * SCALE.get(found.group(2) or "", 1)
    return None


def _area(lower: str, labels: str) -> float | None:
    """An area in sqm after one of the labels (whole words only: "villa 36 sqm" is
    not a lot area)."""
    found = re.search(r"(?<![a-z])(?:" + labels + r")\s*[:\-=]?\s*(\d+(?:\.\d+)?)" + SQM, lower)
    return float(found.group(1)) if found else None


def read_listing(text: str) -> dict:
    """Everything that can be read from a pasted listing; missing items are None."""
    lower = text.lower()
    lines = lower.splitlines()
    kind, signs = classify(text)

    floor = _area(lower, r"floor area|floor|house area|hse|fa")
    lot = _area(lower, r"lot area|lot|la")
    both = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*(?:sq\.?\s*m|sqm)?\s*"
                     r"(?:lot|la)\s*/\s*(?:hse|house|floor|fa)", lower)  # "50/60 lot/hse sqm"
    if both:
        lot, floor = float(both.group(1)), float(both.group(2))

    monthly = _labeled(lines, ["monthly amortization", "amortization"])
    if monthly is None:
        found = re.search(r"(\d[\d,]*(?:\.\d+)?\s*k?)\s*(?:monthly|a month|per month|/\s*mo)",
                          lower)
        monthly = money(found.group(1)) if found else None
    rate = re.search(r"interest(?: rate)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*%", lower)
    term = re.search(r"(\d+)\s*months?\s*\(\s*\d+\s*years?\s*\)|term[^\d\n]{0,30}(\d+)\s*months",
                     lower)
    start = re.search(r"start[^\n:]*[:\-]\s*([a-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})", lower)
    started = None
    if start:
        try:
            started = pd.Timestamp(start.group(1).replace(".", "")).date()
        except ValueError:
            pass

    return {
        "kind": kind,
        "signs": signs,
        "price": _labeled(lines, ["total contract price", "tcp", "selling price", "price",
                                  "asking"]),
        "floor_area_sqm": floor,
        "lot_area_sqm": lot,
        "type": next((name for word, name in TYPES if _has(lower, word)), None),
        "condition": next((name for word, name in CONDITIONS if _has(lower, word)), None),
        "cash_out": _labeled(lines, ["cash out", "cash-out", "cashout"]),
        "balance": _labeled(lines, ["remaining balance", "balance"]),
        "monthly": monthly,
        "annual_rate": float(rate.group(1)) / 100 if rate else None,
        "term_months": int(term.group(1) or term.group(2)) if term else None,
        "payments_started": started,
    }


SEPARATOR = re.compile(r"^\s*(?:-{3,}|={3,})\s*$", re.MULTILINE)
PASALO_NOTE = "pasalo: cash-out + the seller's balance figure, unconfirmed"


def split_posts(text: str) -> list[str]:
    """Several pasted posts, separated by a line of --- (or ===)."""
    return [post.strip() for post in SEPARATOR.split(text) if post.strip()]


def suggested_comp(found: dict) -> dict:
    """The comp a post suggests (from read_listing): its kind and numbers.

    A pasalo's price is its full price when both the cash-out and the
    seller's balance are in the post (cash-out + balance, the cautious
    figure); otherwise it is left blank for you to fill in.
    """
    price, note = found["price"], ""
    if found["kind"] == "pasalo":
        has_both = found["cash_out"] is not None and found["balance"] is not None
        price = found["cash_out"] + found["balance"] if has_both else None
        note = PASALO_NOTE
    return {"kind": found["kind"], "price": price, "floor_area_sqm": found["floor_area_sqm"],
            "lot_area_sqm": found["lot_area_sqm"], "type": found["type"],
            "condition": found["condition"], "note": note}


def payments_left(started: date, term_months: int, today: date) -> int:
    """Monthly payments still to make, one a month on the day payments started.
    Started 2018-08-16, 180 months, on 2026-10-18: 99 made (Aug 2018 to Oct
    2026), 81 left."""
    made = (today.year - started.year) * 12 + (today.month - started.month)
    made += 1 if today.day >= started.day else 0
    return max(term_months - max(made, 0), 0)


def loan_balance(monthly: float, annual_rate: float, payments: int) -> float:
    """What is still owed: today's value of the payments left (a fixed monthly
    payment at annual_rate / 12 a month)."""
    if payments <= 0:
        return 0.0
    r = annual_rate / 12
    if r == 0:
        return monthly * payments
    return monthly * (1 - (1 + r) ** -payments) / r
