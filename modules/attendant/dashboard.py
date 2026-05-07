import streamlit as st

from utils.permissions import require_role, get_current_user
from database.sale_db import (
    get_assigned_nozzles_for_salesman,
    get_salesman_payment_match_summary,
    get_salesman_nozzle_summary,
    get_credit_party_wise_summary,
)
from utils.formatters import format_currency


@require_role(["salesman"])
def attendant_dashboard():
    user = get_current_user()
    st.title("Attendant Dashboard")
    st.caption("Total Sale Amount vs Cash/Paytm/CCMS/Credit breakup.")

    duty, nozzles = get_assigned_nozzles_for_salesman(user["id"])

    if not duty:
        st.error("No active duty found. Login allowed only during active duty.")
        st.stop()

    st.success(f"Active Duty ID: {duty['id']}")

    show_payment_match_block(user["id"])

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

    st.divider()
    st.subheader("Creditor-wise Credit Sale")

    credit_rows = get_credit_party_wise_summary(user["id"])

    if credit_rows:
        st.dataframe(credit_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No credit sale entry yet.")


def show_payment_match_block(salesman_id: str):
    summary = get_salesman_payment_match_summary(salesman_id)

    st.subheader("Today Sale Match")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Sale Amount", format_currency(summary["total"]))
    c2.metric("Payment Breakup Total", format_currency(summary["payment_total"]))
    c3.metric("Difference", format_currency(summary["difference"]))

    c4, c5, c6, c7 = st.columns(4)
    c4.metric("Cash", format_currency(summary["cash"]))
    c5.metric("Paytm", format_currency(summary["paytm"]))
    c6.metric("CCMS", format_currency(summary["ccms"]))
    c7.metric("Credit / Creditor", format_currency(summary["credit"]))

    if summary["is_matched"]:
        st.success("MATCHED: Total Sale = Cash + Paytm + CCMS + Credit")
    else:
        st.error("NOT MATCHED: Payment breakup total sale amount se match nahi kar raha.")
