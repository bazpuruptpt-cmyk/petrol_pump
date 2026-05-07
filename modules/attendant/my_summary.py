import streamlit as st

from utils.permissions import require_role, get_current_user
from database.sale_db import (
    get_shift_sale_summary_for_salesman,
    get_salesman_nozzle_sale_summary,
    get_latest_payment_breakup,
    calculate_payment_match,
)
from utils.formatters import format_currency


@require_role(["salesman"])
def my_summary_page():
    user = get_current_user()
    st.title("My Summary")
    st.caption("Current shift total sale and payment breakup match.")

    summary = get_shift_sale_summary_for_salesman(user["id"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Sale Amount", format_currency(summary["total_sale"]))
    c2.metric("Total Liters", f"{summary['total_liters']:.2f} L")
    c3.metric("Entries", summary["entry_count"])

    st.divider()

    latest = get_latest_payment_breakup(summary["shift_id"], user["id"]) if summary["shift_id"] else None

    st.subheader("Saved Payment Breakup")

    if latest:
        match = calculate_payment_match(
            total_sale=summary["total_sale"],
            cash=latest.get("cash_amount"),
            paytm=latest.get("paytm_amount"),
            ccms=latest.get("ccms_amount"),
            credit=latest.get("credit_amount"),
        )

        c4, c5, c6 = st.columns(3)
        c4.metric("Payment Total", format_currency(match["payment_total"]))
        c5.metric("Difference", format_currency(match["difference"]))
        c6.metric("Status", latest.get("status"))

        c7, c8, c9, c10 = st.columns(4)
        c7.metric("Cash", format_currency(match["cash"]))
        c8.metric("Paytm", format_currency(match["paytm"]))
        c9.metric("CCMS", format_currency(match["ccms"]))
        c10.metric("Credit", format_currency(match["credit"]))

        if match["is_matched"]:
            st.success("MATCHED: Total Sale = Cash + Paytm + CCMS + Credit")
        else:
            st.error("NOT MATCHED")
    else:
        st.info("Payment breakup not submitted yet.")

    st.divider()
    st.subheader("Nozzle-wise Sale")

    rows = get_salesman_nozzle_sale_summary(user["id"])

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No sale entry yet.")
