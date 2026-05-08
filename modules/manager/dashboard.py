import streamlit as st
from utils.permissions import require_role
from utils.formatters import format_currency
from database.duties_db import get_active_duties
from database.payment_db import get_daily_money_summary

@require_role(["manager", "owner"])
def manager_dashboard():
    st.title("Manager Dashboard")
    st.caption("Daily operations summary.")
    s = get_daily_money_summary()
    c1,c2,c3 = st.columns(3)
    c1.metric("Today Total Sale", format_currency(s["total_sale"]))
    c2.metric("Cash In Hand", format_currency(s["cash_in_hand"]))
    c3.metric("Cash Deposited", format_currency(s["cash_deposited"]))
    c4,c5,c6 = st.columns(3)
    c4.metric("Paytm Pending", format_currency(s["paytm_pending"]))
    c5.metric("CCMS Pending", format_currency(s["ccms_pending"]))
    c6.metric("Credit Sale", format_currency(s["credit_sale"]))
    st.divider()
    active = get_active_duties()
    st.subheader("Active Duties")
    st.metric("Active Duty Count", len(active))
    if active:
        st.dataframe([
            {
                "shift_id": d.get("id"),
                "salesman": (d.get("profiles") or {}).get("name"),
                "date": d.get("date"),
                "started_at": d.get("started_at"),
                "is_active": d.get("is_active"),
            }
            for d in active
        ], use_container_width=True, hide_index=True)
    else:
        st.info("No active duties.")
