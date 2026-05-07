import streamlit as st
from utils.permissions import require_role
from utils.formatters import format_currency


@require_role(["owner"])
def owner_dashboard():
    st.title("Owner Dashboard")

    st.caption("Full control: users, nozzles, rates, reports, manager rights.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Today Total Sale", format_currency(0))
    col2.metric("Cash in Hand", format_currency(0))
    col3.metric("Credit Outstanding", format_currency(0))

    col4, col5, col6 = st.columns(3)
    col4.metric("Cash Deposited", format_currency(0))
    col5.metric("Paytm Settled", format_currency(0))
    col6.metric("CCMS Outstanding", format_currency(0))

    st.divider()
    st.subheader("Owner Modules")

    st.write("Phase 1 contains routing only. Full modules will be added in Phase 2.")
    st.button("Manage Users", disabled=True)
    st.button("Manage Nozzles", disabled=True)
    st.button("Fuel Rates", disabled=True)
    st.button("Reports", disabled=True)
