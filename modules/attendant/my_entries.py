import streamlit as st

from utils.permissions import require_role, get_current_user
from database.sale_db import get_active_shift_entries_for_salesman
from utils.formatters import format_currency


@require_role(["salesman"])
def my_entries_page():
    user = get_current_user()
    st.title("My Entries")
    st.caption("Current active shift nozzle-wise sale entries.")

    duty, rows = get_active_shift_entries_for_salesman(user["id"])

    if not duty:
        st.error("No active duty found.")
        return

    if not rows:
        st.info("No entries found.")
        return

    output = []

    for row in rows:
        nozzle = row.get("nozzles") or {}
        status = row.get("status") or "pending"

        if status == "approved":
            status_text = "🟢 Approved"
        elif status == "rejected":
            status_text = "🔴 Rejected"
        else:
            status_text = "🟡 Pending"

        output.append({
            "Entry Time": row.get("entry_time"),
            "Nozzle": nozzle.get("nozzle_name"),
            "Fuel": row.get("fuel_type"),
            "Liters": row.get("liters"),
            "Rate": format_currency(row.get("rate")),
            "Amount": format_currency(row.get("amount")),
            "Status": status_text,
            "Rejection Reason": row.get("rejection_reason"),
        })

    st.dataframe(output, use_container_width=True, hide_index=True)
