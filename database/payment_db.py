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
