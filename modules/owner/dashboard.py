import streamlit as st

from utils.permissions import require_role
from utils.formatters import format_currency
from utils.ui import page_title

try:
    from database.reports_db import get_daily_closing_report
except Exception:
    get_daily_closing_report = None


@require_role(["owner"])
def owner_dashboard():
    page_title("Owner Dashboard", "Daily business summary.")

    if get_daily_closing_report:
        report = get_daily_closing_report()
    else:
        report = {
            "total_sale": 0,
            "cash_in_hand": 0,
            "credit_sale": 0,
            "paytm_pending": 0,
            "ccms_pending": 0,
            "total_difference": 0,
        }

    c1, c2, c3 = st.columns(3)
    c1.metric("Today Total Sale", format_currency(report.get("total_sale")))
    c2.metric("Cash In Hand", format_currency(report.get("cash_in_hand")))
    c3.metric("Credit Sale", format_currency(report.get("credit_sale")))

    c4, c5, c6 = st.columns(3)
    c4.metric("Paytm Pending", format_currency(report.get("paytm_pending")))
    c5.metric("CCMS Pending", format_currency(report.get("ccms_pending")))
    c6.metric("Difference", format_currency(report.get("total_difference")))

    st.divider()
    st.info("Use sidebar for setup, stock, approval, settlement, money control and reports.")
