import streamlit as st
from utils.permissions import require_role
from utils.formatters import format_currency
from database.duties_db import get_active_duties


@require_role(["manager", "owner"])
def manager_dashboard():
    st.title("Manager Dashboard")

    st.caption("Daily operations: duty, settlement, testing, inward, payments, reports.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Today Total Sale", format_currency(0))
    col2.metric("Cash in Hand", format_currency(0))
    col3.metric("Paytm Pending", format_currency(0))

    col4, col5, col6 = st.columns(3)
    col4.metric("CCMS Outstanding", format_currency(0))
    col5.metric("Credit Outstanding", format_currency(0))
    col6.metric("Cash Deposited", format_currency(0))

    st.divider()

    active = get_active_duties()
    st.subheader("Active Duties")
    st.metric("Active Duty Count", len(active))

    if active:
        rows = []
        for d in active:
            profile = d.get("profiles") or {}
            rows.append({
                "shift_id": d.get("id"),
                "salesman": profile.get("name"),
                "date": d.get("date"),
                "started_at": d.get("started_at"),
                "is_active": d.get("is_active"),
            })
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No active duties.")

    st.divider()
    st.subheader("Manager Modules")
    st.write("Use sidebar navigation for Duty Management and Nozzle Assignment.")
