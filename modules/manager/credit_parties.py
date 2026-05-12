import streamlit as st
import re
from urllib.parse import quote

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.credit_db import (
    vehicle_text_to_list,
    list_to_vehicle_text,
    get_all_parties,
    create_party,
    update_party,
    toggle_party_active,
    get_credit_transactions_by_party,
    get_correctable_credit_transactions,
    create_creditor_transfer_correction,
    get_creditor_transfer_corrections,
)


@require_role(["owner", "manager"])
def credit_parties_page():
    st.title("Credit Parties / Creditors")
    st.caption("Owner/Manager creditor create karega. Salesman existing active creditor select karega.")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Creditor List",
        "Create Creditor",
        "Edit Creditor",
        "Creditor Ledger",
        "Correction",
    ])

    with tab1:
        creditor_list_tab()

    with tab2:
        create_creditor_tab()

    with tab3:
        edit_creditor_tab()

    with tab4:
        creditor_ledger_tab()

    with tab5:
        creditor_correction_tab()


def _safe_float(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _normalise_phone_for_whatsapp(phone):
    digits = re.sub(r"\D", "", str(phone or ""))

    if not digits:
        return ""

    # India default: 10 digit mobile -> 91XXXXXXXXXX
    if len(digits) == 10:
        return "91" + digits

    # Remove leading 0 from domestic numbers, then add 91 if 10 digits remain.
    if digits.startswith("0") and len(digits) == 11:
        return "91" + digits[1:]

    return digits


def _credit_txn_label(txn_type):
    mapping = {
        "sale": "Fuel Credit",
        "cash_given": "Cash Given",
        "payment_received": "Payment Received",
        "transfer_out": "Wrong Creditor Transfer Out",
        "transfer_in": "Wrong Creditor Transfer In",
    }
    return mapping.get(txn_type or "", txn_type or "-")


def _build_creditor_whatsapp_message(party, txn):
    name = party.get("name") or "Creditor"
    txn_type = _credit_txn_label(txn.get("type"))
    amount = format_currency(txn.get("amount"))
    entry_date = txn.get("date") or "-"
    ref = txn.get("reference_id") or "-"
    payment_mode = txn.get("payment_mode") or "-"
    narration = txn.get("note") or txn.get("approval_note") or "-"
    balance = format_currency(party.get("current_balance"))

    lines = [
        "Petrol Pump Ledger Update",
        "",
        f"Creditor: {name}",
        f"Date: {entry_date}",
        f"Entry Type: {txn_type}",
        f"Amount: {amount}",
        f"Payment Mode: {payment_mode}",
        f"Reference: {ref}",
        f"Comment: {narration}",
        "",
        f"Current Balance: {balance}",
        "",
        "Agar entry me koi correction ho, manager se contact karein.",
    ]

    return "\n".join(lines)


def render_creditor_whatsapp_button(party, txn, key_prefix):
    phone = _normalise_phone_for_whatsapp(party.get("phone"))

    if not phone:
        st.warning("Is creditor ka phone number missing hai. Edit Creditor me phone add karo.")
        return

    message = _build_creditor_whatsapp_message(party, txn)
    url = f"https://wa.me/{phone}?text={quote(message)}"

    st.text_area(
        "WhatsApp Message Preview",
        value=message,
        height=220,
        key=f"wa_preview_{key_prefix}",
    )

    st.link_button(
        "Open WhatsApp Message",
        url,
        use_container_width=True,
    )


def creditor_list_tab():
    rows = get_all_parties()

    if not rows:
        st.info("No creditors found.")
        return

    output = []
    for r in rows:
        output.append({
            "ID": r.get("id"),
            "Name": r.get("name"),
            "Phone": r.get("phone"),
            "Credit Limit": format_currency(r.get("credit_limit")),
            "Current Balance": format_currency(r.get("current_balance")),
            "Active": "Yes" if r.get("is_active") else "No",
        })

    st.dataframe(output, use_container_width=True, hide_index=True)


def create_creditor_tab():
    user = get_current_user()

    with st.form("create_creditor_form", clear_on_submit=False):
        name = st.text_input("Creditor Name", key="credit_create_name")
        phone = st.text_input("Phone", key="credit_create_phone")
        credit_limit = st.number_input(
            "Credit Limit",
            min_value=0.0,
            step=1000.0,
            format="%.2f",
            key="credit_create_limit",
        )
        vehicles_text = st.text_area(
            "Vehicles / Notes",
            placeholder="One vehicle per line",
            key="credit_create_vehicles",
        )
        ok = st.form_submit_button("Create Creditor")

    if ok:
        clean_name = (name or "").strip()

        if not clean_name:
            st.error("Creditor name required.")
            return

        row, error = create_party(
            name=clean_name,
            phone=(phone or "").strip(),
            credit_limit=credit_limit,
            vehicles_text=vehicles_text or "",
            created_by=user.get("id"),
        )

        if row:
            st.success("Creditor created.")
            st.rerun()
        else:
            st.error(error or "Create failed.")


def edit_creditor_tab():
    rows = get_all_parties()

    if not rows:
        st.info("No creditors found.")
        return

    labels = {f"{r.get('id')} | {r.get('name')}": r for r in rows}

    selected = st.selectbox(
        "Select Creditor",
        list(labels.keys()),
        key="credit_edit_select_creditor",
    )

    party = labels[selected]
    party_id = party.get("id")

    vehicles = party.get("vehicles")
    vehicles_text = list_to_vehicle_text(vehicles)

    with st.form(f"edit_creditor_form_{party_id}", clear_on_submit=False):
        name = st.text_input(
            "Name",
            value=party.get("name") or "",
            key=f"credit_edit_name_{party_id}",
        )
        phone = st.text_input(
            "Phone",
            value=party.get("phone") or "",
            key=f"credit_edit_phone_{party_id}",
        )
        credit_limit = st.number_input(
            "Credit Limit",
            min_value=0.0,
            value=_safe_float(party.get("credit_limit")),
            step=1000.0,
            format="%.2f",
            key=f"credit_edit_limit_{party_id}",
        )
        vehicles_input = st.text_area(
            "Vehicles / Notes",
            value=vehicles_text,
            key=f"credit_edit_vehicles_{party_id}",
        )
        is_active = st.checkbox(
            "Active",
            value=bool(party.get("is_active")),
            key=f"credit_edit_active_{party_id}",
        )
        ok = st.form_submit_button("Update Creditor")

    if ok:
        clean_name = (name or "").strip()

        if not clean_name:
            st.error("Creditor name required.")
            return

        row, error = update_party(
            party_id=party_id,
            name=clean_name,
            phone=(phone or "").strip(),
            credit_limit=credit_limit,
            vehicles_text=vehicles_input or "",
            is_active=is_active,
        )

        if row:
            st.success("Creditor updated.")
            st.rerun()
        else:
            st.error(error or "Update failed.")

    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "Mark Active",
            use_container_width=True,
            key=f"credit_mark_active_{party_id}",
        ):
            row, error = toggle_party_active(party_id, True)

            if row:
                st.success("Marked active.")
                st.rerun()
            else:
                st.error(error or "Action failed.")

    with c2:
        if st.button(
            "Mark Inactive",
            use_container_width=True,
            key=f"credit_mark_inactive_{party_id}",
        ):
            row, error = toggle_party_active(party_id, False)

            if row:
                st.warning("Marked inactive.")
                st.rerun()
            else:
                st.error(error or "Action failed.")


