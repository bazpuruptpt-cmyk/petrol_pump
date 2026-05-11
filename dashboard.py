from datetime import date
import streamlit as st
from utils.permissions import require_role
from utils.formatters import format_currency
from database.duties_db import get_active_duties
from database.reports_db import get_daily_closing_report
from database.salesman_approval_flow_db import get_manager_cash_transfer_summary
from database.payment_db import get_manager_daily_money_position, get_manager_daily_money_position_cards


@require_role(["manager", "owner"])
def manager_dashboard():
    st.title("Manager Dashboard")
    st.caption("Daily money position + approved sale + pending controls.")

    selected_date = str(st.date_input("Date", value=date.today(), key="manager_dashboard_money_date"))

    position = get_manager_daily_money_position(selected_date)
    cards = get_manager_daily_money_position_cards(selected_date)

    st.subheader("Manager Daily Money Position")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Current Cash", format_currency((cards.get("Cash") or {}).get("Current Balance")))
    c2.metric("Current Bank", format_currency((cards.get("Bank") or {}).get("Current Balance")))
    c3.metric("Paytm Pending", format_currency((cards.get("Paytm") or {}).get("Current Balance")))
    c4.metric("CCMS Pending", format_currency((cards.get("CCMS") or {}).get("Current Balance")))
    c5.metric("Credit Outstanding", format_currency((cards.get("Credit Outstanding") or {}).get("Current Balance")))

    st.dataframe([
        {
            "Account": r.get("Account"),
            "Opening Balance": format_currency(r.get("Opening Balance")),
            "Today Inflow": format_currency(r.get("Today Inflow")),
            "Today Outflow": format_currency(r.get("Today Outflow")),
            "Current Balance": format_currency(r.get("Current Balance")),
            "Narration": r.get("Narration"),
        }
        for r in position
    ], use_container_width=True, hide_index=True)

    st.divider()

    r = get_daily_closing_report(selected_date)
    t = get_manager_cash_transfer_summary()

    st.subheader("Sale / Approval Snapshot")
    c6, c7, c8 = st.columns(3)
    c6.metric("Approved Total Sale", format_currency(r["total_sale"]))
    c7.metric("Approved Cash Transfer", format_currency(t["approved_cash_transfer"]))
    c8.metric("Pending Cash Transfer", format_currency(t["pending_cash_transfer"]))

    c9, c10, c11 = st.columns(3)
    c9.metric("Credit Sale", format_currency(r["credit_sale"]))
    c10.metric("Paytm Pending", format_currency(r["paytm_pending"]))
    c11.metric("CCMS Pending", format_currency(r["ccms_pending"]))

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
