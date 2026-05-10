from datetime import date, timedelta
import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.sale_summary_db import (
    get_salesman_daily_summary,
    get_salesman_daily_nozzle_summary,
    get_salesman_day_wise_summary,
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
    for row in rows:
        x = row.copy()
        for key in ["Sale", "Cash", "Paytm", "CCMS", "Credit", "Payment Total", "Difference"]:
            if key in x:
                x[key] = format_currency(x[key])
        output.append(x)
    return output


@require_role(["salesman"])
def my_summary_page():
    _css()

    user = get_current_user()
    st.title("My Summary")
    st.caption("Daily summary aur day-wise summary alag-alag.")

    tab1, tab2 = st.tabs(["Daily Summary", "Day-wise Summary"])

    with tab1:
        daily_summary_tab(user["id"])

    with tab2:
        day_wise_summary_tab(user["id"])


def daily_summary_tab(salesman_id):
    selected_date = str(st.date_input("Select Date", value=date.today(), key="salesman_daily_summary_date"))

    summary = get_salesman_daily_summary(salesman_id, selected_date)

    st.subheader(f"Daily Summary: {selected_date}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Sale", format_currency(summary["total_sale"]))
    c2.metric("Liters", f"{summary['total_liters']:.2f} L")
    c3.metric("Entries", summary["entry_count"])

    st.subheader("Payment Breakup")

    p1, p2, p3 = st.columns(3)
    p1.metric("Payment Total", format_currency(summary["payment_total"]))
    p2.metric("Difference", format_currency(summary["difference"]))
    p3.metric("Status", summary["status"])

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Cash", format_currency(summary["cash"]))
    b2.metric("Paytm", format_currency(summary["paytm"]))
    b3.metric("CCMS", format_currency(summary["ccms"]))
    b4.metric("Credit", format_currency(summary["credit"]))

    if summary["payment_total"] == 0 and summary["total_sale"] > 0:
        st.warning("Payment breakup not submitted for this date.")
    elif summary["is_matched"]:
        st.success("MATCHED")
    else:
        st.error("NOT MATCHED")

    with st.expander("Nozzle-wise Sale", expanded=True):
        rows = get_salesman_daily_nozzle_summary(salesman_id, selected_date)
        if rows:
            display = []
            for r in rows:
                x = r.copy()
                x["Amount"] = format_currency(x["Amount"])
                display.append(x)
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            st.info("Selected date par sale entry nahi hai.")


def day_wise_summary_tab(salesman_id):
    st.subheader("Day-wise Summary")

    c1, c2 = st.columns(2)
    with c1:
        start = st.date_input("From Date", value=date.today() - timedelta(days=29), key="summary_from_date")
    with c2:
        end = st.date_input("To Date", value=date.today(), key="summary_to_date")

    rows = get_salesman_day_wise_summary(
        salesman_id,
        start_date=str(start),
        end_date=str(end),
    )

    if not rows:
        st.info("Selected range me data nahi hai.")
        return

    total_sale = sum(float(str(r.get("Sale", 0)).replace(",", "") or 0) for r in rows)
    total_liters = sum(float(r.get("Liters") or 0) for r in rows)
    total_entries = sum(int(r.get("Entries") or 0) for r in rows)

    c3, c4, c5 = st.columns(3)
    c3.metric("Range Sale", format_currency(total_sale))
    c4.metric("Range Liters", f"{total_liters:.2f} L")
    c5.metric("Range Entries", total_entries)

    st.dataframe(_money_rows(rows), use_container_width=True, hide_index=True)

    st.info("Ye total summary nahi hai; har row ek अलग date ka हिसाब दिखाती है.")
