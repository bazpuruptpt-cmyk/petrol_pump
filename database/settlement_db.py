from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client
from database.profiles_db import get_user_by_id
from database.credit_db import (
    get_credit_transactions_by_reference,
    approve_credit_transactions_by_reference,
)
from database.fuel_rates_db import get_rate_by_fuel


SETTLEMENT_STATUSES = ["pending", "approved", "hold", "reopened"]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _payment_total(row: dict):
    return round(
        _safe_float(row.get("cash_amount"))
        + _safe_float(row.get("paytm_amount"))
        + _safe_float(row.get("ccms_amount"))
        + _safe_float(row.get("credit_amount")),
        2,
    )


def _enrich_settlement(row: dict):
    if not row:
        return row

    salesman = get_user_by_id(row.get("salesman_id"))
    enriched = dict(row)
    enriched["salesman_name"] = salesman.get("name") if salesman else row.get("salesman_id")
    enriched["salesman_phone"] = salesman.get("phone") if salesman else None

    payment_total = _payment_total(row)
    meter_total = round(_safe_float(row.get("meter_total")), 2)

    # If manager closing reading has not been saved yet, meter_total can be 0.
    # For display, use entries_total only as submitted payment reference if needed.
    enriched["payment_total"] = payment_total
    enriched["meter_total_calc"] = meter_total
    enriched["total_sale"] = meter_total
    enriched["match_difference"] = round(meter_total - payment_total, 2)
    enriched["is_matched"] = abs(enriched["match_difference"]) < 0.01
    enriched["closing_saved"] = bool(row.get("nozzle_readings")) and meter_total > 0

    return enriched


def get_settlement_by_id(settlement_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .select("*")
            .eq("id", settlement_id)
            .limit(1)
            .execute()
        )

        return _enrich_settlement(result.data[0]) if result.data else None
    except Exception as exc:
        print(f"Error in get_settlement_by_id: {exc}")
        return None


def get_pending_settlements():
    return get_settlements_by_status("pending")


def get_settlements_by_status(status: str):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .select("*")
            .eq("status", status)
            .order("created_at", desc=True)
            .execute()
        )

        return [_enrich_settlement(row) for row in (result.data or [])]
    except Exception as exc:
        print(f"Error in get_settlements_by_status: {exc}")
        return []


def get_settlements_by_date(entry_date: str = None):
    supabase = get_supabase_client()

    try:
        query = supabase.table("settlements").select("*")

        if entry_date:
            query = query.eq("date", entry_date)

        result = (
            query
            .order("created_at", desc=True)
            .execute()
        )

        return [_enrich_settlement(row) for row in (result.data or [])]
    except Exception as exc:
        print(f"Error in get_settlements_by_date: {exc}")
        return []


def get_sale_entries_for_settlement(settlement: dict):
    if not settlement:
        return []

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("sale_entries")
            .select("*, nozzles:nozzle_id(nozzle_name)")
            .eq("shift_id", settlement.get("shift_id"))
            .eq("salesman_id", settlement.get("salesman_id"))
            .order("entry_time", desc=True)
            .execute()
        )

        return result.data or []
    except Exception as exc:
        print(f"Error in get_sale_entries_for_settlement: {exc}")
        return []


def get_credit_rows_for_settlement(settlement_id: int):
    return get_credit_transactions_by_reference(settlement_id)


def get_manager_payment_summary(entry_date: str = None):
    rows = get_settlements_by_date(entry_date or date.today().isoformat())

    summary = {
        "pending_count": 0,
        "approved_count": 0,
        "hold_count": 0,
        "reopened_count": 0,
        "total_sale": 0.0,
        "cash": 0.0,
        "paytm": 0.0,
        "ccms": 0.0,
        "credit": 0.0,
    }

    for row in rows:
        status = row.get("status") or "pending"
        if status == "pending":
            summary["pending_count"] += 1
        elif status == "approved":
            summary["approved_count"] += 1
        elif status == "hold":
            summary["hold_count"] += 1
        elif status == "reopened":
            summary["reopened_count"] += 1

        summary["total_sale"] += _safe_float(row.get("meter_total"))
        summary["cash"] += _safe_float(row.get("cash_amount"))
        summary["paytm"] += _safe_float(row.get("paytm_amount"))
        summary["ccms"] += _safe_float(row.get("ccms_amount"))
        summary["credit"] += _safe_float(row.get("credit_amount"))

    for key in ["total_sale", "cash", "paytm", "ccms", "credit"]:
        summary[key] = round(summary[key], 2)

    return summary


def get_shift_assignments_for_settlement(settlement: dict):
    """
    Manager closing reading entry ke liye shift ke assigned nozzles laata hai.
    Active filter intentionally nahi lagaya gaya, kyunki duty end hone ke baad bhi
    historical assignment settlement me dikhna chahiye.
    """
    if not settlement:
        return []

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shift_assignments")
            .select("*, nozzles:nozzle_id(*)")
            .eq("shift_id", settlement.get("shift_id"))
            .order("id", desc=False)
            .execute()
        )

        return result.data or []
    except Exception as exc:
        print(f"Error in get_shift_assignments_for_settlement: {exc}")
        return []


