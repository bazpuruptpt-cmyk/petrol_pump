import streamlit as st

from database.profiles_db import (
    get_all_users,
    create_profile,
    update_user,
    toggle_user_active,
)
from utils.permissions import require_role

ROLE_OPTIONS = ["owner", "manager", "salesman"]

ROLE_DEFAULT_PAGES = {
    "owner": [
        "Dashboard", "Money Control", "Reports", "Sale Approval", "Settlement",
        "Credit Parties", "Credit Payment", "Stock Management", "Duty Management",
        "Nozzle Assignment", "Users", "Nozzles", "Fuel Rates", "System Audit", "Backup / Restore"
    ],
    "manager": [
        "Dashboard", "Money Control", "Reports", "Sale Approval", "Settlement",
        "Credit Parties", "Credit Payment", "Stock Management", "Duty Management", "Nozzle Assignment"
    ],
    "salesman": [
        "Dashboard", "Sale Entry", "My Entries", "My Summary"
    ],
}


@require_role(["owner"])
def manage_users_page():
    st.title("Manage Users & Access Profiles")
    st.caption("यहाँ से सीधे नया यूज़र (Manager/Salesman) बनाएं, पासवर्ड सेट करें और तय करें कि उसे कौन-कौन से पेज दिखेंगे।")

    section = st.radio(
        "User Section",
        ["Users List", "Create New User", "Edit User & Permissions"],
        horizontal=True,
        key="manage_users_active_section",
    )

    if section == "Users List":
        show_user_list()
    elif section == "Create New User":
        create_user_form()
    elif section == "Edit User & Permissions":
        edit_user_form()


def show_user_list():
    users = get_all_users()
    if not users:
        st.info("No profiles found.")
        return

    rows = []
    for u in users:
        is_active = bool(u.get("is_active"))
        pages = u.get("allowed_pages") or []
        rows.append({
            "Name": u.get("name"),
            "Username / Login ID": u.get("username") or "-",
            "Role": u.get("role"),
            "Phone": u.get("phone") or "-",
            "Status": "🟢 Active" if is_active else "🔴 Inactive",
            "Allowed Pages": ", ".join(pages) if pages else "All Role Pages (Default)",
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
    st.subheader("➕ Create New User (Direct Login & Profile)")

    selected_role = st.selectbox("Select Role First", ROLE_OPTIONS, index=1, key="new_user_role_select")
    available_pages = ROLE_DEFAULT_PAGES.get(selected_role, [])

    with st.form("create_profile_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Full Name (जैसे: रमेश मुंशी)")
            username = st.text_input("Login Username / Email (जैसे: ramesh1)")
            phone = st.text_input("Phone Number")
        with c2:
            password = st.text_input("Set Password", type="password")
            user_id = st.text_input("Optional Auth UUID (खाली छोड़ दें, अपने आप बन जाएगा)")

        st.markdown("**इस यूज़र को कौन-कौन से पेज (Modules) एक्सेस करने की इजाज़त है?**")
        selected_pages = st.multiselect(
            "Allowed Pages",
            options=available_pages,
            default=available_pages,
        )

        submitted = st.form_submit_button("✅ Create User", use_container_width=True)

    if submitted:
        if not name or not username or not password:
            st.error("Name, Login Username और Password भरना ज़रूरी है!")
            return

        profile = create_profile(
            name=name,
            role=selected_role,
            phone=phone,
            username=username,
            password=password,
            allowed_pages=selected_pages,
            user_id=user_id,
        )

        if profile:
            st.success(f"🎉 यूज़र '{name}' (Login ID: {username}) सफलतापूर्वक बन गया!")
        else:
            st.error("User creation failed. (सुनिश्चित करें कि आपने profiles टेबल में username, password_hash और allowed_pages कॉलम जोड़ लिए हैं)।")


def edit_user_form():
    users = get_all_users()
    if not users:
        st.info("No profiles found.")
        return

    user_labels = {}
    for u in users:
        status = "Active" if bool(u.get("is_active")) else "Inactive"
        label = f"{u.get('name')} | {u.get('role')} | {status} | Login: {u.get('username') or u.get('phone') or 'UUID'}"
        user_labels[label] = u

    selected_label = st.selectbox("Select User to Edit", list(user_labels.keys()))
    selected_user = user_labels[selected_label]

    current_role = selected_user.get("role") if selected_user.get("role") in ROLE_OPTIONS else "manager"
    role = st.selectbox("Role", ROLE_OPTIONS, index=ROLE_OPTIONS.index(current_role))

    available_pages = ROLE_DEFAULT_PAGES.get(role, [])
    existing_pages = selected_user.get("allowed_pages") or available_pages
    valid_existing = [p for p in existing_pages if p in available_pages] or available_pages

    with st.form("edit_user_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Name", value=selected_user.get("name") or "")
            username = st.text_input("Login Username / Email", value=selected_user.get("username") or "")
            phone = st.text_input("Phone", value=selected_user.get("phone") or "")
        with c2:
            new_password = st.text_input("New Password (अगर बदलना हो तभी भरें, वरना खाली छोड़ें)", type="password")
            is_active = st.selectbox(
                "Status",
                ["Active", "Inactive"],
                index=0 if bool(selected_user.get("is_active")) else 1,
            )

        selected_pages = st.multiselect(
            "Allowed Pages (इस यूज़र को दिखने वाले मेन्यू)",
            options=available_pages,
            default=valid_existing,
        )

        submitted = st.form_submit_button("💾 Update User & Permissions", use_container_width=True)

    if submitted:
        updated = update_user(
            selected_user["id"],
            {
                "name": name,
                "role": role,
                "phone": phone,
                "username": username,
                "new_password": new_password,
                "allowed_pages": selected_pages,
                "is_active": True if is_active == "Active" else False,
            },
        )

        if updated:
            st.success("User profile & permissions updated!")
            st.rerun()
        else:
            st.error("User update failed.")

    st.divider()
    if st.button("Toggle Active / Inactive"):
        updated = toggle_user_active(selected_user["id"])
        if updated:
            st.success("User status changed.")
            st.rerun()
