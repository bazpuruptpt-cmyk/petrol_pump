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


def _clear_money_cache():
    try:
        st.cache_data.clear()
    except Exception:
        pass


@st.cache_data(ttl=45, show_spinner=False)
def _cached_daily_money_summary(entry_date):
    return get_daily_money_summary(entry_date)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_cash_deposits(entry_date):
    return get_cash_deposits(entry_date)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_paytm_settlements(entry_date):
    return get_paytm_settlements(entry_date)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_ccms_settlements(entry_date):
    return get_ccms_settlements(entry_date)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_oil_company_summary():
    return get_oil_company_summary()


@st.cache_data(ttl=45, show_spinner=False)
def _cached_oil_company_ledger():
    return get_oil_company_ledger()


@st.cache_data(ttl=45, show_spinner=False)
def _cached_overall_money_summary(from_date, to_date):
    return get_overall_money_summary(from_date, to_date)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_overall_money_ledger(from_date, to_date):
    return get_overall_money_ledger(from_date, to_date)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_account_summary(account, from_date, to_date):
    return get_account_summary(account, from_date, to_date)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_account_ledger(account, from_date, to_date):
    return get_account_ledger(account, from_date, to_date)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_bank_account_summary(bank_name, from_date, to_date):
    return get_bank_account_summary(bank_name, from_date, to_date)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_bank_account_ledger(bank_name, from_date, to_date):
    return get_bank_account_ledger(bank_name, from_date, to_date)


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
@require_role(["owner", "manager"])
def money_control_page():
    st.title("Money Control")
    st.caption("Fast mode: selected section hi load hoga. Heavy ledger/history button dabane par hi load hogi.")

    selected_date = str(st.date_input("Date", value=date.today(), key="money_date"))

    # Light summary only. Heavy total ledger balances are not loaded on page open.
    show_summary(selected_date)

    sections = [
        "Cash Deposit",
        "Paytm Settlement",
        "CCMS Received",
        "Canara OD Account",
        "Canara CC Account",
        "Daily Report",
        "Overall Ledger",
        "Oil Company Ledger",
    ]

    section = st.radio(
        "Money Control Section",
        sections,
        horizontal=True,
        key="money_control_section_fast",
    )

    st.divider()

    # Lazy render: only selected section runs.
    if section == "Cash Deposit":
        cash_tab(selected_date)
    elif section == "Paytm Settlement":
        paytm_tab(selected_date)
    elif section == "CCMS Received":
        ccms_tab(selected_date)
    elif section == "Canara OD Account":
        bank_account_cash_deposit_tab("Canara Bank OD Account", selected_date)
    elif section == "Canara CC Account":
        bank_account_cash_deposit_tab("Canara Bank CC Account", selected_date)
    elif section == "Daily Report":
        report_tab(selected_date)
    elif section == "Overall Ledger":
        overall_ledger_tab()
    elif section == "Oil Company Ledger":
        oil_company_ledger_tab()

def show_summary(entry_date):
    s = _cached_daily_money_summary(entry_date)

    st.markdown("### Daily Position")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sale Today", format_currency(s.get("total_sale")))
    c2.metric("Cash In Hand Today", format_currency(s.get("cash_in_hand")))
    c3.metric("Paytm Pending Today", format_currency(s.get("paytm_pending")))
    c4.metric("CCMS Pending Today", format_currency(s.get("ccms_pending")))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Credit Received", format_currency(s.get("credit_received_total", 0)))
    c6.metric("Credit Cash", format_currency(s.get("credit_cash_received", 0)))
    c7.metric("Credit Bank", format_currency(s.get("credit_bank_received", 0)))
    c8.metric("Bank Inflow Today", format_currency(s.get("bank_inflow_total", 0)))

    if st.button("Load Current Ledger Balances", key="load_money_balances"):
        render_money_balance_snapshot(entry_date, title="Current Ledger Balances")
    else:
        st.caption("Speed ke liye total ledger balances auto-load nahi ho rahe. Button dabane par load honge.")

def _cash_deposits_for_bank(rows, bank_name):
    bank_name = str(bank_name or "").strip()
    return [
        r for r in (rows or [])
        if str(r.get("bank_name") or "").strip() == bank_name
    ]


