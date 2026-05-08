from datetime import date
import streamlit as st

from utils.permissions import require_role
from utils.formatters import format_currency
from utils.export_utils import render_export_buttons, print_view
from database.reports_db import (
    get_daily_closing_report,
    get_salesman_wise_report,
    get_nozzle_wise_report,
    get_creditor_report,
    get_credit_ledger_report,
)


@require_role(["owner", "manager"])
def reports_page():
    st.title("Reports")
    st.caption("Daily closing, salesman-wise, nozzle-wise, creditor reports with export.")

    selected_date = str(st.date_input("Report Date", value=date.today(), key="reports_date"))

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Daily Closing",
        "Salesman-wise",
        "Nozzle-wise",
        "Creditor Summary",
        "Credit Ledger",
    ])

    with tab1:
        daily_closing_tab(selected_date)

    with tab2:
        salesman_report_tab(selected_date)

    with tab3:
        nozzle_report_tab(selected_date)

    with tab4:
        creditor_summary_tab()

    with tab5:
        credit_ledger_tab()


def daily_closing_tab(entry_date):
    r = get_daily_closing_report(entry_date)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sale", format_currency(r["total_sale"]))
    c2.metric("Cash In Hand", format_currency(r["cash_in_hand"]))
    c3.metric("Paytm Pending", format_currency(r["paytm_pending"]))
    c4.metric("CCMS Pending", format_currency(r["ccms_pending"]))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Credit Sale", format_currency(r["credit_sale"]))
    c6.metric("Approved", r["approved_settlements"])
    c7.metric("Pending", r["pending_settlements"])
    c8.metric("Difference", format_currency(r["total_difference"]))

    rows = [
        {"Particular": "Total Sale", "Amount": format_currency(r["total_sale"])},
        {"Particular": "Cash Sale", "Amount": format_currency(r["cash_sale"])},
        {"Particular": "Cash Deposited", "Amount": format_currency(r["cash_deposited"])},
        {"Particular": "Cash In Hand", "Amount": format_currency(r["cash_in_hand"])},
        {"Particular": "Paytm Sale", "Amount": format_currency(r["paytm_sale"])},
        {"Particular": "Paytm Settled", "Amount": format_currency(r["paytm_settled"])},
        {"Particular": "Paytm Pending", "Amount": format_currency(r["paytm_pending"])},
        {"Particular": "CCMS Sale", "Amount": format_currency(r["ccms_sale"])},
        {"Particular": "CCMS Received", "Amount": format_currency(r["ccms_received"])},
        {"Particular": "CCMS Pending", "Amount": format_currency(r["ccms_pending"])},
        {"Particular": "Credit Sale", "Amount": format_currency(r["credit_sale"])},
        {"Particular": "Approved Settlements", "Amount": r["approved_settlements"]},
        {"Particular": "Pending Settlements", "Amount": r["pending_settlements"]},
        {"Particular": "Hold Settlements", "Amount": r["hold_settlements"]},
        {"Particular": "Reopened Settlements", "Amount": r["reopened_settlements"]},
    ]

    st.divider()
    render_export_buttons(rows, f"daily_closing_{entry_date}", "Daily Closing Report", f"daily_{entry_date}")
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Print View"):
        print_view(rows, "Daily Closing Report")


def salesman_report_tab(entry_date):
    rows = get_salesman_wise_report(entry_date)

    if not rows:
        st.info("No salesman report found for selected date.")
        return

    render_export_buttons(rows, f"salesman_report_{entry_date}", "Salesman-wise Report", f"salesman_{entry_date}")
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Print View"):
        print_view(rows, "Salesman-wise Report")


def nozzle_report_tab(entry_date):
    rows = get_nozzle_wise_report(entry_date)

    if not rows:
        st.info("No nozzle report found for selected date.")
        return

    render_export_buttons(rows, f"nozzle_report_{entry_date}", "Nozzle-wise Report", f"nozzle_{entry_date}")
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Print View"):
        print_view(rows, "Nozzle-wise Report")


def creditor_summary_tab():
    rows = get_creditor_report()

    if not rows:
        st.info("No creditor data found.")
        return

    render_export_buttons(rows, "creditor_summary", "Creditor Summary", "creditor_summary")
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Print View"):
        print_view(rows, "Creditor Summary")


def credit_ledger_tab():
    c1, c2 = st.columns(2)
    with c1:
        status = st.selectbox("Status", ["all", "pending", "approved", "rejected"], key="ledger_status")
    with c2:
        txn_type = st.selectbox("Type", ["all", "sale", "payment_received"], key="ledger_type")

    rows = get_credit_ledger_report(
        status=None if status == "all" else status,
        txn_type=None if txn_type == "all" else txn_type,
    )

    if not rows:
        st.info("No ledger data found.")
        return

    render_export_buttons(rows, f"credit_ledger_{status}_{txn_type}", "Credit Ledger", f"credit_ledger_{status}_{txn_type}")
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Print View"):
        print_view(rows, "Credit Ledger")
