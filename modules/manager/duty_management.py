import streamlit as st

from database.profiles_db import get_active_salesmen
from database.duties_db import (
    get_active_duties,
    get_duty_history,
    start_duty,
    end_duty,
)
from utils.permissions import require_role, get_current_user


@require_role(["manager", "owner"])
def duty_management_page():
    st.title("Duty Management")
    st.caption("Manager/Owner: start duty, view active duties, end duty.")

    section = st.radio(
        "Duty Section",
        ["Start Duty", "Active Duties", "Duty History"],
        horizontal=True,
        key="duty_management_active_section",
    )

    if section == "Start Duty":
        start_duty_form()
    elif section == "Active Duties":
        show_active_duties_list()
    elif section == "Duty History":
        show_duty_history()


def start_duty_form():
    user = get_current_user()
    salesmen = get_active_salesmen()

    st.subheader("Start Duty")

    if not salesmen:
        st.info("No active salesman found. Create salesman profile first.")
        return

    labels = {
        f"{s.get('name')} | {s.get('phone') or ''} | {s.get('id')}": s
        for s in salesmen
    }

    selected_label = st.selectbox("Select Salesman", list(labels.keys()))
    selected_salesman = labels[selected_label]

    if st.button("Start Duty"):
        duty, error = start_duty(
            salesman_id=selected_salesman["id"],
            manager_id=user["id"],
        )

        if duty:
            st.success(f"Duty started. Shift ID: {duty.get('id')}")
            st.rerun()
        else:
            st.error(error or "Duty start failed.")


def show_active_duties_list():
    duties = get_active_duties()

    st.subheader("Active Duties")

    if not duties:
        st.info("No active duties.")
        return

    for duty in duties:
        profile = duty.get("profiles") or {}
        with st.container(border=True):
            st.write(f"**Shift ID:** {duty.get('id')}")
            st.write(f"**Salesman:** {profile.get('name')}")
            st.write(f"**Date:** {duty.get('date')}")
            st.write(f"**Started At:** {duty.get('started_at')}")

            if st.button("End Duty", key=f"end_duty_{duty.get('id')}"):
                updated = end_duty(duty.get("id"))
                if updated:
                    st.success("Duty ended.")
                    st.rerun()
                else:
                    st.error("Duty end failed.")


def show_duty_history():
    duties = get_duty_history()

    st.subheader("Duty History")

    if not duties:
        st.info("No duty history found.")
        return

    rows = []
    for d in duties:
        profile = d.get("profiles") or {}
        rows.append({
            "shift_id": d.get("id"),
            "salesman": profile.get("name"),
            "date": d.get("date"),
            "is_active": d.get("is_active"),
            "started_at": d.get("started_at"),
            "ended_at": d.get("ended_at"),
        })

    st.dataframe(rows, use_container_width=True)
