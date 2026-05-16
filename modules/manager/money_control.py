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
    get_bank_account_ledger,
    get_bank_account_summary,
    get_canara_bank_summary,
)
from database.stock_db import (
    create_oil_company_payment,
    get_oil_company_ledger,
    get_oil_company_summary,
)


CANARA_CASH_DEPOSIT_ACCOUNTS = [
    "Canara Bank OD Account",
    "Canara Bank CC Account",
]


def _f(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _cash_deposit_account_summary(rows):
    summary = {name: 0.0 for name in CANARA_CASH_DEPOSIT_ACCOUNTS}
    other = 0.0

    for r in rows or []:
        bank_name = (r.get("bank_name") or "").strip()
        amount = _f(r.get("amount"))

        if bank_name in summary:
            summary[bank_name] += amount
        else:
            other += amount

    summary["Other / Manual Bank"] = other
    return {k: round(v, 2) for k, v in summary.items()}


def _money_balance_snapshot(entry_date=None):
    """
    Ledger balance up to selected date:
    Balance = Credit - Debit
    """
    cash = get_account_summary("cash", None, entry_date)
    paytm = get_account_summary("paytm", None, entry_date)
    ccms = get_account_summary("ccms", None, entry_date)
    bank = get_account_summary("bank", None, entry_date)
    od = get_bank_account_summary("Canara Bank OD Account", None, entry_date)
    cc = get_bank_account_summary("Canara Bank CC Account", None, entry_date)

    return {
        "cash": _f(cash.get("Balance")),
        "paytm": _f(paytm.get("Balance")),
        "ccms": _f(ccms.get("Balance")),
        "bank": _f(bank.get("Balance")),
        "od": _f(od.get("Balance")),
        "cc": _f(cc.get("Balance")),
    }


def render_money_balance_snapshot(entry_date, title="Ledger Balance Snapshot"):
    balances = _money_balance_snapshot(entry_date)

    st.markdown(f"### {title}")

    b1, b2, b3 = st.columns(3)
    b1.metric("Cash Ledger Balance", format_currency(balances["cash"]))
    b2.metric("Paytm Ledger Balance", format_currency(balances["paytm"]))
    b3.metric("CCMS Ledger Balance", format_currency(balances["ccms"]))

    b4, b5, b6 = st.columns(3)
    b4.metric("Total Bank Ledger Balance", format_currency(balances["bank"]))
    b5.metric("Canara OD Balance", format_currency(balances["od"]))
    b6.metric("Canara CC Balance", format_currency(balances["cc"]))

    return balances


def render_selected_account_balance(account_name, entry_date):
    if account_name in ["cash", "paytm", "ccms", "bank"]:
        summary = get_account_summary(account_name, None, entry_date)
        return _f(summary.get("Balance"))

    summary = get_bank_account_summary(account_name, None, entry_date)
    return _f(summary.get("Balance"))


@require_role(["owner", "manager"])
def money_control_page():
    st.title("Money Control")
    st.caption("Cash deposit, Paytm settlement, CCMS received tracking, Canara OD/CC ledger, Oil Company Ledger.")
    selected_date = str(st.date_input("Date", value=date.today(), key="money_date"))
    show_summary(selected_date)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Cash Deposit",
        "Canara OD Account",
        "Canara CC Account",
        "Paytm Settlement",
        "CCMS Received",
        "Daily Report",
        "Overall Ledger",
        "Oil Company Ledger",
    ])

    with tab1:
        cash_tab(selected_date)
    with tab2:
        bank_account_cash_deposit_tab("Canara Bank OD Account", selected_date)
    with tab3:
        bank_account_cash_deposit_tab("Canara Bank CC Account", selected_date)
    with tab4:
        paytm_tab(selected_date)
    with tab5:
        ccms_tab(selected_date)
    with tab6:
        report_tab(selected_date)
    with tab7:
        overall_ledger_tab()
    with tab8:
        oil_company_ledger_tab()

