from datetime import date
import streamlit as st
from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.payment_db import (
    get_daily_money_summary,
    create_cash_deposit, get_cash_deposits,
    create_paytm_settlement, get_paytm_settlements,
    create_ccms_settlement, get_ccms_settlements,
    get_credit_collection_details,
    get_overall_money_summary,
    get_overall_money_ledger,
    get_account_ledger,
    get_account_summary,
)

@require_role(["owner", "manager"])
def money_control_page():
    st.title("Money Control")
    st.caption("Cash deposit, Paytm settlement, CCMS received tracking.")
    selected_date = str(st.date_input("Date", value=date.today(), key="money_date"))
    show_summary(selected_date)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cash Deposit", "Paytm Settlement", "CCMS Received", "Daily Report", "Overall Ledger"])
    with tab1:
        cash_tab(selected_date)
    with tab2:
        paytm_tab(selected_date)
    with tab3:
        ccms_tab(selected_date)
    with tab4:
        report_tab(selected_date)
    with tab5:
        overall_ledger_tab()

def show_summary(entry_date):
    s = get_daily_money_summary(entry_date)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sale", format_currency(s["total_sale"]))
    c2.metric("Cash In Hand", format_currency(s["cash_in_hand"]))
    c3.metric("Paytm Pending", format_currency(s["paytm_pending"]))
    c4.metric("CCMS Pending", format_currency(s["ccms_pending"]))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Credit Received", format_currency(s.get("credit_received_total", 0)))
    c6.metric("Credit Cash", format_currency(s.get("credit_cash_received", 0)))
    c7.metric("Credit Bank", format_currency(s.get("credit_bank_received", 0)))
    c8.metric("Bank Inflow", format_currency(s.get("bank_inflow_total", 0)))

def cash_tab(entry_date):
    user = get_current_user()
    s = get_daily_money_summary(entry_date)
    c1,c2,c3 = st.columns(3)
    c1.metric("Cash Sale", format_currency(s["cash_sale"]))
    c2.metric("Cash Deposited", format_currency(s["cash_deposited"]))
    c3.metric("Cash In Hand", format_currency(s["cash_in_hand"]))
    with st.form("cash_deposit_form"):
        amount = st.number_input("Deposit Amount", min_value=0.0, step=100.0, format="%.2f")
        bank_name = st.text_input("Bank Name")
        reference_no = st.text_input("Slip / Reference No.")
        note = st.text_input("Note")
        submitted = st.form_submit_button("Save Cash Deposit")
    if submitted:
        saved, error = create_cash_deposit(amount, bank_name, reference_no, user["id"], entry_date, note)
        if saved:
            st.success("Cash deposit saved.")
            st.rerun()
        else:
            st.error(error or "Cash deposit failed.")
    show_history(get_cash_deposits(entry_date), "Cash Deposit History")

def paytm_tab(entry_date):
    user = get_current_user()
    s = get_daily_money_summary(entry_date)
    c1,c2,c3 = st.columns(3)
    c1.metric("Paytm Sale", format_currency(s["paytm_sale"]))
    c2.metric("Paytm Settled", format_currency(s["paytm_settled"]))
    c3.metric("Paytm Pending", format_currency(s["paytm_pending"]))
    with st.form("paytm_settle_form"):
        amount = st.number_input("Bank Received Amount", min_value=0.0, step=100.0, format="%.2f")
        bank_name = st.text_input("Bank Name")
        reference_no = st.text_input("UTR / Reference No.")
        note = st.text_input("Note")
        submitted = st.form_submit_button("Save Paytm Settlement")
    if submitted:
        saved, error = create_paytm_settlement(amount, bank_name, reference_no, user["id"], entry_date, note)
        if saved:
            st.success("Paytm settlement saved.")
            st.rerun()
        else:
            st.error(error or "Paytm settlement failed.")
    show_history(get_paytm_settlements(entry_date), "Paytm Settlement History")

def ccms_tab(entry_date):
    user = get_current_user()
    s = get_daily_money_summary(entry_date)
    c1,c2,c3 = st.columns(3)
    c1.metric("CCMS Sale", format_currency(s["ccms_sale"]))
    c2.metric("CCMS Received", format_currency(s["ccms_received"]))
    c3.metric("CCMS Pending", format_currency(s["ccms_pending"]))
    with st.form("ccms_settle_form"):
        amount = st.number_input("CCMS Received Amount", min_value=0.0, step=100.0, format="%.2f")
        bank_name = st.text_input("Bank / Source")
        reference_no = st.text_input("Reference No.")
        note = st.text_input("Note")
        submitted = st.form_submit_button("Save CCMS Received")
    if submitted:
        saved, error = create_ccms_settlement(amount, bank_name, reference_no, user["id"], entry_date, note)
        if saved:
            st.success("CCMS received saved.")
            st.rerun()
        else:
            st.error(error or "CCMS received failed.")
    show_history(get_ccms_settlements(entry_date), "CCMS Received History")

