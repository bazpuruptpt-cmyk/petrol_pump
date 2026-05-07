import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.sale_db import (
    VALID_PAYMENT_MODES,
    get_assigned_nozzles_for_salesman,
    get_current_rate_for_nozzle,
    calculate_sale_amount,
    create_sale_entry,
    get_salesman_payment_match_summary,
    get_salesman_nozzle_summary,
    get_credit_party_wise_summary,
    get_manual_payment_match,
)
from database.credit_db import get_active_parties


@require_role(["salesman"])
def sale_entry_page():
    user = get_current_user()
    st.title("Sale Entry")
    st.caption("Liters enter karte hi amount auto update hoga. Total sale payment breakup se match hoga.")

    duty, nozzles = get_assigned_nozzles_for_salesman(user["id"])

    if not duty:
        st.error("No active duty found.")
        st.stop()

    if not nozzles:
        st.warning("No assigned nozzles found. Ask manager to assign nozzle.")
        return

    show_today_match_cards(user["id"])

    st.divider()

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

    liters = st.number_input(
        "Liters",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key="live_liters",
    )

    amount = calculate_sale_amount(liters, rate)

    c1, c2, c3 = st.columns(3)
    c1.metric("Rate", format_currency(rate))
    c2.metric("Liters", f"{liters:.2f} L")
    c3.metric("Auto Amount", format_currency(amount))

    payment_mode = st.selectbox("Payment Mode", VALID_PAYMENT_MODES)

    credit_party_id = None
    vehicle_number = None

    if payment_mode == "credit":
        parties = get_active_parties()

        if not parties:
            st.warning("No active credit party found. Credit entry ke liye pehle credit party create karo.")
        else:
            party_labels = {
                f"{p.get('name')} | Balance: {p.get('current_balance')} | Limit: {p.get('credit_limit')}": p
                for p in parties
            }
            selected_party_label = st.selectbox("Credit Party", list(party_labels.keys()))
            selected_party = party_labels[selected_party_label]
            credit_party_id = selected_party.get("id")

        vehicle_number = st.text_input("Vehicle Number")

    st.divider()

    if st.button("Submit Sale Entry", type="primary"):
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
            st.success(
                f"Sale entry submitted. Amount: {format_currency(sale.get('amount'))}. "
                f"Payment: {payment_mode}. Status: pending."
            )

            if payment_mode == "credit":
                st.info("Credit amount creditor ledger me pending entry ke form me post ho gayi hai.")

            if error:
                st.warning(error)

            st.rerun()
        else:
            st.error(error or "Sale entry failed.")

    st.divider()
    show_nozzle_wise_summary(user["id"])

    st.divider()
    show_creditor_summary(user["id"])

    st.divider()
    show_manual_match_checker(user["id"])


def show_today_match_cards(salesman_id: str):
    summary = get_salesman_payment_match_summary(salesman_id)

    st.subheader("Today Total Sale Match")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Sale Amount", format_currency(summary["total"]))
    c2.metric("Cash + Paytm + CCMS + Credit", format_currency(summary["payment_total"]))
    c3.metric("Difference", format_currency(summary["difference"]))

    c4, c5, c6, c7 = st.columns(4)
    c4.metric("Cash", format_currency(summary["cash"]))
    c5.metric("Paytm", format_currency(summary["paytm"]))
    c6.metric("CCMS", format_currency(summary["ccms"]))
    c7.metric("Credit / Creditor", format_currency(summary["credit"]))

    if summary["is_matched"]:
        st.success("MATCHED: Total Sale Amount payment breakup se match hai.")
    else:
        st.error("NOT MATCHED: Payment breakup total sale se match nahi kar raha.")


def show_nozzle_wise_summary(salesman_id: str):
    st.subheader("Nozzle-wise Today Summary")

    rows = get_salesman_nozzle_summary(salesman_id)

    if not rows:
        st.info("No sale entry yet.")
        return

    st.dataframe(rows, use_container_width=True, hide_index=True)


def show_creditor_summary(salesman_id: str):
    st.subheader("Creditor-wise Credit Sale")

    rows = get_credit_party_wise_summary(salesman_id)

    if not rows:
        st.info("No credit sale entry yet.")
        return

    st.dataframe(rows, use_container_width=True, hide_index=True)


def show_manual_match_checker(salesman_id: str):
    """
    End-of-shift manual verification.
    Ye save nahi karta; sirf match check karta hai.
    Permanent settlement/locking manager settlement phase me add hoga.
    """
    summary = get_salesman_payment_match_summary(salesman_id)

    with st.expander("Manual Payment Match Checker"):
        st.caption("Yahan salesman actual cash/paytm/ccms/credit amount enter karke total sale se match check kar sakta hai.")

        cash = st.number_input("Actual Cash Amount", min_value=0.0, step=1.0, format="%.2f")
        paytm = st.number_input("Actual Paytm Amount", min_value=0.0, step=1.0, format="%.2f")
        ccms = st.number_input("Actual CCMS Amount", min_value=0.0, step=1.0, format="%.2f")
        credit = st.number_input("Actual Credit/Creditor Amount", min_value=0.0, step=1.0, format="%.2f")

        match = get_manual_payment_match(
            total_sale=summary["total"],
            cash=cash,
            paytm=paytm,
            ccms=ccms,
            credit=credit,
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Sale", format_currency(match["total_sale"]))
        c2.metric("Entered Payment Total", format_currency(match["payment_total"]))
        c3.metric("Difference", format_currency(match["difference"]))

        if match["is_matched"]:
            st.success("MATCHED: Entered payment total sale amount ke barabar hai.")
        else:
            st.warning("NOT MATCHED: Difference clear karo.")
