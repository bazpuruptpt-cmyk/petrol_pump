from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client

def _now():
    return datetime.now(timezone.utc).isoformat()

def _today():
    return date.today().isoformat()

def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0

def get_approved_settlements(entry_date=None):
    supabase = get_supabase_client()
    try:
        q = supabase.table("settlements").select("*").eq("status", "approved")
        if entry_date:
            q = q.eq("date", entry_date)
        r = q.order("created_at", desc=True).execute()
        return r.data or []
    except Exception as exc:
        print(f"Error in get_approved_settlements: {exc}")
        return []

def get_payment_totals(entry_date=None):
    rows = get_approved_settlements(entry_date or _today())
    total = {"total_sale":0.0, "cash":0.0, "paytm":0.0, "ccms":0.0, "credit":0.0, "approved_count":len(rows)}
    for row in rows:
        total["total_sale"] += _safe_float(row.get("meter_total"))
        total["cash"] += _safe_float(row.get("cash_amount"))
        total["paytm"] += _safe_float(row.get("paytm_amount"))
        total["ccms"] += _safe_float(row.get("ccms_amount"))
        total["credit"] += _safe_float(row.get("credit_amount"))
    for k in ["total_sale","cash","paytm","ccms","credit"]:
        total[k] = round(total[k], 2)
    return total

def create_cash_deposit(amount, bank_name, reference_no, deposited_by, deposit_date=None, note=None):
    if _safe_float(amount) <= 0:
        return None, "Cash deposit amount must be greater than 0."
    payload = {"date": deposit_date or _today(), "amount": _safe_float(amount), "bank_name": bank_name, "reference_no": reference_no, "note": note, "deposited_by": deposited_by, "created_at": _now()}
    try:
        r = get_supabase_client().table("cash_deposits").insert(payload).execute()
        return r.data[0] if r.data else None, None
    except Exception as exc:
        print(f"Error in create_cash_deposit: {exc}")
        return None, str(exc)

def get_cash_deposits(entry_date=None):
    try:
        q = get_supabase_client().table("cash_deposits").select("*")
        if entry_date:
            q = q.eq("date", entry_date)
        r = q.order("created_at", desc=True).execute()
        return r.data or []
    except Exception as exc:
        print(f"Error in get_cash_deposits: {exc}")
        return []

def get_cash_deposit_total(entry_date=None):
    return round(sum(_safe_float(r.get("amount")) for r in get_cash_deposits(entry_date or _today())), 2)

def create_paytm_settlement(amount, bank_name, reference_no, settled_by, settlement_date=None, note=None):
    if _safe_float(amount) <= 0:
        return None, "Paytm settled amount must be greater than 0."
    payload = {"date": settlement_date or _today(), "amount": _safe_float(amount), "bank_name": bank_name, "reference_no": reference_no, "note": note, "settled_by": settled_by, "created_at": _now()}
    try:
        r = get_supabase_client().table("paytm_settlements").insert(payload).execute()
        return r.data[0] if r.data else None, None
    except Exception as exc:
        print(f"Error in create_paytm_settlement: {exc}")
        return None, str(exc)

def get_paytm_settlements(entry_date=None):
    try:
        q = get_supabase_client().table("paytm_settlements").select("*")
        if entry_date:
            q = q.eq("date", entry_date)
        r = q.order("created_at", desc=True).execute()
        return r.data or []
    except Exception as exc:
        print(f"Error in get_paytm_settlements: {exc}")
        return []

def get_paytm_settled_total(entry_date=None):
    return round(sum(_safe_float(r.get("amount")) for r in get_paytm_settlements(entry_date or _today())), 2)

def create_ccms_settlement(amount, bank_name, reference_no, settled_by, settlement_date=None, note=None):
    if _safe_float(amount) <= 0:
        return None, "CCMS received amount must be greater than 0."
    payload = {"date": settlement_date or _today(), "amount": _safe_float(amount), "bank_name": bank_name, "reference_no": reference_no, "note": note, "settled_by": settled_by, "created_at": _now()}
    try:
        r = get_supabase_client().table("ccms_settlements").insert(payload).execute()
        return r.data[0] if r.data else None, None
    except Exception as exc:
        print(f"Error in create_ccms_settlement: {exc}")
        return None, str(exc)

def get_ccms_settlements(entry_date=None):
    try:
        q = get_supabase_client().table("ccms_settlements").select("*")
        if entry_date:
            q = q.eq("date", entry_date)
        r = q.order("created_at", desc=True).execute()
        return r.data or []
    except Exception as exc:
        print(f"Error in get_ccms_settlements: {exc}")
        return []

def get_ccms_received_total(entry_date=None):
    return round(sum(_safe_float(r.get("amount")) for r in get_ccms_settlements(entry_date or _today())), 2)

def get_daily_money_summary(entry_date=None):
    entry_date = entry_date or _today()
    p = get_payment_totals(entry_date)
    cash_dep = get_cash_deposit_total(entry_date)
    paytm_set = get_paytm_settled_total(entry_date)
    ccms_rec = get_ccms_received_total(entry_date)
    return {
        "date": entry_date,
        "total_sale": p["total_sale"],
        "cash_sale": p["cash"],
        "paytm_sale": p["paytm"],
        "ccms_sale": p["ccms"],
        "credit_sale": p["credit"],
        "cash_deposited": cash_dep,
        "cash_in_hand": round(p["cash"] - cash_dep, 2),
        "paytm_settled": paytm_set,
        "paytm_pending": round(p["paytm"] - paytm_set, 2),
        "ccms_received": ccms_rec,
        "ccms_pending": round(p["ccms"] - ccms_rec, 2),
        "approved_settlements": p["approved_count"],
    }