def show_summary(entry_date):
    s = get_daily_money_summary(entry_date)

    st.markdown("### Daily Position")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sale", format_currency(s["total_sale"]))
    c2.metric("Cash In Hand Today", format_currency(s["cash_in_hand"]))
    c3.metric("Paytm Pending Today", format_currency(s["paytm_pending"]))
    c4.metric("CCMS Pending Today", format_currency(s["ccms_pending"]))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Credit Received", format_currency(s.get("credit_received_total", 0)))
    c6.metric("Credit Cash", format_currency(s.get("credit_cash_received", 0)))
    c7.metric("Credit Bank", format_currency(s.get("credit_bank_received", 0)))
    c8.metric("Bank Inflow Today", format_currency(s.get("bank_inflow_total", 0)))

    render_money_balance_snapshot(entry_date, title="Current Ledger Balances")



def _cash_deposits_for_bank(rows, bank_name):
    bank_name = str(bank_name or "").strip()
    return [
        r for r in (rows or [])
        if str(r.get("bank_name") or "").strip() == bank_name
    ]


def bank_account_cash_deposit_tab(bank_name, entry_date):
    user = get_current_user()
    s = get_daily_money_summary(entry_date)

    cash_ledger_balance = render_selected_account_balance("cash", entry_date)
    deposits_today = get_cash_deposits(entry_date)
    bank_deposits_today = _cash_deposits_for_bank(deposits_today, bank_name)

    bank_summary_today = get_bank_account_summary(bank_name, entry_date, entry_date)
    bank_summary_total = get_bank_account_summary(bank_name, None, entry_date)

    st.subheader(bank_name)
    st.caption("Is account ke liye cash deposit/transfer yahin se save hoga aur same amount is bank ledger me credit hoga.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash Ledger Balance", format_currency(cash_ledger_balance))
    c2.metric("Today Deposit", format_currency(sum(_f(r.get("amount")) for r in bank_deposits_today)))
    c3.metric("Today Bank Credit", format_currency(bank_summary_today.get("Credit")))
    c4.metric("Bank Ledger Balance", format_currency(bank_summary_total.get("Balance")))

    with st.form(f"cash_transfer_form_{bank_name.replace(' ', '_').lower()}"):
        st.text_input("Bank Account", value=bank_name, disabled=True)

        max_amount = max(0.0, cash_ledger_balance)
        amount = st.number_input(
            "Cash Transfer Amount",
            min_value=0.0,
            max_value=max_amount if max_amount > 0 else None,
            step=100.0,
            format="%.2f",
            key=f"cash_transfer_amount_{bank_name}",
        )

        remaining_cash = round(cash_ledger_balance - _f(amount), 2)
        bank_after_transfer = round(_f(bank_summary_total.get("Balance")) + _f(amount), 2)

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Cash Before", format_currency(cash_ledger_balance))
        p2.metric("Transfer Amount", format_currency(amount))
        p3.metric("Cash After", format_currency(remaining_cash))
        p4.metric("Bank After", format_currency(bank_after_transfer))

        reference_no = st.text_input("Slip / Reference No.", key=f"cash_ref_{bank_name}")
        note = st.text_input("Note", value=f"Cash transfer to {bank_name}", key=f"cash_note_{bank_name}")

        submitted = st.form_submit_button(f"Save Cash Transfer to {bank_name}")

    if submitted:
        if _f(amount) <= 0:
            st.error("Transfer amount greater than 0 hona chahiye.")
            return

        if _f(amount) > cash_ledger_balance:
            st.error("Transfer amount cash ledger balance se zyada nahi ho sakta.")
            return

        saved, error = create_cash_deposit(
            amount=amount,
            bank_name=bank_name,
            reference_no=reference_no,
            deposited_by=user["id"],
            deposit_date=entry_date,
            note=note,
        )

        if saved:
            st.success(f"Cash transfer saved: {format_currency(amount)} → {bank_name}")
            st.rerun()
        else:
            st.error(error or "Cash transfer failed.")

    st.divider()
    st.subheader(f"{bank_name} Deposit History Today")

    if bank_deposits_today:
        st.dataframe([
            {
                "Date": r.get("date"),
                "Amount": format_currency(r.get("amount")),
                "Bank": r.get("bank_name"),
                "Reference": r.get("reference_no"),
                "Note": r.get("note"),
                "Created At": r.get("created_at"),
            }
            for r in bank_deposits_today
        ], use_container_width=True, hide_index=True)
    else:
        st.info("Aaj is account me cash transfer nahi hai.")

    st.divider()
    st.subheader(f"{bank_name} Ledger")

    ledger_rows = get_bank_account_ledger(bank_name, None, entry_date)

    if ledger_rows:
        render_account_ledger_table(ledger_rows, title=f"{bank_name} Ledger")
    else:
        st.info("Is bank account ka ledger empty hai.")



