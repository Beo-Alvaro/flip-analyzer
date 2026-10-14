"""Create the Excel input workbook: one sheet per table, a note on every column.

Run `python -m flip.template` to create data/deals_input.xlsx. It starts
with the anchor deal as an example (Data type: SAMPLE). Replace the example
rows with your own houses, set Data type to REAL, then run
`python -m flip.export --input data/deals_input.xlsx`.
"""

import argparse
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROWS = 500  # rows that get number formats and typing checks
DATA_TYPE_CELL = "B3"
YELLOW = PatternFill("solid", fgColor="FFEB9C")

SAME_ID = "Must match a deal_id on the Properties sheet."

# Sheet -> [(column, note shown on the header, kind)]
SHEET_COLUMNS = {
    "Properties": [
        ("deal_id", "Short ID for the house, e.g. IMUS-01. Use the same ID on every "
                    "sheet to link its renovations, loan offers, and comps.", "text"),
        ("description", "A few words to recognize the house, e.g. 'Hacienda La Joya "
                        "townhouse, Pag-IBIG auction'.", "text"),
        ("purchase_price", "Price you expect to pay, in pesos: the asking price or your bid.",
         "pesos"),
        ("arv", "After Repair Value: what you expect it to sell for once renovated, in "
                "pesos. Base it on your comps; the report shows a suggested ARV next to "
                "yours.", "pesos"),
        ("holding_months", "Months from buying to selling. Include title transfer, "
                           "renovation, and time to find a buyer.", "months"),
        ("monthly_holding_cost", "Cost of owning it per month, in pesos: association "
                                 "dues, utilities, real property tax / 12, security.", "pesos"),
        ("zonal_value", "Optional. BIR zonal value of the property (zonal value per sqm x "
                        "lot area). Leave blank if unknown.", "pesos"),
        ("fair_market_value", "Optional. Fair market value on the tax declaration (ask the "
                              "seller). Leave blank if unknown.", "pesos"),
        ("floor_area_sqm", "Floor area in sqm. Used with your comps to suggest an ARV.", "sqm"),
        ("source_url", "Optional. Link to the listing.", "text"),
    ],
    "Renovations": [
        ("deal_id", SAME_ID, "text"),
        ("item", "What will be done, e.g. Roof repair, Kitchen.", "text"),
        ("cost", "Estimated cost in pesos. Use contractor quotes when you have them.", "pesos"),
    ],
    "Loan offers": [
        ("deal_id", SAME_ID, "text"),
        ("offer", "Name of the offer, e.g. Bank A or Pag-IBIG. Add a row named Cash with "
                  "0% to compare buying with cash. A house with no rows here uses default "
                  "terms (70% loan at 9%).", "text"),
        ("loan_ratio", "Share of the purchase price the lender covers, e.g. 70%. Type the "
                       "% sign. Use 0% for cash.", "rate"),
        ("annual_interest_rate", "Yearly interest rate, e.g. 9%. Type the % sign.", "rate"),
        ("loan_fee_rate", "One-time loan fee as a share of the loan, e.g. 1%. Type the "
                          "% sign.", "rate"),
    ],
    "Comps": [
        ("deal_id", "The house this comp is compared to. " + SAME_ID, "text"),
        ("subdivision", "Where the comp is: subdivision and barangay.", "text"),
        ("link", "Link to the comp's listing.", "text"),
        ("type", "Townhouse, single detached, duplex... Use the same type as your house.",
         "text"),
        ("floor_area_sqm", "Comp's floor area in sqm.", "sqm"),
        ("lot_area_sqm", "Optional. Comp's lot area in sqm.", "sqm"),
        ("price", "Comp's asking or sold price, in pesos.", "pesos"),
        ("condition", "Renovated, original, or brand new. Use renovated resale homes: "
                      "brand-new developer units sell for more and would overstate your "
                      "ARV.", "text"),
        ("date_seen", "Optional. When you saw the listing.", "date"),
    ],
}

FORMATS = {"pesos": "#,##0", "rate": "0.0%", "months": "0", "sqm": "General",
           "date": "yyyy-mm-dd", "text": "General"}

# What Excel accepts in each kind of column: (type, operator, limit(s), message)
CHECKS = {
    "pesos": ("decimal", "greaterThanOrEqual", ("0",), "Type an amount in pesos, 0 or more."),
    "rate": ("decimal", "between", ("0", "1"), "Type a percentage with the % sign, e.g. 9%."),
    "months": ("whole", "greaterThanOrEqual", ("0",), "Type a whole number of months."),
    "sqm": ("decimal", "greaterThan", ("0",), "Type the area in sqm, more than 0."),
}

