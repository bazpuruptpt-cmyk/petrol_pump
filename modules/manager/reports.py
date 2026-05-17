from datetime import date
import streamlit as st
import streamlit.components.v1 as components

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
    get_monthly_sales_master_report,
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
            "Monthly Sales Master",
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
    elif section == "Monthly Sales Master":
        monthly_sales_master_tab()
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



def _daily_master_ledger_dict(report):
    ledger = {}
    for r in report.get("ledger_balances") or []:
        name = str(r.get("Ledger") or "").strip()
        ledger[name] = r
    return ledger


def _daily_master_salesman_fuel_summary(report):
    grouped = {}

    for r in report.get("nozzle_sales") or []:
        salesman = r.get("Salesman") or "-"
        fuel = r.get("Fuel") or "-"
        key = salesman

        if key not in grouped:
            grouped[key] = {
                "Salesman": salesman,
                "Petrol L": 0.0,
                "Petrol Amount": 0.0,
                "Diesel L": 0.0,
                "Diesel Amount": 0.0,
                "Total L": 0.0,
                "Total Amount": 0.0,
            }

        liters = float(r.get("Net Sale Liters") or 0)
        amount = float(r.get("Sale Amount") or 0)

        if fuel == "petrol":
            grouped[key]["Petrol L"] += liters
            grouped[key]["Petrol Amount"] += amount
        elif fuel == "diesel":
            grouped[key]["Diesel L"] += liters
            grouped[key]["Diesel Amount"] += amount

        grouped[key]["Total L"] += liters
        grouped[key]["Total Amount"] += amount

    out = []
    for row in grouped.values():
        out.append({
            "Salesman": row["Salesman"],
            "Petrol L": f"{row['Petrol L']:,.2f}",
            "Petrol ₹": _money(row["Petrol Amount"]),
            "Diesel L": f"{row['Diesel L']:,.2f}",
            "Diesel ₹": _money(row["Diesel Amount"]),
            "Total L": f"{row['Total L']:,.2f}",
            "Total ₹": _money(row["Total Amount"]),
        })

    return out


def _daily_master_compact_creditor_summary(report, summary):
    creditor_rows = report.get("creditor_rows") or []
    names = []

    for r in creditor_rows[:10]:
        creditor = r.get("Creditor")
        entry_type = r.get("Entry Type")
        amount = _money(r.get("Amount"))
        mode = r.get("Payment Mode") or ""
        if creditor:
            mode_text = f" / {mode}" if mode else ""
            names.append(f"{creditor} ({entry_type}{mode_text}: {amount})")

    return {
        "Fuel Credit": _money(summary.get("creditor_credit_total")),
        "Cash Given": _money(summary.get("creditor_cash_given_total")),
        "Payment Cash": _money(summary.get("creditor_payment_cash_total")),
        "Payment Bank": _money(summary.get("creditor_payment_bank_total")),
        "Payment Paytm": _money(summary.get("creditor_payment_paytm_total")),
        "Payment CCMS": _money(summary.get("creditor_payment_ccms_total")),
        "Payment Total": _money(summary.get("creditor_payment_total")),
        "Entries": ", ".join(names) if names else "No creditor credit/cash-given/payment entries",
    }

