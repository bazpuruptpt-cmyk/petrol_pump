from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client
from database.duties_db import get_duty_by_salesman, get_shift_assignments
from database.fuel_rates_db import get_rate_by_fuel


VALID_PAYMENT_MODES = ["cash", "paytm", "ccms", "credit"]


def get_assigned_nozzles_for_salesman(salesman_id: str):
    """
    Active duty ke assigned active nozzles return karega.
    """
    duty = get_duty_by_salesman(salesman_id)

    if not duty:
        return None, []

    assignments = get_shift_assignments(duty["id"])

    output = []
    for assignment in assignments:
        nozzle = assignment.get("nozzles") or {}
        if not nozzle:
            continue

        if not bool(nozzle.get("is_active", True)):
            continue

        output.append({
            "assignment_id": assignment.get("id"),
            "shift_id": duty.get("id"),
            "salesman_id": salesman_id,
            "nozzle_id": nozzle.get("id"),
            "nozzle_name": nozzle.get("nozzle_name"),
            "fuel_type": nozzle.get("fuel_type"),
            "opening_reading": assignment.get("opening_reading"),
            "current_reading": nozzle.get("current_reading"),
        })

    return duty, output


def calculate_sale_amount(liters: float, rate: float) -> float:
    return round(float(liters or 0) * float(rate or 0), 2)


def create_sale_entry(data: dict):
    """
    Salesman sale entry create karega.
    Entry default pending rahegi; manager later approve/reject karega.
    """

    required = ["shift_id", "nozzle_id", "salesman_id", "fuel_type", "liters", "rate", "payment_mode"]

    for field in required:
        if data.get(field) in [None, ""]:
            return None, f"{field} required."

    if data["payment_mode"] not in VALID_PAYMENT_MODES:
        return None, "Invalid payment mode."

    liters = float(data.get("liters") or 0)
    rate = float(data.get("rate") or 0)

    if liters <= 0:
        return None, "Liters must be greater than 0."

    if rate <= 0:
        return None, "Rate must be greater than 0."

    if data["payment_mode"] == "credit" and not data.get("credit_party_id"):
        return None, "Credit party required for credit sale."

    payload = {
        "shift_id": data["shift_id"],
        "nozzle_id": data["nozzle_id"],
        "salesman_id": data["salesman_id"],
        "date": data.get("date") or date.today().isoformat(),
        "entry_time": data.get("entry_time") or datetime.now(timezone.utc).isoformat(),
        "fuel_type": data["fuel_type"],
        "liters": liters,
        "rate": rate,
        "amount": calculate_sale_amount(liters, rate),
        "payment_mode": data["payment_mode"],
        "credit_party_id": data.get("credit_party_id"),
        "vehicle_number": data.get("vehicle_number"),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("sale_entries")
            .insert(payload)
            .execute()
        )

        sale = result.data[0] if result.data else None
        return sale, None

    except Exception as exc:
        print(f"Error in create_sale_entry: {exc}")
        return None, str(exc)


def get_entries_by_salesman(salesman_id: str, entry_date: str = None):
    supabase = get_supabase_client()

    try:
        query = (
            supabase.table("sale_entries")
            .select("*, nozzles:nozzle_id(nozzle_name)")
            .eq("salesman_id", salesman_id)
        )

        if entry_date:
            query = query.eq("date", entry_date)

        result = (
            query
            .order("entry_time", desc=True)
            .execute()
        )

        return result.data or []

    except Exception as exc:
        print(f"Error in get_entries_by_salesman: {exc}")
        return []


def get_entries_by_shift(shift_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("sale_entries")
            .select("*, nozzles:nozzle_id(nozzle_name)")
            .eq("shift_id", shift_id)
            .order("entry_time", desc=True)
            .execute()
        )
        return result.data or []

    except Exception as exc:
        print(f"Error in get_entries_by_shift: {exc}")
        return []


def get_salesman_today_summary(salesman_id: str):
    rows = get_entries_by_salesman(salesman_id, date.today().isoformat())

    summary = {
        "cash": 0.0,
        "paytm": 0.0,
        "ccms": 0.0,
        "credit": 0.0,
        "total": 0.0,
        "pending_count": 0,
        "approved_count": 0,
        "rejected_count": 0,
        "entry_count": len(rows),
    }

    for row in rows:
        mode = row.get("payment_mode")
        amount = float(row.get("amount") or 0)
        status = row.get("status") or "pending"

        if mode in summary:
            summary[mode] += amount

        summary["total"] += amount

        if status == "pending":
            summary["pending_count"] += 1
        elif status == "approved":
            summary["approved_count"] += 1
        elif status == "rejected":
            summary["rejected_count"] += 1

    return summary


def get_current_rate_for_nozzle(nozzle: dict):
    fuel_type = nozzle.get("fuel_type")
    rate_row = get_rate_by_fuel(fuel_type)

    if not rate_row:
        return None

    return float(rate_row.get("price_per_liter") or 0)
