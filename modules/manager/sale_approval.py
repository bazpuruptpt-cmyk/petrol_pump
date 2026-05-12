from datetime import date
import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.sale_approval_db import (
    get_pending_sale_approvals,
    get_sale_approvals,
    get_closing_assignments_for_approval,
    preview_closing_calculation,
    save_closing_for_approval,
    approve_sale_approval,
    reject_sale_approval,
    hold_sale_approval,
    reopen_sale_approval,
    get_manager_day_summary,
)


def _fmt_rows(rows, money_keys=None):
    money_keys = money_keys or []
    output = []

    for row in rows or []:
        x = row.copy()
        for key in money_keys:
            if key in x:
                x[key] = format_currency(x[key])
        output.append(x)

    return output


@require_role(["owner", "manager"])
def sale_approval_page():
    st.title("Sale Approval")
    st.caption("Action screen only: pending / hold / reopened sales. Approved sales yahan nahi dikhenge; approved records Sale Settlement/Reports me jayenge.")

    tab1, tab2, tab3 = st.tabs([
        "Pending Action",
        "Hold / Reopened",
        "Rejected History",
    ])

    with tab1:
        show_action_by_status("pending", title="Pending Sale Approvals", readonly=False)

    with tab2:
        show_hold_reopened_action()

    with tab3:
        show_action_by_status("rejected", title="Rejected Sale Approvals", readonly=True)


def show_action_by_status(status, title=None, readonly=False):
    rows = get_sale_approvals(status=status)

    st.subheader(title or f"{status.title()} Sale Approvals")

    if not rows:
        st.info(f"No {status} sale approvals.")
        return

    for i, row in enumerate(rows):
        approval_card(row, f"{status}_{i}_{row.get('id')}", readonly=readonly)


def show_hold_reopened_action():
    hold_rows = get_sale_approvals(status="hold")
    reopened_rows = get_sale_approvals(status="reopened")
    rows = hold_rows + reopened_rows

    st.subheader("Hold / Reopened Sale Approvals")

    if not rows:
        st.info("No hold/reopened sale approvals.")
        return

    for i, row in enumerate(rows):
        approval_card(row, f"hold_reopened_{i}_{row.get('id')}", readonly=False)


def show_pending():
    # Backward compatibility for any old imports/calls.
    show_action_by_status("pending", title="Pending Sale Approvals", readonly=False)


def show_by_status(status):
    # Backward compatibility for any old imports/calls.
    readonly = status in ["approved", "rejected"]
    show_action_by_status(status, readonly=readonly)


def approval_card(row, key_prefix, readonly=False):
    user = get_current_user()
    settlement_id = row.get("id")

    with st.container(border=True):
        st.subheader(f"Shift {row.get('shift_id')} · {row.get('salesman_name')}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Salesman Entry", format_currency(row.get("salesman_entry_total")))
        c2.metric("Manager Meter Sale", format_currency(row.get("meter_total_calc")))
        c3.metric("Payment Breakup", format_currency(row.get("payment_total")))
        c4.metric("Status", row.get("status"))

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Cash", format_currency(row.get("cash_amount")))
        p2.metric("Paytm", format_currency(row.get("paytm_amount")))
        p3.metric("CCMS", format_currency(row.get("ccms_amount")))
        p4.metric("Credit", format_currency(row.get("credit_amount")))

        st.write(f"**Date:** {row.get('date')} | **Settlement ID:** {settlement_id}")

        if not row.get("closing_saved"):
            st.warning("Closing reading pending. Approval button closing reading save hone ke baad hi valid hoga.")
        elif row.get("is_meter_payment_matched"):
            st.success("MATCHED: Manager meter sale = Salesman breakup")
        else:
            st.error("NOT MATCHED: Manager meter sale aur salesman breakup match nahi kar rahe.")

        if row.get("closing_saved") and not row.get("is_salesman_meter_matched"):
            st.warning(
                "Salesman entry total aur manager meter sale अलग है. Owner ke hisab me meter reading final rahegi."
            )

        render_closing_reading_block(settlement_id, key_prefix)

        with st.expander("Diesel / Petrol Sale Summary", expanded=True):
            fuel_rows = row.get("fuel_summary") or []
            if fuel_rows:
                st.dataframe(_fmt_rows(fuel_rows, money_keys=["Amount"]), use_container_width=True, hide_index=True)
            else:
                st.info("No sale entries found.")

        with st.expander("Creditor Details", expanded=True):
            credit_rows = []
            for c in row.get("credit_rows") or []:
                party = c.get("credit_parties") or {}
                credit_rows.append({
                    "Creditor": party.get("name") or c.get("party_id"),
                    "Amount": c.get("amount"),
                    "Status": c.get("status"),
                    "Reference": c.get("reference_id"),
                    "Created": c.get("created_at"),
                })

            if credit_rows:
                st.dataframe(_fmt_rows(credit_rows, money_keys=["Amount"]), use_container_width=True, hide_index=True)
            else:
                st.info("No creditor rows.")

        note = st.text_input("Manager Note", key=f"approval_note_{key_prefix}")

        if readonly:
            st.info("Read-only record. Approved records Sale Settlement/Reports me available hain.")
        else:
            status = row.get("status") or "pending"
            b1, b2, b3 = st.columns(3)

            with b1:
                if st.button("Approve", type="primary", key=f"approve_{key_prefix}", use_container_width=True):
                    updated, error = approve_sale_approval(settlement_id, user.get("id"), note)
                    if updated:
                        st.success("Approved. Entry Sale Approval action list se hat kar Sale Settlement/Reports me chali gayi.")
                        st.rerun()
                    else:
                        st.error(error or "Approval failed.")

            with b2:
                if st.button("Reject", key=f"reject_{key_prefix}", use_container_width=True):
                    updated, error = reject_sale_approval(settlement_id, user.get("id"), note)
                    if updated:
                        st.warning("Rejected. Salesman must enter fresh sale and breakup.")
                        st.rerun()
                    else:
                        st.error(error or "Reject failed.")

            with b3:
                if status == "hold":
                    if st.button("Reopen", key=f"reopen_{key_prefix}", use_container_width=True):
                        updated, error = reopen_sale_approval(settlement_id, user.get("id"), note)
                        if updated:
                            st.info("Reopened.")
                            st.rerun()
                        else:
                            st.error(error or "Reopen failed.")
                else:
                    if st.button("Hold", key=f"hold_{key_prefix}", use_container_width=True):
                        updated, error = hold_sale_approval(settlement_id, user.get("id"), note)
                        if updated:
                            st.warning("Held.")
                            st.rerun()
                        else:
                            st.error(error or "Hold failed.")


