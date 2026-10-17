"""Flip Deal Analyzer: the web app. Start it with `python -m flip.web`.

Three pages, in the order of the deal cycle:

    Market scan     refresh Pag-IBIG listings, screen every foreclosure,
                    and start a deal from one (views/market.py)
    Edit a house    its details, renovation items, other costs, loan
                    offers, comps, and checklist (views/edit.py)
    Analyze a house the verdict, both ROIs, scenarios, and the max offer for
                    each house in your workbook (views/analyze.py)

The app writes your workbook only when you press a save button, and only
through flip.workbook: checked first, backed up, never while Excel has it
open. What-if numbers on the Analyze page are never saved.
"""

import streamlit as st

from flip.ui import DEFAULT_WORKBOOK

st.set_page_config(page_title="Flip Deal Analyzer", page_icon=":material/home:", layout="wide")

page = st.navigation([
    st.Page("views/market.py", title="Market scan", icon=":material/travel_explore:"),
    st.Page("views/edit.py", title="Edit a house", icon=":material/edit:"),
    st.Page("views/analyze.py", title="Analyze a house", icon=":material/calculate:"),
])

with st.sidebar:
    st.header("Your workbook")
    st.file_uploader("Upload an input workbook (read only)", type=["xlsx"], key="upload")
    st.text_input("...or use the one at this path", value=DEFAULT_WORKBOOK, key="path")

page.run()
