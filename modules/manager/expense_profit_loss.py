from datetime import date
import streamlit as st
from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.expense_db import (
    EXPENSE_CATEGORIES,
    PAYMENT_MODES,
    create_expense,
    get_expenses,
    approve_expense,
    reject_expense,
    hold_expense,
    reopen_expense,
    get_expense_category_report,
    get_expense_payment_mode_report,
    get_cash_bank_expense_summary,
    get_profit_loss_report,
    get_profit_loss_rows,
)

@require_role(["owner", "manager"])
def expense_profit_loss_page():
    st.title("Expense & Profit/Loss")
    st.caption("Expense entry sirf Cash aur Bank mode me.")

    entry_date = str(st.date_input("Date", value=date.today(), key="expense_date"))

    show_summary(entry_date)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Expense Entry",
        "Expense Approval",
        "Category Report",
        "Cash/Bank Outflow",
        "Profit/Loss",
    ])

    with tab1:
        expense_entry_tab(entry_date)
    with tab2:
        expense_approval_tab()
    with tab3:
        expense_report_tab(entry_date)
    with tab4:
        cash_bank_outflow_tab(entry_date)
    with tab5:
        profit_loss_tab(entry_date)

def show_summary(entry_date):
    r = get_profit_loss_report(entry_date)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gross Sale", format_currency(r["gross_sale"]))
    c2.metric("Purchase Cost", format_currency(r["purchase_cost"]))
    c3.metric("Total Expense", format_currency(r["total_expense"]))
    c4.metric("Net Profit/Loss", format_currency(r["net_profit"]))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Cash Expense", format_currency(r["cash_expense"]))
    c6.metric("Bank Expense", format_currency(r["bank_expense"]))
    c7.metric("Gross Margin", format_currency(r["gross_margin"]))
    c8.metric("Pending Expenses", r["pending_expenses"])

def expense_entry_tab(entry_date):
    user = get_current_user()

    st.subheader("Expense Entry")
    st.caption("Payment mode only: Cash / Bank")

    with st.form("expense_entry_form"):
        category = st.selectbox("Category", EXPENSE_CATEGORIES)
        description = st.text_input("Description")
        amount = st.number_input("Amount", min_value=0.0, step=100.0, format="%.2f")
        payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES)
        bank_name = st.text_input("Bank Name", placeholder="cash ke liye blank chhod sakte hain")
        reference_no = st.text_input("Reference No.")
        ok = st.form_submit_button("Save Pending Expense")

    if ok:
        row, err = create_expense({
            "date": entry_date,
            "category": category,
            "description": description,
            "amount": amount,
            "payment_mode": payment_mode,
            "bank_name": bank_name,
            "reference_no": reference_no,
            "created_by": user["id"],
        })

        if row:
            st.success("Expense saved as pending.")
            st.rerun()
        else:
            st.error(err or "Expense save failed.")

    show_expense_table(get_expenses(entry_date=entry_date), "Expense Entries")

def expense_approval_tab():
    status = st.selectbox("Status", ["pending", "hold", "reopened", "approved", "rejected"], key="expense_status")
    rows = get_expenses(status=status)

    if not rows:
        st.info("No expenses found.")
        return

    for r in rows:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ID", r.get("id"))
            c2.metric("Category", r.get("category"))
            c3.metric("Amount", format_currency(r.get("amount")))
            c4.metric("Mode", r.get("payment_mode"))

            st.write(f"**Date:** {r.get('date')} | **Bank:** {r.get('bank_name')} | **Ref:** {r.get('reference_no')} | **Status:** {r.get('status')}")
            st.write(f"**Description:** {r.get('description')}")

            note = st.text_input("Approval Note", key=f"expense_note_{r.get('id')}")
            render_buttons(r.get("id"), note)

def render_buttons(expense_id, note):
    user = get_current_user()
    b1, b2, b3, b4 = st.columns(4)

    with b1:
        if st.button("Approve", key=f"ex_app_{expense_id}", type="primary", use_container_width=True):
            row, err = approve_expense(expense_id, user["id"], note)
            if row:
                st.success("Approved.")
                st.rerun()
            else:
                st.error(err or "Approval failed.")

    with b2:
        if st.button("Hold", key=f"ex_hold_{expense_id}", use_container_width=True):
            row, err = hold_expense(expense_id, user["id"], note)
            if row:
                st.warning("Hold.")
                st.rerun()
            else:
                st.error(err or "Hold failed.")

    with b3:
        if st.button("Reject", key=f"ex_rej_{expense_id}", use_container_width=True):
            row, err = reject_expense(expense_id, user["id"], note)
            if row:
                st.warning("Rejected.")
                st.rerun()
            else:
                st.error(err or "Reject failed.")

    with b4:
        if st.button("Reopen", key=f"ex_reop_{expense_id}", use_container_width=True):
            row, err = reopen_expense(expense_id, user["id"], note)
            if row:
                st.info("Reopened.")
                st.rerun()
            else:
                st.error(err or "Reopen failed.")

def expense_report_tab(entry_date):
    st.subheader("Category-wise Expense")
    rows = [{"Category": r["Category"], "Amount": format_currency(r["Amount"])} for r in get_expense_category_report(entry_date)]
    st.dataframe(rows, use_container_width=True, hide_index=True)

def cash_bank_outflow_tab(entry_date):
    st.subheader("Cash / Bank Outflow")
    s = get_cash_bank_expense_summary(entry_date)

    c1, c2, c3 = st.columns(3)
    c1.metric("Cash Expense", format_currency(s["cash_expense"]))
    c2.metric("Bank Expense", format_currency(s["bank_expense"]))
    c3.metric("Total Expense", format_currency(s["total_expense"]))

    rows = [{"Payment Mode": r["Payment Mode"], "Amount": format_currency(r["Amount"])} for r in get_expense_payment_mode_report(entry_date)]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Approved Cash Expenses")
    show_expense_table(get_expenses(entry_date=entry_date, status="approved", payment_mode="cash"), "Cash Expense Ledger")

    st.subheader("Approved Bank Expenses")
    show_expense_table(get_expenses(entry_date=entry_date, status="approved", payment_mode="bank"), "Bank Expense Ledger")

def profit_loss_tab(entry_date):
    st.subheader("Profit / Loss")
    st.caption("Net Profit = Gross Sale - Approved Purchase Cost - Approved Cash/Bank Expenses")

    rows = [{"Particular": r["Particular"], "Amount": format_currency(r["Amount"])} for r in get_profit_loss_rows(entry_date)]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    report = get_profit_loss_report(entry_date)
    if report["net_profit"] >= 0:
        st.success(f"Net Profit: {format_currency(report['net_profit'])}")
    else:
        st.error(f"Net Loss: {format_currency(abs(report['net_profit']))}")

def show_expense_table(rows, title):
    st.divider()
    st.subheader(title)

    if not rows:
        st.info("No expense entries found.")
        return

    out = []
    for r in rows:
        out.append({
            "ID": r.get("id"),
            "Date": r.get("date"),
            "Category": r.get("category"),
            "Description": r.get("description"),
            "Amount": format_currency(r.get("amount")),
            "Mode": r.get("payment_mode"),
            "Bank": r.get("bank_name"),
            "Reference": r.get("reference_no"),
            "Status": r.get("status"),
        })
    st.dataframe(out, use_container_width=True, hide_index=True)
