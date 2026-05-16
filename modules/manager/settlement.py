from datetime import date
import streamlit as st

from utils.permissions import require_role
from utils.formatters import format_currency
from database.settlement_db import (
    get_settlements_by_date,
    get_sale_entries_for_settlement,
    get_credit_rows_for_settlement,
)
from database.salesman_settlement_report_db import get_salesman_settlement_detail
from utils.salesman_settlement_pdf import build_salesman_settlement_pdf
from utils.salesman_settlement_print import render_salesman_settlement_print_button


def _safe_float(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _payment_total(row):
    return round(
        _safe_float(row.get("cash_amount"))
        + _safe_float(row.get("paytm_amount"))
        + _safe_float(row.get("ccms_amount"))
        + _safe_float(row.get("credit_amount")),
        2,
    )


def _approved_rows(entry_date):
    rows = get_settlements_by_date(entry_date)
    return [r for r in rows if (r.get("status") or "") == "approved"]


def _history_rows(entry_date, status_filter="approved"):
    rows = get_settlements_by_date(entry_date)
    if status_filter and status_filter != "all":
        rows = [r for r in rows if (r.get("status") or "") == status_filter]
    return rows


def _summary_metrics(rows):
    total_sale = round(sum(_safe_float(r.get("meter_total_calc") or r.get("meter_total")) for r in rows), 2)
    cash = round(sum(_safe_float(r.get("cash_amount")) for r in rows), 2)
    paytm = round(sum(_safe_float(r.get("paytm_amount")) for r in rows), 2)
    ccms = round(sum(_safe_float(r.get("ccms_amount")) for r in rows), 2)
    credit = round(sum(_safe_float(r.get("credit_amount")) for r in rows), 2)
    cash_given = round(sum(_safe_float(r.get("cash_given_to_creditor_amount")) for r in rows), 2)
    cash_to_manager = round(sum(
        _safe_float(r.get("cash_transfer_expected"))
        if r.get("cash_transfer_expected") is not None
        else (_safe_float(r.get("cash_amount")) - _safe_float(r.get("cash_given_to_creditor_amount")))
        for r in rows
    ), 2)

    return {
        "count": len(rows),
        "total_sale": total_sale,
        "cash": cash,
        "paytm": paytm,
        "ccms": ccms,
        "credit": credit,
        "cash_given": cash_given,
        "cash_to_manager": cash_to_manager,
    }


@require_role(["owner", "manager"])
def settlement_page():
    st.title("Sale Settlement / Reports")
    st.caption("Report/history screen only. Approve/Reject/Hold actions sirf Sale Approval page par honge.")

    section = st.radio(
        "Settlement Section",
        [
            "Today Approved",
            "Date-wise History",
            "Salesman Settlement Print",
        ],
        horizontal=True,
        key="settlement_active_section",
    )

    if section == "Today Approved":
        show_today_approved()
    elif section == "Date-wise History":
        show_datewise_history()
    elif section == "Salesman Settlement Print":
        show_print_history()


def show_today_approved():
    selected_date = str(date.today())
    rows = _approved_rows(selected_date)

    st.subheader("Today Approved Settlements")
    render_summary(rows)

    if not rows:
        st.info("Aaj koi approved settlement nahi hai.")
        return

    for idx, row in enumerate(rows):
        settlement_report_card(row, key_prefix=f"today_{idx}_{row.get('id')}")


def show_datewise_history():
    selected_date = str(st.date_input("Date", value=date.today(), key="settlement_history_date"))
    status_filter = st.selectbox(
        "Status",
        ["approved", "rejected", "hold", "reopened", "pending", "all"],
        index=0,
        key="settlement_history_status",
    )

    rows = _history_rows(selected_date, status_filter=status_filter)

    st.subheader("Date-wise Settlement History")
    render_summary(rows)

    if not rows:
        st.info("Selected date/status par settlement record nahi hai.")
        return

    for idx, row in enumerate(rows):
        settlement_report_card(row, key_prefix=f"history_{idx}_{row.get('id')}", compact=(row.get("status") != "approved"))


def show_print_history():
    selected_date = str(st.date_input("Approved Date", value=date.today(), key="settlement_print_date"))
    rows = _approved_rows(selected_date)

    st.subheader("Salesman-wise A4 Settlement Print")

    if not rows:
        st.info("Selected date par approved settlement nahi hai.")
        return

    for idx, row in enumerate(rows):
        settlement_report_card(row, key_prefix=f"print_{idx}_{row.get('id')}", show_details=False)


def render_summary(rows):
    summary = _summary_metrics(rows)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Records", summary["count"])
    c2.metric("Meter Sale", format_currency(summary["total_sale"]))
    c3.metric("Cash Sale", format_currency(summary["cash"]))
    c4.metric("Cash To Manager", format_currency(summary["cash_to_manager"]))

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Paytm", format_currency(summary["paytm"]))
    p2.metric("CCMS", format_currency(summary["ccms"]))
    p3.metric("Fuel Credit", format_currency(summary["credit"]))
    p4.metric("Cash Given Creditor", format_currency(summary["cash_given"]))


def settlement_report_card(row, key_prefix, compact=False, show_details=True):
    settlement_id = row.get("id")
    status = row.get("status")

    with st.container(border=True):
        title = f"Settlement {settlement_id} · Shift {row.get('shift_id')} · {row.get('salesman_name')}"
        st.subheader(title)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Meter Sale", format_currency(row.get("meter_total_calc") or row.get("meter_total")))
        c2.metric("Payment Total", format_currency(_payment_total(row)))
        c3.metric("Difference", format_currency(row.get("match_difference") or row.get("difference")))
        c4.metric("Status", status)

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Cash Sale", format_currency(row.get("cash_amount")))
        p2.metric("Paytm", format_currency(row.get("paytm_amount")))
        p3.metric("CCMS", format_currency(row.get("ccms_amount")))
        p4.metric("Fuel Credit", format_currency(row.get("credit_amount")))

        h1, h2, h3 = st.columns(3)
        h1.metric("Cash Sale", format_currency(row.get("cash_amount")))
        h2.metric("Cash Given Creditor", format_currency(row.get("cash_given_to_creditor_amount")))
        h3.metric(
            "Cash To Manager",
            format_currency(
                row.get("cash_transfer_expected")
                if row.get("cash_transfer_expected") is not None
                else _safe_float(row.get("cash_amount")) - _safe_float(row.get("cash_given_to_creditor_amount"))
            ),
        )

        st.caption(f"Date: {row.get('date')} · Created: {row.get('created_at')} · Note: {row.get('manager_note') or '-'}")

        if status == "approved":
            render_report_buttons(settlement_id, row, key_prefix)
        else:
            st.info("Non-approved record. Action ke liye Sale Approval page use karein.")

        if compact or not show_details:
            return

        with st.expander("Nozzle / Reading Summary", expanded=True):
            nozzle_rows = row.get("nozzle_readings") or []
            if nozzle_rows:
                st.dataframe(
                    [
                        {
                            "Nozzle": r.get("nozzle_name"),
                            "Fuel": r.get("fuel_type"),
                            "Opening": r.get("opening"),
                            "Closing": r.get("closing"),
                            "Gross Liters": r.get("gross_liters", r.get("actual_liters")),
                            "Testing": r.get("testing_liters", r.get("testing_adj", 0)),
                            "Net Sale Liters": r.get("actual_liters"),
                            "Rate": format_currency(r.get("rate")),
                            "Sale Amount": format_currency(r.get("sale_amount")),
                        }
                        for r in nozzle_rows
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("Reading/nozzle rows not saved yet.")

        with st.expander("Sale Entries", expanded=False):
            entries = get_sale_entries_for_settlement(row)
            if entries:
                st.dataframe(
                    [
                        {
                            "Entry Time": e.get("entry_time"),
                            "Nozzle": (e.get("nozzles") or {}).get("nozzle_name"),
                            "Fuel": e.get("fuel_type"),
                            "Liters": e.get("liters"),
                            "Rate": format_currency(e.get("rate")),
                            "Amount": format_currency(e.get("amount")),
                            "Status": e.get("status"),
                        }
                        for e in entries
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No sale entries found.")

        with st.expander("Credit Rows", expanded=False):
            credits = get_credit_rows_for_settlement(settlement_id)
            if credits:
                st.dataframe(
                    [
                        {
                            "Creditor": (c.get("credit_parties") or {}).get("name") or c.get("party_id"),
                            "Type": c.get("type"),
                            "Amount": format_currency(c.get("amount")),
                            "Status": c.get("status"),
                            "Note": c.get("note"),
                            "Created": c.get("created_at"),
                        }
                        for c in credits
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No credit rows found.")


def render_report_buttons(settlement_id, row, key_prefix):
    report_data = get_salesman_settlement_detail(settlement_id)
    pdf_bytes, pdf_error = build_salesman_settlement_pdf(report_data)

    if pdf_error:
        st.warning(pdf_error)
        return

    file_name = f"salesman_settlement_{row.get('date')}_shift_{row.get('shift_id')}_settlement_{settlement_id}.pdf"

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Download A4 Settlement PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
            key=f"settlement_pdf_{key_prefix}",
            use_container_width=True,
        )

    with c2:
        render_salesman_settlement_print_button(
            report_data,
            key=f"print_settlement_{key_prefix}",
        )