def render_closing_reading_block(settlement_id, key_prefix):
    settlement, assignments, error = get_closing_assignments_for_approval(settlement_id)

    if error:
        st.error(error)
        return

    if not assignments:
        st.warning("No nozzle assignments found. Duty/nozzle assignment check karo.")
        return

    st.markdown("### Manager Closing Reading")

    closing_inputs = {}

    for idx, assignment in enumerate(assignments):
        nozzle = assignment.get("nozzles") or {}
        assignment_id = assignment.get("id")

        opening = float(assignment.get("opening_reading") or 0)
        saved_closing = assignment.get("closing_reading")
        default_closing = float(saved_closing if saved_closing is not None else opening)

        c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1.2])
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
                key=f"closing_{key_prefix}_{idx}_{assignment_id}",
            )

        closing_inputs[assignment_id] = closing

    calc_rows, meter_total, calc_error = preview_closing_calculation(settlement_id, closing_inputs)

    if calc_error:
        st.error(calc_error)
        return

    st.metric("Calculated Meter Sale", format_currency(meter_total))

    with st.expander("Opening-Closing Calculation", expanded=True):
        st.dataframe(
            [
                {
                    "Nozzle": r.get("nozzle_name"),
                    "Fuel": r.get("fuel_type"),
                    "Opening": r.get("opening"),
                    "Closing": r.get("closing"),
                    "Actual Liters": r.get("actual_liters"),
                    "Rate": format_currency(r.get("rate")),
                    "Sale Amount": format_currency(r.get("sale_amount")),
                }
                for r in calc_rows
            ],
            use_container_width=True,
            hide_index=True,
        )

    if st.button("Save Closing Reading", key=f"save_closing_{key_prefix}", use_container_width=True):
        saved, save_error = save_closing_for_approval(
            settlement_id=settlement_id,
            closing_inputs=closing_inputs,
            manager_id=get_current_user().get("id"),
        )
        if saved:
            st.success("Closing reading saved. Approval logic updated.")
            st.rerun()
        else:
            st.error(save_error or "Closing reading save failed.")


def show_day_summary():
    selected_date = str(st.date_input("Date", value=date.today(), key="manager_day_summary_date"))
    summary = get_manager_day_summary(selected_date)

    c1, c2, c3 = st.columns(3)
    c1.metric("Approved Meter Sale", format_currency(summary["total_sale"]))
    c2.metric("Liters", f"{summary['total_liters']:.2f} L")
    c3.metric("Approved Count", summary["approval_count"])

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Cash", format_currency(summary["cash"]))
    p2.metric("Paytm", format_currency(summary["paytm"]))
    p3.metric("CCMS", format_currency(summary["ccms"]))
    p4.metric("Credit", format_currency(summary["credit"]))

    st.subheader("Diesel / Petrol Summary")
    if summary["fuel_rows"]:
        st.dataframe(_fmt_rows(summary["fuel_rows"], money_keys=["Amount"]), use_container_width=True, hide_index=True)
    else:
        st.info("No approved fuel sale for selected date.")

    st.subheader("Salesman-wise Summary")
    if summary["salesman_rows"]:
        st.dataframe(
            _fmt_rows(summary["salesman_rows"], money_keys=["Meter Sale", "Cash", "Paytm", "CCMS", "Credit"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No salesman rows.")

    st.subheader("Creditor List")
    if summary["credit_rows"]:
        st.dataframe(_fmt_rows(summary["credit_rows"], money_keys=["Amount"]), use_container_width=True, hide_index=True)
    else:
        st.info("No creditor sale.")
