import streamlit as st

from auth.login import login_page, logout
from utils.permissions import get_current_user
from modules.owner.dashboard import owner_dashboard
from modules.manager.dashboard import manager_dashboard
from modules.attendant.dashboard import attendant_dashboard


st.set_page_config(
    page_title="Petrol Pump Management System",
    page_icon="⛽",
    layout="wide",
)


def route_user():
    user = get_current_user()

    if not user:
        login_page()
        return

    with st.sidebar:
        st.write(f"Logged in: **{user['name']}**")
        st.write(f"Role: **{user['role']}**")
        if st.button("Logout"):
            logout()

    role = user["role"]

    if role == "owner":
        page = st.sidebar.radio(
            "Navigation",
            ["Owner Dashboard", "Manager Dashboard"],
        )
        if page == "Owner Dashboard":
            owner_dashboard()
        else:
            manager_dashboard()

    elif role == "manager":
        manager_dashboard()

    elif role == "salesman":
        attendant_dashboard()

    else:
        st.error("Invalid role.")


def main():
    route_user()


if __name__ == "__main__":
    main()

