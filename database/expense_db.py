from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client

EXPENSE_CATEGORIES = ["salary","electricity","maintenance","transport","office","bank_charges","rent","misc"]
PAYMENT_MODES = ["cash", "bank", "upi", "paytm", "ccms", "other"]

def _now(): return datetime.now(timezone.utc).isoformat()
def _today(): return date.today().isoformat()
def _f(v):
    try: return float(v or 0)
    except Exception: return 0.0

def create_expense(data):
    amount = _f(data.get("amount"))
    if amount <= 0: return None, "Expense amount must be greater than 0."
    if not data.get("category"): return None, "Expense category required."
    if not data.get("payment_mode"): return None, "Payment mode required."

    payload = {
        "date": data.get("date") or _today(),
        "category": data.get("category"),
        "description": data.get("description"),
        "amount": amount,
        "payment_mode": data.get("payment_mode"),
        "bank_name": data.get("bank_name"),
        "reference_no": data.get("reference_no"),
        "status": "pending",
        "created_by": data.get("created_by"),
        "created_at": _now(),
    }

    try:
        r = get_supabase_client().table("expenses").insert(payload).execute()
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("create_expense", e)
        return None, str(e)

def get_expenses(entry_date=None, status=None, payment_mode=None):
    try:
        q = get_supabase_client().table("expenses").select("*")
        if entry_date: q = q.eq("date", entry_date)
        if status: q = q.eq("status", status)
        if payment_mode: q = q.eq("payment_mode", payment_mode)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_expenses", e)
        return []

def get_expense_by_id(expense_id):
    try:
        r = get_supabase_client().table("expenses").select("*").eq("id", expense_id).limit(1).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        print("get_expense_by_id", e)
        return None

def update_expense_status(expense_id, status, approved_by, note=None):
    if status not in ["pending","approved","hold","rejected","reopened"]:
        return None, "Invalid status."

    payload = {
        "status": status,
        "approved_by": approved_by,
        "approved_at": _now(),
        "approval_note": note,
    }

    try:
        r = get_supabase_client().table("expenses").update(payload).eq("id", expense_id).execute()
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("update_expense_status", e)
        return None, str(e)

def approve_expense(expense_id, approved_by, note=None):
    exp = get_expense_by_id(expense_id)
    if not exp: return None, "Expense not found."
    if exp.get("status") == "approved": return None, "Expense already approved."
    return update_expense_status(expense_id, "approved", approved_by, note)

def reject_expense(expense_id, approved_by, note=None): return update_expense_status(expense_id, "rejected", approved_by, note)
def hold_expense(expense_id, approved_by, note=None): return update_expense_status(expense_id, "hold", approved_by, note)
def reopen_expense(expense_id, approved_by, note=None): return update_expense_status(expense_id, "reopened", approved_by, note)

def get_expense_summary(entry_date=None):
    rows = get_expenses(entry_date=entry_date, status="approved")
    s = {"total_expense":0.0}
    for c in EXPENSE_CATEGORIES:
        s[c] = 0.0

    for r in rows:
        c = r.get("category") or "misc"
        amt = _f(r.get("amount"))
        s["total_expense"] += amt
        s[c if c in s else "misc"] += amt

    return {k: round(v, 2) for k, v in s.items()}

def get_expense_category_report(entry_date=None):
    s = get_expense_summary(entry_date)
    rows = [{"Category": c, "Amount": round(_f(s.get(c)),2)} for c in EXPENSE_CATEGORIES]
    rows.append({"Category": "TOTAL", "Amount": round(_f(s.get("total_expense")),2)})
    return rows

def get_expense_payment_mode_report(entry_date=None):
    rows = get_expenses(entry_date=entry_date, status="approved")
    out = {m: 0.0 for m in PAYMENT_MODES}
    out["total"] = 0.0

    for r in rows:
        mode = r.get("payment_mode") or "other"
        amount = _f(r.get("amount"))
        if mode not in out:
            mode = "other"
        out[mode] += amount
        out["total"] += amount

    report = []
    for mode in PAYMENT_MODES:
        report.append({"Payment Mode": mode, "Amount": round(out.get(mode, 0), 2)})
    report.append({"Payment Mode": "TOTAL", "Amount": round(out["total"], 2)})
    return report

