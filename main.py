import streamlit as st

from auth.login import login_page, logout
from utils.permissions import get_current_user

from modules.owner.dashboard import owner_dashboard
from modules.owner.manage_users import manage_users_page
from modules.owner.manage_nozzles import manage_nozzles_page
from modules.owner.fuel_rates import fuel_rates_page

from modules.manager.dashboard import manager_dashboard
from modules.manager.duty_management import duty_management_page
from modules.manager.nozzle_assignment import nozzle_assignment_page

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
            [
                "Owner Dashboard",
                "Manage Users",
                "Manage Nozzles",
                "Fuel Rates",
                "Manager Dashboard",
                "Duty Management",
                "Nozzle Assignment",
            ],
        )

        if page == "Owner Dashboard":
            owner_dashboard()
        elif page == "Manage Users":
            manage_users_page()
        elif page == "Manage Nozzles":
            manage_nozzles_page()
        elif page == "Fuel Rates":
            fuel_rates_page()
        elif page == "Manager Dashboard":
            manager_dashboard()
        elif page == "Duty Management":
            duty_management_page()
        elif page == "Nozzle Assignment":
            nozzle_assignment_page()

    elif role == "manager":
        page = st.sidebar.radio(
            "Navigation",
            [
                "Manager Dashboard",
                "Duty Management",
                "Nozzle Assignment",
            ],
        )

        if page == "Manager Dashboard":
            manager_dashboard()
        elif page == "Duty Management":
            duty_management_page()
        elif page == "Nozzle Assignment":
            nozzle_assignment_page()

    elif role == "salesman":
        attendant_dashboard()

    else:
        st.error("Invalid role.")


def main():
    route_user()


if __name__ == "__main__":
    main()
