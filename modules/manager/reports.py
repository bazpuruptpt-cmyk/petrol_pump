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



def _daily_master_single_report_rows(report, summary):
    """
    Daily Sales Master ko single printable/exportable report me convert karta hai.
    Isse alag-alag section ka print nahi lena padega.
    """
    rows = []

    def add_header(title):
        rows.append({
            "Section": f"===== {title} =====",
            "Particular": "",
            "Fuel": "",
            "Salesman": "",
            "Nozzle": "",
            "Liters": "",
            "Amount": "",
            "Cash": "",
            "Paytm": "",
            "CCMS": "",
            "Credit": "",
            "Balance": "",
            "Status": "",
            "Note": "",
        })

    def add_row(section, particular="", fuel="", salesman="", nozzle="", liters="", amount="", cash="", paytm="", ccms="", credit="", balance="", status="", note=""):
        rows.append({
            "Section": section,
            "Particular": particular,
            "Fuel": fuel,
            "Salesman": salesman,
            "Nozzle": nozzle,
            "Liters": liters,
            "Amount": amount,
            "Cash": cash,
            "Paytm": paytm,
            "CCMS": ccms,
            "Credit": credit,
            "Balance": balance,
            "Status": status,
            "Note": note,
        })

    add_header("TOP SUMMARY")
    add_row("Top Summary", "Total Sale", amount=_money(summary.get("total_sale")))
    add_row("Top Summary", "Total Liters", liters=f"{float(summary.get('total_liters') or 0):,.2f} L")
    add_row("Top Summary", "Expense of Day", amount=_money(summary.get("expense_total")))
    add_row("Top Summary", "Sale Difference", amount=_money(summary.get("sale_difference")))
    add_row(
        "Payment Breakup",
        "Payment Mode Total",
        cash=_money(summary.get("cash_sale")),
        paytm=_money(summary.get("paytm_sale")),
        ccms=_money(summary.get("ccms_sale")),
        credit=_money(summary.get("credit_sale")),
        amount=_money(summary.get("payment_total")),
    )

    add_header("PETROL / DIESEL TOTAL")
    for r in report.get("fuel_summary") or []:
        add_row(
            "Fuel Summary",
            particular=f"{r.get('Fuel')} Total",
            fuel=r.get("Fuel"),
            liters=f"{float(r.get('Liters') or 0):,.2f} L",
            amount=_money(r.get("Amount")),
            note=f"Nozzle Rows: {r.get('Nozzle Rows')}",
        )

    add_header("SALESMAN + NOZZLE-WISE SALE")
    for r in report.get("nozzle_sales") or []:
        add_row(
            "Nozzle Sale",
            particular=f"Opening {r.get('Opening')} / Closing {r.get('Closing')}",
            fuel=r.get("Fuel"),
            salesman=r.get("Salesman"),
            nozzle=r.get("Nozzle"),
            liters=f"{float(r.get('Net Sale Liters') or 0):,.2f} L",
            amount=_money(r.get("Sale Amount")),
            status=r.get("Status"),
            note=f"Gross: {r.get('Gross Liters')} | Testing: {r.get('Testing Liters')} | Rate: {r.get('Rate')}",
        )

    add_header("SALESMAN-WISE PAYMENT SUMMARY")
    for r in report.get("salesman_summary") or []:
        add_row(
            "Salesman Summary",
            particular=f"Shift {r.get('Shift ID')} / Settlement {r.get('Settlement ID')}",
            salesman=r.get("Salesman"),
            amount=_money(r.get("Meter Sale")),
            cash=_money(r.get("Cash")),
            paytm=_money(r.get("Paytm")),
            ccms=_money(r.get("CCMS")),
            credit=_money(r.get("Credit")),
            status=r.get("Status"),
            note=f"Difference: {_money(r.get('Difference'))}",
        )

    add_header("PAYMENT MODE SUMMARY")
    for r in report.get("payment_summary") or []:
        add_row(
            "Payment Summary",
            particular=r.get("Particular"),
            amount=_money(r.get("Amount")),
        )

    add_header("EXPENSE OF THE DAY")
    for r in report.get("expense_rows") or []:
        add_row(
            "Expense",
            particular=r.get("Category") or r.get("Description"),
            amount=_money(r.get("Amount")),
            status=r.get("Status"),
            note=f"{r.get('Payment Mode') or ''} | {r.get('Description') or ''} | Ref: {r.get('Reference') or ''}",
        )
    if not report.get("expense_rows"):
        add_row("Expense", "No expense entries", amount=_money(0))

    add_header("CREDITOR LIST: FUEL CREDIT / CASH GIVEN")
    for r in report.get("creditor_rows") or []:
        add_row(
            "Creditor",
            particular=r.get("Creditor"),
            amount=_money(r.get("Amount")),
            balance=r.get("Current Balance"),
            status=r.get("Status"),
            note=f"{r.get('Entry Type')} | {r.get('Note') or ''}",
        )
    if not report.get("creditor_rows"):
        add_row("Creditor", "No creditor credit/cash-given entries")

    add_header("FINAL LEDGER BALANCE")
    for r in report.get("ledger_balances") or []:
        add_row(
            "Ledger Balance",
            particular=r.get("Ledger"),
            amount=f"Credit {r.get('Credit/Inflow')} / Debit {r.get('Debit/Outflow')}",
            balance=r.get("Balance"),
        )

    return rows


