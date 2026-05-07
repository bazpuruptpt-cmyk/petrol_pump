import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.sale_db import (
    get_shift_sale_summary_for_salesman,
    get_salesman_nozzle_sale_summary,
    get_latest_payment_breakup,
    calculate_payment_match,
)


def _css():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.5rem;}
        div[data-testid="stMetric"] {
            border: 1px solid #e9eef5;
            padding: 10px 12px;
            border-radius: 14px;
        }
        div[data-testid="stMetricValue"] {font-size: 1.25rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@require_role(["salesman"])
def my_summary_page():
    _css()

    user = get_current_user()
    st.title("My Summary")

    summary = get_shift_sale_summary_for_salesman(user["id"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Sale", format_currency(summary["total_sale"]))
    c2.metric("Liters", f"{summary['total_liters']:.2f} L")
    c3.metric("Entries", summary["entry_count"])

    latest = get_latest_payment_breakup(summary["shift_id"], user["id"]) if summary["shift_id"] else None

    st.subheader("Payment Breakup")

    if latest:
        match = calculate_payment_match(
            total_sale=summary["total_sale"],
            cash=latest.get("cash_amount"),
            paytm=latest.get("paytm_amount"),
            ccms=latest.get("ccms_amount"),
            credit=latest.get("credit_amount"),
        )

        p1, p2, p3 = st.columns(3)
        p1.metric("Payment Total", format_currency(match["payment_total"]))
        p2.metric("Difference", format_currency(match["difference"]))
        p3.metric("Status", latest.get("status"))

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Cash", format_currency(match["cash"]))
        b2.metric("Paytm", format_currency(match["paytm"]))
        b3.metric("CCMS", format_currency(match["ccms"]))
        b4.metric("Credit", format_currency(match["credit"]))

        if match["is_matched"]:
            st.success("MATCHED")
        else:
            st.error("NOT MATCHED")
    else:
        st.info("Payment breakup not submitted yet.")

    with st.expander("Nozzle-wise Sale", expanded=True):
        rows = get_salesman_nozzle_sale_summary(user["id"])
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No sale entry yet.")
