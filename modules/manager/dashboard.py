import streamlit as st
from utils.permissions import require_role
from utils.formatters import format_currency
from database.duties_db import get_active_duties
from database.reports_db import get_daily_closing_report
from database.salesman_approval_flow_db import get_manager_cash_transfer_summary


@require_role(["manager", "owner"])
def manager_dashboard():
    st.title("Manager Dashboard")
    st.caption("Approved sale aur salesman cash transfer alag-alag.")

    r = get_daily_closing_report()
    t = get_manager_cash_transfer_summary()

    c1, c2, c3 = st.columns(3)
    c1.metric("Approved Total Sale", format_currency(r["total_sale"]))
    c2.metric("Approved Cash Transfer", format_currency(t["approved_cash_transfer"]))
    c3.metric("Pending Cash Transfer", format_currency(t["pending_cash_transfer"]))

    c4, c5, c6 = st.columns(3)
    c4.metric("Credit Sale", format_currency(r["credit_sale"]))
    c5.metric("Paytm Pending", format_currency(r["paytm_pending"]))
    c6.metric("CCMS Pending", format_currency(r["ccms_pending"]))

    st.divider()

    st.subheader("Salesman Cash Transfer")
    rows = t.get("rows") or []
    if rows:
        display = []
        for x in rows:
            y = x.copy()
            for k in ["Cash Transfer", "Paytm", "CCMS", "Credit"]:
                y[k] = format_currency(y[k])
            display.append(y)
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("No transfer rows today.")

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