def bank_account_cash_deposit_tab(bank_name, entry_date):
    user = get_current_user()
    s = _cached_daily_money_summary(entry_date)

    st.subheader(bank_name)
    st.caption("Fast cash transfer entry. Ledger detail button dabane par hi load hogi.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Cash In Hand Today", format_currency(s.get("cash_in_hand")))
    c2.metric("Cash Deposited Today", format_currency(s.get("cash_deposited")))
    c3.metric("Bank Inflow Today", format_currency(s.get("bank_inflow_total")))

    with st.form(f"cash_transfer_form_{bank_name.replace(' ', '_').lower()}_fast"):
        st.text_input("Bank Account", value=bank_name, disabled=True)

        amount = st.number_input(
            "Cash Transfer Amount",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            key=f"cash_transfer_amount_{bank_name}_fast",
        )

        reference_no = st.text_input("Slip / Reference No.", key=f"cash_ref_{bank_name}_fast")
        note = st.text_input("Note", value=f"Cash transfer to {bank_name}", key=f"cash_note_{bank_name}_fast")

        submitted = st.form_submit_button(f"Save Cash Transfer to {bank_name}")

    if submitted:
        if _f(amount) <= 0:
            st.error("Transfer amount greater than 0 hona chahiye.")
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
            _clear_money_cache()
            st.rerun()
        else:
            st.error(error or "Cash transfer failed.")

    if st.button(f"Load {bank_name} Ledger / History", key=f"load_bank_{bank_name}_fast"):
        bank_summary_total = _cached_bank_account_summary(bank_name, None, entry_date)
        bank_deposits_today = _cash_deposits_for_bank(_cached_cash_deposits(entry_date), bank_name)

        m1, m2, m3 = st.columns(3)
        m1.metric("Bank Ledger Balance", format_currency(bank_summary_total.get("Balance")))
        m2.metric("Today Credit", format_currency(bank_summary_total.get("Credit")))
        m3.metric("Today Debit", format_currency(bank_summary_total.get("Debit")))

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
                for r in bank_deposits_today[:200]
            ], use_container_width=True, hide_index=True)
        else:
            st.info("Aaj is account me cash transfer nahi hai.")

        ledger_rows = _cached_bank_account_ledger(bank_name, None, entry_date)
        render_account_ledger_table(ledger_rows, title=f"{bank_name} Ledger")

def cash_tab(entry_date):
    user = get_current_user()
    s = _cached_daily_money_summary(entry_date)

    st.subheader("Cash Transfer / Deposit to Canara Bank")
    st.caption("Fast entry mode. Heavy total ledger/history button dabane par hi load hogi.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash Sale Today", format_currency(s.get("cash_sale")))
    c2.metric("Credit Cash Received Today", format_currency(s.get("credit_cash_received")))
    c3.metric("Cash Deposited Today", format_currency(s.get("cash_deposited")))
    c4.metric("Cash In Hand Today", format_currency(s.get("cash_in_hand")))

    with st.form("cash_deposit_form_fast"):
        bank_name = st.selectbox(
            "Transfer Cash To",
            CANARA_CASH_DEPOSIT_ACCOUNTS,
            key="cash_transfer_target_account_fast",
        )

        amount = st.number_input(
            "Cash Transfer Amount",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            key="cash_transfer_amount_fast",
        )

        reference_no = st.text_input("Slip / Reference No.")
        note = st.text_input("Note", value=f"Cash transfer to {bank_name}")

        submitted = st.form_submit_button("Save Cash Transfer")

    if submitted:
        if _f(amount) <= 0:
            st.error("Transfer amount greater than 0 hona chahiye.")
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
            _clear_money_cache()
            st.rerun()
        else:
            st.error(error or "Cash transfer failed.")

    if st.button("Load Cash / Bank Balances & History", key="load_cash_history_fast"):
        cash_ledger_balance = render_selected_account_balance("cash", entry_date)
        od_balance = render_selected_account_balance("Canara Bank OD Account", entry_date)
        cc_balance = render_selected_account_balance("Canara Bank CC Account", entry_date)

        b1, b2, b3 = st.columns(3)
        b1.metric("Cash Ledger Balance", format_currency(cash_ledger_balance))
        b2.metric("Canara OD Balance", format_currency(od_balance))
        b3.metric("Canara CC Balance", format_currency(cc_balance))

        existing_deposits = _cached_cash_deposits(entry_date)
        show_history(existing_deposits, "Cash Transfer / Deposit History")

