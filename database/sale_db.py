from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client
from database.duties_db import get_duty_by_salesman, get_shift_assignments
from database.fuel_rates_db import get_rate_by_fuel
from database.credit_db import add_pending_credit_sale


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
    Payment mode: cash/paytm/ccms/credit.
    Credit sale par credit_transactions me pending ledger row create hogi.
    """

    required = ["shift_id", "nozzle_id", "salesman_id", "fuel_type", "liters", "rate", "payment_mode"]

    for field in required:
        if data.get(field) in [None, ""]:
            return None, f"{field} required."

    if data["payment_mode"] not in VALID_PAYMENT_MODES:
        return None, "Invalid payment mode."

    liters = float(data.get("liters") or 0)
    rate = float(data.get("rate") or 0)
    amount = calculate_sale_amount(liters, rate)

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
        "amount": amount,
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

        if not sale:
            return None, "Sale insert failed."

        if data["payment_mode"] == "credit":
            ledger, ledger_error = add_pending_credit_sale(
                party_id=data.get("credit_party_id"),
                sale_entry_id=sale.get("id"),
                fuel_type=data["fuel_type"],
                liters=liters,
                amount=amount,
            )

            if ledger_error:
                return sale, f"Sale saved, but credit ledger failed: {ledger_error}"

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


def get_salesman_nozzle_summary(salesman_id: str, entry_date: str = None):
    """
    Salesman ke saare assigned/nozzle-wise sales ka combined summary.
    """
    rows = get_entries_by_salesman(salesman_id, entry_date or date.today().isoformat())

    summary = {}

    for row in rows:
        nozzle = row.get("nozzles") or {}
        nozzle_name = nozzle.get("nozzle_name") or f"Nozzle {row.get('nozzle_id')}"
        amount = float(row.get("amount") or 0)
        liters = float(row.get("liters") or 0)
        mode = row.get("payment_mode")

        if nozzle_name not in summary:
            summary[nozzle_name] = {
                "Nozzle": nozzle_name,
                "Liters": 0.0,
                "Cash": 0.0,
                "Paytm": 0.0,
                "CCMS": 0.0,
                "Credit": 0.0,
                "Total": 0.0,
            }

        summary[nozzle_name]["Liters"] += liters
        summary[nozzle_name]["Total"] += amount

        if mode == "cash":
            summary[nozzle_name]["Cash"] += amount
        elif mode == "paytm":
            summary[nozzle_name]["Paytm"] += amount
        elif mode == "ccms":
            summary[nozzle_name]["CCMS"] += amount
        elif mode == "credit":
            summary[nozzle_name]["Credit"] += amount

    return list(summary.values())


def get_current_rate_for_nozzle(nozzle: dict):
    fuel_type = nozzle.get("fuel_type")
    rate_row = get_rate_by_fuel(fuel_type)

    if not rate_row:
        return None

    return float(rate_row.get("price_per_liter") or 0)
