import streamlit as st

from database.duties_db import (
    get_active_duties,
    get_shift_assignments,
    assign_nozzle_to_shift,
    remove_nozzle_assignment,
)
from database.nozzles_db import get_available_nozzles
from utils.permissions import require_role


@require_role(["manager", "owner"])
def nozzle_assignment_page():
    st.title("Nozzle Assignment")
    st.caption("One nozzle can only be assigned to one active duty at a time.")

    tab1, tab2 = st.tabs(["Assign Nozzle", "Active Assignments"])

    with tab1:
        assign_nozzles_to_duty()

    with tab2:
        show_all_active_assignments()


def assign_nozzles_to_duty():
    duties = get_active_duties()

    st.subheader("Assign Nozzle To Active Duty")

    if not duties:
        st.info("No active duty found. Start duty first.")
        return

    duty_labels = {}
    for d in duties:
        p = d.get("profiles") or {}
        duty_labels[f"Shift {d.get('id')} | {p.get('name')} | {d.get('date')}"] = d

    selected_duty_label = st.selectbox("Select Active Duty", list(duty_labels.keys()))
    selected_duty = duty_labels[selected_duty_label]

    available_nozzles = get_available_nozzles()

    if not available_nozzles:
        st.warning("No available nozzles. All active nozzles may already be assigned.")
        return

    nozzle_labels = {
        f"{n.get('id')} | {n.get('nozzle_name')} | {n.get('fuel_type')} | Reading: {n.get('current_reading')}": n
        for n in available_nozzles
    }

    selected_nozzle_label = st.selectbox("Select Available Nozzle", list(nozzle_labels.keys()))
    selected_nozzle = nozzle_labels[selected_nozzle_label]

    if st.button("Assign Nozzle"):
        assignment, error = assign_nozzle_to_shift(
            shift_id=selected_duty["id"],
            nozzle_id=selected_nozzle["id"],
        )

        if assignment:
            st.success("Nozzle assigned.")
            st.rerun()
        else:
            st.error(error or "Nozzle assignment failed.")


def show_all_active_assignments():
    duties = get_active_duties()

    st.subheader("Active Assignments")

    if not duties:
        st.info("No active duties.")
        return

    found = False

    for duty in duties:
        profile = duty.get("profiles") or {}
        assignments = get_shift_assignments(duty.get("id"))

        with st.container(border=True):
            st.write(f"**Shift {duty.get('id')} — {profile.get('name')}**")

            if not assignments:
                st.info("No nozzle assigned to this duty.")
                continue

            found = True

            for a in assignments:
                nozzle = a.get("nozzles") or {}
                col1, col2 = st.columns([4, 1])

                with col1:
                    st.write(
                        f"Nozzle: **{nozzle.get('nozzle_name')}** | "
                        f"Fuel: **{nozzle.get('fuel_type')}** | "
                        f"Opening: **{a.get('opening_reading')}**"
                    )

                with col2:
                    if st.button("Remove", key=f"remove_assign_{a.get('id')}"):
                        removed = remove_nozzle_assignment(a.get("id"))
                        if removed:
                            st.success("Assignment removed.")
                            st.rerun()
                        else:
                            st.error("Remove failed.")

    if not found:
        st.caption("No active nozzle assignments found.")