def paytm_tab(entry_date):
    user = get_current_user()
    s = _cached_daily_money_summary(entry_date)

    st.subheader("Paytm Settlement")
    st.caption("Fast entry mode. Balance/history button dabane par load hogi.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Paytm Sale Today", format_currency(s.get("paytm_sale")))
    c2.metric("Paytm Settled Today", format_currency(s.get("paytm_settled")))
    c3.metric("Paytm Pending Today", format_currency(s.get("paytm_pending")))

    with st.form("paytm_settle_form_fast"):
        amount = st.number_input("Bank Received Amount", min_value=0.0, step=100.0, format="%.2f")
        bank_name = st.selectbox("Bank Name", CANARA_CASH_DEPOSIT_ACCOUNTS, key="paytm_bank_name_fast")
        reference_no = st.text_input("UTR / Reference No.")
        note = st.text_input("Note")
        submitted = st.form_submit_button("Save Paytm Settlement")

    if submitted:
        if _f(amount) <= 0:
            st.error("Paytm settlement amount greater than 0 hona chahiye.")
            return

        saved, error = create_paytm_settlement(amount, bank_name, reference_no, user["id"], entry_date, note)
        if saved:
            st.success("Paytm settlement saved. Selected bank balance increase ho gaya.")
            _clear_money_cache()
            st.rerun()
        else:
            st.error(error or "Paytm settlement failed.")

    if st.button("Load Paytm Balance / History", key="load_paytm_history_fast"):
        paytm_balance = render_selected_account_balance("paytm", entry_date)
        st.metric("Paytm Ledger Balance", format_currency(paytm_balance))
        show_history(_cached_paytm_settlements(entry_date), "Paytm Settlement History")

def ccms_tab(entry_date):
    user = get_current_user()
    s = _cached_daily_money_summary(entry_date)

    st.subheader("CCMS Oil Company Adjustment")
    st.caption("CCMS bank me nahi jayega. Oil Company Ledger me adjustment hoga.")

    c1, c2, c3 = st.columns(3)
    c1.metric("CCMS Sale Today", format_currency(s.get("ccms_sale")))
    c2.metric("CCMS Adjusted Today", format_currency(s.get("ccms_received")))
    c3.metric("CCMS Pending Today", format_currency(s.get("ccms_pending")))

    with st.form("ccms_settle_form_fast"):
        amount = st.number_input("CCMS Adjustment Amount", min_value=0.0, step=100.0, format="%.2f")
        oil_company = st.text_input("Oil Company", value="IOCL")
        reference_no = st.text_input("Reference No.")
        note = st.text_input("Note", value="CCMS adjustment to Oil Company")
        submitted = st.form_submit_button("Save CCMS Oil Company Adjustment")

    if submitted:
        if _f(amount) <= 0:
            st.error("CCMS adjustment amount greater than 0 hona chahiye.")
            return

        saved, error = create_ccms_settlement(amount, oil_company, reference_no, user["id"], entry_date, note)
        if saved:
            st.success("CCMS adjustment saved. Oil Company Ledger me payable reduce ho gaya.")
            _clear_money_cache()
            st.rerun()
        else:
            st.error(error or "CCMS adjustment failed.")

    if st.button("Load CCMS Balance / History", key="load_ccms_history_fast"):
        ccms_balance = render_selected_account_balance("ccms", entry_date)
        st.metric("CCMS Ledger Balance", format_currency(ccms_balance))
        show_history(_cached_ccms_settlements(entry_date), "CCMS Oil Company Adjustment History")

