import streamlit as st

from database.credit_db import (
    get_credit_summary,
    get_credit_transactions,
    get_active_parties,
    create_credit_payment_received,
    approve_credit_transaction,
    reject_credit_transaction,
)
from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency


@require_role(["owner", "manager"])
def credit_approval_page():
    st.title("Credit Approval & Posting")
    st.caption("Credit sale / payment received approval and creditor balance posting.")

    show_credit_summary()

    tab1, tab2, tab3 = st.tabs([
        "Pending Approval",
        "Post Payment Received",
        "Credit Ledger",
    ])

    with tab1:
        show_pending_credit_approval()

    with tab2:
        show_payment_received_form()

    with tab3:
        show_credit_ledger()


def show_credit_summary():
    summary = get_credit_summary()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Creditors", summary["active_creditors"])
    c2.metric("Outstanding", format_currency(summary["outstanding"]))
    c3.metric("Pending Credit Sales", format_currency(summary["pending_sales"]))
    c4.metric("Pending Payments", format_currency(summary["pending_payments"]))


def show_pending_credit_approval():
    user = get_current_user()
    rows = get_credit_transactions(status="pending")

    st.subheader("Pending Credit Transactions")

    if not rows:
        st.info("No pending credit transactions.")
        return

    for txn in rows:
        party = txn.get("credit_parties") or {}

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Txn ID", txn.get("id"))
            c2.metric("Creditor", party.get("name"))
            c3.metric("Type", txn.get("type"))
            c4.metric("Amount", format_currency(txn.get("amount")))

            d1, d2, d3, d4 = st.columns(4)
            d1.write(f"**Date:** {txn.get('date')}")
            d2.write(f"**Mode:** {txn.get('payment_mode')}")
            d3.write(f"**Status:** {txn.get('status')}")
            d4.write(f"**Current Bal:** {format_currency(party.get('current_balance'))}")

            if txn.get("type") == "sale":
                st.info("Approve karne par creditor balance me amount ADD hoga.")
            elif txn.get("type") == "payment_received":
                st.info("Approve karne par creditor balance se amount MINUS hoga.")

            a1, a2 = st.columns(2)

            with a1:
                if st.button("Approve & Post", key=f"approve_credit_{txn.get('id')}", type="primary", use_container_width=True):
                    updated, error = approve_credit_transaction(txn.get("id"), user["id"])
                    if updated:
                        st.success("Approved and posted to creditor balance.")
                        st.rerun()
                    else:
                        st.error(error or "Approval failed.")

            with a2:
                if st.button("Reject", key=f"reject_credit_{txn.get('id')}", use_container_width=True):
                    updated, error = reject_credit_transaction(txn.get("id"), user["id"])
                    if updated:
                        st.warning("Credit transaction rejected.")
                        st.rerun()
                    else:
                        st.error(error or "Reject failed.")


def show_payment_received_form():
    user = get_current_user()
    parties = get_active_parties()

    st.subheader("Post Creditor Payment Received")

    if not parties:
        st.info("No active creditors. Create creditor first in Credit Parties.")
        return

    labels = {
        f"{p.get('name')} | Balance: {format_currency(p.get('current_balance'))} | Limit: {format_currency(p.get('credit_limit'))}": p
        for p in parties
    }

    with st.form("credit_payment_received_form"):
        selected_label = st.selectbox("Creditor", list(labels.keys()))
        selected_party = labels[selected_label]

        amount = st.number_input("Payment Received Amount", min_value=0.0, step=100.0, format="%.2f")
        payment_mode = st.selectbox("Payment Mode", ["cash", "paytm", "ccms", "bank", "neft", "upi"])
        note = st.text_input("Note / Reference", placeholder="optional")

        submitted = st.form_submit_button("Create Pending Payment Posting")

    if submitted:
        txn, error = create_credit_payment_received(
            party_id=selected_party["id"],
            amount=amount,
            payment_mode=payment_mode,
            created_by=user["id"],
            note=note,
        )

        if txn:
            st.success("Payment received entry created. Approve it in Pending Approval to update balance.")
            st.rerun()
        else:
            st.error(error or "Payment received entry failed.")


def show_credit_ledger():
    status_filter = st.selectbox("Status", ["all", "pending", "approved", "rejected"])
    type_filter = st.selectbox("Type", ["all", "sale", "payment_received"])

    rows = get_credit_transactions(
        status=None if status_filter == "all" else status_filter,
        txn_type=None if type_filter == "all" else type_filter,
    )

    if not rows:
        st.info("No credit ledger rows found.")
        return

    output = []

    for txn in rows:
        party = txn.get("credit_parties") or {}
        output.append({
            "ID": txn.get("id"),
            "Date": txn.get("date"),
            "Creditor": party.get("name"),
            "Type": txn.get("type"),
            "Amount": format_currency(txn.get("amount")),
            "Mode": txn.get("payment_mode"),
            "Status": txn.get("status"),
            "Reference": txn.get("reference_id"),
            "Created At": txn.get("created_at"),
        })

    st.dataframe(output, use_container_width=True, hide_index=True)
