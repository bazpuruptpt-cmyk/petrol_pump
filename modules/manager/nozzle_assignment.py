
import streamlit as st

from utils.permissions import require_role, get_current_user
from database.nozzle_assignment_db import (
    get_active_duties_for_assignment,
    get_active_salesmen_for_assignment,
    get_available_nozzles,
    get_active_shift_assignments,
    assign_nozzle_to_salesman,
    end_nozzle_assignment,
    get_duplicate_active_nozzle_assignments,
)


@require_role(["owner", "manager"])
def nozzle_assignment_page():
    st.title("Nozzle Assignment")
    st.caption("Duty salesman is final. Different salesman cannot be selected for the same shift.")

    show_debug_counts()
    show_duplicate_warning()

    tab1, tab2 = st.tabs(["Assign Nozzle", "Active Assignments"])

    with tab1:
        assign_tab()

    with tab2:
        active_assignments_tab()


def show_debug_counts():
    duties = get_active_duties_for_assignment()
    salesmen = get_active_salesmen_for_assignment()
    nozzles = get_available_nozzles()

    c1, c2, c3 = st.columns(3)
    c1.metric("Active Duties", len(duties))
    c2.metric("Active Salesmen", len(salesmen))
    c3.metric("Available Nozzles", len(nozzles))


def show_duplicate_warning():
    duplicates = get_duplicate_active_nozzle_assignments()

    if not duplicates:
        return

    st.error("Duplicate active nozzle assignments found. Run hard-lock SQL.")
    for d in duplicates:
        st.write(f"Nozzle ID {d['nozzle_id']} has {d['count']} active assignments.")


def assign_tab():
    user = get_current_user()

    duties = get_active_duties_for_assignment()
    nozzles = get_available_nozzles()

    if not duties:
        st.warning("No active duty found. Pehle Duty Management me salesman ki duty start karo.")
        return

    if not nozzles:
        st.warning("No available nozzle found. Ya to nozzles inactive hain, ya already assigned hain.")
        return

    duty_labels = {}
    for d in duties:
        profile = d.get("profiles") or {}
        salesman_name = profile.get("name") or d.get("salesman_id")
        label = f"Shift {d.get('id')} | Salesman: {salesman_name} | {d.get('date')}"
        duty_labels[label] = d

    nozzle_labels = {
        f"{n.get('nozzle_name')} | {n.get('fuel_type')} | Reading {n.get('current_reading')}": n
        for n in nozzles
    }

    with st.form("assign_nozzle_form_hard_lock"):
        selected_duty_label = st.selectbox("Duty / Shift", list(duty_labels.keys()))
        selected_duty = duty_labels[selected_duty_label]
        duty_profile = selected_duty.get("profiles") or {}

        st.text_input(
            "Salesman",
            value=duty_profile.get("name") or str(selected_duty.get("salesman_id")),
            disabled=True,
            help="Salesman duty se auto-lock hai. Isko alag select nahi karna hai.",
        )

        selected_nozzle_label = st.selectbox("Available Nozzle", list(nozzle_labels.keys()))

        submitted = st.form_submit_button("Assign Nozzle")

    if submitted:
        duty = duty_labels[selected_duty_label]
        nozzle = nozzle_labels[selected_nozzle_label]

        row, error = assign_nozzle_to_salesman(
            shift_id=duty.get("id"),
            salesman_id=duty.get("salesman_id"),
            nozzle_id=nozzle.get("id"),
            assigned_by=user.get("id"),
        )

        if row:
            st.success("Nozzle assigned successfully.")
            st.rerun()
        else:
            st.error(error or "Nozzle assignment failed.")


def active_assignments_tab():
    rows = get_active_shift_assignments()

    if not rows:
        st.info("No active assignments.")
        return

    for row in rows:
        profile = row.get("profiles") or {}
        duty_profile = row.get("duty_profile") or {}
        nozzle = row.get("nozzles") or {}

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Assignment ID", row.get("id"))
            c2.metric("Salesman", profile.get("name") or duty_profile.get("name") or row.get("salesman_id"))
            c3.metric("Nozzle", nozzle.get("nozzle_name") or row.get("nozzle_id"))
            c4.metric("Fuel", nozzle.get("fuel_type"))

            st.write(
                f"**Shift ID:** {row.get('shift_id')} | "
                f"**Opening:** {row.get('opening_reading')} | "
                f"**Created:** {row.get('created_at')}"
            )

            if st.button("End Assignment", key=f"end_assignment_{row.get('id')}", use_container_width=True):
                updated, error = end_nozzle_assignment(row.get("id"))
                if updated:
                    st.success("Assignment ended.")
                    st.rerun()
                else:
                    st.error(error or "End assignment failed.")