def calculate_closing_meter_rows(settlement: dict, closing_inputs: dict):
    """
    closing_inputs format:
    {
      assignment_id: closing_reading
    }

    Formula:
    actual_liters = closing_reading - opening_reading
    sale_amount = actual_liters × latest fuel rate
    """
    assignments = get_shift_assignments_for_settlement(settlement)

    if not assignments:
        return [], 0.0, "No nozzle assignments found for this shift."

    rows = []
    meter_total = 0.0

    for assignment in assignments:
        assignment_id = assignment.get("id")
        nozzle = assignment.get("nozzles") or {}

        opening = _safe_float(assignment.get("opening_reading"))
        closing = _safe_float(closing_inputs.get(assignment_id))

        if closing <= 0:
            return [], 0.0, f"Closing reading required for {nozzle.get('nozzle_name') or assignment_id}."

        if closing < opening:
            return [], 0.0, f"Closing reading cannot be less than opening for {nozzle.get('nozzle_name')}."

        fuel_type = nozzle.get("fuel_type")
        rate_row = get_rate_by_fuel(fuel_type)

        if not rate_row:
            return [], 0.0, f"Fuel rate missing for {fuel_type}."

        rate = _safe_float(rate_row.get("price_per_liter"))
        actual_liters = round(closing - opening, 2)
        sale_amount = round(actual_liters * rate, 2)

        row = {
            "assignment_id": assignment_id,
            "nozzle_id": assignment.get("nozzle_id"),
            "nozzle_name": nozzle.get("nozzle_name"),
            "fuel_type": fuel_type,
            "opening": opening,
            "closing": closing,
            "testing_adj": 0.0,
            "actual_liters": actual_liters,
            "rate": rate,
            "sale_amount": sale_amount,
        }

        meter_total += sale_amount
        rows.append(row)

    return rows, round(meter_total, 2), None


def save_manager_closing_readings(settlement_id: int, closing_inputs: dict, manager_id: str):
    """
    Manager closing readings save karta hai.
    Effects:
    - shift_assignments.closing_reading update
    - nozzles.current_reading update, so next duty opening becomes this closing
    - settlements.nozzle_readings update
    - settlements.meter_total = closing-based total
    - settlements.entries_total = salesman payment breakup total
    - settlements.difference = meter_total - payment_breakup_total
    """
    settlement = get_settlement_by_id(settlement_id)

    if not settlement:
        return None, "Settlement not found."

    if settlement.get("status") == "approved":
        return None, "Approved settlement cannot be changed."

    nozzle_rows, meter_total, error = calculate_closing_meter_rows(settlement, closing_inputs)

    if error:
        return None, error

    payment_total = _payment_total(settlement)
    difference = round(meter_total - payment_total, 2)

    supabase = get_supabase_client()

    try:
        # Update each assignment closing and nozzle current reading
        for row in nozzle_rows:
            supabase.table("shift_assignments").update({
                "closing_reading": row["closing"],
            }).eq("id", row["assignment_id"]).execute()

            # Next duty opening reading will come from nozzles.current_reading
            supabase.table("nozzles").update({
                "current_reading": row["closing"],
            }).eq("id", row["nozzle_id"]).execute()

        result = (
            supabase.table("settlements")
            .update({
                "nozzle_readings": nozzle_rows,
                "meter_total": meter_total,
                "entries_total": payment_total,
                "difference": difference,
                "manager_note": "Manager closing readings saved",
            })
            .eq("id", settlement_id)
            .execute()
        )

        updated = result.data[0] if result.data else None
        return _enrich_settlement(updated), None

    except Exception as exc:
        print(f"Error in save_manager_closing_readings: {exc}")
        return None, str(exc)


def approve_settlement(settlement_id: int, manager_id: str):
    """
    Settlement approve:
    - closing readings must be saved
    - difference must be zero
    - settlement status approved
    - related sale_entries status approved
    - related credit_transactions status approved
    - credit_party current_balance update
    """
    settlement = get_settlement_by_id(settlement_id)

    if not settlement:
        return None, "Settlement not found."

    if settlement.get("status") == "approved":
        return None, "Settlement already approved."

    if not settlement.get("closing_saved"):
        return None, "Save manager closing readings before approval."

    if not settlement.get("is_matched"):
        return None, "Difference is not zero. Hold/reopen instead of approve."

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .update({
                "status": "approved",
                "approved_by": manager_id,
                "approved_at": _now(),
            })
            .eq("id", settlement_id)
            .execute()
        )

        approved_settlement = result.data[0] if result.data else None

        try:
            supabase.table("sale_entries").update({
                "status": "approved",
                "approved_by": manager_id,
                "approved_at": _now(),
            }).eq("shift_id", settlement.get("shift_id")).eq(
                "salesman_id", settlement.get("salesman_id")
            ).execute()
        except Exception as sale_exc:
            print(f"Error approving sale entries: {sale_exc}")

        try:
            approve_credit_transactions_by_reference(settlement_id, manager_id)
        except Exception as credit_exc:
            print(f"Error approving credit transactions: {credit_exc}")

        return approved_settlement, None

    except Exception as exc:
        print(f"Error in approve_settlement: {exc}")
        return None, str(exc)


def hold_settlement(settlement_id: int, manager_id: str, note: str = ""):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .update({
                "status": "hold",
                "manager_note": note or "Held by manager",
                "approved_by": manager_id,
                "approved_at": _now(),
            })
            .eq("id", settlement_id)
            .execute()
        )

        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"Error in hold_settlement: {exc}")
        return None, str(exc)


def reopen_settlement(settlement_id: int, manager_id: str, note: str = ""):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .update({
                "status": "reopened",
                "manager_note": note or "Reopened by manager",
                "approved_by": manager_id,
                "approved_at": _now(),
            })
            .eq("id", settlement_id)
            .execute()
        )

        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"Error in reopen_settlement: {exc}")
        return None, str(exc)
