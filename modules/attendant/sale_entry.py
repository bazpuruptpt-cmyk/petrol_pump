import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.sale_db import (
    VALID_PAYMENT_MODES,
    get_assigned_nozzles_for_salesman,
    get_current_rate_for_nozzle,
    calculate_sale_amount,
    create_sale_entry,
)
from database.credit_db import get_active_parties


@require_role(["salesman"])
def sale_entry_page():
    user = get_current_user()
    st.title("Sale Entry")
    st.caption("Salesman can enter sales only for assigned active nozzles.")

    duty, nozzles = get_assigned_nozzles_for_salesman(user["id"])

    if not duty:
        st.error("No active duty found.")
        st.stop()

    if not nozzles:
        st.warning("No assigned nozzles found. Ask manager to assign nozzle.")
        return

    nozzle_labels = {
        f"{n.get('nozzle_name')} | {n.get('fuel_type')} | Opening: {n.get('opening_reading')}": n
        for n in nozzles
    }

    selected_label = st.selectbox("Select Nozzle", list(nozzle_labels.keys()))
    selected_nozzle = nozzle_labels[selected_label]

    rate = get_current_rate_for_nozzle(selected_nozzle)

    if not rate:
        st.error(f"No fuel rate found for {selected_nozzle.get('fuel_type')}. Owner must set fuel rate first.")
        return

    st.info(f"Current Rate: {format_currency(rate)} per liter")

    with st.form("sale_entry_form"):
        liters = st.number_input("Liters", min_value=0.0, step=0.01, format="%.2f")
        amount = calculate_sale_amount(liters, rate)
        st.metric("Auto Amount", format_currency(amount))

        payment_mode = st.selectbox("Payment Mode", VALID_PAYMENT_MODES)

        credit_party_id = None
        vehicle_number = None

        if payment_mode == "credit":
            parties = get_active_parties()

            if not parties:
                st.warning("No active credit party found. Create credit party first.")
            else:
                party_labels = {
                    f"{p.get('name')} | Balance: {p.get('current_balance')} | Limit: {p.get('credit_limit')}": p
                    for p in parties
                }
                selected_party_label = st.selectbox("Credit Party", list(party_labels.keys()))
                selected_party = party_labels[selected_party_label]
                credit_party_id = selected_party.get("id")

            vehicle_number = st.text_input("Vehicle Number")

        submitted = st.form_submit_button("Submit Sale Entry")

    if submitted:
        if liters <= 0:
            st.error("Liters must be greater than 0.")
            return

        if payment_mode == "credit" and not credit_party_id:
            st.error("Credit party required.")
            return

        sale, error = create_sale_entry({
            "shift_id": selected_nozzle["shift_id"],
            "nozzle_id": selected_nozzle["nozzle_id"],
            "salesman_id": user["id"],
            "fuel_type": selected_nozzle["fuel_type"],
            "liters": liters,
            "rate": rate,
            "payment_mode": payment_mode,
            "credit_party_id": credit_party_id,
            "vehicle_number": vehicle_number,
        })

        if sale:
            st.success(f"Sale entry submitted. Amount: {format_currency(sale.get('amount'))}. Status: pending.")
            st.rerun()
        else:
            st.error(error or "Sale entry failed.")
