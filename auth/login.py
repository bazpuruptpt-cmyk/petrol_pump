import streamlit as st
from config.supabase_client import get_supabase_client
from database.profiles_db import get_profile_by_user_id
from database.duties_db import is_duty_active


def authenticate_user(email: str, password: str):
    supabase = get_supabase_client()

    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
    except Exception as exc:
        st.error("Invalid login credentials.")
        return None

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
            st.session_state["current_user"] = user
            st.success("Login successful.")
            st.rerun()


def logout():
    supabase = get_supabase_client()
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state.pop("current_user", None)
    st.rerun()
