from datetime import date
from config.supabase_client import get_supabase_client
from database.payment_db import get_daily_money_summary
from database.credit_db import get_all_parties, get_credit_transactions


def _today():
    return date.today().isoformat()


def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_num(value):
    return round(_safe_float(value), 2)


def get_settlements_for_date(entry_date=None):
    entry_date = entry_date or _today()
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .select("*")
            .eq("date", entry_date)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_settlements_for_date: {exc}")
        return []


def get_profiles_map():
    supabase = get_supabase_client()

    try:
        result = supabase.table("profiles").select("id, name, role, phone").execute()
        rows = result.data or []
        return {r.get("id"): r for r in rows}
    except Exception as exc:
        print(f"Error in get_profiles_map: {exc}")
        return {}


def get_daily_closing_report(entry_date=None):
    entry_date = entry_date or _today()
    money = get_daily_money_summary(entry_date)
    settlements = get_settlements_for_date(entry_date)

    status_count = {"pending": 0, "approved": 0, "hold": 0, "reopened": 0}
    total_difference = 0.0

    for s in settlements:
        status = s.get("status") or "pending"
        if status in status_count:
            status_count[status] += 1
        total_difference += _safe_float(s.get("difference"))

    return {
        "date": entry_date,
        "total_sale": money.get("total_sale", 0),
        "cash_sale": money.get("cash_sale", 0),
        "cash_deposited": money.get("cash_deposited", 0),
        "cash_in_hand": money.get("cash_in_hand", 0),
        "paytm_sale": money.get("paytm_sale", 0),
        "paytm_settled": money.get("paytm_settled", 0),
        "paytm_pending": money.get("paytm_pending", 0),
        "ccms_sale": money.get("ccms_sale", 0),
        "ccms_received": money.get("ccms_received", 0),
        "ccms_pending": money.get("ccms_pending", 0),
        "credit_sale": money.get("credit_sale", 0),
        "approved_settlements": status_count["approved"],
        "pending_settlements": status_count["pending"],
        "hold_settlements": status_count["hold"],
        "reopened_settlements": status_count["reopened"],
        "total_difference": round(total_difference, 2),
    }


def get_salesman_wise_report(entry_date=None):
    entry_date = entry_date or _today()
    settlements = get_settlements_for_date(entry_date)
    profiles = get_profiles_map()

    rows = []

    for s in settlements:
        profile = profiles.get(s.get("salesman_id"), {})
        payment_total = (
            _safe_float(s.get("cash_amount"))
            + _safe_float(s.get("paytm_amount"))
            + _safe_float(s.get("ccms_amount"))
            + _safe_float(s.get("credit_amount"))
        )

        rows.append({
            "Settlement ID": s.get("id"),
            "Shift ID": s.get("shift_id"),
            "Salesman": profile.get("name") or s.get("salesman_id"),
            "Status": s.get("status"),
            "Meter Sale": _fmt_num(s.get("meter_total")),
            "Cash": _fmt_num(s.get("cash_amount")),
            "Paytm": _fmt_num(s.get("paytm_amount")),
            "CCMS": _fmt_num(s.get("ccms_amount")),
            "Credit": _fmt_num(s.get("credit_amount")),
            "Payment Total": _fmt_num(payment_total),
            "Difference": _fmt_num(s.get("difference")),
            "Created At": s.get("created_at"),
            "Approved At": s.get("approved_at"),
        })

    return rows


def get_nozzle_wise_report(entry_date=None):
    entry_date = entry_date or _today()
    settlements = get_settlements_for_date(entry_date)
    profiles = get_profiles_map()

    rows = []

    for s in settlements:
        salesman = profiles.get(s.get("salesman_id"), {}).get("name") or s.get("salesman_id")
        readings = s.get("nozzle_readings") or []

        if not isinstance(readings, list):
            continue

        for r in readings:
            rows.append({
                "Date": s.get("date"),
                "Settlement ID": s.get("id"),
                "Shift ID": s.get("shift_id"),
                "Salesman": salesman,
                "Nozzle": r.get("nozzle_name"),
                "Fuel": r.get("fuel_type"),
                "Opening": _fmt_num(r.get("opening")),
                "Closing": _fmt_num(r.get("closing")),
                "Actual Liters": _fmt_num(r.get("actual_liters")),
                "Rate": _fmt_num(r.get("rate")),
                "Sale Amount": _fmt_num(r.get("sale_amount")),
                "Status": s.get("status"),
            })

    return rows


def get_creditor_report():
    parties = get_all_parties()
    txns = get_credit_transactions()

    party_map = {p.get("id"): p for p in parties}
    report = {}

    for p in parties:
        pid = p.get("id")
        report[pid] = {
            "Creditor ID": pid,
            "Creditor": p.get("name"),
            "Phone": p.get("phone"),
            "Credit Limit": _fmt_num(p.get("credit_limit")),
            "Current Balance": _fmt_num(p.get("current_balance")),
            "Approved Sales": 0.0,
            "Approved Payments": 0.0,
            "Pending Sales": 0.0,
            "Pending Payments": 0.0,
            "Status": "Active" if p.get("is_active") else "Inactive",
        }

    for t in txns:
        pid = t.get("party_id")
        if pid not in report:
            p = party_map.get(pid, {})
            report[pid] = {
                "Creditor ID": pid,
                "Creditor": p.get("name") or f"Party {pid}",
                "Phone": p.get("phone"),
                "Credit Limit": _fmt_num(p.get("credit_limit")),
                "Current Balance": _fmt_num(p.get("current_balance")),
                "Approved Sales": 0.0,
                "Approved Payments": 0.0,
                "Pending Sales": 0.0,
                "Pending Payments": 0.0,
                "Status": "Unknown",
            }

        amount = _safe_float(t.get("amount"))
        status = t.get("status") or "pending"
        txn_type = t.get("type")

        if status == "approved" and txn_type == "sale":
            report[pid]["Approved Sales"] += amount
        elif status == "approved" and txn_type == "payment_received":
            report[pid]["Approved Payments"] += amount
        elif status == "pending" and txn_type == "sale":
            report[pid]["Pending Sales"] += amount
        elif status == "pending" and txn_type == "payment_received":
            report[pid]["Pending Payments"] += amount

    for row in report.values():
        for key in ["Approved Sales", "Approved Payments", "Pending Sales", "Pending Payments"]:
            row[key] = round(row[key], 2)

    return list(report.values())


def get_credit_ledger_report(status=None, txn_type=None):
    txns = get_credit_transactions(status=status, txn_type=txn_type)
    rows = []

    for t in txns:
        party = t.get("credit_parties") or {}
        rows.append({
            "Txn ID": t.get("id"),
            "Date": t.get("date"),
            "Creditor": party.get("name"),
            "Type": t.get("type"),
            "Amount": _fmt_num(t.get("amount")),
            "Mode": t.get("payment_mode"),
            "Status": t.get("status"),
            "Reference": t.get("reference_id"),
            "Created At": t.get("created_at"),
            "Approved At": t.get("approved_at"),
        })

    return rows
