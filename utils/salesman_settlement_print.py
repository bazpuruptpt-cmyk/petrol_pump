import json
import streamlit.components.v1 as components


def _s(value):
    if value is None:
        return ""
    return str(value)


def _n(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _money(value):
    return f"Rs. {_n(value):,.2f}"


def _num(value):
    return f"{_n(value):,.2f}"


def _escape(value):
    return (
        _s(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_salesman_settlement_print_html(report):
    totals = report.get("totals") or {}
    nozzle_rows = report.get("nozzle_rows") or []
    credit_rows = report.get("credit_rows") or []

    nozzle_html = ""
    for r in nozzle_rows:
        nozzle_html += f"""
        <tr>
            <td>{_escape(r.get("nozzle_name"))}</td>
            <td>{_escape(r.get("fuel_type"))}</td>
            <td class="num">{_num(r.get("opening"))}</td>
            <td class="num">{_num(r.get("closing"))}</td>
            <td class="num">{_num(r.get("liters"))}</td>
            <td class="num">{_money(r.get("rate"))}</td>
            <td class="num">{_money(r.get("amount"))}</td>
        </tr>
        """

    if not nozzle_html:
        nozzle_html = """
        <tr><td colspan="7">No nozzle reading found.</td></tr>
        """

    credit_html = ""
    for c in credit_rows:
        credit_html += f"""
        <tr>
            <td>{_escape(c.get("creditor"))}</td>
            <td class="num">{_money(c.get("amount"))}</td>
            <td>{_escape(c.get("vehicle"))}</td>
            <td>{_escape(c.get("comment"))}</td>
        </tr>
        """

    if not credit_html:
        credit_html = """
        <tr><td>No credit sale</td><td class="num">Rs. 0.00</td><td>-</td><td>-</td></tr>
        """

    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Salesman Settlement Report</title>
<style>
    @page {{
        size: A4;
        margin: 10mm;
    }}
    body {{
        font-family: Arial, sans-serif;
        font-size: 11px;
        color: #111827;
        margin: 0;
        background: #ffffff;
    }}
    .toolbar {{
        margin: 0 0 10px 0;
        padding: 8px;
        background: #f3f4f6;
        border: 1px solid #d1d5db;
        border-radius: 8px;
    }}
    .print-btn {{
        border: 1px solid #ef4444;
        background: white;
        color: #ef4444;
        padding: 8px 14px;
        border-radius: 8px;
        font-weight: 700;
        cursor: pointer;
    }}
    .page {{
        width: 190mm;
        min-height: 270mm;
        margin: 0 auto;
        background: white;
    }}
    h1 {{
        text-align: center;
        font-size: 18px;
        margin: 0 0 8px 0;
    }}
    h2 {{
        font-size: 13px;
        margin: 12px 0 6px 0;
    }}
    table {{
        border-collapse: collapse;
        width: 100%;
        margin-bottom: 8px;
    }}
    th, td {{
        border: 1px solid #d0d5dd;
        padding: 5px;
        vertical-align: top;
    }}
    th {{
        background: #e5e7eb;
        font-weight: 700;
    }}
    .label {{
        background: #f3f4f6;
        font-weight: 700;
        width: 18%;
    }}
    .num {{
        text-align: right;
        white-space: nowrap;
    }}
    .sign-box {{
        height: 70px;
    }}
    .muted {{
        color: #667085;
        font-size: 10px;
    }}
    @media print {{
        .toolbar {{
            display: none;
        }}
        body {{
            margin: 0;
        }}
        .page {{
            margin: 0;
            width: auto;
            min-height: auto;
        }}
    }}
</style>
</head>
<body>
<div class="toolbar">
    <button class="print-btn" onclick="window.print()">Print A4 Settlement Report</button>
</div>

<div class="page">
    <h1>Salesman Settlement Report</h1>
    <div class="muted">Print Date: <span id="printDate"></span></div>

    <table>
        <tr>
            <td class="label">Date</td><td>{_escape(report.get("date"))}</td>
            <td class="label">Settlement ID</td><td>{_escape(report.get("settlement_id"))}</td>
        </tr>
        <tr>
            <td class="label">Salesman</td><td>{_escape(report.get("salesman_name"))}</td>
            <td class="label">Shift ID</td><td>{_escape(report.get("shift_id"))}</td>
        </tr>
        <tr>
            <td class="label">Status</td><td>{_escape(report.get("status")).upper()}</td>
            <td class="label">Approved At</td><td>{_escape(report.get("approved_at") or "-")}</td>
        </tr>
    </table>

    <h2>Nozzle Reading and Sale Details</h2>
    <table>
        <thead>
            <tr>
                <th>Nozzle</th>
                <th>Fuel</th>
                <th>Opening</th>
                <th>Closing</th>
                <th>Sale Ltrs</th>
                <th>Rate</th>
                <th>Sale Amount</th>
            </tr>
        </thead>
        <tbody>
            {nozzle_html}
        </tbody>
    </table>

    <h2>Payment Breakup</h2>
    <table>
        <tr>
            <td class="label">Total Liters</td><td class="num">{_num(totals.get("total_liters"))}</td>
            <td class="label">Total Sale</td><td class="num">{_money(totals.get("total_sale"))}</td>
        </tr>
        <tr>
            <td class="label">Cash</td><td class="num">{_money(totals.get("cash"))}</td>
            <td class="label">Paytm</td><td class="num">{_money(totals.get("paytm"))}</td>
        </tr>
        <tr>
            <td class="label">CCMS</td><td class="num">{_money(totals.get("ccms"))}</td>
            <td class="label">Credit</td><td class="num">{_money(totals.get("credit"))}</td>
        </tr>
        <tr>
            <td class="label">Payment Total</td><td class="num">{_money(totals.get("payment_total"))}</td>
            <td class="label">Difference</td><td class="num">{_money(totals.get("difference"))}</td>
        </tr>
    </table>

    <h2>Credit Sale Details</h2>
    <table>
        <thead>
            <tr>
                <th>Creditor</th>
                <th>Amount</th>
                <th>Vehicle</th>
                <th>Comment</th>
            </tr>
        </thead>
        <tbody>
            {credit_html}
        </tbody>
    </table>

    <h2>Signatures</h2>
    <table>
        <tr>
            <th>Salesman Signature</th>
            <th>Manager Signature</th>
        </tr>
        <tr>
            <td class="sign-box"></td>
            <td class="sign-box"></td>
        </tr>
        <tr>
            <td>Name: ____________________</td>
            <td>Name: ____________________</td>
        </tr>
        <tr>
            <td>Date: ____________________</td>
            <td>Date: ____________________</td>
        </tr>
    </table>
</div>

<script>
document.getElementById("printDate").innerText = new Date().toLocaleString();
</script>
</body>
</html>
"""
    return html


def render_salesman_settlement_print_button(report, key=None):
    if not report or report.get("error"):
        return

    html = build_salesman_settlement_print_html(report)
    components.html(html, height=140, scrolling=False)
