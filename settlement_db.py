from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client
from database.profiles_db import get_user_by_id
from database.credit_db import (
    get_credit_transactions_by_reference,
    approve_credit_transactions_by_reference,
)
from database.fuel_rates_db import get_rate_by_fuel
from database.rate_lock_db import get_locked_rate_for_nozzle_assignment
from database.stock_db import get_testing_adjustment_for_assignment, get_tank_by_fuel, update_tank_stock


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


SETTLEMENT_TOLERANCE = 2.0


def is_settlement_matched(difference):
    """
    Settlement tolerance rule:
    Difference -2 se +2 ke beech ho to MATCHED maana jayega.
    """
    try:
        return abs(float(difference or 0)) <= SETTLEMENT_TOLERANCE
    except Exception:
        return False


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

    enriched["payment_total"] = payment_total
    enriched["meter_total_calc"] = meter_total
    enriched["total_sale"] = meter_total
    enriched["match_difference"] = round(meter_total - payment_total, 2)
    enriched["is_matched"] = is_settlement_matched(enriched["match_difference"])
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

        result = query.order("created_at", desc=True).execute()
        return [_enrich_settlement(row) for row in (result.data or [])]
    except Exception as exc:
        print(f"Error in get_settlements_by_date: {exc}")
        return []


def get_existing_settlement_for_shift(shift_id: int, salesman_id: str):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .select("*")
            .eq("shift_id", shift_id)
            .eq("salesman_id", salesman_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return _enrich_settlement(result.data[0]) if result.data else None
    except Exception as exc:
        print(f"Error in get_existing_settlement_for_shift: {exc}")
        return None


def get_active_duties_for_closing():
    """
    Manager Closing Reading tab ke liye active duties laata hai.
    """
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shifts")
            .select("*, profiles:salesman_id(id, name, role, phone)")
            .eq("is_active", True)
            .order("started_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_active_duties_for_closing: {exc}")
        return []


def get_shift_assignments_for_shift(shift_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shift_assignments")
            .select("*, nozzles:nozzle_id(*)")
            .eq("shift_id", shift_id)
            .order("id", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_shift_assignments_for_shift: {exc}")
        return []


def get_shift_assignments_for_settlement(settlement: dict):
    if not settlement:
        return []
    return get_shift_assignments_for_shift(settlement.get("shift_id"))


def get_sale_entries_for_shift(shift_id: int, salesman_id: str):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("sale_entries")
            .select("*, nozzles:nozzle_id(nozzle_name)")
            .eq("shift_id", shift_id)
            .eq("salesman_id", salesman_id)
            .order("entry_time", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_sale_entries_for_shift: {exc}")
        return []


def get_sale_entries_for_settlement(settlement: dict):
    if not settlement:
        return []
    return get_sale_entries_for_shift(settlement.get("shift_id"), settlement.get("salesman_id"))


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


def calculate_closing_meter_rows_from_assignments(assignments: list, closing_inputs: dict, effective_date: str = None):
    if not assignments:
        return [], 0.0, "No nozzle assignments found for this duty."

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
        gross_liters = round(closing - opening, 2)

        testing = get_testing_adjustment_for_assignment(
            assignment_id=assignment_id,
            entry_date=effective_date,
            approved_only=True,
        )

        testing_liters = _safe_float(testing.get("testing_liters"))
        testing_returned = _safe_float(testing.get("returned_liters"))
        testing_loss = _safe_float(testing.get("loss_liters"))

        if testing_liters > gross_liters:
            return [], 0.0, (
                f"Testing liters ({testing_liters}) gross meter liters ({gross_liters}) se zyada hai "
                f"for {nozzle.get('nozzle_name')}."
            )

        actual_liters = round(gross_liters - testing_liters, 2)
        sale_amount = round(actual_liters * rate, 2)

        row = {
            "assignment_id": assignment_id,
            "nozzle_id": assignment.get("nozzle_id"),
            "nozzle_name": nozzle.get("nozzle_name"),
            "fuel_type": fuel_type,
            "opening": opening,
            "closing": closing,
            "gross_liters": gross_liters,
            "testing_adj": testing_liters,
            "testing_liters": testing_liters,
            "testing_returned_liters": testing_returned,
            "testing_loss_liters": testing_loss,
            "actual_liters": actual_liters,
            "net_sale_liters": actual_liters,
            "rate": rate,
            "sale_amount": sale_amount,
        }

        meter_total += sale_amount
        rows.append(row)

    return rows, round(meter_total, 2), None


def calculate_closing_meter_rows(settlement: dict, closing_inputs: dict):
    assignments = get_shift_assignments_for_settlement(settlement)
    return calculate_closing_meter_rows_from_assignments(assignments, closing_inputs, settlement.get('date'))


def save_manager_closing_for_shift(shift_id: int, salesman_id: str, closing_inputs: dict, manager_id: str):
    """
    Direct visible meter reading tab ka save function.
    Settlement/payment breakup ho ya na ho, manager closing reading save kar sakta hai.
    """
    supabase = get_supabase_client()

    assignments = get_shift_assignments_for_shift(shift_id)
    nozzle_rows, meter_total, error = calculate_closing_meter_rows_from_assignments(assignments, closing_inputs, date.today().isoformat())

    if error:
        return None, error

    existing = get_existing_settlement_for_shift(shift_id, salesman_id)

    cash_amount = _safe_float(existing.get("cash_amount")) if existing else 0.0
    paytm_amount = _safe_float(existing.get("paytm_amount")) if existing else 0.0
    ccms_amount = _safe_float(existing.get("ccms_amount")) if existing else 0.0
    credit_amount = _safe_float(existing.get("credit_amount")) if existing else 0.0

    payment_total = round(cash_amount + paytm_amount + ccms_amount + credit_amount, 2)
    difference = round(meter_total - payment_total, 2)

    try:
        for row in nozzle_rows:
            supabase.table("shift_assignments").update({
                "closing_reading": row["closing"],
            }).eq("id", row["assignment_id"]).execute()

            # Next duty opening reading will come from this value.
            supabase.table("nozzles").update({
                "current_reading": row["closing"],
            }).eq("id", row["nozzle_id"]).execute()

        payload = {
            "shift_id": shift_id,
            "salesman_id": salesman_id,
            "date": date.today().isoformat(),
            "nozzle_readings": nozzle_rows,
            "meter_total": meter_total,
            "entries_total": payment_total,
            "difference": difference,
            "cash_amount": cash_amount,
            "paytm_amount": paytm_amount,
            "ccms_amount": ccms_amount,
            "credit_amount": credit_amount,
            "status": existing.get("status") if existing else "pending",
            "manager_note": "Manager closing readings saved",
        }

        if existing:
            result = (
                supabase.table("settlements")
                .update(payload)
                .eq("id", existing["id"])
                .execute()
            )
        else:
            payload["created_at"] = _now()
            result = supabase.table("settlements").insert(payload).execute()

        saved = result.data[0] if result.data else None
        return _enrich_settlement(saved), None

    except Exception as exc:
        print(f"Error in save_manager_closing_for_shift: {exc}")
        return None, str(exc)




def _sale_stock_deduction_totals(nozzle_rows):
    """
    Approved sale stock effect:
    Sale liters = net/actual sale liters after testing subtraction.

    Testing returned to tank ka stock effect 0 hai.
    Isliye stock sirf actual_liters / net_sale_liters se kam hoga.
    """
    totals = {"petrol": 0.0, "diesel": 0.0}

    for row in nozzle_rows or []:
        ft = row.get("fuel_type")
        if ft not in totals:
            continue

        liters = _safe_float(row.get("actual_liters") or row.get("net_sale_liters"))

        if liters <= 0:
            gross = _safe_float(row.get("gross_liters"))
            testing = _safe_float(row.get("testing_liters") or row.get("testing_adj"))
            liters = round(gross - testing, 2)

        if liters > 0:
            totals[ft] += liters

    return {k: round(v, 2) for k, v in totals.items()}


def deduct_stock_for_approved_settlement(settlement, manager_id=None):
    """
    Manager approval ke time petrol/diesel stock reduce karta hai.

    Logic:
    - settlement.nozzle_readings me fuel-wise net sale liters already available hain.
    - Petrol sale -> petrol tank current_stock minus
    - Diesel sale -> diesel tank current_stock minus
    - Testing liters already sale se minus hain, isliye double minus nahi hoga.
    """
    if not settlement:
        return None, "Settlement not found."

    if settlement.get("stock_deducted") is True:
        return {
            "petrol": 0.0,
            "diesel": 0.0,
            "already_deducted": True,
        }, None

    nozzle_rows = settlement.get("nozzle_readings") or []
    totals = _sale_stock_deduction_totals(nozzle_rows)

    if totals.get("petrol", 0) <= 0 and totals.get("diesel", 0) <= 0:
        return None, "No sale liters found for stock deduction."

    updated = {}

    for fuel_type, sale_liters in totals.items():
        if sale_liters <= 0:
            continue

        tank = get_tank_by_fuel(fuel_type)
        if not tank:
            return None, f"{fuel_type} tank not found. Stock setup check karo."

        current_stock = _safe_float(tank.get("current_stock"))
        new_stock = round(current_stock - sale_liters, 2)

        if new_stock < -0.001:
            return None, (
                f"{fuel_type} stock insufficient. "
                f"Current: {current_stock} L, Sale: {sale_liters} L."
            )

        row, err = update_tank_stock(fuel_type, new_stock)
        if err:
            return None, err

        updated[fuel_type] = {
            "old_stock": current_stock,
            "sale_liters": sale_liters,
            "new_stock": new_stock,
        }

    return updated, None

def save_manager_closing_readings(settlement_id: int, closing_inputs: dict, manager_id: str):
    settlement = get_settlement_by_id(settlement_id)

    if not settlement:
        return None, "Settlement not found."

    if settlement.get("status") == "approved":
        return None, "Approved settlement cannot be changed."

    return save_manager_closing_for_shift(
        shift_id=settlement.get("shift_id"),
        salesman_id=settlement.get("salesman_id"),
        closing_inputs=closing_inputs,
        manager_id=manager_id,
    )


def approve_settlement(settlement_id: int, manager_id: str):
    settlement = get_settlement_by_id(settlement_id)

    if not settlement:
        return None, "Settlement not found."

    if settlement.get("status") == "approved":
        return None, "Settlement already approved."

    if not settlement.get("closing_saved"):
        return None, "Save manager closing readings before approval."

    if not settlement.get("is_matched"):
        return None, "Difference is outside ±₹2 tolerance. Hold/reopen instead of approve."

    supabase = get_supabase_client()

    # Stock deduction must happen before approval.
    # If stock is not available, approval block rahega.
    stock_effect, stock_err = deduct_stock_for_approved_settlement(settlement, manager_id)
    if stock_err:
        return None, f"Approval blocked: {stock_err}"

    try:
        approval_payload = {
            "status": "approved",
            "approved_by": manager_id,
            "approved_at": _now(),
            "stock_deducted": True,
            "stock_deducted_at": _now(),
            "stock_deducted_by": manager_id,
            "stock_effect": stock_effect,
        }

        try:
            result = (
                supabase.table("settlements")
                .update(approval_payload)
                .eq("id", settlement_id)
                .execute()
            )
        except Exception:
            # If SQL columns not added yet, approval should still work.
            # But SQL_SALE_STOCK_DEDUCTION_COLUMNS.sql run karna recommended hai.
            fallback_payload = {
                "status": "approved",
                "approved_by": manager_id,
                "approved_at": _now(),
            }
            result = (
                supabase.table("settlements")
                .update(fallback_payload)
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
