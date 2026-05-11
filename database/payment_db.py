from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client

def _now():
    return datetime.now(timezone.utc).isoformat()

def _today():
    return date.today().isoformat()

def _f(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def get_approved_settlements(entry_date=None):
    try:
        q = get_supabase_client().table("settlements").select("*").eq("status", "approved")
        if entry_date:
            q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_approved_settlements", e)
        return []


def get_payment_totals(entry_date=None):
    rows = get_approved_settlements(entry_date or _today())
    total = {
        "total_sale": 0.0,
        "cash": 0.0,
        "paytm": 0.0,
        "ccms": 0.0,
        "credit": 0.0,
        "approved_count": len(rows),
    }

    for row in rows:
        total["total_sale"] += _f(row.get("meter_total"))
        total["cash"] += _f(row.get("cash_amount"))
        total["paytm"] += _f(row.get("paytm_amount"))
        total["ccms"] += _f(row.get("ccms_amount"))
        total["credit"] += _f(row.get("credit_amount"))

    for k in ["total_sale", "cash", "paytm", "ccms", "credit"]:
        total[k] = round(total[k], 2)

    return total


def _approved_expense_total(entry_date=None, payment_mode=None):
    try:
        q = get_supabase_client().table("expenses").select("*").eq("status", "approved")
        if entry_date:
            q = q.eq("date", entry_date)
        if payment_mode:
            q = q.eq("payment_mode", payment_mode)
        rows = q.execute().data or []
        return round(sum(_f(r.get("amount")) for r in rows), 2)
    except Exception as e:
        print("approved expense optional", e)
        return 0.0


def _approved_credit_collection(entry_date=None, payment_mode=None):
    try:
        q = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*")
            .eq("status", "approved")
            .eq("type", "payment_received")
        )
        if entry_date:
            q = q.eq("date", entry_date)
        if payment_mode:
            q = q.eq("payment_mode", payment_mode)
        rows = q.execute().data or []
        return round(sum(_f(r.get("amount")) for r in rows), 2)
    except Exception as e:
        print("approved credit collection optional", e)
        return 0.0



def get_credit_collection_details(entry_date=None, status="approved", payment_mode=None):
    """
    Approved creditor payment details for daily summary.
    Shows narration/date/mode-wise received amount.
    """
    try:
        q = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*, credit_parties:party_id(name, phone)")
            .eq("type", "payment_received")
        )

        if entry_date:
            q = q.eq("date", entry_date)

        if status:
            q = q.eq("status", status)

        if payment_mode:
            q = q.eq("payment_mode", payment_mode)

        rows = q.order("created_at", desc=True).execute().data or []

        output = []
        for r in rows:
            party = r.get("credit_parties") or {}
            output.append({
                "date": r.get("date"),
                "mode": r.get("payment_mode"),
                "amount": round(_f(r.get("amount")), 2),
                "creditor": party.get("name") or r.get("party_id"),
                "bank_name": r.get("bank_name"),
                "reference": r.get("reference_id"),
                "narration": r.get("note"),
                "status": r.get("status"),
                "created_at": r.get("created_at"),
            })

        return output
    except Exception as e:
        print("get_credit_collection_details optional", e)
        return []


def get_credit_collection_summary(entry_date=None, status="approved"):
    rows = get_credit_collection_details(entry_date, status=status)

    summary = {
        "cash": 0.0,
        "bank": 0.0,
        "paytm": 0.0,
        "ccms": 0.0,
        "total": 0.0,
    }

    for r in rows:
        mode = r.get("mode")
        amount = _f(r.get("amount"))

        if mode in summary:
            summary[mode] += amount
            summary["total"] += amount

    return {k: round(v, 2) for k, v in summary.items()}


