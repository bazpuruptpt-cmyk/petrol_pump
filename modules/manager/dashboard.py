import streamlit as st
from utils.permissions import require_role
from utils.formatters import format_currency


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
    st.subheader("Manager Modules")

    st.write("Phase 1 contains routing only. Full modules will be added in Phase 2.")
    st.button("Duty Management", disabled=True)
    st.button("Settlement", disabled=True)
    st.button("Daily Testing", disabled=True)
    st.button("Fuel Inward", disabled=True)
