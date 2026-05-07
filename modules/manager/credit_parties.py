import streamlit as st

from database.credit_db import (
    _vehicle_text_to_list,
    get_all_parties,
    create_party,
    update_party,
    toggle_party_active,
    get_party_ledger,
)
from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency


@require_role(["owner", "manager"])
def credit_parties_page():
    st.title("Credit Parties / Creditors")
    st.caption("Owner/Manager creditor create karega. Salesman sirf existing active creditor select karke credit amount entry karega.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Creditor List",
        "Create Creditor",
        "Edit Creditor",
        "Creditor Ledger",
    ])

    with tab1:
        show_party_list()

    with tab2:
        create_party_form()

    with tab3:
        edit_party_form()

    with tab4:
        show_party_ledger()


def show_party_list():
    parties = get_all_parties()

    if not parties:
        st.info("No creditors found. Create creditor first.")
        return

    rows = []

    for p in parties:
        rows.append({
            "ID": p.get("id"),
            "Name": p.get("name"),
            "Phone": p.get("phone"),
            "Vehicles": ", ".join(p.get("vehicle_numbers") or []),
            "Credit Limit": format_currency(p.get("credit_limit")),
            "Current Balance": format_currency(p.get("current_balance")),
            "Status": "🟢 Active" if bool(p.get("is_active")) else "🔴 Inactive",
            "Created At": p.get("created_at"),
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)

    active_count = sum(1 for p in parties if bool(p.get("is_active")))
    inactive_count = len(parties) - active_count
    outstanding = sum(float(p.get("current_balance") or 0) for p in parties)

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Creditors", active_count)
    c2.metric("Inactive Creditors", inactive_count)
    c3.metric("Total Outstanding", format_currency(outstanding))


def create_party_form():
    user = get_current_user()

    st.subheader("Create Creditor")

    with st.form("create_credit_party_form"):
        name = st.text_input("Creditor / Party Name")
        phone = st.text_input("Phone")
        vehicle_text = st.text_input("Vehicle Numbers", placeholder="UP12AB1234, UP14CD5678")
        credit_limit = st.number_input("Credit Limit", min_value=0.0, step=100.0, format="%.2f")
        opening_balance = st.number_input("Opening Balance", min_value=0.0, step=100.0, format="%.2f")
        submitted = st.form_submit_button("Create Creditor")

    if submitted:
        party, error = create_party({
            "name": name,
            "phone": phone,
            "vehicle_numbers": _vehicle_text_to_list(vehicle_text),
            "credit_limit": credit_limit,
            "current_balance": opening_balance,
            "is_active": True,
            "created_by": user["id"],
        })

        if party:
            st.success("Creditor created. Salesman ke credit dropdown me ab ye party dikhegi.")
            st.rerun()
        else:
            st.error(error or "Creditor creation failed.")


def edit_party_form():
    parties = get_all_parties()

    if not parties:
        st.info("No creditors found.")
        return

    labels = {}
    for p in parties:
        status = "Active" if bool(p.get("is_active")) else "Inactive"
        labels[f"{p.get('id')} | {p.get('name')} | {status}"] = p

    selected_label = st.selectbox("Select Creditor", list(labels.keys()))
    selected = labels[selected_label]

    st.info("Current Status: " + ("🟢 Active" if bool(selected.get("is_active")) else "🔴 Inactive"))

    with st.form("edit_credit_party_form"):
        name = st.text_input("Creditor / Party Name", value=selected.get("name") or "")
        phone = st.text_input("Phone", value=selected.get("phone") or "")
        vehicle_text = st.text_input(
            "Vehicle Numbers",
            value=", ".join(selected.get("vehicle_numbers") or []),
        )
        credit_limit = st.number_input(
            "Credit Limit",
            min_value=0.0,
            value=float(selected.get("credit_limit") or 0),
            step=100.0,
            format="%.2f",
        )
        current_balance = st.number_input(
            "Current Balance",
            min_value=0.0,
            value=float(selected.get("current_balance") or 0),
            step=100.0,
            format="%.2f",
        )
        status = st.selectbox(
            "Status",
            ["Active", "Inactive"],
            index=0 if bool(selected.get("is_active")) else 1,
        )
        submitted = st.form_submit_button("Update Creditor")

    if submitted:
        updated, error = update_party(
            selected["id"],
            {
                "name": name,
                "phone": phone,
                "vehicle_numbers": _vehicle_text_to_list(vehicle_text),
                "credit_limit": credit_limit,
                "current_balance": current_balance,
                "is_active": True if status == "Active" else False,
            },
        )

        if updated:
            st.success("Creditor updated.")
            st.rerun()
        else:
            st.error(error or "Creditor update failed.")

    st.divider()

    if st.button("Toggle Active / Inactive"):
        updated, error = toggle_party_active(selected["id"])

        if updated:
            st.success("Creditor status changed.")
            st.rerun()
        else:
            st.error(error or "Status change failed.")


def show_party_ledger():
    parties = get_all_parties()

    if not parties:
        st.info("No creditors found.")
        return

    labels = {f"{p.get('id')} | {p.get('name')}": p for p in parties}
    selected_label = st.selectbox("Select Creditor", list(labels.keys()), key="ledger_party_select")
    selected = labels[selected_label]

    rows = get_party_ledger(selected["id"])

    st.subheader(f"Ledger: {selected.get('name')}")

    if not rows:
        st.info("No ledger entries found.")
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