def create_cash_deposit(amount, bank_name, reference_no, deposited_by, deposit_date=None, note=None):
    if _f(amount) <= 0:
        return None, "Cash deposit amount must be greater than 0."

    payload = {
        "date": deposit_date or _today(),
        "amount": _f(amount),
        "bank_name": bank_name,
        "reference_no": reference_no,
        "note": note,
        "deposited_by": deposited_by,
        "created_at": _now(),
    }

    try:
        r = get_supabase_client().table("cash_deposits").insert(payload).execute()
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("create_cash_deposit", e)
        return None, str(e)


def get_cash_deposits(entry_date=None):
    try:
        q = get_supabase_client().table("cash_deposits").select("*")
        if entry_date:
            q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_cash_deposits", e)
        return []


def get_cash_deposit_total(entry_date=None):
    return round(sum(_f(r.get("amount")) for r in get_cash_deposits(entry_date or _today())), 2)


def create_paytm_settlement(amount, bank_name, reference_no, settled_by, settlement_date=None, note=None):
    if _f(amount) <= 0:
        return None, "Paytm settled amount must be greater than 0."

    payload = {
        "date": settlement_date or _today(),
        "amount": _f(amount),
        "bank_name": bank_name,
        "reference_no": reference_no,
        "note": note,
        "settled_by": settled_by,
        "created_at": _now(),
    }

    try:
        r = get_supabase_client().table("paytm_settlements").insert(payload).execute()
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("create_paytm_settlement", e)
        return None, str(e)


def get_paytm_settlements(entry_date=None):
    try:
        q = get_supabase_client().table("paytm_settlements").select("*")
        if entry_date:
            q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_paytm_settlements", e)
        return []


def get_paytm_settled_total(entry_date=None):
    return round(sum(_f(r.get("amount")) for r in get_paytm_settlements(entry_date or _today())), 2)


def create_ccms_settlement(amount, bank_name, reference_no, settled_by, settlement_date=None, note=None):
    if _f(amount) <= 0:
        return None, "CCMS received amount must be greater than 0."

    payload = {
        "date": settlement_date or _today(),
        "amount": _f(amount),
        "bank_name": bank_name,
        "reference_no": reference_no,
        "note": note,
        "settled_by": settled_by,
        "created_at": _now(),
    }

    try:
        r = get_supabase_client().table("ccms_settlements").insert(payload).execute()
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("create_ccms_settlement", e)
        return None, str(e)


def get_ccms_settlements(entry_date=None):
    try:
        q = get_supabase_client().table("ccms_settlements").select("*")
        if entry_date:
            q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_ccms_settlements", e)
        return []


def get_ccms_received_total(entry_date=None):
    return round(sum(_f(r.get("amount")) for r in get_ccms_settlements(entry_date or _today())), 2)


def get_daily_money_summary(entry_date=None):
    entry_date = entry_date or _today()

    p = get_payment_totals(entry_date)

    cash_deposit = get_cash_deposit_total(entry_date)
    paytm_settled = get_paytm_settled_total(entry_date)
    ccms_received = get_ccms_received_total(entry_date)

    cash_expense = _approved_expense_total(entry_date, "cash")
    bank_expense = _approved_expense_total(entry_date, "bank")

    credit_summary = get_credit_collection_summary(entry_date, status="approved")

    credit_cash_received = credit_summary["cash"]
    credit_bank_received = credit_summary["bank"]
    credit_paytm_received = credit_summary["paytm"]
    credit_ccms_received = credit_summary["ccms"]
    credit_total_received = credit_summary["total"]

    return {
        "date": entry_date,

        "total_sale": p["total_sale"],
        "cash_sale": p["cash"],
        "paytm_sale": p["paytm"],
        "ccms_sale": p["ccms"],
        "credit_sale": p["credit"],

        "credit_received_total": credit_total_received,
        "credit_cash_received": credit_cash_received,
        "credit_bank_received": credit_bank_received,
        "credit_paytm_received": credit_paytm_received,
        "credit_ccms_received": credit_ccms_received,

        "cash_deposited": cash_deposit,
        "cash_expense": cash_expense,
        "bank_expense": bank_expense,

        "cash_in_hand": round(
            p["cash"] + credit_cash_received - cash_deposit - cash_expense,
            2,
        ),

        "bank_credit_received": credit_bank_received,
        "bank_inflow_total": round(cash_deposit + paytm_settled + ccms_received + credit_bank_received, 2),

        "paytm_settled": paytm_settled,
        "paytm_pending": round(
            p["paytm"] + credit_paytm_received - paytm_settled,
            2,
        ),

        "ccms_received": ccms_received,
        "ccms_pending": round(
            p["ccms"] + credit_ccms_received - ccms_received,
            2,
        ),

        "approved_settlements": p["approved_count"],
    }

