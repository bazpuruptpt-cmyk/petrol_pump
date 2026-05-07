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
from modules.manager.credit_parties import credit_parties_page

from modules.attendant.dashboard import attendant_dashboard
from modules.attendant.sale_entry import sale_entry_page
from modules.attendant.my_entries import my_entries_page
from modules.attendant.my_summary import my_summary_page


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

        st.divider()

    role = user["role"]

    if role == "owner":
        with st.sidebar:
            page = st.radio(
                "Navigation",
                [
                    "Owner Dashboard",
                    "Manage Users",
                    "Manage Nozzles",
                    "Fuel Rates",
                    "Credit Parties",
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
        elif page == "Credit Parties":
            credit_parties_page()
        elif page == "Manager Dashboard":
            manager_dashboard()
        elif page == "Duty Management":
            duty_management_page()
        elif page == "Nozzle Assignment":
            nozzle_assignment_page()

    elif role == "manager":
        with st.sidebar:
            page = st.radio(
                "Navigation",
                [
                    "Manager Dashboard",
                    "Duty Management",
                    "Nozzle Assignment",
                    "Credit Parties",
                ],
            )

        if page == "Manager Dashboard":
            manager_dashboard()
        elif page == "Duty Management":
            duty_management_page()
        elif page == "Nozzle Assignment":
            nozzle_assignment_page()
        elif page == "Credit Parties":
            credit_parties_page()

    elif role == "salesman":
        with st.sidebar:
            page = st.radio(
                "Navigation",
                [
                    "Attendant Dashboard",
                    "Sale Entry",
                    "My Entries",
                    "My Summary",
                ],
            )

        if page == "Attendant Dashboard":
            attendant_dashboard()
        elif page == "Sale Entry":
            sale_entry_page()
        elif page == "My Entries":
            my_entries_page()
        elif page == "My Summary":
            my_summary_page()

    else:
        st.error("Invalid role.")


def main():
    route_user()


if __name__ == "__main__":
    main()
