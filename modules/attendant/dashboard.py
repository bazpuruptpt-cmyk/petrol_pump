import streamlit as st

from utils.permissions import require_role, get_current_user
from database.sale_db import (
    get_assigned_nozzles_for_salesman,
    get_salesman_today_summary,
    get_salesman_nozzle_summary,
)
from utils.formatters import format_currency


@require_role(["salesman"])
def attendant_dashboard():
    user = get_current_user()
    st.title("Attendant Dashboard")
    st.caption("Assigned nozzles ka combined total aur payment mode breakup.")

    duty, nozzles = get_assigned_nozzles_for_salesman(user["id"])

    if not duty:
        st.error("No active duty found. Login allowed only during active duty.")
        st.stop()

    st.success(f"Active Duty ID: {duty['id']}")

    summary = get_salesman_today_summary(user["id"])

    col1, col2, col3 = st.columns(3)
    col1.metric("All Nozzle Total", format_currency(summary["total"]))
    col2.metric("Cash", format_currency(summary["cash"]))
    col3.metric("Paytm", format_currency(summary["paytm"]))

    col4, col5, col6 = st.columns(3)
    col4.metric("CCMS", format_currency(summary["ccms"]))
    col5.metric("Credit", format_currency(summary["credit"]))
    col6.metric("Pending Entries", summary["pending_count"])

    st.divider()
    st.subheader("Assigned Nozzles")

    if not nozzles:
        st.warning("No nozzle assigned yet. Ask manager to assign nozzle.")
        return

    rows = []
    for n in nozzles:
        rows.append({
            "Nozzle ID": n.get("nozzle_id"),
            "Nozzle Name": n.get("nozzle_name"),
            "Fuel Type": n.get("fuel_type"),
            "Opening Reading": n.get("opening_reading"),
            "Current Reading": n.get("current_reading"),
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Nozzle-wise Today Sale")

    nozzle_summary = get_salesman_nozzle_summary(user["id"])

    if nozzle_summary:
        st.dataframe(nozzle_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No sale entry yet.")
