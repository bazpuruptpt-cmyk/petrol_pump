from datetime import date
from config.supabase_client import get_supabase_client

from database.settlement_db import (
    get_settlements_by_status,
    get_settlements_by_date,
    get_settlement_by_id,
    get_shift_assignments_for_settlement,
    calculate_closing_meter_rows,
    save_manager_closing_readings,
    approve_settlement,
    hold_settlement,
    reopen_settlement,
)
from database.credit_db import reject_credit_transactions_by_reference


def _today():
    return date.today().isoformat()


def _f(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _payment_total(row):
    return round(
        _f(row.get("cash_amount"))
        + _f(row.get("paytm_amount"))
        + _f(row.get("ccms_amount"))
        + _f(row.get("credit_amount")),
        2,
    )


def _profiles_map():
    try:
        rows = get_supabase_client().table("profiles").select("id, name, role, phone").execute().data or []
        return {r.get("id"): r for r in rows}
    except Exception:
        return {}


def _name(user_id, profiles=None):
    profiles = profiles or _profiles_map()
    return (profiles.get(user_id) or {}).get("name") or user_id or "-"


def get_sale_entries_for_shift(shift_id):
    try:
        return (
            get_supabase_client()
            .table("sale_entries")
            .select("*, nozzles:nozzle_id(nozzle_name, fuel_type)")
            .eq("shift_id", shift_id)
            .neq("status", "rejected")
            .order("entry_time", desc=True)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(f"get_sale_entries_for_shift error: {exc}")
        return []


def get_credit_rows_for_settlement(settlement_id):
    try:
        return (
            get_supabase_client()
            .table("credit_transactions")
            .select("*, credit_parties:party_id(name, phone, current_balance)")
            .eq("reference_id", str(settlement_id))
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(f"get_credit_rows_for_settlement error: {exc}")
        return []


def build_fuel_summary(entries):
    grouped = {}

    for row in entries:
        nozzle = row.get("nozzles") or {}
        fuel = row.get("fuel_type") or nozzle.get("fuel_type") or "-"

        if fuel not in grouped:
            grouped[fuel] = {
                "Fuel": fuel,
                "Liters": 0.0,
                "Amount": 0.0,
                "Entries": 0,
            }

        grouped[fuel]["Liters"] += _f(row.get("liters"))
        grouped[fuel]["Amount"] += _f(row.get("amount"))
        grouped[fuel]["Entries"] += 1

    out = []
    for r in grouped.values():
        r["Liters"] = round(r["Liters"], 2)
        r["Amount"] = round(r["Amount"], 2)
        out.append(r)

    return out


def enrich_sale_approval(row, profiles=None):
    if not row:
        return row

    profiles = profiles or _profiles_map()

    entries = get_sale_entries_for_shift(row.get("shift_id"))
    credit_rows = get_credit_rows_for_settlement(row.get("id"))

    salesman_entry_total = round(sum(_f(e.get("amount")) for e in entries), 2)
    salesman_entry_liters = round(sum(_f(e.get("liters")) for e in entries), 2)

    payment_total = _payment_total(row)
    meter_total = round(_f(row.get("meter_total")), 2)
    closing_saved = bool(row.get("nozzle_readings")) and meter_total > 0

    # Approval ka real difference manager meter reading se niklega.
    meter_payment_difference = round(meter_total - payment_total, 2)

    # Salesman entered sale vs manager meter sale optional cross-check.
    salesman_meter_difference = round(meter_total - salesman_entry_total, 2) if closing_saved else None

    return {
        **row,
        "salesman_name": _name(row.get("salesman_id"), profiles),
        "salesman_entry_total": salesman_entry_total,
        "salesman_entry_liters": salesman_entry_liters,
        "salesman_entry_count": len(entries),
        "fuel_summary": build_fuel_summary(entries),
        "credit_rows": credit_rows,
        "payment_total": payment_total,
        "meter_total_calc": meter_total,
        "closing_saved": closing_saved,
        "meter_payment_difference": meter_payment_difference,
        "salesman_meter_difference": salesman_meter_difference,
        "is_meter_payment_matched": closing_saved and abs(meter_payment_difference) < 0.01,
        "is_salesman_meter_matched": closing_saved and abs(salesman_meter_difference or 0) < 0.01,
        "can_approve": closing_saved and abs(meter_payment_difference) < 0.01,
    }


def get_pending_sale_approvals(entry_date=None):
    statuses = ["pending", "hold", "reopened"]
    rows = []
    for status in statuses:
        rows.extend(get_settlements_by_status(status))

    if entry_date:
        rows = [r for r in rows if r.get("date") == entry_date]

    profiles = _profiles_map()
    return [enrich_sale_approval(r, profiles) for r in rows]


def get_sale_approvals(status=None, entry_date=None):
    if entry_date:
        rows = get_settlements_by_date(entry_date)
        if status:
            rows = [r for r in rows if (r.get("status") or "pending") == status]
    elif status:
        rows = get_settlements_by_status(status)
    else:
        rows = get_settlements_by_date(_today())

    profiles = _profiles_map()
    return [enrich_sale_approval(r, profiles) for r in rows]


def get_approval_detail(settlement_id):
    row = get_settlement_by_id(settlement_id)
    return enrich_sale_approval(row) if row else None


def get_closing_assignments_for_approval(settlement_id):
    settlement = get_settlement_by_id(settlement_id)
    if not settlement:
        return None, [], "Sale approval not found."

    assignments = get_shift_assignments_for_settlement(settlement)
    return settlement, assignments, None


def preview_closing_calculation(settlement_id, closing_inputs):
    settlement = get_settlement_by_id(settlement_id)
    if not settlement:
        return [], 0.0, "Sale approval not found."

    return calculate_closing_meter_rows(settlement, closing_inputs)


def save_closing_for_approval(settlement_id, closing_inputs, manager_id):
    return save_manager_closing_readings(settlement_id, closing_inputs, manager_id)


def approve_sale_approval(settlement_id, manager_id=None, note=None):
    """
    Main approval rule:
    Manager closing reading saved honi chahiye.
    Meter sale = Cash + Paytm + CCMS + Credit hona chahiye.
    approve_settlement() already:
    - closing_saved check karta hai
    - difference zero check karta hai
    - sale_entries approve karta hai
    - credit ledger approve/post karta hai
    """
    detail = get_approval_detail(settlement_id)
    if not detail:
        return None, "Sale approval not found."

    if not detail.get("closing_saved"):
        return None, "Closing reading required before approval."

    if not detail.get("is_meter_payment_matched"):
        return None, "Approval blocked: Meter sale and salesman breakup are not matched."

    return approve_settlement(settlement_id, manager_id)


def reject_sale_approval(settlement_id, manager_id=None, note=None):
    """
    Full reject rule:
    Manager reject kare to salesman ko fresh entry karni padegi.

    Effects:
    1. Current shift ke salesman sale_entries rejected.
    2. Settlement rejected.
    3. Creditor fuel credit rows rejected.
    4. Creditor cash_given rows rejected.
    """
    supabase = get_supabase_client()

    detail = get_approval_detail(settlement_id)
    if not detail:
        return None, "Sale approval not found."

    if detail.get("status") == "approved":
        return None, "Approved sale cannot be rejected."

    shift_id = detail.get("shift_id")
    salesman_id = detail.get("salesman_id")
    rejection_note = note or "Rejected by manager. Salesman must enter fresh sale."

    try:
        sale_query = (
            supabase.table("sale_entries")
            .update({"status": "rejected"})
            .eq("shift_id", shift_id)
        )

        if salesman_id:
            sale_query = sale_query.eq("salesman_id", salesman_id)

        sale_query.execute()

        rejected_credit_rows, credit_errors = reject_credit_transactions_by_reference(
            settlement_id,
            manager_id,
            rejection_note,
        )
        if credit_errors:
            print("Credit reject cleanup errors:", credit_errors)

        result = (
            supabase.table("settlements")
            .update({
                "status": "rejected",
                "manager_note": rejection_note,
            })
            .eq("id", settlement_id)
            .execute()
        )

        return result.data[0] if result.data else None, None

    except Exception as exc:
        return None, str(exc)


def hold_sale_approval(settlement_id, manager_id=None, note=None):
    return hold_settlement(settlement_id, manager_id, note or "Held by manager")


def reopen_sale_approval(settlement_id, manager_id=None, note=None):
    return reopen_settlement(settlement_id, manager_id, note or "Reopened by manager")


def get_manager_day_summary(entry_date=None):
    entry_date = entry_date or _today()
    approved = get_sale_approvals(status="approved", entry_date=entry_date)

    summary = {
        "date": entry_date,
        "total_sale": 0.0,
        "total_liters": 0.0,
        "cash": 0.0,
        "paytm": 0.0,
        "ccms": 0.0,
        "credit": 0.0,
        "approval_count": len(approved),
        "fuel_rows": {},
        "credit_rows": [],
        "salesman_rows": [],
    }

    salesman_group = {}

    for row in approved:
        meter_sale = _f(row.get("meter_total_calc"))
        summary["total_sale"] += meter_sale
        summary["total_liters"] += _f(row.get("salesman_entry_liters"))
        summary["cash"] += _f(row.get("cash_amount"))
        summary["paytm"] += _f(row.get("paytm_amount"))
        summary["ccms"] += _f(row.get("ccms_amount"))
        summary["credit"] += _f(row.get("credit_amount"))

        sm = row.get("salesman_name")
        salesman_group.setdefault(sm, {
            "Salesman": sm,
            "Meter Sale": 0.0,
            "Liters": 0.0,
            "Cash": 0.0,
            "Paytm": 0.0,
            "CCMS": 0.0,
            "Credit": 0.0,
        })
        salesman_group[sm]["Meter Sale"] += meter_sale
        salesman_group[sm]["Liters"] += _f(row.get("salesman_entry_liters"))
        salesman_group[sm]["Cash"] += _f(row.get("cash_amount"))
        salesman_group[sm]["Paytm"] += _f(row.get("paytm_amount"))
        salesman_group[sm]["CCMS"] += _f(row.get("ccms_amount"))
        salesman_group[sm]["Credit"] += _f(row.get("credit_amount"))

        for f in row.get("fuel_summary") or []:
            fuel = f.get("Fuel")
            summary["fuel_rows"].setdefault(fuel, {
                "Fuel": fuel,
                "Liters": 0.0,
                "Amount": 0.0,
                "Entries": 0,
            })
            summary["fuel_rows"][fuel]["Liters"] += _f(f.get("Liters"))
            summary["fuel_rows"][fuel]["Amount"] += _f(f.get("Amount"))
            summary["fuel_rows"][fuel]["Entries"] += int(f.get("Entries") or 0)

        for c in row.get("credit_rows") or []:
            party = c.get("credit_parties") or {}
            summary["credit_rows"].append({
                "Salesman": row.get("salesman_name"),
                "Creditor": party.get("name") or c.get("party_id"),
                "Amount": round(_f(c.get("amount")), 2),
                "Status": c.get("status"),
                "Reference": c.get("reference_id"),
            })

    for k in ["total_sale", "total_liters", "cash", "paytm", "ccms", "credit"]:
        summary[k] = round(summary[k], 2)

    summary["fuel_rows"] = list(summary["fuel_rows"].values())
    for r in summary["fuel_rows"]:
        r["Liters"] = round(r["Liters"], 2)
        r["Amount"] = round(r["Amount"], 2)

    summary["salesman_rows"] = list(salesman_group.values())
    for r in summary["salesman_rows"]:
        for key in ["Meter Sale", "Liters", "Cash", "Paytm", "CCMS", "Credit"]:
            r[key] = round(r[key], 2)

    return summary
