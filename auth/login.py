import streamlit as st
from config.supabase_client import get_auth_client
from database.profiles_db import get_profile_by_user_id
import time
from database.duties_db import is_duty_active
from auth.persistent_session import save_persistent_login, clear_persistent_login, render_session_bridge


def authenticate_user(email: str, password: str):
    # Basic brute-force throttle per browser session.
    now = time.time()
    if st.session_state.get("_login_locked_until", 0) > now:
        st.error("Too many failed attempts. Thodi der baad try karo.")
        return None

    email = (email or "").strip().lower()
    supabase = get_auth_client()

    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
    except Exception:
        fails = st.session_state.get("_login_fails", 0) + 1
        st.session_state["_login_fails"] = fails
        if fails >= 5:
            st.session_state["_login_locked_until"] = now + 60
            st.session_state["_login_fails"] = 0
        st.error("Invalid login credentials.")
        return None
    st.session_state["_login_fails"] = 0

    user = auth_response.user
    if not user:
        st.error("Login failed.")
        return None

    profile = get_profile_by_user_id(user.id)
    if not profile:
        st.error("Profile not found or inactive.")
        return None

    if profile["role"] == "salesman":
        if not is_duty_active(profile["id"]):
            st.error("Salesman login allowed only when duty is active.")
            return None

    return {
        "id": profile["id"],
        "name": profile["name"],
        "role": profile["role"],
        "phone": profile.get("phone"),
        "email": email,
    }


def login_page():
    st.title("Petrol Pump Management System")
    st.subheader("Login")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if not email or not password:
            st.error("Email and password required.")
            return

        user = authenticate_user(email, password)
        if user:
            save_persistent_login(user)
            render_session_bridge(token=st.session_state.get("_pump_session_token"))
            st.success("Login successful.")
            st.rerun()


def logout():
    # Login uses a throw-away auth client, so there is no shared Supabase
    # session to sign out. Only clear this browser session.
    clear_persistent_login()
    render_session_bridge(clear=True)
    st.rerun()
