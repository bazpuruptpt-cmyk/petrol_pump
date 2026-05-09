import streamlit as st

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
)


@require_role(["owner", "manager"])
def credit_parties_page():
    st.title("Credit Parties / Creditors")
    st.caption("Owner/Manager creditor create karega. Salesman existing active creditor select karega.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Creditor List",
        "Create Creditor",
        "Edit Creditor",
        "Creditor Ledger",
    ])

    with tab1:
        creditor_list_tab()

    with tab2:
        create_creditor_tab()

    with tab3:
        edit_creditor_tab()

    with tab4:
        creditor_ledger_tab()


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

    with st.form("create_creditor_form"):
        name = st.text_input("Creditor Name")
        phone = st.text_input("Phone")
        credit_limit = st.number_input("Credit Limit", min_value=0.0, step=1000.0, format="%.2f")
        vehicles_text = st.text_area("Vehicles / Notes", placeholder="One vehicle per line")
        ok = st.form_submit_button("Create Creditor")

    if ok:
        row, error = create_party(
            name=name,
            phone=phone,
            credit_limit=credit_limit,
            vehicles_text=vehicles_text,
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
    selected = st.selectbox("Select Creditor", list(labels.keys()))
    party = labels[selected]

    vehicles = party.get("vehicles")
    vehicles_text = list_to_vehicle_text(vehicles)

    with st.form("edit_creditor_form"):
        name = st.text_input("Name", value=party.get("name") or "")
        phone = st.text_input("Phone", value=party.get("phone") or "")
        credit_limit = st.number_input(
            "Credit Limit",
            min_value=0.0,
            value=float(party.get("credit_limit") or 0),
            step=1000.0,
            format="%.2f",
        )
        vehicles_input = st.text_area("Vehicles / Notes", value=vehicles_text)
        is_active = st.checkbox("Active", value=bool(party.get("is_active")))
        ok = st.form_submit_button("Update Creditor")

    if ok:
        row, error = update_party(
            party_id=party.get("id"),
            name=name,
            phone=phone,
            credit_limit=credit_limit,
            vehicles_text=vehicles_input,
            is_active=is_active,
        )
        if row:
            st.success("Creditor updated.")
            st.rerun()
        else:
            st.error(error or "Update failed.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Mark Active", use_container_width=True):
            row, error = toggle_party_active(party.get("id"), True)
            if row:
                st.success("Marked active.")
                st.rerun()
            else:
                st.error(error or "Action failed.")

    with c2:
        if st.button("Mark Inactive", use_container_width=True):
            row, error = toggle_party_active(party.get("id"), False)
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
    selected = st.selectbox("Select Creditor", list(labels.keys()))
    party = labels[selected]

    st.subheader(f"Ledger: {party.get('name')}")

    rows = get_credit_transactions_by_party(party.get("id"))

    if not rows:
        st.info("No ledger entries.")
        return

    output = []
    for r in rows:
        output.append({
            "Date": r.get("date"),
            "Type": r.get("type"),
            "Amount": format_currency(r.get("amount")),
            "Payment Mode": r.get("payment_mode"),
            "Status": r.get("status"),
            "Reference ID": r.get("reference_id"),
            "Created At": r.get("created_at"),
        })

    st.dataframe(output, use_container_width=True, hide_index=True)
