from io import BytesIO, StringIO
import csv
import html
from datetime import datetime

import streamlit as st


def _clean_rows(rows):
    clean = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        clean.append({str(k): "" if v is None else v for k, v in row.items()})
    return clean


def rows_to_csv_bytes(rows):
    rows = _clean_rows(rows)
    if not rows:
        return b""

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def rows_to_xlsx_bytes(rows, sheet_name="Report"):
    rows = _clean_rows(rows)
    output = BytesIO()

    if not rows:
        rows = [{"Message": "No data found"}]

    try:
        import pandas as pd

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df = pd.DataFrame(rows)
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31])

            ws = writer.sheets[sheet_name[:31]]
            for col_cells in ws.columns:
                max_len = 10
                col_letter = col_cells[0].column_letter
                for cell in col_cells:
                    value = "" if cell.value is None else str(cell.value)
                    max_len = max(max_len, min(len(value) + 2, 35))
                ws.column_dimensions[col_letter].width = max_len

        output.seek(0)
        return output.getvalue()

    except Exception:
        # Fallback: Excel can open CSV even if xlsx engine is unavailable.
        return rows_to_csv_bytes(rows)


def rows_to_pdf_bytes(rows, title="Report"):
    rows = _clean_rows(rows)

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

        output = BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=landscape(A4),
            rightMargin=24,
            leftMargin=24,
            topMargin=24,
            bottomMargin=24,
        )

        styles = getSampleStyleSheet()
        story = [
            Paragraph(html.escape(title), styles["Title"]),
            Paragraph(datetime.now().strftime("Generated: %d-%m-%Y %H:%M"), styles["Normal"]),
            Spacer(1, 12),
        ]

        if not rows:
            story.append(Paragraph("No data found.", styles["Normal"]))
        else:
            headers = list(rows[0].keys())
            data = [headers]
            for row in rows:
                data.append([str(row.get(h, ""))[:80] for h in headers])

            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D5DD")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FCFCFD")]),
            ]))
            story.append(table)

        doc.build(story)
        output.seek(0)
        return output.getvalue(), None

    except Exception as exc:
        return b"", str(exc)


def render_export_buttons(rows, filename_prefix, title="Report", key_prefix="export"):
    rows = _clean_rows(rows)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.download_button(
            "Download CSV",
            data=rows_to_csv_bytes(rows),
            file_name=f"{filename_prefix}.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
            use_container_width=True,
        )

    with c2:
        xlsx_bytes = rows_to_xlsx_bytes(rows, sheet_name=title[:31])
        st.download_button(
            "Download Excel",
            data=xlsx_bytes,
            file_name=f"{filename_prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_xlsx",
            use_container_width=True,
        )

    with c3:
        pdf_bytes, pdf_error = rows_to_pdf_bytes(rows, title=title)
        if pdf_error:
            st.warning("PDF export needs reportlab in requirements.txt")
            st.code("reportlab")
        else:
            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=f"{filename_prefix}.pdf",
                mime="application/pdf",
                key=f"{key_prefix}_pdf",
                use_container_width=True,
            )


def print_view(rows, title="Print View"):
    rows = _clean_rows(rows)

    st.subheader(title)
    if not rows:
        st.info("No data found.")
        return

    escaped_headers = [html.escape(str(h)) for h in rows[0].keys()]

    html_rows = []
    html_rows.append("<tr>" + "".join(f"<th>{h}</th>" for h in escaped_headers) + "</tr>")

    for row in rows:
        html_rows.append(
            "<tr>" + "".join(
                f"<td>{html.escape(str(row.get(h, '')))}</td>" for h in row.keys()
            ) + "</tr>"
        )

    st.markdown(
        f"""
        <style>
        @media print {{
            .stButton, .stDownloadButton, header, footer, [data-testid="stSidebar"] {{
                display: none !important;
            }}
            .print-table {{
                font-size: 10px;
            }}
        }}
        .print-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        .print-table th {{
            background: #f2f4f7;
            text-align: left;
            padding: 6px;
            border: 1px solid #d0d5dd;
        }}
        .print-table td {{
            padding: 5px;
            border: 1px solid #d0d5dd;
        }}
        </style>
        <div class="section-card">
            <h3>{html.escape(title)}</h3>
            <p>Use browser print: Ctrl+P / Cmd+P</p>
            <table class="print-table">{''.join(html_rows)}</table>
        </div>
        """,
        unsafe_allow_html=True,
    )