def cash_tab(entry_date):
    user = get_current_user()
    s = get_daily_money_summary(entry_date)

    cash_sale = _f(s.get("cash_sale"))
    cash_deposited = _f(s.get("cash_deposited"))
    cash_in_hand = _f(s.get("cash_in_hand"))
    cash_ledger_balance = render_selected_account_balance("cash", entry_date)

    st.subheader("Cash Transfer / Deposit to Canara Bank")
    st.caption("Yahan total cash ledger balance dikhega. Usme se OD ya CC account me jitna transfer karna ho, amount enter karo.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash Ledger Balance", format_currency(cash_ledger_balance))
    c2.metric("Cash Sale Today", format_currency(cash_sale))
    c3.metric("Cash Already Deposited Today", format_currency(cash_deposited))
    c4.metric("Cash In Hand Today", format_currency(cash_in_hand))

    if cash_ledger_balance < 0:
        st.warning("Cash ledger balance negative aa raha hai. Pehle sale/payment/expense entries verify karo.")

    existing_deposits = get_cash_deposits(entry_date)
    account_summary = _cash_deposit_account_summary(existing_deposits)

    st.markdown("### Canara Account-wise Cash Deposit Today")
    a1, a2, a3 = st.columns(3)
    a1.metric("Canara OD Account Deposit Today", format_currency(account_summary.get("Canara Bank OD Account")))
    a2.metric("Canara CC Account Deposit Today", format_currency(account_summary.get("Canara Bank CC Account")))
    a3.metric("Other / Manual Bank", format_currency(account_summary.get("Other / Manual Bank")))

    st.markdown("### Bank Ledger Balances")
    od_balance = render_selected_account_balance("Canara Bank OD Account", entry_date)
    cc_balance = render_selected_account_balance("Canara Bank CC Account", entry_date)
    bank_balance = render_selected_account_balance("bank", entry_date)

    b1, b2, b3 = st.columns(3)
    b1.metric("Canara OD Balance", format_currency(od_balance))
    b2.metric("Canara CC Balance", format_currency(cc_balance))
    b3.metric("Total Bank Balance", format_currency(bank_balance))

    with st.form("cash_deposit_form"):
        bank_name = st.selectbox(
            "Transfer Cash To",
            CANARA_CASH_DEPOSIT_ACCOUNTS,
            key="cash_transfer_target_account",
        )

        max_amount = max(0.0, cash_ledger_balance)

        amount = st.number_input(
            "Cash Transfer Amount",
            min_value=0.0,
            max_value=max_amount if max_amount > 0 else None,
            step=100.0,
            format="%.2f",
            key="cash_transfer_amount",
        )

        selected_bank_balance = render_selected_account_balance(bank_name, entry_date)
        remaining_cash = round(cash_ledger_balance - _f(amount), 2)
        bank_after_transfer = round(selected_bank_balance + _f(amount), 2)

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Cash Ledger Balance", format_currency(cash_ledger_balance))
        p2.metric("Transfer Amount", format_currency(amount))
        p3.metric("Cash After Transfer", format_currency(remaining_cash))
        p4.metric("Selected Bank After Transfer", format_currency(bank_after_transfer))

        reference_no = st.text_input("Slip / Reference No.")
        note = st.text_input("Note", value=f"Cash transfer to {bank_name}")

        submitted = st.form_submit_button("Save Cash Transfer")

    if submitted:
        if _f(amount) <= 0:
            st.error("Transfer amount greater than 0 hona chahiye.")
            return

        if _f(amount) > cash_ledger_balance:
            st.error("Transfer amount cash ledger balance se zyada nahi ho sakta.")
            return

        saved, error = create_cash_deposit(
            amount=amount,
            bank_name=bank_name,
            reference_no=reference_no,
            deposited_by=user["id"],
            deposit_date=entry_date,
            note=note,
        )

        if saved:
            st.success(f"Cash transfer saved: {format_currency(amount)} → {bank_name}")
            st.rerun()
        else:
            st.error(error or "Cash transfer failed.")

    show_history(existing_deposits, "Cash Transfer / Deposit History")