def creditor_ledger_tab():
    parties = get_all_parties()

    if not parties:
        st.info("No creditors found.")
        return

    labels = {f"{p.get('id')} | {p.get('name')}": p for p in parties}

    selected = st.selectbox(
        "Select Creditor",
        list(labels.keys()),
        key="credit_ledger_select_creditor",
    )

    party = labels[selected]

    st.subheader(f"Ledger: {party.get('name')}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Creditor", party.get("name") or "-")
    c2.metric("Phone", party.get("phone") or "-")
    c3.metric("Current Balance", format_currency(party.get("current_balance")))

    rows = get_credit_transactions_by_party(party.get("id"))

    if not rows:
        st.info("No ledger entries.")
        return

    output = []
    for r in rows:
        output.append({
            "ID": r.get("id"),
            "Date": r.get("date"),
            "Type": _credit_txn_label(r.get("type")),
            "Amount": format_currency(r.get("amount")),
            "Payment Mode": r.get("payment_mode"),
            "Status": r.get("status"),
            "Reference ID": r.get("reference_id"),
            "Comment": r.get("note") or r.get("approval_note") or "",
            "Created At": r.get("created_at"),
        })

    st.dataframe(output, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Manual WhatsApp Message")

    st.caption(
        "Automatic message nahi bheja jayega. Button click karne par WhatsApp pre-filled message open hoga."
    )

    txn_options = []
    for r in rows:
        label = (
            f"Txn {r.get('id')} | {_credit_txn_label(r.get('type'))} | "
            f"{format_currency(r.get('amount'))} | {r.get('date') or '-'} | Ref {r.get('reference_id') or '-'}"
        )
        txn_options.append((label, r))

    selected_txn = st.selectbox(
        "Select ledger entry for WhatsApp message",
        txn_options,
        format_func=lambda x: x[0],
        key=f"wa_txn_select_{party.get('id')}",
    )

    render_creditor_whatsapp_button(
        party=party,
        txn=selected_txn[1],
        key_prefix=f"{party.get('id')}_{selected_txn[1].get('id')}",
    )


def creditor_correction_tab():
    st.subheader("Wrong Creditor Correction")
    st.caption(
        "Only creditor-to-creditor transfer. Cash / Paytm / CCMS / Sale total untouched. "
        "Approved original entry delete/edit nahi hogi."
    )

    user = get_current_user()
    parties = get_all_parties()
    correctable_rows = get_correctable_credit_transactions(limit=200)

    if not parties:
        st.info("No creditors found.")
        return

    if not correctable_rows:
        st.info("No approved fuel credit / cash given rows found for correction.")
        return

    def _sid(value):
        return str(value or "").strip()

    party_by_id = {_sid(p.get("id")): p for p in parties}

    txn_options = []
    for r in correctable_rows:
        party_id = _sid(r.get("party_id"))
        party = r.get("credit_parties") or party_by_id.get(party_id) or {}
        txn_type = "Fuel Credit" if r.get("type") == "sale" else "Cash Given"

        label = (
            f"Txn {r.get('id')} | {txn_type} | "
            f"{party.get('name') or party_id} | "
            f"{format_currency(r.get('amount'))} | Ref {r.get('reference_id') or '-'}"
        )
        txn_options.append((label, r))

    selected_pair = st.selectbox(
        "Original wrong creditor ledger entry",
        txn_options,
        format_func=lambda x: x[0],
        key="creditor_correction_original_txn_select_v2",
    )

    original = selected_pair[1]
    wrong_party_id = _sid(original.get("party_id"))
    wrong_party = original.get("credit_parties") or party_by_id.get(wrong_party_id) or {}
    original_type = "Fuel Credit" if original.get("type") == "sale" else "Cash Given"
    max_amount = _safe_float(original.get("amount"))

    st.info(
        f"Wrong Creditor: {wrong_party.get('name') or wrong_party_id} "
        f"(ID: {wrong_party_id}) | "
        f"Type: {original_type} | "
        f"Amount: {format_currency(max_amount)} | "
        f"Txn ID: {original.get('id')} | Ref: {original.get('reference_id') or '-'}"
    )

    correct_parties = [
        p for p in parties
        if _sid(p.get("id")) != wrong_party_id
    ]

    if not correct_parties:
        st.warning("No different creditor available.")
        return

    def _party_label(p):
        active_label = "Active" if p.get("is_active") is not False else "Inactive"
        return (
            f"{p.get('name')} | ID: {p.get('id')} | {active_label} | "
            f"Balance: {format_currency(p.get('current_balance'))}"
        )

    with st.form(f"creditor_wrong_account_correction_form_{original.get('id')}", clear_on_submit=False):
        correct_party = st.selectbox(
            "Correct creditor",
            correct_parties,
            format_func=_party_label,
            key=f"creditor_correction_correct_party_{original.get('id')}_v2",
        )

        if _sid(correct_party.get("id")) == wrong_party_id:
            st.error("Correct creditor wrong creditor jaisa nahi ho sakta.")
            submitted = False
        else:
            amount = st.number_input(
                "Correction amount",
                min_value=0.0,
                max_value=max_amount,
                value=max_amount,
                step=1.0,
                format="%.2f",
                key=f"creditor_correction_amount_{original.get('id')}_v2",
            )

            reason = st.text_area(
                "Reason / Narration",
                placeholder="Example: Wrong creditor selected in settlement. Actual party is ...",
                key=f"creditor_correction_reason_{original.get('id')}_v2",
            )

            submitted = st.form_submit_button("Submit Creditor Transfer Correction")

    if submitted:
        result, error = create_creditor_transfer_correction(
            original_txn_id=original.get("id"),
            correct_party_id=correct_party.get("id"),
            amount=amount,
            reason=reason,
            created_by=str(user.get("id") or ""),
        )

        if result:
            st.success("Creditor correction posted. Wrong creditor balance reduced and correct creditor balance increased.")
            st.json(result)
            st.rerun()
        else:
            st.error(error or "Correction failed.")

    st.divider()
    st.subheader("Recent Creditor Corrections")
    rows = get_creditor_transfer_corrections(limit=100)

    if not rows:
        st.info("No correction rows yet.")
        return

    output = []
    for row in rows:
        party_id = _sid(row.get("party_id"))
        party = row.get("credit_parties") or party_by_id.get(party_id) or {}
        output.append({
            "ID": row.get("id"),
            "Date": row.get("date"),
            "Creditor": f"{party.get('name') or party_id} (ID: {party_id})",
            "Type": "Transfer Out" if row.get("type") == "transfer_out" else "Transfer In",
            "Amount": format_currency(row.get("amount")),
            "Reference": row.get("reference_id"),
            "Status": row.get("status"),
            "Narration": row.get("note"),
            "Created At": row.get("created_at"),
        })

    st.dataframe(output, use_container_width=True, hide_index=True)
