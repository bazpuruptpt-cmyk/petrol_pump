from io import BytesIO
from datetime import datetime


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


def _para(text, style):
    from reportlab.platypus import Paragraph
    from xml.sax.saxutils import escape

    return Paragraph(escape(_s(text)).replace("\n", "<br/>"), style)


def build_salesman_settlement_pdf(report):
    """
    Returns: (pdf_bytes, error)
    A4 settlement handover report with signature space.
    """
    if not report or report.get("error"):
        return b"", report.get("error") if report else "Report data missing."

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            KeepTogether,
        )
    except Exception:
        return b"", "PDF export needs reportlab in requirements.txt"

    output = BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        alignment=1,
        spaceAfter=6,
    )
    h_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        spaceBefore=8,
        spaceAfter=4,
    )
    normal = ParagraphStyle(
        "NormalSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
    )
    small = ParagraphStyle(
        "Tiny",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=8,
    )

    story = []

    story.append(Paragraph("Salesman Settlement Report", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}", small))
    story.append(Spacer(1, 4))

    totals = report.get("totals") or {}
    nozzle_rows = report.get("nozzle_rows") or []
    credit_rows = report.get("credit_rows") or []

    header_data = [
        ["Date", _s(report.get("date")), "Settlement ID", _s(report.get("settlement_id"))],
        ["Salesman", _s(report.get("salesman_name")), "Shift ID", _s(report.get("shift_id"))],
        ["Status", _s(report.get("status")).upper(), "Approved At", _s(report.get("approved_at") or "-")],
    ]

    header_table = Table(header_data, colWidths=[28 * mm, 67 * mm, 28 * mm, 67 * mm])
    header_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F4F7")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F2F4F7")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(header_table)

    story.append(Paragraph("Nozzle Reading and Sale Details", h_style))

    nozzle_data = [[
        "Nozzle",
        "Fuel",
        "Opening",
        "Closing",
        "Sale Ltrs",
        "Rate",
        "Sale Amount",
    ]]

    for r in nozzle_rows:
        nozzle_data.append([
            _s(r.get("nozzle_name")),
            _s(r.get("fuel_type")),
            _num(r.get("opening")),
            _num(r.get("closing")),
            _num(r.get("liters")),
            _money(r.get("rate")),
            _money(r.get("amount")),
        ])

    if not nozzle_rows:
        nozzle_data.append(["-", "-", "0.00", "0.00", "0.00", "Rs. 0.00", "Rs. 0.00"])

    nozzle_table = Table(
        nozzle_data,
        colWidths=[29 * mm, 24 * mm, 25 * mm, 25 * mm, 22 * mm, 25 * mm, 40 * mm],
        repeatRows=1,
    )
    nozzle_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E4E7EC")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(nozzle_table)

    story.append(Paragraph("Payment Breakup", h_style))

    payment_data = [
        ["Total Liters", _num(totals.get("total_liters")), "Total Sale", _money(totals.get("total_sale"))],
        ["Cash", _money(totals.get("cash")), "Paytm", _money(totals.get("paytm"))],
        ["CCMS", _money(totals.get("ccms")), "Credit", _money(totals.get("credit"))],
        ["Payment Total", _money(totals.get("payment_total")), "Difference", _money(totals.get("difference"))],
    ]
    payment_table = Table(payment_data, colWidths=[35 * mm, 60 * mm, 35 * mm, 60 * mm])
    payment_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F4F7")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F2F4F7")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(payment_table)

    story.append(Paragraph("Credit Sale Details", h_style))

    credit_data = [["Creditor", "Amount", "Vehicle", "Comment"]]
    for c in credit_rows:
        credit_data.append([
            _para(c.get("creditor"), small),
            _money(c.get("amount")),
            _para(c.get("vehicle"), small),
            _para(c.get("comment"), small),
        ])

    if not credit_rows:
        credit_data.append(["No credit sale", "Rs. 0.00", "-", "-"])

    credit_table = Table(
        credit_data,
        colWidths=[55 * mm, 28 * mm, 35 * mm, 72 * mm],
        repeatRows=1,
    )
    credit_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E4E7EC")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(credit_table)

    if report.get("manager_note"):
        story.append(Paragraph("Manager Note", h_style))
        story.append(_para(report.get("manager_note"), normal))

    story.append(Spacer(1, 14))

    signature_data = [
        ["Salesman Signature", "Manager Signature"],
        ["\n\n\n", "\n\n\n"],
        ["Name: ____________________", "Name: ____________________"],
        ["Date: ____________________", "Date: ____________________"],
    ]
    signature_table = Table(signature_data, colWidths=[95 * mm, 95 * mm])
    signature_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#98A2B3")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, 1), 18),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 18),
    ]))
    story.append(KeepTogether(signature_table))

    def page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(200 * mm, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    output.seek(0)
    return output.getvalue(), None