def paytm_tab(entry_date):
    user = get_current_user()
    s = get_daily_money_summary(entry_date)

    paytm_ledger_balance = render_selected_account_balance("paytm", entry_date)
    od_balance = render_selected_account_balance("Canara Bank OD Account", entry_date)
    cc_balance = render_selected_account_balance("Canara Bank CC Account", entry_date)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Paytm Ledger Balance", format_currency(paytm_ledger_balance))
    c2.metric("Paytm Sale Today", format_currency(s["paytm_sale"]))
    c3.metric("Paytm Settled Today", format_currency(s["paytm_settled"]))
    c4.metric("Paytm Pending Today", format_currency(s["paytm_pending"]))

    b1, b2 = st.columns(2)
    b1.metric("Canara OD Balance", format_currency(od_balance))
    b2.metric("Canara CC Balance", format_currency(cc_balance))

    with st.form("paytm_settle_form"):
        amount = st.number_input(
            "Bank Received Amount",
            min_value=0.0,
            max_value=max(0.0, paytm_ledger_balance) if paytm_ledger_balance > 0 else None,
            step=100.0,
            format="%.2f",
        )
        bank_name = st.selectbox("Bank Name", CANARA_CASH_DEPOSIT_ACCOUNTS, key="paytm_bank_name")

        selected_bank_balance = render_selected_account_balance(bank_name, entry_date)
        paytm_after = round(paytm_ledger_balance - _f(amount), 2)
        bank_after = round(selected_bank_balance + _f(amount), 2)

        p1, p2, p3 = st.columns(3)
        p1.metric("Paytm After Settlement", format_currency(paytm_after))
        p2.metric("Selected Bank Current", format_currency(selected_bank_balance))
        p3.metric("Selected Bank After", format_currency(bank_after))

        reference_no = st.text_input("UTR / Reference No.")
        note = st.text_input("Note")
        submitted = st.form_submit_button("Save Paytm Settlement")

    if submitted:
        if _f(amount) <= 0:
            st.error("Paytm settlement amount greater than 0 hona chahiye.")
            return

        if _f(amount) > paytm_ledger_balance:
            st.error("Settlement amount Paytm ledger balance se zyada nahi ho sakta.")
            return

        saved, error = create_paytm_settlement(amount, bank_name, reference_no, user["id"], entry_date, note)
        if saved:
            st.success("Paytm settlement saved. Selected bank balance increase ho gaya.")
            st.rerun()
        else:
            st.error(error or "Paytm settlement failed.")

    show_history(get_paytm_settlements(entry_date), "Paytm Settlement History")