def _html_escape(value):
    return str(value if value is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _daily_master_professional_html(report, summary, entry_date):
    """
    Compact professional one-page style owner report.
    Detailed data remains in Detailed Section View.
    """
    ledger = _daily_master_ledger_dict(report)
    salesman_fuel = _daily_master_salesman_fuel_summary(report)
    creditor = _daily_master_compact_creditor_summary(report, summary)

    def esc(v):
        return _html_escape(v)

    def money(v):
        return esc(_money(v))

    def ledger_balance(name):
        row = ledger.get(name) or {}
        return esc(row.get("Balance") or "₹0.00")

    def table_html(columns, rows):
        if not rows:
            return '<div class="pr-empty">No data</div>'
        html = ['<table class="pr-table"><thead><tr>']
        for c in columns:
            html.append(f"<th>{esc(c)}</th>")
        html.append("</tr></thead><tbody>")
        for r in rows:
            html.append("<tr>")
            for c in columns:
                html.append(f"<td>{esc(r.get(c))}</td>")
            html.append("</tr>")
        html.append("</tbody></table>")
        return "".join(html)

    payment_rows = [
        {"Mode": "Cash", "Amount": money(summary.get("cash_sale"))},
        {"Mode": "Paytm", "Amount": money(summary.get("paytm_sale"))},
        {"Mode": "CCMS", "Amount": money(summary.get("ccms_sale"))},
        {"Mode": "Credit", "Amount": money(summary.get("credit_sale"))},
    ]

    fuel_rows = [
        {"Fuel": "Petrol", "Liters": f"{float(summary.get('petrol_liters') or 0):,.2f}", "Amount": money(summary.get("petrol_amount"))},
        {"Fuel": "Diesel", "Liters": f"{float(summary.get('diesel_liters') or 0):,.2f}", "Amount": money(summary.get("diesel_amount"))},
        {"Fuel": "Total", "Liters": f"{float(summary.get('total_liters') or 0):,.2f}", "Amount": money(summary.get("total_sale"))},
    ]

    ledger_rows = [
        {"Ledger": "Cash", "Balance": ledger_balance("CASH")},
        {"Ledger": "Paytm", "Balance": ledger_balance("PAYTM")},
        {"Ledger": "CCMS", "Balance": ledger_balance("CCMS")},
        {"Ledger": "Canara OD", "Balance": ledger_balance("Canara Bank OD Account")},
        {"Ledger": "Canara CC", "Balance": ledger_balance("Canara Bank CC Account")},
    ]

    expense_rows = report.get("expense_summary") or []
    if not expense_rows:
        expense_rows = [{"Payment Mode": "-", "Amount": money(summary.get("expense_total"))}]
    else:
        expense_rows = [{"Payment Mode": r.get("Payment Mode"), "Amount": money(r.get("Amount"))} for r in expense_rows]

    html = f"""
    <style>
    .pr-report {{
        width: 100%;
        background: #ffffff;
        color: #111827;
        font-family: Arial, Helvetica, sans-serif;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 16px;
        box-sizing: border-box;
    }}
    .pr-head {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        border-bottom: 2px solid #111827;
        padding-bottom: 8px;
        margin-bottom: 10px;
    }}
    .pr-title {{
        font-size: 22px;
        font-weight: 900;
        letter-spacing: -0.3px;
    }}
    .pr-sub {{
        color: #6b7280;
        font-size: 12px;
        margin-top: 2px;
    }}
    .pr-date {{
        text-align: right;
        font-size: 12px;
        color: #374151;
        font-weight: 700;
    }}
    .pr-kpis {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        margin: 10px 0;
    }}
    .pr-kpi {{
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 8px 9px;
        background: #f9fafb;
    }}
    .pr-kpi-label {{
        font-size: 10px;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }}
    .pr-kpi-value {{
        margin-top: 3px;
        font-size: 15px;
        font-weight: 900;
        color: #111827;
    }}
    .pr-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin-top: 8px;
    }}
    .pr-box {{
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        overflow: hidden;
    }}
    .pr-box-title {{
        background: #111827;
        color: white;
        font-size: 12px;
        font-weight: 800;
        padding: 6px 8px;
    }}
    .pr-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
    }}
    .pr-table th {{
        background: #f3f4f6;
        color: #374151;
        text-align: left;
        padding: 5px 6px;
        border-bottom: 1px solid #e5e7eb;
        font-weight: 800;
    }}
    .pr-table td {{
        padding: 5px 6px;
        border-bottom: 1px solid #f1f5f9;
    }}
    .pr-note {{
        font-size: 11px;
        line-height: 1.35;
        color: #374151;
        padding: 8px;
        background: #f9fafb;
        border-top: 1px solid #e5e7eb;
    }}
    .pr-empty {{
        padding: 8px;
        font-size: 11px;
        color: #6b7280;
    }}
    .pr-wide {{
        grid-column: 1 / -1;
    }}
    @media print {{
        body * {{ visibility: hidden; }}
        .pr-report, .pr-report * {{ visibility: visible; }}
        .pr-report {{
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            border: none;
            border-radius: 0;
            padding: 8px;
        }}
        .pr-title {{ font-size: 18px; }}
        .pr-kpis {{ grid-template-columns: repeat(4, 1fr); gap: 5px; }}
        .pr-kpi {{ padding: 5px; }}
        .pr-kpi-value {{ font-size: 12px; }}
        .pr-grid {{ gap: 6px; }}
        .pr-table {{ font-size: 9px; }}
        .pr-table th, .pr-table td {{ padding: 3px 4px; }}
        .pr-box-title {{ font-size: 10px; padding: 4px 6px; }}
    }}
    </style>

    <div class="pr-report">
        <div class="pr-head">
            <div>
                <div class="pr-title">Daily Sales Master Report</div>
                <div class="pr-sub">Owner summary: sales, fuel, payment, expense, creditors and ledger position</div>
            </div>
            <div class="pr-date">
                Date<br>{esc(entry_date)}
            </div>
        </div>

        <div class="pr-kpis">
            <div class="pr-kpi"><div class="pr-kpi-label">Total Sale</div><div class="pr-kpi-value">{money(summary.get("total_sale"))}</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Total Liters</div><div class="pr-kpi-value">{float(summary.get("total_liters") or 0):,.2f} L</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Cash Sale</div><div class="pr-kpi-value">{money(summary.get("cash_sale"))}</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Credit Sale</div><div class="pr-kpi-value">{money(summary.get("credit_sale"))}</div></div>

            <div class="pr-kpi"><div class="pr-kpi-label">Paytm Sale</div><div class="pr-kpi-value">{money(summary.get("paytm_sale"))}</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">CCMS Sale</div><div class="pr-kpi-value">{money(summary.get("ccms_sale"))}</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Creditor Received</div><div class="pr-kpi-value">{money(summary.get("creditor_payment_total"))}</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Difference</div><div class="pr-kpi-value">{money(summary.get("sale_difference"))}</div></div>
        </div>

        <div class="pr-grid">
            <div class="pr-box">
                <div class="pr-box-title">Fuel Summary</div>
                {table_html(["Fuel", "Liters", "Amount"], fuel_rows)}
            </div>

            <div class="pr-box">
                <div class="pr-box-title">Payment Summary</div>
                {table_html(["Mode", "Amount"], payment_rows)}
            </div>

            <div class="pr-box pr-wide">
                <div class="pr-box-title">Salesman-wise Fuel Summary</div>
                {table_html(["Salesman", "Petrol L", "Petrol ₹", "Diesel L", "Diesel ₹", "Total L", "Total ₹"], salesman_fuel)}
            </div>

            <div class="pr-box">
                <div class="pr-box-title">Expense Summary</div>
                {table_html(["Payment Mode", "Amount"], expense_rows)}
            </div>

            <div class="pr-box">
                <div class="pr-box-title">Final Ledger Balances</div>
                {table_html(["Ledger", "Balance"], ledger_rows)}
            </div>

            <div class="pr-box pr-wide">
                <div class="pr-box-title">Creditor Summary</div>
                <div class="pr-note">
                    <b>Fuel Credit:</b> {esc(creditor["Fuel Credit"])} &nbsp; | &nbsp;
                    <b>Cash Given:</b> {esc(creditor["Cash Given"])} &nbsp; | &nbsp;
                    <b>Payment Received:</b> {esc(creditor["Payment Total"])}<br>
                    <b>Received Mode-wise:</b>
                    Cash {esc(creditor["Payment Cash"])} |
                    Bank {esc(creditor["Payment Bank"])} |
                    Paytm {esc(creditor["Payment Paytm"])} |
                    CCMS {esc(creditor["Payment CCMS"])}<br>
                    <b>Entries:</b> {esc(creditor["Entries"])}
                </div>
            </div>
        </div>
    </div>
    """

    return html.strip()


def _daily_master_professional_export_rows(report, summary):
    rows = []

    def add(section, item, value="", amount="", note=""):
        rows.append({
            "Section": section,
            "Item": item,
            "Value": value,
            "Amount": amount,
            "Note": note,
        })

    add("Top Summary", "Total Sale", amount=_money(summary.get("total_sale")))
    add("Top Summary", "Total Liters", value=f"{float(summary.get('total_liters') or 0):,.2f} L")
    add("Top Summary", "Cash Sale", amount=_money(summary.get("cash_sale")))
    add("Top Summary", "Paytm Sale", amount=_money(summary.get("paytm_sale")))
    add("Top Summary", "CCMS Sale", amount=_money(summary.get("ccms_sale")))
    add("Top Summary", "Credit Sale", amount=_money(summary.get("credit_sale")))
    add("Top Summary", "Expense", amount=_money(summary.get("expense_total")))
    add("Top Summary", "Difference", amount=_money(summary.get("sale_difference")))

    for r in report.get("fuel_summary") or []:
        add("Fuel Summary", r.get("Fuel"), value=f"{float(r.get('Liters') or 0):,.2f} L", amount=_money(r.get("Amount")))

    for r in _daily_master_salesman_fuel_summary(report):
        add(
            "Salesman Fuel Summary",
            r.get("Salesman"),
            value=f"Petrol {r.get('Petrol L')} L | Diesel {r.get('Diesel L')} L | Total {r.get('Total L')} L",
            amount=r.get("Total ₹"),
            note=f"Petrol {r.get('Petrol ₹')} | Diesel {r.get('Diesel ₹')}",
        )

    creditor = _daily_master_compact_creditor_summary(report, summary)
    add("Creditor Summary", "Fuel Credit", amount=creditor.get("Fuel Credit"))
    add("Creditor Summary", "Cash Given", amount=creditor.get("Cash Given"))
    add("Creditor Payment Received", "Cash", amount=creditor.get("Payment Cash"))
    add("Creditor Payment Received", "Bank", amount=creditor.get("Payment Bank"))
    add("Creditor Payment Received", "Paytm", amount=creditor.get("Payment Paytm"))
    add("Creditor Payment Received", "CCMS", amount=creditor.get("Payment CCMS"))
    add("Creditor Payment Received", "Total", amount=creditor.get("Payment Total"), note=creditor.get("Entries"))

    for r in report.get("ledger_balances") or []:
        add("Final Ledger Balance", r.get("Ledger"), amount=r.get("Balance"), note=f"Credit {r.get('Credit/Inflow')} | Debit {r.get('Debit/Outflow')}")

    return rows


def daily_sales_master_tab(entry_date):
    st.subheader("Daily Sales Master Report")
    st.caption("Professional one-page owner report. Summary first, detailed checking optional.")

    report = get_daily_sales_master_report(entry_date)
    summary = report.get("summary") or {}

    view = st.radio(
        "Report View",
        ["Professional One Page", "Detailed Checking"],
        horizontal=True,
        key=f"daily_master_professional_view_{entry_date}",
    )

    if view == "Professional One Page":
        st.markdown("### Professional One Page Summary")
        st.caption("Is view me data summarize hai taaki owner ek page me business position samajh sake.")

        professional_rows = _daily_master_professional_export_rows(report, summary)
        html_data = _daily_master_professional_html(report, summary, entry_date).strip()

        c1, c2, c3 = st.columns(3)
        with c1:
            csv_data = "\n".join(
                [",".join(["Section", "Item", "Value", "Amount", "Note"])]
                + [
                    ",".join([
                        str(r.get("Section", "")).replace(",", " "),
                        str(r.get("Item", "")).replace(",", " "),
                        str(r.get("Value", "")).replace(",", " "),
                        str(r.get("Amount", "")).replace(",", " "),
                        str(r.get("Note", "")).replace(",", " "),
                    ])
                    for r in professional_rows
                ]
            )
            st.download_button(
                "Download Summary CSV",
                csv_data,
                file_name=f"daily_sales_professional_summary_{entry_date}.csv",
                mime="text/csv",
                key=f"daily_professional_csv_{entry_date}",
            )

        with c2:
            st.download_button(
                "Download Print HTML",
                html_data,
                file_name=f"daily_sales_professional_report_{entry_date}.html",
                mime="text/html",
                key=f"daily_professional_html_{entry_date}",
            )

        with c3:
            st.info("Best print ke liye Download Print HTML open karke Ctrl+P / Cmd+P karein.")

        # HTML ko Streamlit markdown me render karne par raw <div> text dikhta tha.
        # Components iframe me render karne se professional layout correctly show hota hai.
        components.html(
            html_data,
            height=920,
            scrolling=True,
        )

        if st.checkbox("Show compact export table", value=False, key=f"show_compact_export_{entry_date}"):
            st.dataframe(professional_rows, use_container_width=True, hide_index=True)

        return

    # Detailed checking view
    _metric_card_row(summary)

    st.divider()

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

    st.markdown("### Creditor List: Fuel Credit / Cash Given / Payment Received")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fuel Credit", _money(summary.get("creditor_credit_total")))
    c2.metric("Cash Given", _money(summary.get("creditor_cash_given_total")))
    c3.metric("Payment Received", _money(summary.get("creditor_payment_total")))
    c4.metric("Creditor Increase", _money((summary.get("creditor_credit_total") or 0) + (summary.get("creditor_cash_given_total") or 0)))

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Received Cash", _money(summary.get("creditor_payment_cash_total")))
    p2.metric("Received Bank", _money(summary.get("creditor_payment_bank_total")))
    p3.metric("Received Paytm", _money(summary.get("creditor_payment_paytm_total")))
    p4.metric("Received CCMS", _money(summary.get("creditor_payment_ccms_total")))

    render_report(report.get("creditor_rows") or [], f"daily_creditors_{entry_date}", "Daily Creditor Credit / Cash Given / Payment Received List", f"daily_creditors_{entry_date}")

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




def _sales_summary_metric_cards(summary):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sale", _money(summary.get("total_sale")))
    c2.metric("Gross Liters", f"{float(summary.get('total_gross_liters') or 0):,.2f} L")
    c3.metric("Testing Liters", f"{float(summary.get('total_testing_liters') or 0):,.2f} L")
    c4.metric("Net Sale Liters", f"{float(summary.get('total_liters') or 0):,.2f} L")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Cash Sale", _money(summary.get("cash_sale")))
    c6.metric("Paytm Sale", _money(summary.get("paytm_sale")))
    c7.metric("CCMS Sale", _money(summary.get("ccms_sale")))
    c8.metric("Credit Sale", _money(summary.get("credit_sale")))


def _monthly_sales_professional_html(report, summary):
    def esc(v):
        return _html_escape(v)

    def money(v):
        return esc(_money(v))

    def table_html(columns, rows):
        if not rows:
            return '<div class="pr-empty">No data</div>'
        html = ['<table class="pr-table"><thead><tr>']
        for c in columns:
            html.append(f"<th>{esc(c)}</th>")
        html.append("</tr></thead><tbody>")
        for r in rows:
            html.append("<tr>")
            for c in columns:
                html.append(f"<td>{esc(r.get(c))}</td>")
            html.append("</tr>")
        html.append("</tbody></table>")
        return "".join(html)

    fuel_rows = report.get("fuel_summary") or []
    rate_rows = (report.get("rate_summary") or [])[:40]
    daily_rows = report.get("daily_summary") or []
    salesman_rows = report.get("salesman_summary") or []
    payment_rows = report.get("payment_summary") or []
    ledger_rows = report.get("ledger_balances") or []

    html = f"""
    <style>
    .pr-report {{font-family:Arial,Helvetica,sans-serif;color:#111827;border:1px solid #e5e7eb;border-radius:14px;padding:14px;background:#fff;}}
    .pr-head {{display:flex;justify-content:space-between;border-bottom:2px solid #111827;padding-bottom:8px;margin-bottom:10px;}}
    .pr-title {{font-size:21px;font-weight:900;}}
    .pr-sub {{font-size:12px;color:#6b7280;}}
    .pr-date {{font-size:12px;text-align:right;font-weight:700;}}
    .pr-kpis {{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0;}}
    .pr-kpi {{border:1px solid #e5e7eb;background:#f9fafb;border-radius:10px;padding:8px;}}
    .pr-kpi-label {{font-size:10px;color:#6b7280;text-transform:uppercase;}}
    .pr-kpi-value {{font-size:14px;font-weight:900;margin-top:2px;}}
    .pr-grid {{display:grid;grid-template-columns:1fr 1fr;gap:10px;}}
    .pr-box {{border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;}}
    .pr-wide {{grid-column:1/-1;}}
    .pr-box-title {{background:#111827;color:white;font-size:12px;font-weight:800;padding:6px 8px;}}
    .pr-table {{width:100%;border-collapse:collapse;font-size:10.5px;}}
    .pr-table th {{background:#f3f4f6;text-align:left;padding:5px;border-bottom:1px solid #e5e7eb;}}
    .pr-table td {{padding:5px;border-bottom:1px solid #f1f5f9;}}
    .pr-note {{font-size:11px;line-height:1.35;color:#374151;padding:8px;background:#f9fafb;}}
    .pr-empty {{font-size:11px;color:#6b7280;padding:8px;}}
    </style>
    <div class="pr-report">
        <div class="pr-head">
            <div>
                <div class="pr-title">Monthly Sales Master Report</div>
                <div class="pr-sub">Rate-wise, testing-wise, payment-wise monthly summary</div>
            </div>
            <div class="pr-date">{esc(summary.get("month"))}<br>{esc(summary.get("from_date"))} to {esc(summary.get("to_date"))}</div>
        </div>

        <div class="pr-kpis">
            <div class="pr-kpi"><div class="pr-kpi-label">Total Sale</div><div class="pr-kpi-value">{money(summary.get("total_sale"))}</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Gross Liters</div><div class="pr-kpi-value">{float(summary.get("total_gross_liters") or 0):,.2f} L</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Testing Liters</div><div class="pr-kpi-value">{float(summary.get("total_testing_liters") or 0):,.2f} L</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Net Sale Liters</div><div class="pr-kpi-value">{float(summary.get("total_liters") or 0):,.2f} L</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Cash Sale</div><div class="pr-kpi-value">{money(summary.get("cash_sale"))}</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Paytm Sale</div><div class="pr-kpi-value">{money(summary.get("paytm_sale"))}</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">CCMS Sale</div><div class="pr-kpi-value">{money(summary.get("ccms_sale"))}</div></div>
            <div class="pr-kpi"><div class="pr-kpi-label">Credit Sale</div><div class="pr-kpi-value">{money(summary.get("credit_sale"))}</div></div>
        </div>

        <div class="pr-grid">
            <div class="pr-box">
                <div class="pr-box-title">Fuel Summary</div>
                {table_html(["Fuel","Gross Liters","Testing Liters","Net Sale Liters","Amount"], fuel_rows)}
            </div>
            <div class="pr-box">
                <div class="pr-box-title">Payment Summary</div>
                {table_html(["Particular","Amount"], payment_rows)}
            </div>
            <div class="pr-box pr-wide">
                <div class="pr-box-title">Date-wise Daily Summary</div>
                {table_html(["Date","Gross Liters","Testing Liters","Net Sale Liters","Total Sale","Cash","Paytm","CCMS","Credit"], daily_rows)}
            </div>
            <div class="pr-box pr-wide">
                <div class="pr-box-title">Rate-wise Breakup</div>
                {table_html(["Date","Fuel","Rate","Gross Liters","Testing Liters","Net Sale Liters","Amount"], rate_rows)}
            </div>
            <div class="pr-box pr-wide">
                <div class="pr-box-title">Salesman-wise Summary</div>
                {table_html(["Salesman","Petrol L","Petrol Amount","Diesel L","Diesel Amount","Testing Liters","Net Sale Liters","Total Amount"], salesman_rows)}
            </div>
            <div class="pr-box pr-wide">
                <div class="pr-box-title">Final Ledger Balance</div>
                {table_html(["Ledger","Credit/Inflow","Debit/Outflow","Balance"], ledger_rows)}
            </div>
        </div>
    </div>
    """
    return html.strip()


def monthly_sales_master_tab():
    st.subheader("Monthly Sales Master")
    st.caption("Daily price update aur testing ko safely handle karta hai. Amount saved/locked rate se calculate hota hai.")

    today = date.today()
    c1, c2 = st.columns(2)
    with c1:
        month = st.selectbox("Month", list(range(1, 13)), index=today.month - 1, key="monthly_sales_master_month")
    with c2:
        year = st.number_input("Year", min_value=2020, max_value=2100, value=today.year, step=1, key="monthly_sales_master_year")

    report = get_monthly_sales_master_report(month=month, year=year)
    summary = report.get("summary") or {}

    view = st.radio(
        "Monthly Report View",
        ["Professional Summary", "Detailed Checking"],
        horizontal=True,
        key=f"monthly_sales_master_view_{int(year)}_{int(month):02d}",
    )

    if view == "Professional Summary":
        _sales_summary_metric_cards(summary)

        html_data = _monthly_sales_professional_html(report, summary)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download Print HTML",
                html_data,
                file_name=f"monthly_sales_master_{int(year)}_{int(month):02d}.html",
                mime="text/html",
                key=f"monthly_sales_master_html_{int(year)}_{int(month):02d}",
            )
        with c2:
            st.info("Rate-wise breakup aur testing summary included.")

        components.html(html_data, height=1050, scrolling=True)
        return

    _sales_summary_metric_cards(summary)

    st.markdown("### Fuel Summary")
    render_report(report.get("fuel_summary") or [], f"monthly_fuel_{int(year)}_{int(month):02d}", "Monthly Fuel Summary", f"monthly_fuel_{int(year)}_{int(month):02d}")

    st.markdown("### Date-wise Summary")
    render_report(report.get("daily_summary") or [], f"monthly_daily_{int(year)}_{int(month):02d}", "Monthly Date-wise Summary", f"monthly_daily_{int(year)}_{int(month):02d}")

    st.markdown("### Rate-wise Breakup")
    render_report(report.get("rate_summary") or [], f"monthly_rate_{int(year)}_{int(month):02d}", "Monthly Rate-wise Breakup", f"monthly_rate_{int(year)}_{int(month):02d}")

    st.markdown("### Salesman-wise Summary")
    render_report(report.get("salesman_summary") or [], f"monthly_salesman_{int(year)}_{int(month):02d}", "Monthly Salesman-wise Summary", f"monthly_salesman_{int(year)}_{int(month):02d}")

    st.markdown("### Payment Summary")
    render_report(report.get("payment_summary") or [], f"monthly_payment_{int(year)}_{int(month):02d}", "Monthly Payment Summary", f"monthly_payment_{int(year)}_{int(month):02d}")

    st.markdown("### Expense Summary")
    render_report(report.get("expense_summary") or [], f"monthly_expense_{int(year)}_{int(month):02d}", "Monthly Expense Summary", f"monthly_expense_{int(year)}_{int(month):02d}")

    st.markdown("### Final Ledger Balances")
    render_report(report.get("ledger_balances") or [], f"monthly_ledger_{int(year)}_{int(month):02d}", "Monthly Final Ledger Balances", f"monthly_ledger_{int(year)}_{int(month):02d}")



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
