import streamlit as st
from utils.permissions import require_role, get_current_user
from database.duties_db import get_duty_by_salesman
from utils.formatters import format_currency


@require_role(["salesman"])
def attendant_dashboard():
    user = get_current_user()
    st.title("Attendant Dashboard")
    st.caption("Assigned nozzle sale entry only.")

    duty = get_duty_by_salesman(user["id"])

    if not duty:
        st.error("No active duty found. Login should only be allowed during active duty.")
        st.stop()

    st.success(f"Active Duty ID: {duty['id']}")

    col1, col2, col3 = st.columns(3)
    col1.metric("My Cash Sale", format_currency(0))
    col2.metric("My Paytm Sale", format_currency(0))
    col3.metric("My Credit Sale", format_currency(0))

    st.divider()
    st.subheader("Attendant Modules")

    st.write("Phase 1 contains routing only. Sale-entry module will be added in Phase 2.")
    st.button("Sale Entry", disabled=True)
    st.button("Credit Entry", disabled=True)
    st.button("My Entries", disabled=True)
    st.button("My Summary", disabled=True)