def report_tab(entry_date):
    s = get_daily_money_summary(entry_date)
    rows = [
        {"Particular": "Total Sale", "Amount": format_currency(s["total_sale"])},
        {"Particular": "Cash Sale", "Amount": format_currency(s["cash_sale"])},
        {"Particular": "Credit Payment Received - Cash", "Amount": format_currency(s.get("credit_cash_received", 0))},
        {"Particular": "Cash Deposited", "Amount": format_currency(s["cash_deposited"])},
        {"Particular": "Cash In Hand", "Amount": format_currency(s["cash_in_hand"])},

        {"Particular": "Credit Payment Received - Bank", "Amount": format_currency(s.get("credit_bank_received", 0))},
        {"Particular": "Bank Inflow Total", "Amount": format_currency(s.get("bank_inflow_total", 0))},

        {"Particular": "Paytm Sale", "Amount": format_currency(s["paytm_sale"])},
        {"Particular": "Credit Payment Received - Paytm", "Amount": format_currency(s.get("credit_paytm_received", 0))},
        {"Particular": "Paytm Settled", "Amount": format_currency(s["paytm_settled"])},
        {"Particular": "Paytm Pending", "Amount": format_currency(s["paytm_pending"])},

        {"Particular": "CCMS Sale", "Amount": format_currency(s["ccms_sale"])},
        {"Particular": "Credit Payment Received - CCMS", "Amount": format_currency(s.get("credit_ccms_received", 0))},
        {"Particular": "CCMS Received", "Amount": format_currency(s["ccms_received"])},
        {"Particular": "CCMS Pending", "Amount": format_currency(s["ccms_pending"])},

        {"Particular": "Credit Sale", "Amount": format_currency(s["credit_sale"])},
        {"Particular": "Credit Received Total", "Amount": format_currency(s.get("credit_received_total", 0))},
        {"Particular": "Approved Settlements", "Amount": s["approved_settlements"]},
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.subheader("Creditor Payment Narration")
    credit_rows = get_credit_collection_details(entry_date, status="approved")
    if credit_rows:
        st.dataframe([
            {
                "Date": r.get("date"),
                "Mode": r.get("mode"),
                "Creditor": r.get("creditor"),
                "Amount": format_currency(r.get("amount")),
                "Bank/Source": r.get("bank_name"),
                "Reference": r.get("reference"),
                "Narration": r.get("narration"),
                "Status": r.get("status"),
            }
            for r in credit_rows
        ], use_container_width=True, hide_index=True)
    else:
        st.info("No approved creditor payment for this date.")

def show_history(rows, title):
    st.divider()
    st.subheader(title)
    if not rows:
        st.info("No entries found.")
        return
    st.dataframe([
        {
            "Date": r.get("date"),
            "Amount": format_currency(r.get("amount")),
            "Bank/Source": r.get("bank_name"),
            "Reference": r.get("reference_no"),
            "Note": r.get("note"),
            "Created At": r.get("created_at"),
        }
        for r in rows
    ], use_container_width=True, hide_index=True)


def overall_ledger_tab():
    st.subheader("Overall Cash / Bank / Paytm / CCMS Ledger")
    st.caption("Credit = inflow, Debit = outflow, Balance = Credit - Debit")

    c1, c2 = st.columns(2)
    with c1:
        from_date = str(st.date_input("From Date", value=date.today().replace(day=1), key="overall_ledger_from_date"))
    with c2:
        to_date = str(st.date_input("To Date", value=date.today(), key="overall_ledger_to_date"))

    summary = get_overall_money_summary(from_date, to_date)
    ledger = get_overall_money_ledger(from_date, to_date)

    st.markdown("### Account Summary")
    if summary:
        st.dataframe([
            {
                "Account": r.get("Account"),
                "Total Credit / Inflow": format_currency(r.get("Credit")),
                "Total Debit / Outflow": format_currency(r.get("Debit")),
                "Balance": format_currency(r.get("Balance")),
            }
            for r in summary
        ], use_container_width=True, hide_index=True)
    else:
        st.info("No ledger data found.")

    st.markdown("### Ledger Details")
    ledger_tabs = st.tabs(["All", "Cash Ledger", "Bank Ledger", "Paytm Ledger", "CCMS Ledger"])

    with ledger_tabs[0]:
        render_account_ledger_table(ledger, title="All Ledger")

    with ledger_tabs[1]:
        render_single_account_ledger("cash", from_date, to_date)

    with ledger_tabs[2]:
        render_single_account_ledger("bank", from_date, to_date)

    with ledger_tabs[3]:
        render_single_account_ledger("paytm", from_date, to_date)

    with ledger_tabs[4]:
        render_single_account_ledger("ccms", from_date, to_date)


def render_single_account_ledger(account, from_date, to_date):
    summary = get_account_summary(account, from_date, to_date)
    rows = get_account_ledger(account, from_date, to_date)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Account", str(account).upper())
    c2.metric("Credit / Inflow", format_currency(summary.get("Credit")))
    c3.metric("Debit / Outflow", format_currency(summary.get("Debit")))
    c4.metric("Balance", format_currency(summary.get("Balance")))

    render_account_ledger_table(rows, title=f"{str(account).upper()} Ledger")


def render_account_ledger_table(rows, title="Ledger"):
    st.write(f"**{title} Rows:** {len(rows or [])}")

    if not rows:
        st.info("No ledger rows found.")
        return

    st.dataframe([
        {
            "Date": r.get("Date"),
            "Account": r.get("Account"),
            "Type": r.get("Type"),
            "Reference": r.get("Reference"),
            "Particular": r.get("Particular"),
            "Credit": format_currency(r.get("Credit")),
            "Debit": format_currency(r.get("Debit")),
            "Narration": r.get("Narration"),
            "Status": r.get("Status"),
        }
        for r in rows
    ], use_container_width=True, hide_index=True)
