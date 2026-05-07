import streamlit as st

from utils.permissions import require_role
from utils.formatters import format_currency
from database.duties_db import get_active_duties
from database.settlement_db import get_manager_payment_summary


@require_role(["manager", "owner"])
def manager_dashboard():
    st.title("Manager Dashboard")
    st.caption("Daily operations: duty, nozzle assignment, settlement, payments.")

    summary = get_manager_payment_summary()

    col1, col2, col3 = st.columns(3)
    col1.metric("Today Total Sale", format_currency(summary["total_sale"]))
    col2.metric("Cash", format_currency(summary["cash"]))
    col3.metric("Paytm", format_currency(summary["paytm"]))

    col4, col5, col6 = st.columns(3)
    col4.metric("CCMS", format_currency(summary["ccms"]))
    col5.metric("Credit", format_currency(summary["credit"]))
    col6.metric("Pending Settlements", summary["pending_count"])

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
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No active duties.")