# Example rows: the anchor deal (docs/project-context.md) with 3 made-up comps.
# Comps: 4,500,000 / 90 = 50,000; 5,200,000 / 100 = 52,000; 4,080,000 / 85 = 48,000
# per sqm. Median 50,000 x 84 sqm = 4,200,000 suggested ARV, the anchor's ARV.
EXAMPLES = {
    "Properties": [
        ["SAMPLE-01", "Example: anchor deal (hand-calculated)", 2_800_000, 4_200_000,
         6, 15_000, None, None, 84, None],
    ],
    "Renovations": [
        ["SAMPLE-01", "Roof and ceiling repair", 90_000],
        ["SAMPLE-01", "Kitchen", 120_000],
        ["SAMPLE-01", "Bathroom", 80_000],
        ["SAMPLE-01", "Electrical and plumbing", 70_000],
        ["SAMPLE-01", "Paint and finishes", 60_000],
        ["SAMPLE-01", "Flooring", 30_000],
    ],
    "Loan offers": [
        ["SAMPLE-01", "Bank A", 0.70, 0.09, 0.01],
        ["SAMPLE-01", "Bank B", 0.80, 0.10, 0.015],
        ["SAMPLE-01", "Cash", 0, 0, 0],
    ],
    "Comps": [
        ["SAMPLE-01", "Example subdivision", None, "Townhouse", 90, 60, 4_500_000,
         "Renovated", None],
        ["SAMPLE-01", "Example subdivision", None, "Townhouse", 100, 70, 5_200_000,
         "Renovated", None],
        ["SAMPLE-01", "Example subdivision", None, "Townhouse", 85, 60, 4_080_000,
         "Renovated", None],
    ],
}

STEPS = [
    "1. Replace the SAMPLE-01 example rows on every sheet with your own houses.",
    "   Give each house a deal_id and use the same deal_id on every sheet.",
    "2. Properties: one row per house. Renovations: one row per item.",
    "   Loan offers: one row per offer. Comps: one row per comparable renovated house.",
    "3. Type percentages with the % sign (9%). Hover over a column header for help.",
    "4. Set Data type above to REAL.",
    "5. Run:  python -m flip.export --input data/deals_input.xlsx",
]


def create_template(path, force: bool = False) -> Path:
    """Write the input workbook. Refuses to replace an existing file unless force."""
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(path)

    wb = Workbook()
    add_instructions(wb.active)
    for sheet_name, columns in SHEET_COLUMNS.items():
        add_table_sheet(wb.create_sheet(sheet_name), columns, EXAMPLES[sheet_name])

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def add_instructions(ws) -> None:
    ws.title = "Instructions"
    ws["A1"] = "Flip analyzer input workbook"
    ws["A1"].font = Font(bold=True, size=14)

    ws["A3"] = "Data type"
    ws["A3"].font = Font(bold=True)
    ws[DATA_TYPE_CELL] = "SAMPLE"
    ws[DATA_TYPE_CELL].fill = YELLOW
    ws["C3"] = ("SAMPLE = example or made-up data; reports get a SAMPLE banner. "
                "Choose REAL once your own houses replace the examples.")
    choice = DataValidation(type="list", formula1='"SAMPLE,REAL"', allow_blank=False)
    ws.add_data_validation(choice)
    choice.add(DATA_TYPE_CELL)

    for i, step in enumerate(STEPS, start=5):
        ws.cell(row=i, column=1, value=step)

    guide_row = 5 + len(STEPS) + 1
    for col, header in enumerate(["Sheet", "Column", "What it means"], start=1):
        ws.cell(row=guide_row, column=col, value=header).font = Font(bold=True)
    row = guide_row + 1
    for sheet_name, columns in SHEET_COLUMNS.items():
        for column, note, _ in columns:
            ws.cell(row=row, column=1, value=sheet_name)
            ws.cell(row=row, column=2, value=column)
            ws.cell(row=row, column=3, value=note).alignment = Alignment(wrap_text=True)
            row += 1

    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 100


def add_table_sheet(ws, columns, examples) -> None:
    for col, (column, note, kind) in enumerate(columns, start=1):
        letter = get_column_letter(col)
        header = ws.cell(row=1, column=col, value=column)
        header.font = Font(bold=True)
        header.fill = YELLOW
        header.comment = Comment(note, "flip-analyzer", width=320, height=110)
        ws.column_dimensions[letter].width = max(len(column) + 4, 14)

        for row in range(2, ROWS + 1):
            ws.cell(row=row, column=col).number_format = FORMATS[kind]
        if kind in CHECKS:
            check_type, operator, limits, message = CHECKS[kind]
            dv = DataValidation(type=check_type, operator=operator, formula1=limits[0],
                                formula2=limits[1] if len(limits) > 1 else None,
                                allow_blank=True, showErrorMessage=True,
                                errorTitle=column, error=message)
            ws.add_data_validation(dv)
            dv.add(f"{letter}2:{letter}{ROWS}")

    # Written cell by cell: ws.append() would add them after the 500
    # formatted rows instead of starting at row 2.
    for r, values in enumerate(examples, start=2):
        for c, value in enumerate(values, start=1):
            ws.cell(row=r, column=c, value=value)
    ws.freeze_panes = "A2"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create the Excel input workbook.")
    parser.add_argument("path", nargs="?", default="data/deals_input.xlsx")
    parser.add_argument("--force", action="store_true",
                        help="replace the file if it already exists")
    args = parser.parse_args()

    try:
        path = create_template(args.path, force=args.force)
    except FileExistsError:
        sys.exit(f"{args.path} already exists and may hold your deals. "
                 "Use --force to replace it, or give another path.")
    print(f"Created {path}")
