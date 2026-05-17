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
    get_daily_sales_master_report,
)


@require_role(["owner", "manager"])
def reports_page():
    st.title("Reports")
    st.caption("Daily Sales Master + Sale, Cash, Bank, Paytm, CCMS, Credit, Testing, Stock, Inward, Expense and Monthly reports.")

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

    section = st.radio(
        "Report Section",
        [
            "Daily Sales Master",
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
        ],
        horizontal=True,
        key="reports_active_section",
    )

    if section == "Daily Sales Master":
        daily_sales_master_tab(report_date)
    elif section == "Daily Closing":
        daily_closing_tab(report_date)
    elif section == "Sale Report":
        sale_report_tab(from_date, to_date)
    elif section == "Salesman-wise":
        salesman_report_tab(from_date, to_date)
    elif section == "Nozzle-wise":
        nozzle_report_tab(from_date, to_date)
    elif section == "Payment Mode":
        payment_mode_tab(report_date)
    elif section == "Cash":
        cash_report_tab(from_date, to_date)
    elif section == "Bank":
        bank_report_tab(from_date, to_date)
    elif section == "Paytm":
        paytm_report_tab(from_date, to_date)
    elif section == "CCMS":
        ccms_report_tab(from_date, to_date)
    elif section == "Credit":
        credit_report_tab(from_date, to_date)
    elif section == "Testing":
        testing_report_tab(from_date, to_date)
    elif section == "Stock":
        stock_report_tab(report_date, from_date, to_date)
    elif section == "Inward":
        inward_report_tab(from_date, to_date)
    elif section == "Expense":
        expense_report_tab(from_date, to_date)
    elif section == "Monthly Summary":
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

    # Important:
    # Streamlit nested expander error aa raha tha because render_report()
    # ke andar Print View expander tha aur kuch reports outer expander me render ho rahi thi.
    # Expander remove karke normal checkbox use kiya gaya hai.
    show_print = st.checkbox(
        "Show Print View",
        value=False,
        key=f"print_view_{key_prefix}",
    )

    if show_print:
        print_view(rows or [], title)

def _money(value):
    return format_currency(value)


def _metric_card_row(summary):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sale", _money(summary.get("total_sale")))
    c2.metric("Total Liters", f"{float(summary.get('total_liters') or 0):,.2f} L")
    c3.metric("Expense of Day", _money(summary.get("expense_total")))
    c4.metric("Sale Difference", _money(summary.get("sale_difference")))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Cash Sale", _money(summary.get("cash_sale")))
    c6.metric("Paytm Sale", _money(summary.get("paytm_sale")))
    c7.metric("CCMS Sale", _money(summary.get("ccms_sale")))
    c8.metric("Credit Sale", _money(summary.get("credit_sale")))


def _section_table(title, rows, filename_prefix, key_prefix):
    st.markdown(f"### {title}")
    render_report(rows or [], filename_prefix, title, key_prefix)


def daily_sales_master_tab(entry_date):
    st.subheader("Daily Sales Master Report")
    st.caption("Same day ke all salesmen, nozzle-wise sale, petrol/diesel totals, payment breakup, expenses, creditors and final ledger balances.")

    report = get_daily_sales_master_report(entry_date)
    summary = report.get("summary") or {}

    _metric_card_row(summary)

    st.divider()

    st.markdown("### Petrol / Diesel Total")
    f1, f2, f3 = st.columns(3)
    f1.metric("Petrol", f"{float(summary.get('petrol_liters') or 0):,.2f} L | {_money(summary.get('petrol_amount'))}")
    f2.metric("Diesel", f"{float(summary.get('diesel_liters') or 0):,.2f} L | {_money(summary.get('diesel_amount'))}")
    f3.metric("Grand Total", f"{float(summary.get('total_liters') or 0):,.2f} L | {_money(summary.get('total_sale'))}")

    st.divider()

    st.markdown("### Fuel-wise Summary Table")
    render_report(
        report.get("fuel_summary") or [],
        f"daily_fuel_summary_{entry_date}",
        "Fuel-wise Daily Summary",
        f"daily_fuel_summary_{entry_date}",
    )

    st.divider()

    st.markdown("### Salesman + Nozzle-wise Sale")
    render_report(
        report.get("nozzle_sales") or [],
        f"daily_nozzle_sales_{entry_date}",
        "Daily Salesman Nozzle-wise Sale",
        f"daily_nozzle_sales_{entry_date}",
    )

    st.divider()

    st.markdown("### Salesman-wise Payment Summary")
    render_report(
        report.get("salesman_summary") or [],
        f"daily_salesman_payment_{entry_date}",
        "Daily Salesman-wise Payment Summary",
        f"daily_salesman_payment_{entry_date}",
    )

    st.divider()

    st.markdown("### Payment Mode Summary")
    render_report(
        report.get("payment_summary") or [],
        f"daily_payment_mode_{entry_date}",
        "Daily Payment Mode Summary",
        f"daily_payment_mode_{entry_date}",
    )

    st.divider()

    st.markdown("### Expense of the Day")
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("**Expense Summary**")
        st.dataframe(report.get("expense_summary") or [], use_container_width=True, hide_index=True)
    with e2:
        st.metric("Total Expense", _money(summary.get("expense_total")))

    render_report(
        report.get("expense_rows") or [],
        f"daily_expenses_{entry_date}",
        "Expense of the Day",
        f"daily_expenses_{entry_date}",
    )

    st.divider()

    st.markdown("### Creditor List: Fuel Credit / Cash Given")
    c1, c2, c3 = st.columns(3)
    c1.metric("Fuel Credit", _money(summary.get("creditor_credit_total")))
    c2.metric("Cash Given", _money(summary.get("creditor_cash_given_total")))
    c3.metric(
        "Creditor Increase",
        _money((summary.get("creditor_credit_total") or 0) + (summary.get("creditor_cash_given_total") or 0)),
    )

    render_report(
        report.get("creditor_rows") or [],
        f"daily_creditors_{entry_date}",
        "Daily Creditor Credit / Cash Given List",
        f"daily_creditors_{entry_date}",
    )

    st.divider()

    st.markdown("### Final Ledger Balance: Cash / Paytm / CCMS / Bank")
    render_report(
        report.get("ledger_balances") or [],
        f"daily_ledger_balances_{entry_date}",
        "Daily Final Ledger Balances",
        f"daily_ledger_balances_{entry_date}",
    )

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
