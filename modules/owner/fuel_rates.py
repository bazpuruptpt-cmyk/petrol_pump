import streamlit as st

from database.fuel_rates_db import (
    VALID_FUEL_TYPES,
    get_current_rates,
    get_rate_history,
    set_rate,
)
from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency


@require_role(["owner"])
def fuel_rates_page():
    st.title("Fuel Rates")
    st.caption("Owner only. Latest effective rate will be used for sales.")

    section = st.radio(
        "Fuel Rate Section",
        ["Current Rates", "Set New Rate", "Rate History"],
        horizontal=True,
        key="fuel_rates_active_section",
    )

    if section == "Current Rates":
        show_current_rates()
    elif section == "Set New Rate":
        update_rate_form()
    elif section == "Rate History":
        show_rate_history()


def show_current_rates():
    rates = get_current_rates()

    if not rates:
        st.info("No fuel rates found.")
        return

    cols = st.columns(4)

    for idx, fuel_type in enumerate(VALID_FUEL_TYPES):
        row = rates.get(fuel_type)
        amount = row.get("price_per_liter") if row else 0
        cols[idx].metric(fuel_type.replace("_", " ").title(), format_currency(amount))


def update_rate_form():
    user = get_current_user()

    st.subheader("Set New Rate")

    with st.form("set_rate_form"):
        fuel_type = st.selectbox("Fuel Type", VALID_FUEL_TYPES)
        price = st.number_input("Price Per Liter", min_value=0.0, step=0.01, format="%.2f")
        effective_from = st.date_input("Effective From")
        submitted = st.form_submit_button("Save Rate")

    if submitted:
        if price <= 0:
            st.error("Price must be greater than 0.")
            return

        saved = set_rate(
            fuel_type=fuel_type,
            price=price,
            effective_from=str(effective_from),
            created_by=user["id"],
        )

        if saved:
            st.success("Fuel rate saved.")
            st.rerun()
        else:
            st.error("Fuel rate save failed.")


def show_rate_history():
    selected = st.selectbox("Filter Fuel Type", ["all"] + VALID_FUEL_TYPES)

    if selected == "all":
        rows = get_rate_history()
    else:
        rows = get_rate_history(selected)

    if not rows:
        st.info("No rate history found.")
        return

    st.dataframe(rows, use_container_width=True)
