from datetime import date
import streamlit as st

from utils.permissions import require_role, get_current_user
from database.sale_db import get_entries_by_salesman
from utils.formatters import format_currency


@require_role(["salesman"])
def my_entries_page():
    user = get_current_user()
    st.title("My Entries")
    st.caption("Today's and selected date sale entries.")

    selected_date = st.date_input("Date", value=date.today())
    rows = get_entries_by_salesman(user["id"], str(selected_date))

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
            "Rate": row.get("rate"),
            "Amount": format_currency(row.get("amount")),
            "Payment": row.get("payment_mode"),
            "Status": status_text,
            "Rejection Reason": row.get("rejection_reason"),
        })

    st.dataframe(output, use_container_width=True, hide_index=True)
