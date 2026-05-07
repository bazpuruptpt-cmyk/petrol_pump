import streamlit as st

from utils.permissions import require_role, get_current_user
from database.sale_db import (
    get_assigned_nozzles_for_salesman,
    get_shift_sale_summary_for_salesman,
    get_salesman_nozzle_sale_summary,
    get_latest_payment_breakup,
    calculate_payment_match,
)
from utils.formatters import format_currency


@require_role(["salesman"])
def attendant_dashboard():
    user = get_current_user()
    st.title("Attendant Dashboard")
    st.caption("Current shift sale and final payment breakup status.")

    duty, nozzles = get_assigned_nozzles_for_salesman(user["id"])

    if not duty:
        st.error("No active duty found. Login allowed only during active duty.")
        st.stop()

    st.success(f"Active Duty ID: {duty['id']}")

    summary = get_shift_sale_summary_for_salesman(user["id"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Sale Amount", format_currency(summary["total_sale"]))
    c2.metric("Total Liters", f"{summary['total_liters']:.2f} L")
    c3.metric("Entries", summary["entry_count"])

    latest = get_latest_payment_breakup(duty["id"], user["id"])

    st.divider()
    st.subheader("Payment Breakup Status")

    if latest:
        match = calculate_payment_match(
            total_sale=summary["total_sale"],
            cash=latest.get("cash_amount"),
            paytm=latest.get("paytm_amount"),
            ccms=latest.get("ccms_amount"),
            credit=latest.get("credit_amount"),
        )

        c4, c5, c6 = st.columns(3)
        c4.metric("Payment Total", format_currency(match["payment_total"]))
        c5.metric("Difference", format_currency(match["difference"]))
        c6.metric("Status", latest.get("status"))

        c7, c8, c9, c10 = st.columns(4)
        c7.metric("Cash", format_currency(match["cash"]))
        c8.metric("Paytm", format_currency(match["paytm"]))
        c9.metric("CCMS", format_currency(match["ccms"]))
        c10.metric("Credit", format_currency(match["credit"]))

        if match["is_matched"]:
            st.success("MATCHED")
        else:
            st.error("NOT MATCHED")
    else:
        st.info("Final payment breakup not submitted yet.")

    st.divider()
    st.subheader("Assigned Nozzles")

    if not nozzles:
        st.warning("No nozzle assigned yet. Ask manager to assign nozzle.")
        return

    assigned_rows = []
    for n in nozzles:
        assigned_rows.append({
            "Nozzle ID": n.get("nozzle_id"),
            "Nozzle Name": n.get("nozzle_name"),
            "Fuel Type": n.get("fuel_type"),
            "Opening Reading": n.get("opening_reading"),
            "Current Reading": n.get("current_reading"),
        })

    st.dataframe(assigned_rows, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Nozzle-wise Sale")

    nozzle_rows = get_salesman_nozzle_sale_summary(user["id"])

    if nozzle_rows:
        st.dataframe(nozzle_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No sale entry yet.")