def _safe_date_value(row):
    return row.get("date") or row.get("payment_date") or row.get("created_at")


def _add_ledger_row(rows, entry_date, account, txn_type, reference, particular, credit=0, debit=0, narration=None, status=None):
    rows.append({
        "Date": entry_date,
        "Account": account,
        "Type": txn_type,
        "Reference": reference,
        "Particular": particular,
        "Credit": round(_f(credit), 2),
        "Debit": round(_f(debit), 2),
        "Narration": narration,
        "Status": status,
    })


def get_overall_money_ledger(from_date=None, to_date=None):
    """
    Overall debit/credit ledger for Cash, Bank, Paytm, CCMS.

    Accounting rule:
    Credit = money/account inflow
    Debit  = money/account outflow
    Balance = Credit - Debit
    """
    from_date = from_date or "1900-01-01"
    to_date = to_date or _today()

    rows = []

    # 1. Approved sale breakup from settlements
    try:
        sale_rows = (
            get_supabase_client()
            .table("settlements")
            .select("*")
            .eq("status", "approved")
            .gte("date", from_date)
            .lte("date", to_date)
            .order("date")
            .execute()
            .data
            or []
        )
    except Exception as e:
        print("overall sale rows optional", e)
        sale_rows = []

    for r in sale_rows:
        ref = f"Settlement {r.get('id')}"
        note = f"Shift {r.get('shift_id')} | Salesman {r.get('salesman_id')}"

        if _f(r.get("cash_amount")):
            _add_ledger_row(rows, r.get("date"), "cash", "Sale Cash", ref, "Approved sale cash", credit=r.get("cash_amount"), narration=note, status=r.get("status"))

        if _f(r.get("paytm_amount")):
            _add_ledger_row(rows, r.get("date"), "paytm", "Sale Paytm", ref, "Approved sale Paytm", credit=r.get("paytm_amount"), narration=note, status=r.get("status"))

        if _f(r.get("ccms_amount")):
            _add_ledger_row(rows, r.get("date"), "ccms", "Sale CCMS", ref, "Approved sale CCMS", credit=r.get("ccms_amount"), narration=note, status=r.get("status"))

    # 2. Approved creditor payments
    credit_rows = get_credit_collection_details(None, status="approved")
    for r in credit_rows:
        d = r.get("date")
        if str(d) < str(from_date) or str(d) > str(to_date):
            continue

        mode = r.get("mode")
        if mode not in ["cash", "bank", "paytm", "ccms"]:
            continue

        _add_ledger_row(
            rows,
            d,
            mode,
            f"Creditor Payment - {str(mode).upper()}",
            r.get("reference"),
            r.get("creditor"),
            credit=r.get("amount"),
            narration=r.get("narration"),
            status=r.get("status"),
        )

    # 3. Cash deposit: cash out, bank in
    for r in get_cash_deposits(None):
        d = r.get("date")
        if str(d) < str(from_date) or str(d) > str(to_date):
            continue

        ref = r.get("reference_no") or r.get("id")
        bank = r.get("bank_name") or "Bank"
        amount = r.get("amount")

        _add_ledger_row(rows, d, "cash", "Cash Deposit", ref, bank, debit=amount, narration=r.get("note"))
        _add_ledger_row(rows, d, "bank", "Cash Deposit", ref, bank, credit=amount, narration=r.get("note"))

    # 4. Paytm settlement: paytm out, bank in
    for r in get_paytm_settlements(None):
        d = r.get("date")
        if str(d) < str(from_date) or str(d) > str(to_date):
            continue

        ref = r.get("reference_no") or r.get("id")
        bank = r.get("bank_name") or "Bank"
        amount = r.get("amount")

        _add_ledger_row(rows, d, "paytm", "Paytm Settlement", ref, bank, debit=amount, narration=r.get("note"))
        _add_ledger_row(rows, d, "bank", "Paytm Settlement", ref, bank, credit=amount, narration=r.get("note"))

    # 5. CCMS settlement: ccms out, bank in
    for r in get_ccms_settlements(None):
        d = r.get("date")
        if str(d) < str(from_date) or str(d) > str(to_date):
            continue

        ref = r.get("reference_no") or r.get("id")
        bank = r.get("bank_name") or "Bank"
        amount = r.get("amount")

        _add_ledger_row(rows, d, "ccms", "CCMS Received", ref, bank, debit=amount, narration=r.get("note"))
        _add_ledger_row(rows, d, "bank", "CCMS Received", ref, bank, credit=amount, narration=r.get("note"))

    # 6. Expenses
    try:
        exp_rows = (
            get_supabase_client()
            .table("expenses")
            .select("*")
            .eq("status", "approved")
            .gte("date", from_date)
            .lte("date", to_date)
            .execute()
            .data
            or []
        )
    except Exception as e:
        print("overall expense rows optional", e)
        exp_rows = []

    for r in exp_rows:
        mode = r.get("payment_mode")
        if mode not in ["cash", "bank"]:
            continue

        _add_ledger_row(
            rows,
            r.get("date"),
            mode,
            "Expense",
            r.get("reference_no") or r.get("id"),
            r.get("category") or "Expense",
            debit=r.get("amount"),
            narration=r.get("description") or r.get("note"),
            status=r.get("status"),
        )

    # 7. Oil company / inward bank payments if table exists
    try:
        inward_rows = (
            get_supabase_client()
            .table("inward_payments")
            .select("*")
            .gte("date", from_date)
            .lte("date", to_date)
            .execute()
            .data
            or []
        )
    except Exception as e:
        print("overall inward payments optional", e)
        inward_rows = []

    for r in inward_rows:
        amount = _f(r.get("amount")) or _f(r.get("neft_amount")) or _f(r.get("total_paid"))
        if amount <= 0:
            continue

        _add_ledger_row(
            rows,
            r.get("date") or r.get("payment_date"),
            "bank",
            "Oil Company Payment",
            r.get("reference_no") or r.get("utr_number") or r.get("id"),
            r.get("oil_company") or "Oil Company",
            debit=amount,
            narration=r.get("note") or r.get("inward_id"),
        )

    rows.sort(key=lambda x: (str(x.get("Date") or ""), str(x.get("Account") or ""), str(x.get("Type") or "")))
    return rows


def get_overall_money_summary(from_date=None, to_date=None):
    rows = get_overall_money_ledger(from_date, to_date)

    summary = {
        "cash": {"Account": "cash", "Credit": 0.0, "Debit": 0.0, "Balance": 0.0},
        "bank": {"Account": "bank", "Credit": 0.0, "Debit": 0.0, "Balance": 0.0},
        "paytm": {"Account": "paytm", "Credit": 0.0, "Debit": 0.0, "Balance": 0.0},
        "ccms": {"Account": "ccms", "Credit": 0.0, "Debit": 0.0, "Balance": 0.0},
    }

    for r in rows:
        acc = r.get("Account")
        if acc not in summary:
            continue

        summary[acc]["Credit"] += _f(r.get("Credit"))
        summary[acc]["Debit"] += _f(r.get("Debit"))

    for acc in summary:
        summary[acc]["Credit"] = round(summary[acc]["Credit"], 2)
        summary[acc]["Debit"] = round(summary[acc]["Debit"], 2)
        summary[acc]["Balance"] = round(summary[acc]["Credit"] - summary[acc]["Debit"], 2)

    return list(summary.values())

