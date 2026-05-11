from datetime import date
import streamlit as st

from utils.permissions import require_role
from utils.formatters import format_currency
from database.pump_summary_db import get_pump_daily_summary


def _fmt_money(value):
    return format_currency(value)


@require_role(["owner", "manager"])
def pump_summary_page():
    st.title("Pump Daily Summary")
    st.caption("Complete daily pump summary: nozzle-wise sale, cash/paytm/ccms/credit totals, credit details, and expenses.")

    selected_date = str(st.date_input("Date", value=date.today(), key="pump_summary_date"))

    data = get_pump_daily_summary(selected_date)
    totals = data["totals"]

    st.subheader("Daily Totals")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sale", _fmt_money(totals["total_sale"]))
    c2.metric("Total Liters", f"{totals['total_liters']:.2f}")
    c3.metric("Settlements", totals["settlement_count"])
    c4.metric("Daily Expense", _fmt_money(totals["expense_total"]))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Cash Total", _fmt_money(totals["cash_total"]))
    c6.metric("Paytm Total", _fmt_money(totals["paytm_total"]))
    c7.metric("CCMS Total", _fmt_money(totals["ccms_total"]))
    c8.metric("Credit Total", _fmt_money(totals["credit_total"]))

    st.divider()

    st.subheader("Fuel Summary")
    if totals["fuel_rows"]:
        st.dataframe(
            [
                {
                    "Fuel": r["Fuel"],
                    "Liters": f"{r['Liters']:.2f}",
                    "Amount": _fmt_money(r["Amount"]),
                }
                for r in totals["fuel_rows"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No fuel sale found for selected date.")

    st.divider()

    tabs = st.tabs([
        "Nozzle-wise Sale",
        "Salesman-wise Sale",
        "Credit Sale Details",
        "Expense Details",
        "Final Summary",
    ])

    with tabs[0]:
        st.subheader("Nozzle-wise Sale")
        rows = data["nozzle_wise"]
        if rows:
            st.dataframe(
                [
                    {
                        "Date": r.get("Date"),
                        "Salesman": r.get("Salesman"),
                        "Nozzle": r.get("Nozzle"),
                        "Fuel": r.get("Fuel"),
                        "Opening": r.get("Opening"),
                        "Closing": r.get("Closing"),
                        "Sale Liters": r.get("Sale Liters"),
                        "Rate": _fmt_money(r.get("Rate")),
                        "Sale Amount": _fmt_money(r.get("Sale Amount")),
                    }
                    for r in rows
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No nozzle-wise approved sale found.")

    with tabs[1]:
        st.subheader("Salesman-wise Sale")
        rows = data["salesman_wise"]
        if rows:
            st.dataframe(
                [
                    {
                        "Salesman": r.get("Salesman"),
                        "Shift ID": r.get("Shift ID"),
                        "Total Liters": r.get("Total Liters"),
                        "Total Sale": _fmt_money(r.get("Total Sale")),
                        "Cash": _fmt_money(r.get("Cash")),
                        "Paytm": _fmt_money(r.get("Paytm")),
                        "CCMS": _fmt_money(r.get("CCMS")),
                        "Credit": _fmt_money(r.get("Credit")),
                        "Difference": _fmt_money(r.get("Difference")),
                        "Status": r.get("Status"),
                    }
                    for r in rows
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No salesman-wise approved sale found.")

    with tabs[2]:
        st.subheader("Credit Sale Details")
        rows = data["credit_details"]
        if rows:
            st.dataframe(
                [
                    {
                        "Creditor": r.get("Creditor"),
                        "Amount": _fmt_money(r.get("Amount")),
                        "Vehicle": r.get("Vehicle"),
                        "Comment": r.get("Comment"),
                        "Salesman": r.get("Salesman"),
                        "Settlement ID": r.get("Settlement ID"),
                        "Status": r.get("Status"),
                    }
                    for r in rows
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No credit sale found.")

    with tabs[3]:
        st.subheader("Daily Expense Details")
        rows = data["expense_details"]
        if rows:
            st.dataframe(
                [
                    {
                        "Category": r.get("Category"),
                        "Payment Mode": r.get("Payment Mode"),
                        "Amount": _fmt_money(r.get("Amount")),
                        "Description": r.get("Description"),
                        "Status": r.get("Status"),
                        "Reference": r.get("Reference"),
                    }
                    for r in rows
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No expense found.")

    with tabs[4]:
        st.subheader("Final Pump Summary")
        final_rows = [
            {"Particular": "Total Sale", "Amount": _fmt_money(totals["total_sale"])},
            {"Particular": "Total Liters", "Amount": f"{totals['total_liters']:.2f}"},
            {"Particular": "Cash Total", "Amount": _fmt_money(totals["cash_total"])},
            {"Particular": "Paytm Total", "Amount": _fmt_money(totals["paytm_total"])},
            {"Particular": "CCMS Total", "Amount": _fmt_money(totals["ccms_total"])},
            {"Particular": "Credit Total", "Amount": _fmt_money(totals["credit_total"])},
            {"Particular": "Daily Expense Total", "Amount": _fmt_money(totals["expense_total"])},
            {"Particular": "Cash Expense", "Amount": _fmt_money(totals["cash_expense"])},
            {"Particular": "Bank Expense", "Amount": _fmt_money(totals["bank_expense"])},
        ]
        st.dataframe(final_rows, use_container_width=True, hide_index=True)
