from datetime import date
import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.stock_approval_db import (
    get_fuel_inward_by_status,
    approve_fuel_inward,
    reject_fuel_inward,
    hold_fuel_inward,
    reopen_fuel_inward,
    get_testing_by_status,
    approve_testing,
    reject_testing,
    hold_testing,
    reopen_testing,
    get_stock_closing_by_status,
    approve_stock_closing,
    reject_stock_closing,
    hold_stock_closing,
    reopen_stock_closing,
    get_stock_variance_report,
    get_stock_movement_report,
    get_stock_approval_summary,
)


@require_role(["owner", "manager"])
def stock_approval_page():
    st.title("Stock Approval & Reports")
    st.caption("Inward, nozzle-wise testing, stock closing approval and stock variance reports.")

    show_top_summary()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Inward Approval",
        "Testing Approval",
        "Stock Closing Approval",
        "Variance Report",
        "Movement Report",
    ])

    with tab1:
        inward_approval_tab()

    with tab2:
        testing_approval_tab()

    with tab3:
        stock_closing_approval_tab()

    with tab4:
        variance_report_tab()

    with tab5:
        movement_report_tab()


def show_top_summary():
    s = get_stock_approval_summary()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pending Inward", s["pending_inward"])
    c2.metric("Pending Testing", s["pending_testing"])
    c3.metric("Pending Closing", s["pending_stock_closing"])
    c4.metric("Total Pending", s["total_pending"])


def inward_approval_tab():
    status = st.selectbox("Status", ["pending", "hold", "reopened", "approved", "rejected"], key="inward_status")
    rows = get_fuel_inward_by_status(status)

    if not rows:
        st.info("No inward entries found.")
        return

    for r in rows:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ID", r.get("id"))
            c2.metric("Fuel", r.get("fuel_type"))
            c3.metric("Qty", f"{float(r.get('quantity_liters') or 0):.2f} L")
            c4.metric("Amount", format_currency(r.get("total_amount")))

            st.write(f"**Oil Company:** {r.get('oil_company')} | **Invoice:** {r.get('invoice_no')} | **Tanker:** {r.get('tanker_no')}")
            st.write(f"**Date:** {r.get('date')} | **Status:** {r.get('status')}")

            note = st.text_input("Approval Note", key=f"inward_note_{r.get('id')}")
            render_approval_buttons(
                row_id=r.get("id"),
                prefix="inward",
                approve_fn=approve_fuel_inward,
                reject_fn=reject_fuel_inward,
                hold_fn=hold_fuel_inward,
                reopen_fn=reopen_fuel_inward,
                note=note,
            )


def testing_approval_tab():
    status = st.selectbox("Status", ["pending", "hold", "reopened", "approved", "rejected"], key="testing_status")
    rows = get_testing_by_status(status)

    if not rows:
        st.info("No testing entries found.")
        return

    for r in rows:
        nozzle = r.get("nozzles") or {}

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ID", r.get("id"))
            c2.metric("Nozzle", nozzle.get("nozzle_name"))
            c3.metric("Fuel", r.get("fuel_type"))
            c4.metric("Testing", f"{float(r.get('testing_liters') or 0):.2f} L")

            st.write(f"**Reading:** {r.get('reading_before')} → {r.get('reading_after')}")
            st.write(f"**Density:** {r.get('density')} | **Temp:** {r.get('temperature')} | **Result:** {r.get('result')}")
            st.write(f"**Date:** {r.get('date')} | **Status:** {r.get('status')}")

            note = st.text_input("Approval Note", key=f"testing_note_{r.get('id')}")
            render_approval_buttons(
                row_id=r.get("id"),
                prefix="testing",
                approve_fn=approve_testing,
                reject_fn=reject_testing,
                hold_fn=hold_testing,
                reopen_fn=reopen_testing,
                note=note,
            )


def stock_closing_approval_tab():
    status = st.selectbox("Status", ["pending", "hold", "reopened", "approved", "rejected"], key="closing_status")
    rows = get_stock_closing_by_status(status)

    if not rows:
        st.info("No stock closing entries found.")
        return

    for r in rows:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ID", r.get("id"))
            c2.metric("Fuel", r.get("fuel_type"))
            c3.metric("Physical", f"{float(r.get('physical_stock') or 0):.2f} L")
            c4.metric("Difference", f"{float(r.get('difference') or 0):.2f} L")

            st.write(f"**Expected:** {r.get('expected_stock')} | **Date:** {r.get('date')} | **Status:** {r.get('status')}")
            st.write(f"**Remark:** {r.get('remark')}")

            note = st.text_input("Approval Note", key=f"closing_note_{r.get('id')}")
            render_approval_buttons(
                row_id=r.get("id"),
                prefix="closing",
                approve_fn=approve_stock_closing,
                reject_fn=reject_stock_closing,
                hold_fn=hold_stock_closing,
                reopen_fn=reopen_stock_closing,
                note=note,
            )


def render_approval_buttons(row_id, prefix, approve_fn, reject_fn, hold_fn, reopen_fn, note):
    user = get_current_user()
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("Approve", type="primary", key=f"{prefix}_approve_{row_id}", use_container_width=True):
            row, error = approve_fn(row_id, user["id"], note)
            if row:
                st.success("Approved.")
                st.rerun()
            else:
                st.error(error or "Approval failed.")

    with c2:
        if st.button("Hold", key=f"{prefix}_hold_{row_id}", use_container_width=True):
            row, error = hold_fn(row_id, user["id"], note)
            if row:
                st.warning("Put on hold.")
                st.rerun()
            else:
                st.error(error or "Hold failed.")

    with c3:
        if st.button("Reject", key=f"{prefix}_reject_{row_id}", use_container_width=True):
            row, error = reject_fn(row_id, user["id"], note)
            if row:
                st.warning("Rejected.")
                st.rerun()
            else:
                st.error(error or "Reject failed.")

    with c4:
        if st.button("Reopen", key=f"{prefix}_reopen_{row_id}", use_container_width=True):
            row, error = reopen_fn(row_id, user["id"], note)
            if row:
                st.info("Reopened.")
                st.rerun()
            else:
                st.error(error or "Reopen failed.")


def variance_report_tab():
    selected_date = str(st.date_input("Date", value=date.today(), key="variance_date"))
    rows = get_stock_variance_report(selected_date)

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No variance data found.")


def movement_report_tab():
    selected_date = str(st.date_input("Date", value=date.today(), key="movement_date"))
    rows = get_stock_movement_report(selected_date)

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No stock movement data found.")
