from datetime import date, timedelta
from config.supabase_client import get_supabase_client


def _today():
    return date.today().isoformat()


def _f(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _profiles_map():
    try:
        rows = get_supabase_client().table("profiles").select("id, name, role").execute().data or []
        return {r.get("id"): r for r in rows}
    except Exception:
        return {}


def _name(user_id, profiles=None):
    profiles = profiles or _profiles_map()
    return (profiles.get(user_id) or {}).get("name") or user_id or "-"


def get_salesman_approval_summary(salesman_id, entry_date=None):
    """
    Salesman view:
    - Entered sale = nozzle entries created by salesman.
    - Pending transfer = submitted settlement but not approved.
    - Approved sale/payment = only manager-approved settlement.
    """
    entry_date = entry_date or _today()

    try:
        entries = (
            get_supabase_client()
            .table("sale_entries")
            .select("*")
            .eq("salesman_id", salesman_id)
            .eq("date", entry_date)
            .execute()
            .data
            or []
        )
    except Exception:
        entries = []

    try:
        settlements = (
            get_supabase_client()
            .table("settlements")
            .select("*")
            .eq("salesman_id", salesman_id)
            .eq("date", entry_date)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception:
        settlements = []

    entered_sale = round(sum(_f(r.get("amount")) for r in entries), 2)
    entered_liters = round(sum(_f(r.get("liters")) for r in entries), 2)

    latest = settlements[0] if settlements else None
    approved = [s for s in settlements if s.get("status") == "approved"]
    approved_latest = approved[0] if approved else None

    pending_statuses = ["pending", "hold", "reopened"]
    pending = [s for s in settlements if (s.get("status") or "pending") in pending_statuses]
    pending_latest = pending[0] if pending else None

    def totals(row):
        if not row:
            return {"cash": 0.0, "paytm": 0.0, "ccms": 0.0, "credit": 0.0, "payment": 0.0, "sale": 0.0}
        cash = _f(row.get("cash_amount"))
        paytm = _f(row.get("paytm_amount"))
        ccms = _f(row.get("ccms_amount"))
        credit = _f(row.get("credit_amount"))
        return {
            "cash": round(cash, 2),
            "paytm": round(paytm, 2),
            "ccms": round(ccms, 2),
            "credit": round(credit, 2),
            "payment": round(cash + paytm + ccms + credit, 2),
            "sale": round(_f(row.get("meter_total") or row.get("entries_total")), 2),
        }

    pending_t = totals(pending_latest)
    approved_t = totals(approved_latest)

    return {
        "date": entry_date,
        "entered_sale": entered_sale,
        "entered_liters": entered_liters,
        "entry_count": len(entries),

        "latest_status": (latest or {}).get("status") if latest else "not submitted",

        "pending_sale": pending_t["sale"],
        "pending_cash_transfer": pending_t["cash"],
        "pending_payment_total": pending_t["payment"],

        "approved_sale": approved_t["sale"],
        "approved_cash": approved_t["cash"],
        "approved_paytm": approved_t["paytm"],
        "approved_ccms": approved_t["ccms"],
        "approved_credit": approved_t["credit"],
        "approved_payment_total": approved_t["payment"],
    }


def get_salesman_daywise_approval_summary(salesman_id, start_date=None, end_date=None):
    if not end_date:
        end_date = _today()
    if not start_date:
        start_date = (date.today() - timedelta(days=29)).isoformat()

    try:
        entries = (
            get_supabase_client()
            .table("sale_entries")
            .select("*")
            .eq("salesman_id", salesman_id)
            .gte("date", start_date)
            .lte("date", end_date)
            .execute()
            .data
            or []
        )
    except Exception:
        entries = []

    try:
        settlements = (
            get_supabase_client()
            .table("settlements")
            .select("*")
            .eq("salesman_id", salesman_id)
            .gte("date", start_date)
            .lte("date", end_date)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception:
        settlements = []

    by_date = {}

    def init(d):
        by_date.setdefault(d, {
            "Date": d,
            "Entered Sale": 0.0,
            "Liters": 0.0,
            "Entries": 0,
            "Pending Cash Transfer": 0.0,
            "Approved Sale": 0.0,
            "Approved Cash": 0.0,
            "Approved Paytm": 0.0,
            "Approved CCMS": 0.0,
            "Approved Credit": 0.0,
            "Status": "not submitted",
        })
        return by_date[d]

    for e in entries:
        d = e.get("date")
        if not d:
            continue
        r = init(d)
        r["Entered Sale"] += _f(e.get("amount"))
        r["Liters"] += _f(e.get("liters"))
        r["Entries"] += 1

    seen_shift = set()
    for s in settlements:
        sid = s.get("shift_id")
        if sid in seen_shift:
            continue
        seen_shift.add(sid)
        d = s.get("date")
        if not d:
            continue
        r = init(d)
        status = s.get("status") or "pending"
        r["Status"] = status

        if status in ["pending", "hold", "reopened"]:
            r["Pending Cash Transfer"] += _f(s.get("cash_amount"))

        if status == "approved":
            r["Approved Sale"] += _f(s.get("meter_total") or s.get("entries_total"))
            r["Approved Cash"] += _f(s.get("cash_amount"))
            r["Approved Paytm"] += _f(s.get("paytm_amount"))
            r["Approved CCMS"] += _f(s.get("ccms_amount"))
            r["Approved Credit"] += _f(s.get("credit_amount"))

    out = []
    for d in sorted(by_date.keys(), reverse=True):
        r = by_date[d]
        for k in r:
            if isinstance(r[k], float):
                r[k] = round(r[k], 2)
        out.append(r)

    return out


def get_manager_cash_transfer_summary(entry_date=None):
    """
    Manager dashboard/settlement:
    Pending cash transfer = salesman submitted cash, manager not approved.
    Approved cash transfer = cash moved to manager after approval.
    """
    entry_date = entry_date or _today()
    profiles = _profiles_map()

    try:
        rows = (
            get_supabase_client()
            .table("settlements")
            .select("*")
            .eq("date", entry_date)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []

    seen_shift = set()
    dedup = []
    for r in rows:
        sid = r.get("shift_id")
        if sid in seen_shift:
            continue
        seen_shift.add(sid)
        dedup.append(r)

    summary = {
        "date": entry_date,
        "pending_cash_transfer": 0.0,
        "approved_cash_transfer": 0.0,
        "pending_count": 0,
        "approved_count": 0,
        "rows": [],
    }

    for r in dedup:
        status = r.get("status") or "pending"
        cash = _f(r.get("cash_amount"))
        item = {
            "Date": r.get("date"),
            "Shift": r.get("shift_id"),
            "Salesman": _name(r.get("salesman_id"), profiles),
            "Cash Transfer": round(cash, 2),
            "Paytm": round(_f(r.get("paytm_amount")), 2),
            "CCMS": round(_f(r.get("ccms_amount")), 2),
            "Credit": round(_f(r.get("credit_amount")), 2),
            "Status": status,
        }

        if status in ["pending", "hold", "reopened"]:
            summary["pending_cash_transfer"] += cash
            summary["pending_count"] += 1
            summary["rows"].append(item)

        if status == "approved":
            summary["approved_cash_transfer"] += cash
            summary["approved_count"] += 1
            summary["rows"].append(item)

    summary["pending_cash_transfer"] = round(summary["pending_cash_transfer"], 2)
    summary["approved_cash_transfer"] = round(summary["approved_cash_transfer"], 2)
    return summary