def ccms_tab(entry_date):
    user = get_current_user()
    s = get_daily_money_summary(entry_date)

    ccms_ledger_balance = render_selected_account_balance("ccms", entry_date)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CCMS Ledger Balance", format_currency(ccms_ledger_balance))
    c2.metric("CCMS Sale Today", format_currency(s["ccms_sale"]))
    c3.metric("CCMS Oil Company Adjusted Today", format_currency(s["ccms_received"]))
    c4.metric("CCMS Pending Today", format_currency(s["ccms_pending"]))

    st.caption("CCMS amount bank me nahi jayega. Selected oil company ledger me credit/adjustment hoga.")

    oil_summary = get_oil_company_summary()
    oil_companies = sorted({r.get("Oil Company") for r in oil_summary if r.get("Oil Company")})

    if not oil_companies:
        oil_companies = ["IOCL", "BPCL", "HPCL"]

    if oil_summary:
        st.markdown("### Oil Company Outstanding")
        st.dataframe(oil_summary, use_container_width=True, hide_index=True)

    with st.form("ccms_settle_form"):
        amount = st.number_input(
            "CCMS Adjustment Amount",
            min_value=0.0,
            max_value=max(0.0, ccms_ledger_balance) if ccms_ledger_balance > 0 else None,
            step=100.0,
            format="%.2f",
        )
        oil_company = st.selectbox("Oil Company", oil_companies, key="ccms_oil_company")
        ccms_after = round(ccms_ledger_balance - _f(amount), 2)

        p1, p2 = st.columns(2)
        p1.metric("CCMS Before Adjustment", format_currency(ccms_ledger_balance))
        p2.metric("CCMS After Adjustment", format_currency(ccms_after))

        reference_no = st.text_input("Reference No.")
        note = st.text_input("Note", value=f"CCMS adjustment to {oil_company}")
        submitted = st.form_submit_button("Save CCMS Oil Company Adjustment")

    if submitted:
        if _f(amount) <= 0:
            st.error("CCMS adjustment amount greater than 0 hona chahiye.")
            return

        if _f(amount) > ccms_ledger_balance:
            st.error("Adjustment amount CCMS ledger balance se zyada nahi ho sakta.")
            return

        saved, error = create_ccms_settlement(amount, oil_company, reference_no, user["id"], entry_date, note)
        if saved:
            st.success("CCMS adjustment saved. Oil Company Ledger me payable reduce ho gaya.")
            st.rerun()
        else:
            st.error(error or "CCMS adjustment failed.")

    show_history(get_ccms_settlements(entry_date), "CCMS Oil Company Adjustment History")




def oil_company_ledger_tab():
    user = get_current_user()

    st.subheader("Oil Company Ledger")
    st.caption("Fuel inward se denadari badhegi. CCMS adjustment aur payment se outstanding kam hoga.")

    summary = get_oil_company_summary()

    if summary:
        st.markdown("### Company-wise Outstanding")
        st.dataframe(summary, use_container_width=True, hide_index=True)
    else:
        st.info("No oil company outstanding found.")

    st.divider()
    st.markdown("### Payment to Oil Company")

    with st.form("oil_company_payment_form_money_control"):
        company_options = sorted({r.get("Oil Company") for r in summary if r.get("Oil Company")}) if summary else []
        if company_options:
            oil_company = st.selectbox("Oil Company", company_options, key="oil_payment_company")
        else:
            oil_company = st.text_input("Oil Company", key="oil_payment_company_text")

        amount = st.number_input("Payment Amount", min_value=0.0, step=1000.0, format="%.2f")
        reference_no = st.text_input("Reference No.")
        submitted = st.form_submit_button("Save Oil Company Payment")

    if submitted:
        row, err = create_oil_company_payment(
            oil_company=oil_company,
            amount=amount,
            reference_no=reference_no,
            created_by=user["id"],
        )

        if row:
            st.success("Oil company payment saved. Outstanding reduce ho gaya.")
            st.rerun()
        else:
            st.error(err or "Oil company payment failed.")

    st.divider()
    st.markdown("### Oil Company Ledger Details")

    rows = get_oil_company_ledger()

    if rows:
        st.dataframe([
            {
                "Date": r.get("date"),
                "Oil Company": r.get("oil_company"),
                "Type": r.get("type"),
                "Fuel": r.get("fuel_type"),
                "Qty Ltrs": r.get("quantity_liters"),
                "Amount": format_currency(r.get("amount")),
                "Reference": r.get("reference_no"),
                "Note": r.get("note") or "",
                "Created At": r.get("created_at"),
            }
            for r in rows
        ], use_container_width=True, hide_index=True)
    else:
        st.info("No oil company ledger entries found.")



