import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.sale_db import (
    get_assigned_nozzles_for_salesman,
    get_shift_sale_summary_for_salesman,
    get_salesman_nozzle_sale_summary,
    get_latest_payment_breakup,
    calculate_payment_match,
)


def _css():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.6rem; padding-bottom: 1rem;}
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e9eef5;
            padding: 10px 12px;
            border-radius: 14px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }
        div[data-testid="stMetricLabel"] {font-size: 0.78rem;}
        div[data-testid="stMetricValue"] {font-size: 1.35rem;}
        .small-note {
            font-size: 0.82rem;
            color: #667085;
            margin-top: -8px;
            margin-bottom: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@require_role(["salesman"])
def attendant_dashboard():
    _css()

    user = get_current_user()
    duty, nozzles = get_assigned_nozzles_for_salesman(user["id"])

    st.title("Attendant Dashboard")

    if not duty:
        st.error("No active duty found.")
        st.stop()

    st.markdown(f"<div class='small-note'>Shift ID: {duty['id']} · Active duty</div>", unsafe_allow_html=True)

    summary = get_shift_sale_summary_for_salesman(user["id"])
    latest = get_latest_payment_breakup(duty["id"], user["id"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sale", format_currency(summary["total_sale"]))
    c2.metric("Total Liters", f"{summary['total_liters']:.2f} L")
    c3.metric("Entries", summary["entry_count"])
    c4.metric("Assigned Nozzles", len(nozzles))

    st.divider()

    st.subheader("Payment Status")

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
        p3.metric("Settlement Status", latest.get("status"))

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

    with st.expander("Assigned Nozzles", expanded=False):
        if nozzles:
            st.dataframe(
                [
                    {
                        "Nozzle": n.get("nozzle_name"),
                        "Fuel": n.get("fuel_type"),
                        "Opening": n.get("opening_reading"),
                        "Current": n.get("current_reading"),
                    }
                    for n in nozzles
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No nozzle assigned.")

    with st.expander("Nozzle-wise Sale", expanded=True):
        rows = get_salesman_nozzle_sale_summary(user["id"])
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No sale entry yet.")
