from datetime import date, timedelta
import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.salesman_approval_flow_db import (
    get_salesman_approval_summary,
    get_salesman_daywise_approval_summary,
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
            background: #ffffff;
        }
        div[data-testid="stMetricValue"] {font-size: 1.18rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _money_rows(rows):
    output = []
    money_keys = [
        "Entered Sale", "Pending Cash Transfer", "Approved Sale",
        "Approved Cash", "Approved Paytm", "Approved CCMS", "Approved Credit"
    ]
    for r in rows:
        x = r.copy()
        for k in money_keys:
            if k in x:
                x[k] = format_currency(x[k])
        output.append(x)
    return output


@require_role(["salesman"])
def my_summary_page():
    _css()

    user = get_current_user()
    st.title("My Summary")
    st.caption("Pending transfer aur approved sale alag-alag.")

    tab1, tab2 = st.tabs(["Daily Approval Summary", "Day-wise Approval Summary"])

    with tab1:
        daily_tab(user["id"])

    with tab2:
        daywise_tab(user["id"])


def daily_tab(salesman_id):
    selected_date = str(st.date_input("Date", value=date.today(), key="approval_daily_date"))
    s = get_salesman_approval_summary(salesman_id, selected_date)

    st.subheader(f"Daily Approval Summary: {selected_date}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entered Sale", format_currency(s["entered_sale"]))
    c2.metric("Approved Sale", format_currency(s["approved_sale"]))
    c3.metric("Pending Cash Transfer", format_currency(s["pending_cash_transfer"]))
    c4.metric("Status", s["latest_status"])

    st.markdown("### Approved Payment Breakup")
    a1, a2, a3, a4, a5 = st.columns(5)
    a1.metric("Cash", format_currency(s["approved_cash"]))
    a2.metric("Paytm", format_currency(s["approved_paytm"]))
    a3.metric("CCMS", format_currency(s["approved_ccms"]))
    a4.metric("Credit", format_currency(s["approved_credit"]))
    a5.metric("Approved Total", format_currency(s["approved_payment_total"]))

    if s["latest_status"] in ["pending", "hold", "reopened"]:
        st.warning("Submitted amount manager approval pending me hai. Approved hone ke baad hi approved sale me count hoga.")
    elif s["latest_status"] == "approved":
        st.success("Manager approved. Approved sale/payment figures final hain.")
    else:
        st.info("Payment breakup not submitted yet.")


def daywise_tab(salesman_id):
    c1, c2 = st.columns(2)
    with c1:
        start = st.date_input("From Date", value=date.today() - timedelta(days=29), key="approval_start_date")
    with c2:
        end = st.date_input("To Date", value=date.today(), key="approval_end_date")

    rows = get_salesman_daywise_approval_summary(salesman_id, str(start), str(end))

    if not rows:
        st.info("Selected range me data nahi hai.")
        return

    approved_total = sum(float(r.get("Approved Sale") or 0) for r in rows)
    pending_cash = sum(float(r.get("Pending Cash Transfer") or 0) for r in rows)

    m1, m2 = st.columns(2)
    m1.metric("Range Approved Sale", format_currency(approved_total))
    m2.metric("Range Pending Cash Transfer", format_currency(pending_cash))

    st.dataframe(_money_rows(rows), use_container_width=True, hide_index=True)
