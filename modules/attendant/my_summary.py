import streamlit as st

from utils.permissions import require_role, get_current_user
from database.sale_db import get_salesman_today_summary, get_salesman_nozzle_summary
from utils.formatters import format_currency


@require_role(["salesman"])
def my_summary_page():
    user = get_current_user()
    st.title("My Summary")
    st.caption("Today all-nozzle combined summary.")

    summary = get_salesman_today_summary(user["id"])

    col1, col2, col3 = st.columns(3)
    col1.metric("All Nozzle Total", format_currency(summary["total"]))
    col2.metric("Cash", format_currency(summary["cash"]))
    col3.metric("Paytm", format_currency(summary["paytm"]))

    col4, col5, col6 = st.columns(3)
    col4.metric("CCMS", format_currency(summary["ccms"]))
    col5.metric("Credit", format_currency(summary["credit"]))
    col6.metric("Entries", summary["entry_count"])

    st.divider()

    c1, c2, c3 = st.columns(3)
    c1.metric("Pending", summary["pending_count"])
    c2.metric("Approved", summary["approved_count"])
    c3.metric("Rejected", summary["rejected_count"])

    st.divider()
    st.subheader("Nozzle-wise Sale Breakup")

    rows = get_salesman_nozzle_summary(user["id"])

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No sale entry yet.")
