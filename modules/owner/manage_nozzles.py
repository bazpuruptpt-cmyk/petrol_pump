import streamlit as st

from database.nozzles_db import (
    VALID_FUEL_TYPES,
    get_all_nozzles,
    create_nozzle,
    update_nozzle,
    toggle_nozzle_active,
)
from utils.permissions import require_role, get_current_user


@require_role(["owner"])
def manage_nozzles_page():
    st.title("Manage Nozzles")
    st.caption("Owner only. Nozzle creation and fuel assignment.")

    section = st.radio(
        "Nozzle Section",
        ["Nozzle List", "Create Nozzle", "Edit Nozzle"],
        horizontal=True,
        key="manage_nozzles_active_section",
    )

    if section == "Nozzle List":
        show_nozzle_list()
    elif section == "Create Nozzle":
        create_nozzle_form()
    elif section == "Edit Nozzle":
        edit_nozzle_form()


def show_nozzle_list():
    nozzles = get_all_nozzles()

    if not nozzles:
        st.info("No nozzles found.")
        return

    rows = []

    for n in nozzles:
        is_active = bool(n.get("is_active"))

        rows.append({
            "Nozzle ID": n.get("id"),
            "Nozzle Name": n.get("nozzle_name"),
            "Fuel Type": n.get("fuel_type"),
            "Current Reading": n.get("current_reading"),
            "Status": "🟢 Active" if is_active else "🔴 Inactive",
            "Created By": n.get("created_by"),
            "Created At": n.get("created_at"),
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()

    active_count = sum(1 for n in nozzles if bool(n.get("is_active")))
    inactive_count = len(nozzles) - active_count

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Nozzles", len(nozzles))
    c2.metric("Active Nozzles", active_count)
    c3.metric("Inactive Nozzles", inactive_count)


def create_nozzle_form():
    user = get_current_user()

    st.subheader("Create Nozzle")

    with st.form("create_nozzle_form"):
        nozzle_name = st.text_input("Nozzle Name", placeholder="Nozzle 1")
        fuel_type = st.selectbox("Fuel Type", VALID_FUEL_TYPES)
        current_reading = st.number_input(
            "Current Reading",
            min_value=0.0,
            step=0.01,
            format="%.2f",
        )

        submitted = st.form_submit_button("Create Nozzle")

    if submitted:
        if not nozzle_name:
            st.error("Nozzle name required.")
            return

        nozzle = create_nozzle(
            nozzle_name=nozzle_name,
            fuel_type=fuel_type,
            current_reading=current_reading,
            created_by=user["id"],
        )

        if nozzle:
            st.success("Nozzle created.")
            st.rerun()
        else:
            st.error("Nozzle creation failed.")


def edit_nozzle_form():
    nozzles = get_all_nozzles()

    if not nozzles:
        st.info("No nozzles found.")
        return

    nozzle_labels = {}

    for n in nozzles:
        status = "Active" if bool(n.get("is_active")) else "Inactive"
        label = f"{n.get('id')} | {n.get('nozzle_name')} | {n.get('fuel_type')} | {status}"
        nozzle_labels[label] = n

    selected_label = st.selectbox("Select Nozzle", list(nozzle_labels.keys()))
    selected_nozzle = nozzle_labels[selected_label]

    current_status = "🟢 Active" if bool(selected_nozzle.get("is_active")) else "🔴 Inactive"
    st.info(f"Current Status: {current_status}")

    current_fuel = selected_nozzle.get("fuel_type")
    fuel_index = VALID_FUEL_TYPES.index(current_fuel) if current_fuel in VALID_FUEL_TYPES else 0

    with st.form("edit_nozzle_form"):
        nozzle_name = st.text_input(
            "Nozzle Name",
            value=selected_nozzle.get("nozzle_name") or "",
        )

        fuel_type = st.selectbox(
            "Fuel Type",
            VALID_FUEL_TYPES,
            index=fuel_index,
        )

        current_reading = st.number_input(
            "Current Reading",
            min_value=0.0,
            value=float(selected_nozzle.get("current_reading") or 0),
            step=0.01,
            format="%.2f",
        )

        is_active = st.selectbox(
            "Status",
            ["Active", "Inactive"],
            index=0 if bool(selected_nozzle.get("is_active")) else 1,
        )

        submitted = st.form_submit_button("Update Nozzle")

    if submitted:
        updated = update_nozzle(
            selected_nozzle["id"],
            {
                "nozzle_name": nozzle_name,
                "fuel_type": fuel_type,
                "current_reading": current_reading,
                "is_active": True if is_active == "Active" else False,
            },
        )

        if updated:
            st.success("Nozzle updated.")
            st.rerun()
        else:
            st.error("Nozzle update failed.")

    st.divider()

    if st.button("Toggle Active / Inactive"):
        updated = toggle_nozzle_active(selected_nozzle["id"])

        if updated:
            st.success("Nozzle status changed.")
            st.rerun()
        else:
            st.error("Nozzle status change failed.")