def get_cash_bank_expense_summary(entry_date=None):
    rows = get_expenses(entry_date=entry_date, status="approved")

    s = {
        "cash_expense": 0.0,
        "bank_expense": 0.0,
        "upi_expense": 0.0,
        "paytm_expense": 0.0,
        "ccms_expense": 0.0,
        "other_expense": 0.0,
        "total_expense": 0.0,
    }

    for r in rows:
        mode = r.get("payment_mode") or "other"
        amount = _f(r.get("amount"))
        key = f"{mode}_expense"
        if key not in s:
            key = "other_expense"
        s[key] += amount
        s["total_expense"] += amount

    return {k: round(v, 2) for k, v in s.items()}

def get_pending_expense_count():
    return len(get_expenses(status="pending"))

def _money(entry_date=None):
    try:
        from database.payment_db import get_daily_money_summary
        return get_daily_money_summary(entry_date)
    except Exception as e:
        print("money unavailable", e)
        return {"total_sale":0,"cash_sale":0,"paytm_sale":0,"ccms_sale":0,"credit_sale":0,"cash_deposited":0,"cash_in_hand":0}

def _purchase(entry_date=None):
    try:
        q = get_supabase_client().table("fuel_inward").select("*").eq("status", "approved")
        if entry_date:
            q = q.eq("date", entry_date)
        rows = q.execute().data or []
        out = {"total_purchase":0.0,"petrol_purchase":0.0,"diesel_purchase":0.0}
        for r in rows:
            amt = _f(r.get("total_amount"))
            out["total_purchase"] += amt
            if r.get("fuel_type") == "petrol": out["petrol_purchase"] += amt
            if r.get("fuel_type") == "diesel": out["diesel_purchase"] += amt
        return {k: round(v,2) for k,v in out.items()}
    except Exception as e:
        print("purchase", e)
        return {"total_purchase":0,"petrol_purchase":0,"diesel_purchase":0}

def get_profit_loss_report(entry_date=None):
    entry_date = entry_date or _today()
    m = _money(entry_date)
    p = _purchase(entry_date)
    e = get_expense_summary(entry_date)
    mode = get_cash_bank_expense_summary(entry_date)

    gross = _f(m.get("total_sale"))
    purchase = _f(p.get("total_purchase"))
    expenses = _f(e.get("total_expense"))

    return {
        "date": entry_date,
        "gross_sale": round(gross,2),
        "cash_sale": round(_f(m.get("cash_sale")),2),
        "paytm_sale": round(_f(m.get("paytm_sale")),2),
        "ccms_sale": round(_f(m.get("ccms_sale")),2),
        "credit_sale": round(_f(m.get("credit_sale")),2),
        "cash_deposited": round(_f(m.get("cash_deposited")), 2),
        "cash_expense": round(_f(mode.get("cash_expense")), 2),
        "bank_expense": round(_f(mode.get("bank_expense")), 2),
        "upi_expense": round(_f(mode.get("upi_expense")), 2),
        "paytm_expense": round(_f(mode.get("paytm_expense")), 2),
        "purchase_cost": round(purchase,2),
        "petrol_purchase": round(_f(p.get("petrol_purchase")),2),
        "diesel_purchase": round(_f(p.get("diesel_purchase")),2),
        "gross_margin": round(gross - purchase,2),
        "total_expense": round(expenses,2),
        "net_profit": round(gross - purchase - expenses,2),
        "pending_expenses": get_pending_expense_count(),
    }

def get_profit_loss_rows(entry_date=None):
    r = get_profit_loss_report(entry_date)
    return [
        {"Particular":"Gross Sale","Amount":r["gross_sale"]},
        {"Particular":"Cash Sale","Amount":r["cash_sale"]},
        {"Particular":"Paytm Sale","Amount":r["paytm_sale"]},
        {"Particular":"CCMS Sale","Amount":r["ccms_sale"]},
        {"Particular":"Credit Sale","Amount":r["credit_sale"]},
        {"Particular":"Purchase Cost","Amount":r["purchase_cost"]},
        {"Particular":"Gross Margin","Amount":r["gross_margin"]},
        {"Particular":"Cash Expense", "Amount": r["cash_expense"]},
        {"Particular":"Bank Expense", "Amount": r["bank_expense"]},
        {"Particular":"UPI Expense", "Amount": r["upi_expense"]},
        {"Particular":"Paytm Expense", "Amount": r["paytm_expense"]},
        {"Particular":"Approved Expenses","Amount":r["total_expense"]},
        {"Particular":"Net Profit / Loss","Amount":r["net_profit"]},
    ]
