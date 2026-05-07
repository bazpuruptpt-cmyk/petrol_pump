import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.sale_db import (
    get_assigned_nozzles_for_salesman,
    get_current_rate_for_nozzle,
    calculate_sale_amount,
    create_nozzle_sale_entry,
    get_shift_sale_summary_for_salesman,
    get_salesman_nozzle_sale_summary,
    calculate_payment_match,
    save_payment_breakup,
    get_latest_payment_breakup,
)
from database.credit_db import get_active_parties


@require_role(["salesman"])
def sale_entry_page():
    user = get_current_user()
    st.title("Sale Entry")
    st.caption("Correct flow: nozzle-wise liters first, payment breakup later.")

    duty, nozzles = get_assigned_nozzles_for_salesman(user["id"])

    if not duty:
        st.error("No active duty found.")
        st.stop()

    if not nozzles:
        st.warning("No assigned nozzles found. Ask manager to assign nozzle.")
        return

    show_total_sale_block(user["id"])

    st.divider()

    tab1, tab2 = st.tabs(["1. Nozzle Sale Entry", "2. Final Payment Breakup"])

    with tab1:
        nozzle_sale_entry_form(user["id"], nozzles)

    with tab2:
        final_payment_breakup_form(user["id"])


def show_total_sale_block(salesman_id: str):
    summary = get_shift_sale_summary_for_salesman(salesman_id)

    st.subheader("Current Shift Total Sale")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Sale Amount", format_currency(summary["total_sale"]))
    c2.metric("Total Liters", f"{summary['total_liters']:.2f} L")
    c3.metric("Nozzle Entries", summary["entry_count"])

    st.caption("Ye total saare assigned nozzles ki liters × rate entries ka sum hai.")


def nozzle_sale_entry_form(salesman_id: str, nozzles: list):
    st.subheader("Nozzle-wise Liter Entry")

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

    liters = st.number_input(
        "Liters",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key="nozzle_liters_live",
    )

    amount = calculate_sale_amount(liters, rate)

    c1, c2, c3 = st.columns(3)
    c1.metric("Rate", format_currency(rate))
    c2.metric("Liters", f"{liters:.2f} L")
    c3.metric("Auto Amount", format_currency(amount))

    if st.button("Add Nozzle Sale", type="primary"):
        if liters <= 0:
            st.error("Liters must be greater than 0.")
            return

        sale, error = create_nozzle_sale_entry({
            "shift_id": selected_nozzle["shift_id"],
            "nozzle_id": selected_nozzle["nozzle_id"],
            "salesman_id": salesman_id,
            "fuel_type": selected_nozzle["fuel_type"],
            "liters": liters,
            "rate": rate,
        })

        if sale:
            st.success(f"Nozzle sale added. Amount: {format_currency(sale.get('amount'))}")
            st.rerun()
        else:
            st.error(error or "Sale entry failed.")

    st.divider()
    st.subheader("Nozzle-wise Current Shift Summary")

    rows = get_salesman_nozzle_sale_summary(salesman_id)

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No nozzle sale entry yet.")


def final_payment_breakup_form(salesman_id: str):
    st.subheader("Final Payment Breakup")

    summary = get_shift_sale_summary_for_salesman(salesman_id)
    total_sale = summary["total_sale"]

    latest = get_latest_payment_breakup(summary["shift_id"], salesman_id) if summary["shift_id"] else None

    if latest:
        st.info(
            "Latest saved breakup: "
            f"Cash {format_currency(latest.get('cash_amount'))}, "
            f"Paytm {format_currency(latest.get('paytm_amount'))}, "
            f"CCMS {format_currency(latest.get('ccms_amount'))}, "
            f"Credit {format_currency(latest.get('credit_amount'))}, "
            f"Difference {format_currency(latest.get('difference'))}"
        )

    st.metric("Total Sale Amount", format_currency(total_sale))

    cash = st.number_input("Cash Amount", min_value=0.0, step=1.0, format="%.2f", key="cash_breakup")
    paytm = st.number_input("Paytm Amount", min_value=0.0, step=1.0, format="%.2f", key="paytm_breakup")
    ccms = st.number_input("CCMS Amount", min_value=0.0, step=1.0, format="%.2f", key="ccms_breakup")

    st.divider()
    st.subheader("Credit / Creditor Amount")

    parties = get_active_parties()
    credit_allocations = []

    if not parties:
        st.warning("No active credit party found. Credit amount save karne ke liye credit party create karo.")
    else:
        party_options = {"-- Select Creditor --": None}
        for p in parties:
            party_options[f"{p.get('name')} | Balance: {p.get('current_balance')} | Limit: {p.get('credit_limit')}"] = p

        credit_rows = st.number_input(
            "Number of creditor entries",
            min_value=0,
            max_value=5,
            value=0,
            step=1,
            key="credit_rows_count",
        )

        labels = list(party_options.keys())

        for i in range(int(credit_rows)):
            st.markdown(f"**Creditor Entry {i + 1}**")
            c1, c2, c3 = st.columns([2, 1, 1])

            with c1:
                label = st.selectbox("Creditor", labels, key=f"credit_party_{i}")
                party = party_options[label]

            with c2:
                amount = st.number_input(
                    "Credit Amount",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                    key=f"credit_amount_{i}",
                )

            with c3:
                vehicle_number = st.text_input("Vehicle No.", key=f"vehicle_number_{i}")

            if party and amount > 0:
                credit_allocations.append({
                    "party_id": party["id"],
                    "amount": amount,
                    "vehicle_number": vehicle_number,
                })

    credit_total = round(sum(float(x.get("amount") or 0) for x in credit_allocations), 2)

    st.divider()
    match = calculate_payment_match(
        total_sale=total_sale,
        cash=cash,
        paytm=paytm,
        ccms=ccms,
        credit=credit_total,
    )

    st.subheader("Match Result")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Sale", format_currency(match["total_sale"]))
    c2.metric("Cash + Paytm + CCMS + Credit", format_currency(match["payment_total"]))
    c3.metric("Difference", format_currency(match["difference"]))

    c4, c5, c6, c7 = st.columns(4)
    c4.metric("Cash", format_currency(match["cash"]))
    c5.metric("Paytm", format_currency(match["paytm"]))
    c6.metric("CCMS", format_currency(match["ccms"]))
    c7.metric("Credit", format_currency(match["credit"]))

    if match["is_matched"]:
        st.success("MATCHED: Total Sale Amount = Cash + Paytm + CCMS + Credit")
    else:
        st.error("NOT MATCHED: Difference clear karo.")

    if st.button("Save Payment Breakup", type="primary"):
        settlement, error = save_payment_breakup(
            salesman_id=salesman_id,
            cash_amount=cash,
            paytm_amount=paytm,
            ccms_amount=ccms,
            credit_allocations=credit_allocations,
        )

        if settlement:
            st.success("Payment breakup saved. Status: pending manager approval.")
            if credit_total > 0:
                st.info("Credit amount creditor ledger me pending entry ke form me chala gaya.")
            st.rerun()
        else:
            st.error(error or "Payment breakup save failed.")
