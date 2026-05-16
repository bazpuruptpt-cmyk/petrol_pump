import streamlit as st

from auth.login import login_page, logout
from auth.persistent_session import restore_persistent_login, keep_session_alive, render_session_bridge
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
from modules.manager.sale_approval import sale_approval_page
from modules.manager.money_control import money_control_page
from modules.manager.reports import reports_page
from modules.manager.pump_summary import pump_summary_page
from modules.manager.stock_management import stock_management_page
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


# ---------------- App Navigation ----------------

OWNER_NAV_GROUPS = {
    "Main": {
        "Dashboard": owner_dashboard,
        "Money Control": money_control_page,
        "Reports": reports_page,
    },
    "Sales": {
        "Sale Approval": sale_approval_page,
        "Settlement": settlement_page,
    },
    "Creditors": {
        "Credit Parties": credit_parties_page,
        "Credit Payment": credit_payment_page,
    },
    "Stock": {
        "Stock Management": stock_management_page,
    },
    "Setup": {
        "Duty Management": duty_management_page,
        "Nozzle Assignment": nozzle_assignment_page,
        "Users": manage_users_page,
        "Nozzles": manage_nozzles_page,
        "Fuel Rates": fuel_rates_page,
    },
    "Admin": {
        "System Audit": system_audit_page,
    },
}


MANAGER_NAV_GROUPS = {
    "Main": {
        "Dashboard": manager_dashboard,
        "Money Control": money_control_page,
        "Reports": reports_page,
    },
    "Sales": {
        "Sale Approval": sale_approval_page,
        "Settlement": settlement_page,
    },
    "Creditors": {
        "Credit Parties": credit_parties_page,
        "Credit Payment": credit_payment_page,
    },
    "Stock": {
        "Stock Management": stock_management_page,
    },
    "Setup": {
        "Duty Management": duty_management_page,
        "Nozzle Assignment": nozzle_assignment_page,
    },
}


SALESMAN_NAV_GROUPS = {
    "Work": {
        "Dashboard": attendant_dashboard,
        "Sale Entry": sale_entry_page,
        "My Entries": my_entries_page,
        "My Summary": my_summary_page,
    },
}


PAGE_CAPTIONS = {
    "Dashboard": "Owner/manager daily control centre.",
    "Money Control": "Cash, bank, Paytm, CCMS and oil company control.",
    "Reports": "Daily and date-range business picture.",
    "Sale Approval": "Pending sale verification and approval.",
    "Settlement": "Approved sale settlement history.",
    "Credit Parties": "Creditor ledger, corrections and balances.",
    "Credit Payment": "Creditor payment collection entry.",
    "Stock Management": "Tank, fuel inward and nozzle testing.",
    "Duty Management": "Shift creation and duty control.",
    "Nozzle Assignment": "Nozzle allotment to salesman.",
    "Users": "Create and manage users.",
    "Nozzles": "Nozzle master setup.",
    "Fuel Rates": "Fuel rate control.",
    "System Audit": "System activity audit.",
    "Sale Entry": "Salesman daily sale entry.",
    "My Entries": "Salesman own entries.",
    "My Summary": "Salesman own summary.",
}


def _flatten_nav(groups):
    pages = {}
    for _group, items in groups.items():
        pages.update(items)
    return pages


def _nav_groups_for_role(role):
    if role == "owner":
        return OWNER_NAV_GROUPS
    if role == "manager":
        return MANAGER_NAV_GROUPS
    if role == "salesman":
        return SALESMAN_NAV_GROUPS
    return {}


def _render_app_header(page, user):
    st.markdown(
        f"""
        <div class="app-topbar">
            <div>
                <div class="app-page-title">{page}</div>
                <div class="app-page-caption">{PAGE_CAPTIONS.get(page, "Pump operation control.")}</div>
            </div>
            <div class="app-user-chip">{(user.get('role') or '').upper()} • {user.get('name') or '-'}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(user):
    role = user.get("role")
    groups = _nav_groups_for_role(role)

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="brand-icon">⛽</div>
                <div>
                    <div class="brand-title">Pump Control</div>
                    <div class="brand-subtitle">Sale • Money • Stock</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="sidebar-user">
                <div class="sidebar-user-name">{user.get('name') or '-'}</div>
                <div class="sidebar-user-role">{str(role or '-').upper()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        page_key = f"active_page_{role}"

        # Default page
        if page_key not in st.session_state:
            first_group = next(iter(groups.values()))
            st.session_state[page_key] = next(iter(first_group.keys()))

        st.markdown('<div class="nav-label">Navigation</div>', unsafe_allow_html=True)

        for group_name, pages in groups.items():
            with st.expander(group_name, expanded=(group_name in ["Main", "Work"])):
                for page_name in pages.keys():
                    is_active = st.session_state.get(page_key) == page_name
                    label = f"● {page_name}" if is_active else page_name
                    if st.button(label, key=f"nav_btn_{role}_{group_name}_{page_name}", use_container_width=True):
                        st.session_state[page_key] = page_name
                        st.rerun()

        st.divider()

        if st.button("Logout", use_container_width=True, type="secondary"):
            logout()

    selected_page = st.session_state.get(page_key)
    pages_flat = _flatten_nav(groups)

    if selected_page not in pages_flat:
        selected_page = next(iter(pages_flat.keys()))
        st.session_state[page_key] = selected_page

    return selected_page, pages_flat


def route_by_role(user):
    role = user.get("role")

    groups = _nav_groups_for_role(role)
    if not groups:
        st.error("Invalid role.")
        return

    page, pages = render_sidebar(user)
    _render_app_header(page, user)

    try:
        pages[page]()

    except ModuleNotFoundError:
        st.error("Required module missing. Admin ko code file check karni hogi.")

    except ImportError:
        st.error("Page load configuration issue. Admin ko latest files replace karni hongi.")

    except Exception as exc:
        st.error("Page load error. Screenshot bhej kar admin se check karayein.")
        with st.expander("Technical detail"):
            st.code(str(exc))



# ---------------- Main App ----------------
def main():
    restore_persistent_login()
    user = get_current_user()

    if not user:
        render_session_bridge()
        login_page()
        return

    keep_session_alive()
    route_by_role(user)


if __name__ == "__main__":
    main()
