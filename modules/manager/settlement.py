from datetime import date
import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.settlement_db import (
    get_pending_settlements,
    get_settlements_by_status,
    get_settlements_by_date,
    get_sale_entries_for_settlement,
    get_credit_rows_for_settlement,
    get_shift_assignments_for_settlement,
    calculate_closing_meter_rows,
    save_manager_closing_readings,
    approve_settlement,
    hold_settlement,
    reopen_settlement,
    get_manager_payment_summary,
)


def _css():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.2rem; max-width: 1240px;}
        div[data-testid="stMetric"] {
            border: 1px solid #e8edf3;
            padding: 8px 10px;
            border-radius: 12px;
            box-shadow: 0 1px 4px rgba(16,24,40,.04);
        }
        div[data-testid="stMetricValue"] {font-size: 1.16rem;}
        .muted {font-size:.82rem;color:#667085;}
        .step-title {font-size:1rem;font-weight:700;margin:8px 0 4px;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@require_role(["owner", "manager"])
def settlement_page():
    _css()

    st.title("Manager Settlement")
    st.caption("Duty → Nozzles → Closing reading → Meter total → Payment match → Approve.")

    show_today_manager_summary()

    tab1, tab2, tab3 = st.tabs(["Pending Approval", "Hold / Reopened", "History"])

    with tab1:
        show_pending_settlements()

    with tab2:
        show_hold_reopened()

    with tab3:
        show_settlement_history()


def show_today_manager_summary():
    summary = get_manager_payment_summary(str(date.today()))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today Meter Sale", format_currency(summary["total_sale"]))
    c2.metric("Cash", format_currency(summary["cash"]))
    c3.metric("Paytm", format_currency(summary["paytm"]))
    c4.metric("CCMS", format_currency(summary["ccms"]))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Credit", format_currency(summary["credit"]))
    c6.metric("Pending", summary["pending_count"])
    c7.metric("Approved", summary["approved_count"])
    c8.metric("Hold", summary["hold_count"])


def show_pending_settlements():
    rows = get_pending_settlements()

    st.subheader("Pending Settlements")

    if not rows:
        st.info("No pending settlements.")
        return

    for row in rows:
        settlement_card(row, mode="pending")


def show_hold_reopened():
    hold_rows = get_settlements_by_status("hold")
    reopened_rows = get_settlements_by_status("reopened")
    rows = hold_rows + reopened_rows

    st.subheader("Hold / Reopened Settlements")

    if not rows:
        st.info("No hold/reopened settlements.")
        return

    for row in rows:
        settlement_card(row, mode="hold_reopened")


def show_settlement_history():
    selected_date = st.date_input("Date", value=date.today())
    rows = get_settlements_by_date(str(selected_date))

    if not rows:
        st.info("No settlements found for selected date.")
        return

    for row in rows:
        settlement_card(row, mode="history")


def settlement_card(row: dict, mode: str):
    user = get_current_user()

    with st.container(border=True):
        top1, top2, top3, top4 = st.columns(4)
        top1.metric("Settlement ID", row.get("id"))
        top2.metric("Salesman", row.get("salesman_name"))
        top3.metric("Meter Sale", format_currency(row.get("meter_total_calc")))
        top4.metric("Difference", format_currency(row.get("match_difference")))

        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("Cash", format_currency(row.get("cash_amount")))
        b2.metric("Paytm", format_currency(row.get("paytm_amount")))
        b3.metric("CCMS", format_currency(row.get("ccms_amount")))
        b4.metric("Credit", format_currency(row.get("credit_amount")))
        b5.metric("Status", row.get("status"))

        st.markdown(
            f"<div class='muted'>Shift: {row.get('shift_id')} · Date: {row.get('date')} · Created: {row.get('created_at')}</div>",
            unsafe_allow_html=True,
        )

        render_closing_reading_editor(row)

        if row.get("closing_saved"):
            if row.get("is_matched"):
                st.success("MATCHED: Meter sale = Cash + Paytm + CCMS + Credit")
            else:
                st.error("NOT MATCHED: Meter sale payment breakup se match nahi kar raha.")
        else:
            st.warning("Closing readings not saved yet.")

        note = st.text_input(
            "Manager note",
            value=row.get("manager_note") or "",
            key=f"note_{row.get('id')}_{mode}",
        )

        if mode in ["pending", "hold_reopened"]:
            a1, a2, a3 = st.columns(3)

            with a1:
                if st.button("Approve", key=f"approve_{row.get('id')}", use_container_width=True):
                    approved, error = approve_settlement(row.get("id"), user["id"])
                    if approved:
                        st.success("Settlement approved.")
                        st.rerun()
                    else:
                        st.error(error or "Approval failed.")

            with a2:
                if st.button("Hold", key=f"hold_{row.get('id')}", use_container_width=True):
                    held, error = hold_settlement(row.get("id"), user["id"], note)
                    if held:
                        st.warning("Settlement put on hold.")
                        st.rerun()
                    else:
                        st.error(error or "Hold failed.")

            with a3:
                if st.button("Reopen", key=f"reopen_{row.get('id')}", use_container_width=True):
                    reopened, error = reopen_settlement(row.get("id"), user["id"], note)
                    if reopened:
                        st.info("Settlement reopened.")
                        st.rerun()
                    else:
                        st.error(error or "Reopen failed.")

        with st.expander("Sale Entries"):
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

        with st.expander("Credit Rows"):
            credits = get_credit_rows_for_settlement(row.get("id"))
            if credits:
                st.dataframe(
                    [
                        {
                            "Creditor": (c.get("credit_parties") or {}).get("name"),
                            "Amount": format_currency(c.get("amount")),
                            "Status": c.get("status"),
                            "Created At": c.get("created_at"),
                        }
                        for c in credits
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No credit entries.")


def render_closing_reading_editor(row: dict):
    st.markdown("<div class='step-title'>Manager Closing Reading</div>", unsafe_allow_html=True)

    assignments = get_shift_assignments_for_settlement(row)

    if not assignments:
        st.info("No nozzle assignment found for this shift.")
        return

    closing_inputs = {}

    for assignment in assignments:
        nozzle = assignment.get("nozzles") or {}
        assignment_id = assignment.get("id")
        opening = float(assignment.get("opening_reading") or 0)
        saved_closing = assignment.get("closing_reading")
        default_closing = float(saved_closing if saved_closing is not None else opening)

        c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1.2])
        c1.write(f"**{nozzle.get('nozzle_name')}**")
        c1.caption(nozzle.get("fuel_type"))
        c2.metric("Opening", f"{opening:.2f}")
        c3.metric("Current", f"{float(nozzle.get('current_reading') or 0):.2f}")

        with c4:
            closing = st.number_input(
                "Closing",
                min_value=0.0,
                value=default_closing,
                step=0.01,
                format="%.2f",
                key=f"closing_{row.get('id')}_{assignment_id}",
            )

        closing_inputs[assignment_id] = closing

    calc_rows, meter_total, error = calculate_closing_meter_rows(row, closing_inputs)

    if error:
        st.error(error)
        return

    payment_total = (
        float(row.get("cash_amount") or 0)
        + float(row.get("paytm_amount") or 0)
        + float(row.get("ccms_amount") or 0)
        + float(row.get("credit_amount") or 0)
    )
    difference = round(meter_total - payment_total, 2)

    st.markdown("<div class='step-title'>Calculated Meter Total</div>", unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("Meter Sale", format_currency(meter_total))
    m2.metric("Salesman Payment", format_currency(payment_total))
    m3.metric("Difference", format_currency(difference))

    with st.expander("Nozzle Calculation"):
        st.dataframe(
            [
                {
                    "Nozzle": r["nozzle_name"],
                    "Fuel": r["fuel_type"],
                    "Opening": r["opening"],
                    "Closing": r["closing"],
                    "Actual Liters": r["actual_liters"],
                    "Rate": format_currency(r["rate"]),
                    "Sale Amount": format_currency(r["sale_amount"]),
                }
                for r in calc_rows
            ],
            use_container_width=True,
            hide_index=True,
        )

    if st.button("Save Closing Readings", type="primary", key=f"save_closing_{row.get('id')}"):
        updated, save_error = save_manager_closing_readings(
            settlement_id=row.get("id"),
            closing_inputs=closing_inputs,
            manager_id=get_current_user()["id"],
        )

        if updated:
            st.success("Closing readings saved. Nozzle current reading updated for next opening.")
            st.rerun()
        else:
            st.error(save_error or "Closing readings save failed.")