def _daily_master_print_html(report, summary, entry_date):
    """
    Single clean print view. Browser print se one complete report print/PDF ban jayega.
    """
    def esc(v):
        return str(v if v is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def money(v):
        return esc(_money(v))

    html = []
    html.append("""
    <style>
    .dm-report {font-family: Arial, sans-serif; color:#111827;}
    .dm-title {font-size:22px; font-weight:800; margin-bottom:2px;}
    .dm-sub {font-size:12px; color:#4b5563; margin-bottom:14px;}
    .dm-grid {display:grid; grid-template-columns: repeat(4, 1fr); gap:8px; margin:10px 0 16px;}
    .dm-card {border:1px solid #e5e7eb; border-radius:10px; padding:8px 10px;}
    .dm-label {font-size:11px; color:#6b7280;}
    .dm-value {font-size:15px; font-weight:800; margin-top:3px;}
    .dm-section {font-size:15px; font-weight:800; margin:18px 0 6px; border-bottom:1px solid #d1d5db; padding-bottom:4px;}
    table.dm-table {width:100%; border-collapse:collapse; font-size:11px; margin-bottom:10px;}
    .dm-table th {background:#f3f4f6; text-align:left; border:1px solid #e5e7eb; padding:5px;}
    .dm-table td {border:1px solid #e5e7eb; padding:5px; vertical-align:top;}
    @media print {
        button, [data-testid="stToolbar"], header, footer {display:none !important;}
        .dm-report {font-size:11px;}
        .dm-section {page-break-after: avoid;}
        table {page-break-inside:auto;}
        tr {page-break-inside:avoid; page-break-after:auto;}
    }
    </style>
    """)

    html.append('<div class="dm-report">')
    html.append(f'<div class="dm-title">Daily Sales Master Report</div>')
    html.append(f'<div class="dm-sub">Date: {esc(entry_date)} | Complete one-page business report</div>')

    cards = [
        ("Total Sale", money(summary.get("total_sale"))),
        ("Total Liters", f"{float(summary.get('total_liters') or 0):,.2f} L"),
        ("Cash Sale", money(summary.get("cash_sale"))),
        ("Paytm Sale", money(summary.get("paytm_sale"))),
        ("CCMS Sale", money(summary.get("ccms_sale"))),
        ("Credit Sale", money(summary.get("credit_sale"))),
        ("Expense", money(summary.get("expense_total"))),
        ("Difference", money(summary.get("sale_difference"))),
    ]
    html.append('<div class="dm-grid">')
    for label, value in cards:
        html.append(f'<div class="dm-card"><div class="dm-label">{esc(label)}</div><div class="dm-value">{esc(value)}</div></div>')
    html.append('</div>')

    def table(title, rows, cols):
        html.append(f'<div class="dm-section">{esc(title)}</div>')
        if not rows:
            html.append('<div class="dm-sub">No data found.</div>')
            return
        html.append('<table class="dm-table"><thead><tr>')
        for c in cols:
            html.append(f'<th>{esc(c)}</th>')
        html.append('</tr></thead><tbody>')
        for r in rows:
            html.append('<tr>')
            for c in cols:
                html.append(f'<td>{esc(r.get(c))}</td>')
            html.append('</tr>')
        html.append('</tbody></table>')

    table("Petrol / Diesel Total", report.get("fuel_summary") or [], ["Fuel", "Liters", "Amount", "Nozzle Rows"])
    table("Salesman + Nozzle-wise Sale", report.get("nozzle_sales") or [], ["Salesman", "Nozzle", "Fuel", "Opening", "Closing", "Gross Liters", "Testing Liters", "Net Sale Liters", "Rate", "Sale Amount"])
    table("Salesman-wise Payment Summary", report.get("salesman_summary") or [], ["Salesman", "Shift ID", "Meter Sale", "Cash", "Paytm", "CCMS", "Credit", "Payment Total", "Difference", "Status"])
    table("Payment Mode Summary", report.get("payment_summary") or [], ["Particular", "Amount"])
    table("Expense of the Day", report.get("expense_rows") or [], ["Category", "Description", "Payment Mode", "Bank", "Amount", "Reference", "Status"])
    table("Creditor List: Fuel Credit / Cash Given", report.get("creditor_rows") or [], ["Creditor", "Entry Type", "Amount", "Payment Mode", "Note", "Status", "Current Balance"])
    table("Final Ledger Balance", report.get("ledger_balances") or [], ["Ledger", "Credit/Inflow", "Debit/Outflow", "Balance"])

    html.append('</div>')
    return "\n".join(html)


def daily_sales_master_tab(entry_date):
    st.subheader("Daily Sales Master Report")
    st.caption("Single report: one print/export me complete daily business picture.")

    report = get_daily_sales_master_report(entry_date)
    summary = report.get("summary") or {}

    _metric_card_row(summary)

    st.divider()

    view = st.radio(
        "Report View",
        ["Single Complete Report", "Detailed Section View"],
        horizontal=True,
        key=f"daily_master_view_{entry_date}",
    )

    if view == "Single Complete Report":
        st.markdown("### Single Complete Report")
        st.caption("Is single table / print view me saari cheeze ek saath hain. Ab alag-alag print lene ki zarurat nahi.")

        single_rows = _daily_master_single_report_rows(report, summary)

        render_report(
            single_rows,
            f"daily_sales_master_complete_{entry_date}",
            "Daily Sales Master Complete Report",
            f"daily_sales_master_complete_{entry_date}",
        )

        st.markdown("### Single Print Layout")
        st.caption("Browser print / Save as PDF ke liye ye clean combined layout use karein.")
        st.components.v1.html(
            _daily_master_print_html(report, summary, entry_date),
            height=900,
            scrolling=True,
        )

        return

    # Detailed Section View: screen checking ke liye.
    st.markdown("### Petrol / Diesel Total")
    f1, f2, f3 = st.columns(3)
    f1.metric("Petrol", f"{float(summary.get('petrol_liters') or 0):,.2f} L | {_money(summary.get('petrol_amount'))}")
    f2.metric("Diesel", f"{float(summary.get('diesel_liters') or 0):,.2f} L | {_money(summary.get('diesel_amount'))}")
    f3.metric("Grand Total", f"{float(summary.get('total_liters') or 0):,.2f} L | {_money(summary.get('total_sale'))}")

    st.divider()

    st.markdown("### Fuel-wise Summary Table")
    render_report(report.get("fuel_summary") or [], f"daily_fuel_summary_{entry_date}", "Fuel-wise Daily Summary", f"daily_fuel_summary_{entry_date}")

    st.divider()

    st.markdown("### Salesman + Nozzle-wise Sale")
    render_report(report.get("nozzle_sales") or [], f"daily_nozzle_sales_{entry_date}", "Daily Salesman Nozzle-wise Sale", f"daily_nozzle_sales_{entry_date}")

    st.divider()

    st.markdown("### Salesman-wise Payment Summary")
    render_report(report.get("salesman_summary") or [], f"daily_salesman_payment_{entry_date}", "Daily Salesman-wise Payment Summary", f"daily_salesman_payment_{entry_date}")

    st.divider()

    st.markdown("### Payment Mode Summary")
    render_report(report.get("payment_summary") or [], f"daily_payment_mode_{entry_date}", "Daily Payment Mode Summary", f"daily_payment_mode_{entry_date}")

    st.divider()

    st.markdown("### Expense of the Day")
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("**Expense Summary**")
        st.dataframe(report.get("expense_summary") or [], use_container_width=True, hide_index=True)
    with e2:
        st.metric("Total Expense", _money(summary.get("expense_total")))

    render_report(report.get("expense_rows") or [], f"daily_expenses_{entry_date}", "Expense of the Day", f"daily_expenses_{entry_date}")

    st.divider()

    st.markdown("### Creditor List: Fuel Credit / Cash Given")
    c1, c2, c3 = st.columns(3)
    c1.metric("Fuel Credit", _money(summary.get("creditor_credit_total")))
    c2.metric("Cash Given", _money(summary.get("creditor_cash_given_total")))
    c3.metric("Creditor Increase", _money((summary.get("creditor_credit_total") or 0) + (summary.get("creditor_cash_given_total") or 0)))

    render_report(report.get("creditor_rows") or [], f"daily_creditors_{entry_date}", "Daily Creditor Credit / Cash Given List", f"daily_creditors_{entry_date}")

    st.divider()

    st.markdown("### Final Ledger Balance: Cash / Paytm / CCMS / Bank")
    render_report(report.get("ledger_balances") or [], f"daily_ledger_balances_{entry_date}", "Daily Final Ledger Balances", f"daily_ledger_balances_{entry_date}")

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