def report_tab(entry_date):
    s = get_daily_money_summary(entry_date)
    rows = [
        {"Particular": "Total Sale", "Amount": format_currency(s["total_sale"])},
        {"Particular": "Cash Sale", "Amount": format_currency(s["cash_sale"])},
        {"Particular": "Credit Payment Received - Cash", "Amount": format_currency(s.get("credit_cash_received", 0))},
        {"Particular": "Cash Deposited", "Amount": format_currency(s["cash_deposited"])},
        {"Particular": "Cash In Hand", "Amount": format_currency(s["cash_in_hand"])},

        {"Particular": "Credit Payment Received - Bank", "Amount": format_currency(s.get("credit_bank_received", 0))},
        {"Particular": "Bank Inflow Total (Cash + Paytm + Bank Credit Only)", "Amount": format_currency(s.get("bank_inflow_total", 0))},

        {"Particular": "Paytm Sale", "Amount": format_currency(s["paytm_sale"])},
        {"Particular": "Credit Payment Received - Paytm", "Amount": format_currency(s.get("credit_paytm_received", 0))},
        {"Particular": "Paytm Settled", "Amount": format_currency(s["paytm_settled"])},
        {"Particular": "Paytm Pending", "Amount": format_currency(s["paytm_pending"])},

        {"Particular": "CCMS Sale", "Amount": format_currency(s["ccms_sale"])},
        {"Particular": "Credit Payment Received - CCMS", "Amount": format_currency(s.get("credit_ccms_received", 0))},
        {"Particular": "CCMS Oil Company Adjustment", "Amount": format_currency(s["ccms_received"])},
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
    ledger_tabs = st.tabs([
        "All",
        "Cash Ledger",
        "Bank Ledger",
        "Canara OD Ledger",
        "Canara CC Ledger",
        "Paytm Ledger",
        "CCMS Ledger",
    ])

    with ledger_tabs[0]:
        render_account_ledger_table(ledger, title="All Ledger")

    with ledger_tabs[1]:
        render_single_account_ledger("cash", from_date, to_date)

    with ledger_tabs[2]:
        render_single_account_ledger("bank", from_date, to_date)

    with ledger_tabs[3]:
        render_single_bank_ledger("Canara Bank OD Account", from_date, to_date)

    with ledger_tabs[4]:
        render_single_bank_ledger("Canara Bank CC Account", from_date, to_date)

    with ledger_tabs[5]:
        render_single_account_ledger("paytm", from_date, to_date)

    with ledger_tabs[6]:
        render_single_account_ledger("ccms", from_date, to_date)



def render_single_bank_ledger(bank_name, from_date, to_date):
    summary = get_bank_account_summary(bank_name, from_date, to_date)
    rows = get_bank_account_ledger(bank_name, from_date, to_date)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bank Account", bank_name)
    c2.metric("Credit / Inflow", format_currency(summary.get("Credit")))
    c3.metric("Debit / Outflow", format_currency(summary.get("Debit")))
    c4.metric("Balance", format_currency(summary.get("Balance")))

    render_account_ledger_table(rows, title=f"{bank_name} Ledger")


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
            "Bank Name": r.get("Bank Name") or "",
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
