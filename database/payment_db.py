from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client

def _now(): return datetime.now(timezone.utc).isoformat()
def _today(): return date.today().isoformat()
def _f(v):
    try: return float(v or 0)
    except Exception: return 0.0

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
    total = {"total_sale":0.0, "cash":0.0, "paytm":0.0, "ccms":0.0, "credit":0.0, "approved_count":len(rows)}
    for row in rows:
        total["total_sale"] += _f(row.get("meter_total"))
        total["cash"] += _f(row.get("cash_amount"))
        total["paytm"] += _f(row.get("paytm_amount"))
        total["ccms"] += _f(row.get("ccms_amount"))
        total["credit"] += _f(row.get("credit_amount"))
    for k in ["total_sale","cash","paytm","ccms","credit"]:
        total[k] = round(total[k], 2)
    return total

def _get_approved_cash_expense(entry_date=None):
    try:
        q = get_supabase_client().table("expenses").select("*").eq("status", "approved").eq("payment_mode", "cash")
        if entry_date:
            q = q.eq("date", entry_date)
        rows = q.execute().data or []
        return round(sum(_f(r.get("amount")) for r in rows), 2)
    except Exception as e:
        print("approved cash expense optional", e)
        return 0.0

def _get_approved_bank_expense(entry_date=None):
    try:
        q = get_supabase_client().table("expenses").select("*").eq("status", "approved").eq("payment_mode", "bank")
        if entry_date:
            q = q.eq("date", entry_date)
        rows = q.execute().data or []
        return round(sum(_f(r.get("amount")) for r in rows), 2)
    except Exception as e:
        print("approved bank expense optional", e)
        return 0.0

def create_cash_deposit(amount, bank_name, reference_no, deposited_by, deposit_date=None, note=None):
    if _f(amount) <= 0:
        return None, "Cash deposit amount must be greater than 0."
    payload = {"date": deposit_date or _today(), "amount": _f(amount), "bank_name": bank_name, "reference_no": reference_no, "note": note, "deposited_by": deposited_by, "created_at": _now()}
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
    payload = {"date": settlement_date or _today(), "amount": _f(amount), "bank_name": bank_name, "reference_no": reference_no, "note": note, "settled_by": settled_by, "created_at": _now()}
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
    payload = {"date": settlement_date or _today(), "amount": _f(amount), "bank_name": bank_name, "reference_no": reference_no, "note": note, "settled_by": settled_by, "created_at": _now()}
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
    cash_dep = get_cash_deposit_total(entry_date)
    paytm_set = get_paytm_settled_total(entry_date)
    ccms_rec = get_ccms_received_total(entry_date)
    cash_exp = _get_approved_cash_expense(entry_date)
    bank_exp = _get_approved_bank_expense(entry_date)

    return {
        "date": entry_date,
        "total_sale": p["total_sale"],
        "cash_sale": p["cash"],
        "paytm_sale": p["paytm"],
        "ccms_sale": p["ccms"],
        "credit_sale": p["credit"],
        "cash_deposited": cash_dep,
        "cash_expense": cash_exp,
        "bank_expense": bank_exp,
        "cash_in_hand": round(p["cash"] - cash_dep - cash_exp, 2),
        "paytm_settled": paytm_set,
        "paytm_pending": round(p["paytm"] - paytm_set, 2),
        "ccms_received": ccms_rec,
        "ccms_pending": round(p["ccms"] - ccms_rec, 2),
        "approved_settlements": p["approved_count"],
    }
