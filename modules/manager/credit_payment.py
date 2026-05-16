from datetime import date
import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.credit_payment_db import (
    PAYMENT_MODES,
    get_active_credit_parties,
    create_credit_payment,
    get_credit_payments,
    get_approved_credit_collection_summary,
    get_credit_collection_rows,
)

try:
    from utils.export_utils import render_export_buttons
except Exception:
    render_export_buttons = None


@require_role(["owner", "manager"])
def credit_payment_page():
    st.title("Creditor Payment")
    st.caption("Creditor se payment receive karo: Cash / Bank / Paytm / CCMS. Entry pending rahegi; Credit Approval ke baad balance adjust hoga.")

    selected_date = str(st.date_input("Date", value=date.today(), key="credit_payment_date"))

    show_summary(selected_date)

    section = st.radio(
        "Credit Payment Section",
        ["Receive Payment", "Payment History"],
        horizontal=True,
        key="credit_payment_active_section",
    )

    if section == "Receive Payment":
        receive_payment_tab(selected_date)
    elif section == "Payment History":
        payment_history_tab(selected_date)


def show_summary(entry_date):
    s = get_approved_credit_collection_summary(entry_date)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Received", format_currency(s["total"]))
    c2.metric("Cash", format_currency(s["cash"]))
    c3.metric("Bank", format_currency(s["bank"]))
    c4.metric("Paytm", format_currency(s["paytm"]))
    c5.metric("CCMS", format_currency(s["ccms"]))


def receive_payment_tab(entry_date):
    user = get_current_user()
    parties = get_active_credit_parties()

    if not parties:
        st.warning("No active creditors found. Pehle Credit Parties me creditor create/active karo.")
        return

    labels = {
        f"{p.get('name')} | Balance: {format_currency(p.get('current_balance'))}": p
        for p in parties
    }

    with st.form("credit_payment_form"):
        selected = st.selectbox("Creditor", list(labels.keys()))
        party = labels[selected]

        amount = st.number_input("Payment Amount", min_value=0.0, step=100.0, format="%.2f")
        payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES)
        bank_name = st.text_input("Bank/Source Name", placeholder="cash ke liye blank chhod sakte hain")
        reference_id = st.text_input("Reference / UTR / Slip No.")
        note = st.text_input("Note")

        submitted = st.form_submit_button("Save Pending Payment")

    if submitted:
        row, error = create_credit_payment({
            "date": entry_date,
            "party_id": party.get("id"),
            "amount": amount,
            "payment_mode": payment_mode,
            "bank_name": bank_name,
            "reference_id": reference_id,
            "note": note,
            "created_by": user["id"],
        })

        if row:
            st.success("Creditor payment saved as pending. Credit Approval me approve karna hoga.")
            st.rerun()
        else:
            st.error(error or "Payment save failed.")

    st.info("Important: Payment approve hone ke baad hi creditor balance reduce hoga.")


def payment_history_tab(entry_date):
    status = st.selectbox("Status Filter", ["all", "pending", "approved", "hold", "rejected", "reopened"], key="credit_pay_status")
    mode = st.selectbox("Mode Filter", ["all", "cash", "bank", "paytm", "ccms"], key="credit_pay_mode")

    rows = get_credit_payments(
        entry_date=entry_date,
        status=None if status == "all" else status,
        payment_mode=None if mode == "all" else mode,
    )

    output = []
    for row in rows:
        party = row.get("credit_parties") or {}
        output.append({
            "ID": row.get("id"),
            "Date": row.get("date"),
            "Creditor": party.get("name"),
            "Amount": format_currency(row.get("amount")),
            "Mode": row.get("payment_mode"),
            "Bank/Source": row.get("bank_name"),
            "Reference": row.get("reference_id"),
            "Status": row.get("status"),
            "Note": row.get("note"),
        })

    if not output:
        st.info("No payment entries found.")
        return

    if render_export_buttons:
        render_export_buttons(output, f"creditor_payments_{entry_date}", "Creditor Payments", f"credit_pay_{entry_date}")

    st.dataframe(output, use_container_width=True, hide_index=True)
