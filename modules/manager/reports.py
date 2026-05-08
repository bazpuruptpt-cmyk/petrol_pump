from datetime import date
import streamlit as st

from utils.permissions import require_role
from utils.formatters import format_currency
from utils.export_utils import render_export_buttons, print_view
from database.reports_db import (
    get_daily_closing_report,
    get_daily_closing_rows,
    get_sale_report_by_range,
    get_salesman_wise_report_by_range,
    get_nozzle_wise_report_by_range,
    get_payment_mode_report,
    get_cash_report,
    get_bank_report,
    get_paytm_report,
    get_ccms_report,
    get_creditor_report,
    get_credit_report,
    get_testing_report,
    get_stock_report,
    get_stock_movement_report,
    get_inward_report,
    get_oil_company_report,
    get_expense_report,
    get_expense_summary_report,
    get_monthly_summary,
)


@require_role(["owner", "manager"])
def reports_page():
    st.title("Reports")
    st.caption("Complete Phase 3C: Sale, Cash, Bank, Paytm, CCMS, Credit, Testing, Stock, Inward, Expense, Monthly Summary + CSV/Excel/PDF export.")

    today = date.today()

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            report_date = str(st.date_input("Single Date", value=today, key="reports_single_date"))
        with c2:
            from_date = str(st.date_input("From Date", value=today.replace(day=1), key="reports_from_date"))
        with c3:
            to_date = str(st.date_input("To Date", value=today, key="reports_to_date"))

    daily_kpis(report_date)

    tabs = st.tabs([
        "Daily Closing",
        "Sale Report",
        "Salesman-wise",
        "Nozzle-wise",
        "Payment Mode",
        "Cash",
        "Bank",
        "Paytm",
        "CCMS",
        "Credit",
        "Testing",
        "Stock",
        "Inward",
        "Expense",
        "Monthly Summary",
    ])

    with tabs[0]:
        daily_closing_tab(report_date)
    with tabs[1]:
        sale_report_tab(from_date, to_date)
    with tabs[2]:
        salesman_report_tab(from_date, to_date)
    with tabs[3]:
        nozzle_report_tab(from_date, to_date)
    with tabs[4]:
        payment_mode_tab(report_date)
    with tabs[5]:
        cash_report_tab(from_date, to_date)
    with tabs[6]:
        bank_report_tab(from_date, to_date)
    with tabs[7]:
        paytm_report_tab(from_date, to_date)
    with tabs[8]:
        ccms_report_tab(from_date, to_date)
    with tabs[9]:
        credit_report_tab(from_date, to_date)
    with tabs[10]:
        testing_report_tab(from_date, to_date)
    with tabs[11]:
        stock_report_tab(report_date, from_date, to_date)
    with tabs[12]:
        inward_report_tab(from_date, to_date)
    with tabs[13]:
        expense_report_tab(from_date, to_date)
    with tabs[14]:
        monthly_summary_tab()


def daily_kpis(entry_date):
    r = get_daily_closing_report(entry_date)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sale", format_currency(r["total_sale"]))
    c2.metric("Cash In Hand", format_currency(r["cash_in_hand"]))
    c3.metric("Paytm Pending", format_currency(r["paytm_pending"]))
    c4.metric("CCMS Pending", format_currency(r["ccms_pending"]))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Credit Sale", format_currency(r["credit_sale"]))
    c6.metric("Cash Expense", format_currency(r["cash_expense"]))
    c7.metric("Bank Expense", format_currency(r["bank_expense"]))
    c8.metric("Difference", format_currency(r["total_difference"]))


def render_report(rows, filename_prefix, title, key_prefix):
    st.write(f"**Rows:** {len(rows or [])}")
    render_export_buttons(rows or [], filename_prefix, title, key_prefix)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No data found for selected filter.")
    with st.expander("Print View"):
        print_view(rows or [], title)


def daily_closing_tab(entry_date):
    st.subheader("Daily Closing Report")
    rows = get_daily_closing_rows(entry_date)
    render_report(rows, f"daily_closing_{entry_date}", "Daily Closing Report", f"daily_closing_{entry_date}")


def sale_report_tab(from_date, to_date):
    st.subheader("Sale Report")
    status = st.selectbox("Settlement Status", ["all", "approved", "pending", "hold", "reopened", "rejected"], key="sale_status")
    rows = get_sale_report_by_range(from_date, to_date, status=status)
    render_report(rows, f"sale_report_{from_date}_to_{to_date}_{status}", "Sale Report", f"sale_{from_date}_{to_date}_{status}")


def salesman_report_tab(from_date, to_date):
    st.subheader("Salesman-wise Report")
    rows = get_salesman_wise_report_by_range(from_date, to_date)
    render_report(rows, f"salesman_report_{from_date}_to_{to_date}", "Salesman-wise Report", f"salesman_{from_date}_{to_date}")


def nozzle_report_tab(from_date, to_date):
    st.subheader("Nozzle-wise Report")
    rows = get_nozzle_wise_report_by_range(from_date, to_date)
    render_report(rows, f"nozzle_report_{from_date}_to_{to_date}", "Nozzle-wise Report", f"nozzle_{from_date}_{to_date}")


def payment_mode_tab(entry_date):
    st.subheader("Payment Mode Report")
    rows = get_payment_mode_report(entry_date)
    render_report(rows, f"payment_mode_{entry_date}", "Payment Mode Report", f"payment_mode_{entry_date}")


