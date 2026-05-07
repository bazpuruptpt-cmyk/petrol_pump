import streamlit as st
from functools import wraps

OWNER = "owner"
MANAGER = "manager"
SALESMAN = "salesman"


def get_current_user():
    return st.session_state.get("current_user")


def get_current_role():
    user = get_current_user()
    return user.get("role") if user else None


def is_owner() -> bool:
    return get_current_role() == OWNER


def is_manager() -> bool:
    return get_current_role() == MANAGER


def is_salesman() -> bool:
    return get_current_role() == SALESMAN


def require_login():
    if not get_current_user():
        st.error("Login required.")
        st.stop()


def require_role(roles):
    """
    Usage:
        @require_role(["owner", "manager"])
        def page():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            require_login()
            role = get_current_role()
            if role not in roles:
                st.error("Access denied.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def can_access_module(module_name: str) -> bool:
    role = get_current_role()

    owner_modules = {
        "owner_dashboard",
        "manage_users",
        "manage_nozzles",
        "fuel_rates",
        "credit_parties",
        "owner_reports",
        "manager_dashboard",
        "duty_management",
        "settlement",
        "testing",
        "inward",
        "payments",
        "reports",
    }

    manager_modules = {
        "manager_dashboard",
        "duty_management",
        "settlement",
        "testing",
        "inward",
        "payments",
        "reports",
    }

    salesman_modules = {
        "attendant_dashboard",
        "sale_entry",
        "credit_entry",
        "my_entries",
        "my_summary",
    }

    if role == OWNER:
        return module_name in owner_modules
    if role == MANAGER:
        return module_name in manager_modules
    if role == SALESMAN:
        return module_name in salesman_modules

    return False
