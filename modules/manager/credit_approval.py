import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.whatsapp_db import get_whatsapp_messages, retry_whatsapp_message
from database.credit_db import (
    get_credit_transactions,
    approve_credit_transaction,
    reject_credit_transaction,
    hold_credit_transaction,
    reopen_credit_transaction,
    recalculate_all_credit_party_balances,
)


@require_role(["owner", "manager"])
def credit_approval_page():
    st.title("Credit Approval")
    st.caption("Duplicate guard enabled. Same creditor + same reference sale duplicate approve nahi hogi.")

    if st.button("Recalculate Credit Balances", use_container_width=True):
        updated = recalculate_all_credit_party_balances()
        st.success(f"Credit balances recalculated for {updated} parties.")
        st.rerun()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Pending", "Approved", "Hold/Reopened", "Rejected", "WhatsApp Logs"])

    with tab1:
        show_transactions("pending")

    with tab2:
        show_transactions("approved")

    with tab3:
        status = st.selectbox("Status", ["hold", "reopened"], key="credit_hold_reopen_status")
        show_transactions(status)

    with tab4:
        show_transactions("rejected")

    with tab5:
        show_whatsapp_logs()



def show_whatsapp_logs():
    st.subheader("Automatic WhatsApp Logs")
    st.caption("Credit sale approval par WhatsApp Cloud API se automatic send attempt hota hai. Failed messages yahan retry ho sakte hain.")

    status = st.selectbox("Status", ["all", "sent", "failed"], key="wa_auto_status")
    rows = get_whatsapp_messages(status=status)

    if not rows:
        st.info("No WhatsApp logs found.")
        return

    user = get_current_user()

    for row in rows:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Creditor", row.get("party_name") or row.get("party_id"))
            c2.metric("Amount", format_currency(row.get("amount")))
            c3.metric("Phone", row.get("phone") or "-")
            c4.metric("Status", row.get("status"))

            st.write("**Message:**")
            st.text(row.get("message") or "")

            if row.get("provider_message_id"):
                st.caption(f"Provider Message ID: {row.get('provider_message_id')}")

            if row.get("error_message"):
                st.error(row.get("error_message"))

            if row.get("status") == "failed":
                if st.button("Retry Automatic WhatsApp", key=f"wa_retry_{row.get('id')}", use_container_width=True):
                    _updated, err = retry_whatsapp_message(row.get("id"), user.get("id"))
                    if err:
                        st.error(err)
                    else:
                        st.success("WhatsApp sent.")
                        st.rerun()



def show_transactions(status):
    rows = get_credit_transactions(status=status)

    if not rows:
        st.info(f"No {status} credit transactions.")
        return

    for row in rows:
        party = row.get("credit_parties") or {}

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Txn ID", row.get("id"))
            c2.metric("Creditor", party.get("name") or row.get("party_id"))
            c3.metric("Type", row.get("type"))
            c4.metric("Amount", format_currency(row.get("amount")))

            st.write(
                f"**Date:** {row.get('date')} | "
                f"**Mode:** {row.get('payment_mode')} | "
                f"**Reference:** {row.get('reference_id')} | "
                f"**Status:** {row.get('status')}"
            )
            st.write(f"**Note:** {row.get('note')}")

            note = st.text_input("Approval Note", key=f"credit_note_{row.get('id')}")

            b1, b2, b3, b4 = st.columns(4)
            user = get_current_user()

            with b1:
                if st.button("Approve", key=f"credit_approve_{row.get('id')}", type="primary", use_container_width=True):
                    updated, error = approve_credit_transaction(row.get("id"), user.get("id"), note)
                    if updated:
                        st.success("Approved. Automatic WhatsApp send attempt completed. WhatsApp Logs tab check karein.")
                        st.rerun()
                    else:
                        st.error(error or "Approval failed.")

            with b2:
                if st.button("Hold", key=f"credit_hold_{row.get('id')}", use_container_width=True):
                    updated, error = hold_credit_transaction(row.get("id"), user.get("id"), note)
                    if updated:
                        st.warning("Put on hold.")
                        st.rerun()
                    else:
                        st.error(error or "Hold failed.")

            with b3:
                if st.button("Reject", key=f"credit_reject_{row.get('id')}", use_container_width=True):
                    updated, error = reject_credit_transaction(row.get("id"), user.get("id"), note)
                    if updated:
                        st.warning("Rejected.")
                        st.rerun()
                    else:
                        st.error(error or "Reject failed.")

            with b4:
                if st.button("Reopen", key=f"credit_reopen_{row.get('id')}", use_container_width=True):
                    updated, error = reopen_credit_transaction(row.get("id"), user.get("id"), note)
                    if updated:
                        st.info("Reopened.")
                        st.rerun()
                    else:
                        st.error(error or "Reopen failed.")