def cash_report_tab(from_date, to_date):
    st.subheader("Cash Report")
    st.caption("Cash Sale - Cash Deposit - Cash Expense = Cash Running Balance")
    rows = get_cash_report(from_date, to_date)
    render_report(rows, f"cash_report_{from_date}_to_{to_date}", "Cash Report", f"cash_{from_date}_{to_date}")


def bank_report_tab(from_date, to_date):
    st.subheader("Bank Report")
    st.caption("Bank inflow: cash deposit, Paytm settlement, CCMS received. Bank outflow: bank expenses and oil-company payments.")
    rows = get_bank_report(from_date, to_date)
    render_report(rows, f"bank_report_{from_date}_to_{to_date}", "Bank Report", f"bank_{from_date}_{to_date}")


def paytm_report_tab(from_date, to_date):
    st.subheader("Paytm Report")
    rows = get_paytm_report(from_date, to_date)
    render_report(rows, f"paytm_report_{from_date}_to_{to_date}", "Paytm Report", f"paytm_{from_date}_{to_date}")


def ccms_report_tab(from_date, to_date):
    st.subheader("CCMS Report")
    rows = get_ccms_report(from_date, to_date)
    render_report(rows, f"ccms_report_{from_date}_to_{to_date}", "CCMS Report", f"ccms_{from_date}_{to_date}")


def credit_report_tab(from_date, to_date):
    st.subheader("Credit Report")
    c1, c2 = st.columns(2)
    with c1:
        status = st.selectbox("Credit Status", ["all", "pending", "approved", "rejected"], key="credit_status")
    with c2:
        txn_type = st.selectbox("Credit Type", ["all", "sale", "payment_received"], key="credit_type")

    sub1, sub2 = st.tabs(["Ledger", "Creditor Summary"])
    with sub1:
        rows = get_credit_report(from_date, to_date, status=status, txn_type=txn_type)
        render_report(rows, f"credit_ledger_{from_date}_to_{to_date}_{status}_{txn_type}", "Credit Ledger Report", f"credit_{from_date}_{to_date}_{status}_{txn_type}")
    with sub2:
        rows = get_creditor_report()
        render_report(rows, "creditor_summary", "Creditor Summary", "creditor_summary")


def testing_report_tab(from_date, to_date):
    st.subheader("Testing Report")
    status = st.selectbox("Testing Status", ["all", "pending", "approved", "hold", "reopened", "rejected"], key="testing_status")
    rows = get_testing_report(from_date, to_date, status=status)
    render_report(rows, f"testing_report_{from_date}_to_{to_date}_{status}", "Testing Report", f"testing_{from_date}_{to_date}_{status}")


def stock_report_tab(entry_date, from_date, to_date):
    st.subheader("Stock Report")
    sub1, sub2 = st.tabs(["Stock Summary / Closing", "Stock Movement"])
    with sub1:
        rows = get_stock_report(entry_date)
        render_report(rows, f"stock_report_{entry_date}", "Stock Report", f"stock_{entry_date}")
    with sub2:
        rows = get_stock_movement_report(from_date, to_date)
        render_report(rows, f"stock_movement_{from_date}_to_{to_date}", "Stock Movement Report", f"stock_movement_{from_date}_{to_date}")


def inward_report_tab(from_date, to_date):
    st.subheader("Inward Report")
    status = st.selectbox("Inward Status", ["all", "pending", "approved", "hold", "reopened", "rejected"], key="inward_status")
    sub1, sub2 = st.tabs(["Fuel Inward", "Oil Company Ledger"])
    with sub1:
        rows = get_inward_report(from_date, to_date, status=status)
        render_report(rows, f"inward_report_{from_date}_to_{to_date}_{status}", "Inward Report", f"inward_{from_date}_{to_date}_{status}")
    with sub2:
        rows = get_oil_company_report("all", from_date, to_date)
        render_report(rows, f"oil_company_ledger_{from_date}_to_{to_date}", "Oil Company Ledger", f"oil_company_{from_date}_{to_date}")


def expense_report_tab(from_date, to_date):
    st.subheader("Expense Report")
    c1, c2 = st.columns(2)
    with c1:
        status = st.selectbox("Expense Status", ["all", "pending", "approved", "hold", "reopened", "rejected"], key="expense_status_report")
    with c2:
        payment_mode = st.selectbox("Payment Mode", ["all", "cash", "bank"], key="expense_payment_mode_report")

    sub1, sub2 = st.tabs(["Expense Ledger", "Expense Summary"])
    with sub1:
        rows = get_expense_report(from_date, to_date, status=status, payment_mode=payment_mode)
        render_report(rows, f"expense_report_{from_date}_to_{to_date}_{status}_{payment_mode}", "Expense Report", f"expense_{from_date}_{to_date}_{status}_{payment_mode}")
    with sub2:
        rows = get_expense_summary_report(from_date, to_date)
        render_report(rows, f"expense_summary_{from_date}_to_{to_date}", "Expense Summary", f"expense_summary_{from_date}_{to_date}")


def monthly_summary_tab():
    st.subheader("Monthly Summary")
    today = date.today()
    c1, c2 = st.columns(2)
    with c1:
        month = st.selectbox("Month", list(range(1, 13)), index=today.month - 1, key="monthly_month")
    with c2:
        year = st.number_input("Year", min_value=2020, max_value=2100, value=today.year, step=1, key="monthly_year")
    rows = get_monthly_summary(month=month, year=year)
    render_report(rows, f"monthly_summary_{int(year)}_{int(month):02d}", "Monthly Summary", f"monthly_{int(year)}_{int(month):02d}")
