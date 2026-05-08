import streamlit as st

from auth.login import login_page, logout
from utils.permissions import get_current_user

try:
    from utils.ui import apply_global_ui
except Exception:
    def apply_global_ui():
        pass


# ---------------- Owner Modules ----------------
from modules.owner.dashboard import owner_dashboard
from modules.owner.manage_users import manage_users_page
from modules.owner.manage_nozzles import manage_nozzles_page
from modules.owner.fuel_rates import fuel_rates_page


# ---------------- Manager Modules ----------------
from modules.manager.dashboard import manager_dashboard
from modules.manager.duty_management import duty_management_page
from modules.manager.nozzle_assignment import nozzle_assignment_page
from modules.manager.credit_parties import credit_parties_page
from modules.manager.credit_approval import credit_approval_page
from modules.manager.credit_payment import credit_payment_page
from modules.manager.settlement import settlement_page
from modules.manager.money_control import money_control_page
from modules.manager.reports import reports_page
from modules.manager.stock_management import stock_management_page
from modules.manager.stock_approval import stock_approval_page
from modules.manager.expense_profit_loss import expense_profit_loss_page
from modules.manager.system_audit import system_audit_page


# ---------------- Salesman Modules ----------------
from modules.attendant.dashboard import attendant_dashboard
from modules.attendant.sale_entry import sale_entry_page
from modules.attendant.my_entries import my_entries_page
from modules.attendant.my_summary import my_summary_page


# ---------------- Page Config ----------------
st.set_page_config(
    page_title="Petrol Pump Management System",
    page_icon="⛽",
    layout="wide",
)

apply_global_ui()


# ---------------- Navigation Maps ----------------
OWNER_PAGES = {
    "Dashboard": owner_dashboard,

    "Users": manage_users_page,
    "Nozzles": manage_nozzles_page,
    "Fuel Rates": fuel_rates_page,

    "Duty Management": duty_management_page,
    "Nozzle Assignment": nozzle_assignment_page,
    "Settlement": settlement_page,

    "Credit Parties": credit_parties_page,
    "Credit Payment": credit_payment_page,
    "Credit Approval": credit_approval_page,

    "Stock Management": stock_management_page,
    "Stock Approval": stock_approval_page,

    "Money Control": money_control_page,
    "Expense P/L": expense_profit_loss_page,
    "Reports": reports_page,

    "Manager Dashboard": manager_dashboard,
    "System Audit": system_audit_page,
}


MANAGER_PAGES = {
    "Dashboard": manager_dashboard,

    "Duty Management": duty_management_page,
    "Nozzle Assignment": nozzle_assignment_page,
    "Settlement": settlement_page,

    "Credit Parties": credit_parties_page,
    "Credit Payment": credit_payment_page,
    "Credit Approval": credit_approval_page,

    "Stock Management": stock_management_page,
    "Stock Approval": stock_approval_page,

    "Money Control": money_control_page,
    "Expense P/L": expense_profit_loss_page,
    "Reports": reports_page,

    "System Audit": system_audit_page,
}


SALESMAN_PAGES = {
    "Dashboard": attendant_dashboard,
    "Sale Entry": sale_entry_page,
    "My Entries": my_entries_page,
    "My Summary": my_summary_page,
}


# ---------------- UI Helpers ----------------
def render_sidebar(user):
    with st.sidebar:
        st.markdown("## ⛽ Pump System")
        st.caption("Operations Control Panel")
        st.divider()

        st.write(f"**User:** {user.get('name')}")
        st.write(f"**Role:** {user.get('role')}")

        if st.button("Logout", use_container_width=True):
            logout()

        st.divider()


def route_by_role(user):
    role = user.get("role")

    if role == "owner":
        pages = OWNER_PAGES
    elif role == "manager":
        pages = MANAGER_PAGES
    elif role == "salesman":
        pages = SALESMAN_PAGES
    else:
        st.error("Invalid role.")
        return

    with st.sidebar:
        page = st.radio("Navigation", list(pages.keys()))

    try:
        pages[page]()

    except ModuleNotFoundError as exc:
        st.error(f"Missing module/file: {exc}")
        st.info("GitHub me required file upload karo, phir Streamlit reboot karo.")

    except ImportError as exc:
        st.error(f"Import error: {exc}")
        st.info("Related file ka function name check karo.")

    except Exception as exc:
        st.error(f"Page error: {exc}")
        st.info("Error ka screenshot bhejo; exact patch diya jayega.")


# ---------------- Main App ----------------
def main():
    user = get_current_user()

    if not user:
        login_page()
        return

    render_sidebar(user)
    route_by_role(user)


if __name__ == "__main__":
    main()