def oil_company_ledger_tab():
    user = get_current_user()

    st.subheader("Oil Company Ledger")
    st.caption("Fuel inward se payable badhega. CCMS adjustment aur selected bank payment se outstanding kam hoga.")

    if st.button("Load Oil Company Summary", key="load_oil_summary_fast"):
        summary = _cached_oil_company_summary()
        if summary:
            st.dataframe(summary, use_container_width=True, hide_index=True)
        else:
            st.info("No oil company outstanding found.")

    st.divider()
    st.markdown("### Transfer from Bank to Oil Company")

    with st.form("oil_company_payment_form_money_control_fast"):
        oil_company = st.text_input(
            "Oil Company",
            value="IOCL",
            key="oil_payment_company_text_fast",
        )

        source_bank = st.selectbox(
            "Pay From Bank Account",
            CANARA_CASH_DEPOSIT_ACCOUNTS,
            key="oil_payment_source_bank_fast",
        )

        amount = st.number_input(
            "Payment / Transfer Amount",
            min_value=0.0,
            step=1000.0,
            format="%.2f",
            key="oil_payment_amount_fast",
        )

        reference_no = st.text_input("Reference No. / UTR", key="oil_payment_ref_fast")
        note = st.text_input(
            "Note",
            value="Bank transfer to oil company",
            key="oil_payment_note_fast",
        )

        submitted = st.form_submit_button("Save Bank Transfer to Oil Company")

    if submitted:
        if _f(amount) <= 0:
            st.error("Payment amount greater than 0 hona chahiye.")
            return

        row, err = create_oil_company_payment(
            oil_company=oil_company,
            amount=amount,
            reference_no=reference_no,
            created_by=user["id"],
            bank_name=source_bank,
            payment_date=str(st.session_state.get("money_date") or date.today()),
            note=note,
        )

        if row and not err:
            st.success(f"{source_bank} se {oil_company} ko {format_currency(amount)} transfer saved.")
            _clear_money_cache()
            st.rerun()
        elif row and err:
            st.warning(err)
            _clear_money_cache()
        else:
            st.error(err or "Oil company payment failed.")

    if st.button("Load Oil Company Ledger Rows", key="load_oil_rows_fast"):
        rows = _cached_oil_company_ledger()
        if rows:
            st.dataframe([
                {
                    "Date": r.get("date"),
                    "Oil Company": r.get("oil_company") or r.get("company_name"),
                    "Type": r.get("type") or r.get("entry_type"),
                    "Fuel": r.get("fuel_type"),
                    "Qty Ltrs": r.get("quantity_liters"),
                    "Amount": format_currency(r.get("amount")),
                    "Reference": r.get("reference_no"),
                    "Note": r.get("note") or "",
                    "Created At": r.get("created_at"),
                }
                for r in rows[:500]
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
    st.caption("Heavy report: button dabane par hi DB query chalegi.")

    c1, c2 = st.columns(2)
    with c1:
        from_date = str(st.date_input("From Date", value=date.today().replace(day=1), key="overall_ledger_from_date_fast"))
    with c2:
        to_date = str(st.date_input("To Date", value=date.today(), key="overall_ledger_to_date_fast"))

    ledger_view = st.radio(
        "Ledger View",
        [
            "Summary Only",
            "All",
            "Cash Ledger",
            "Bank Ledger",
            "Canara OD Ledger",
            "Canara CC Ledger",
            "Paytm Ledger",
            "CCMS Ledger",
        ],
        horizontal=True,
        key="overall_ledger_lazy_view_fast",
    )

    if not st.button("Load Selected Ledger", key="load_overall_ledger_fast"):
        st.info("Speed ke liye ledger auto-load nahi hota. Date range select karke button dabao.")
        return

    if ledger_view == "Summary Only":
        summary = _cached_overall_money_summary(from_date, to_date)
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

    elif ledger_view == "All":
        ledger = _cached_overall_money_ledger(from_date, to_date)
        render_account_ledger_table(ledger, title="All Ledger")
    elif ledger_view == "Cash Ledger":
        render_single_account_ledger("cash", from_date, to_date)
    elif ledger_view == "Bank Ledger":
        render_single_account_ledger("bank", from_date, to_date)
    elif ledger_view == "Canara OD Ledger":
        render_single_bank_ledger("Canara Bank OD Account", from_date, to_date)
    elif ledger_view == "Canara CC Ledger":
        render_single_bank_ledger("Canara Bank CC Account", from_date, to_date)
    elif ledger_view == "Paytm Ledger":
        render_single_account_ledger("paytm", from_date, to_date)
    elif ledger_view == "CCMS Ledger":
        render_single_account_ledger("ccms", from_date, to_date)

def render_single_bank_ledger(bank_name, from_date, to_date):
    summary = _cached_bank_account_summary(bank_name, from_date, to_date)
    rows = _cached_bank_account_ledger(bank_name, from_date, to_date)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bank Account", bank_name)
    c2.metric("Credit / Inflow", format_currency(summary.get("Credit")))
    c3.metric("Debit / Outflow", format_currency(summary.get("Debit")))
    c4.metric("Balance", format_currency(summary.get("Balance")))

    render_account_ledger_table(rows, title=f"{bank_name} Ledger")

def render_single_account_ledger(account, from_date, to_date):
    summary = _cached_account_summary(account, from_date, to_date)
    rows = _cached_account_ledger(account, from_date, to_date)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Account", str(account).upper())
    c2.metric("Credit / Inflow", format_currency(summary.get("Credit")))
    c3.metric("Debit / Outflow", format_currency(summary.get("Debit")))
    c4.metric("Balance", format_currency(summary.get("Balance")))

    render_account_ledger_table(rows, title=f"{str(account).upper()} Ledger")

def render_account_ledger_table(rows, title="Ledger"):
    total_rows = len(rows or [])
    st.write(f"**{title} Rows:** {total_rows}")

    if not rows:
        st.info("No ledger rows found.")
        return

    display_rows = list(rows or [])[:300]

    if total_rows > 300:
        st.warning("Speed ke liye latest 300 rows show ho rahi hain. Full export/report later add karenge.")

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
        for r in display_rows
    ], use_container_width=True, hide_index=True)

