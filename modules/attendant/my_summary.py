import streamlit as st

from utils.permissions import require_role, get_current_user
from database.sale_db import (
    get_salesman_payment_match_summary,
    get_salesman_nozzle_summary,
    get_credit_party_wise_summary,
)
from utils.formatters import format_currency


@require_role(["salesman"])
def my_summary_page():
    user = get_current_user()
    st.title("My Summary")
    st.caption("Total Sale Amount vs Cash/Paytm/CCMS/Credit breakup.")

    summary = get_salesman_payment_match_summary(user["id"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Sale Amount", format_currency(summary["total"]))
    col2.metric("Payment Breakup Total", format_currency(summary["payment_total"]))
    col3.metric("Difference", format_currency(summary["difference"]))

    col4, col5, col6, col7 = st.columns(4)
    col4.metric("Cash", format_currency(summary["cash"]))
    col5.metric("Paytm", format_currency(summary["paytm"]))
    col6.metric("CCMS", format_currency(summary["ccms"]))
    col7.metric("Credit / Creditor", format_currency(summary["credit"]))

    if summary["is_matched"]:
        st.success("MATCHED: Total Sale = Cash + Paytm + CCMS + Credit")
    else:
        st.error("NOT MATCHED: Payment breakup total sale se match nahi kar raha.")

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

    st.divider()
    st.subheader("Creditor-wise Credit Sale")

    credit_rows = get_credit_party_wise_summary(user["id"])

    if credit_rows:
        st.dataframe(credit_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No credit sale entry yet.")
