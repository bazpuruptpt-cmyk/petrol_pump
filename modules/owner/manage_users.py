import streamlit as st

from database.profiles_db import (
    get_all_users,
    create_profile,
    update_user,
    toggle_user_active,
)
from utils.permissions import require_role


ROLE_OPTIONS = ["owner", "manager", "salesman"]


@require_role(["owner"])
def manage_users_page():
    st.title("Manage Users")
    st.caption("Owner only. Supabase Auth user pehle Dashboard me banao, phir yahan profile create/update karo.")

    tab1, tab2, tab3 = st.tabs(["Users List", "Create Profile", "Edit User"])

    with tab1:
        show_user_list()

    with tab2:
        create_user_form()

    with tab3:
        edit_user_form()


def show_user_list():
    users = get_all_users()

    if not users:
        st.info("No profiles found.")
        return

    rows = []
    for u in users:
        is_active = bool(u.get("is_active"))

        rows.append({
            "Name": u.get("name"),
            "Role": u.get("role"),
            "Phone": u.get("phone"),
            "Status": "🟢 Active" if is_active else "🔴 Inactive",
            "User ID": u.get("id"),
            "Created At": u.get("created_at"),
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()

    active_count = sum(1 for u in users if bool(u.get("is_active")))
    inactive_count = len(users) - active_count
    salesman_count = sum(1 for u in users if u.get("role") == "salesman" and bool(u.get("is_active")))

    c1, c2, c3 = st.columns(3)
    c1.metric("Active Users", active_count)
    c2.metric("Inactive Users", inactive_count)
    c3.metric("Active Salesmen", salesman_count)


def create_user_form():
    st.subheader("Create / Upsert Profile")

    st.warning("Pehle Supabase → Authentication → Users me user banao. Wahan se UUID copy karke yahan paste karo.")

    with st.form("create_profile_form"):
        user_id = st.text_input("Auth User UUID")
        name = st.text_input("Name")
        role = st.selectbox("Role", ROLE_OPTIONS)
        phone = st.text_input("Phone")
        submitted = st.form_submit_button("Save Profile")

    if submitted:
        if not user_id or not name:
            st.error("Auth User UUID and Name required.")
            return

        profile = create_profile(user_id=user_id, name=name, role=role, phone=phone)

        if profile:
            st.success("Profile saved.")
            st.rerun()
        else:
            st.error("Profile save failed. Check UUID/RLS/table permissions.")


def edit_user_form():
    users = get_all_users()

    if not users:
        st.info("No profiles found.")
        return

    user_labels = {}

    for u in users:
        status = "Active" if bool(u.get("is_active")) else "Inactive"
        label = f"{u.get('name')} | {u.get('role')} | {status} | {u.get('id')}"
        user_labels[label] = u

    selected_label = st.selectbox("Select User", list(user_labels.keys()))
    selected_user = user_labels[selected_label]

    current_status = "🟢 Active" if bool(selected_user.get("is_active")) else "🔴 Inactive"
    st.info(f"Current Status: {current_status}")

    with st.form("edit_user_form"):
        name = st.text_input("Name", value=selected_user.get("name") or "")
        role = st.selectbox(
            "Role",
            ROLE_OPTIONS,
            index=ROLE_OPTIONS.index(selected_user.get("role")) if selected_user.get("role") in ROLE_OPTIONS else 0,
        )
        phone = st.text_input("Phone", value=selected_user.get("phone") or "")
        is_active = st.selectbox(
            "Status",
            ["Active", "Inactive"],
            index=0 if bool(selected_user.get("is_active")) else 1,
        )

        submitted = st.form_submit_button("Update User")

    if submitted:
        updated = update_user(
            selected_user["id"],
            {
                "name": name,
                "role": role,
                "phone": phone,
                "is_active": True if is_active == "Active" else False,
            },
        )

        if updated:
            st.success("User updated.")
            st.rerun()
        else:
            st.error("User update failed.")

    st.divider()

    if st.button("Toggle Active / Inactive"):
        updated = toggle_user_active(selected_user["id"])
        if updated:
            st.success("User status changed.")
            st.rerun()
        else:
            st.error("Status change failed.")
