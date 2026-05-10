from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client


def _truthy_active(row):
    if row is None:
        return False
    if 'is_active' not in row:
        return True
    if row.get('is_active') is None:
        return True
    return bool(row.get('is_active'))

from database.duties_db import get_duty_by_salesman, get_shift_assignments
from database.fuel_rates_db import get_rate_by_fuel
from database.rate_lock_db import get_locked_rate_for_sale, get_shift_date
from database.credit_db import get_active_parties, create_credit_sale_transaction

def _is_live_sale(row):
    return (row.get("status") or "pending") not in ["rejected", "cancelled"]


def get_assigned_nozzles_for_salesman(salesman_id: str):
    """
    Salesman dropdown valid nozzle rules:
    - active duty
    - active assignment
    - active nozzle
    - same salesman
    - approved settlement locks current batch
    """
    supabase = get_supabase_client()

    try:
        duty_rows = (
            supabase.table("shifts")
            .select("*")
            .eq("salesman_id", salesman_id)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )

        if not duty_rows:
            return None, []

        duty = duty_rows[0]

        try:
            existing_rows = (
                supabase.table("settlements")
                .select("*")
                .eq("shift_id", duty.get("id"))
                .order("created_at", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            if existing_rows and existing_rows[0].get("status") == "approved":
                return duty, []
        except Exception:
            pass

        rows = (
            supabase.table("shift_assignments")
            .select("*, nozzles:nozzle_id(*)")
            .eq("shift_id", duty.get("id"))
            .eq("salesman_id", salesman_id)
            .eq("is_active", True)
            .order("id")
            .execute()
            .data
            or []
        )

        nozzles = []

        for row in rows:
            nozzle = row.get("nozzles") or {}

            if not nozzle:
                continue

            if not _truthy_active(nozzle):
                continue

            nozzles.append({
                "assignment_id": row.get("id"),
                "shift_id": duty.get("id"),
                "salesman_id": salesman_id,
                "nozzle_id": nozzle.get("id") or row.get("nozzle_id"),
                "nozzle_name": nozzle.get("nozzle_name"),
                "fuel_type": nozzle.get("fuel_type"),
                "opening_reading": row.get("opening_reading"),
                "current_reading": nozzle.get("current_reading"),
            })

        return duty, nozzles

    except Exception as exc:
        print(f"get_assigned_nozzles_for_salesman error: {exc}")
        return None, []


def calculate_sale_amount(liters: float, rate: float) -> float:
    return round(float(liters or 0) * float(rate or 0), 2)


def get_current_rate_for_nozzle(nozzle: dict):
    fuel_type = nozzle.get("fuel_type")
    rate_row = get_rate_by_fuel(fuel_type)

    if not rate_row:
        return None

    return float(rate_row.get("price_per_liter") or 0)


def create_nozzle_sale_entry(data: dict):
    supabase = get_supabase_client()
    liters = _safe_float(data.get("liters"))
    if liters <= 0:
        return None, "Liters must be greater than 0."
    shift_id = data.get("shift_id")
    fuel_type = data.get("fuel_type")
    shift_date = get_shift_date(shift_id)
    locked_rate, rate_snapshot = get_locked_rate_for_sale(fuel_type, shift_date)
    if locked_rate is None:
        return None, f"Fuel rate missing for {fuel_type} on {shift_date or 'shift date'}."
    rate = locked_rate
    amount = calculate_sale_amount(liters, rate)
    payload = {
        "shift_id": data["shift_id"],
        "nozzle_id": data["nozzle_id"],
        "salesman_id": data["salesman_id"],
        "date": data.get("date") or date.today().isoformat(),
        "entry_time": data.get("entry_time") or datetime.now(timezone.utc).isoformat(),
        "fuel_type": data["fuel_type"],
        "liters": liters,
        "rate": rate,
        "locked_rate": rate,
        "rate_date": shift_date,
        "rate_snapshot": rate_snapshot,
        "amount": amount,
        "payment_mode": None,
        "credit_party_id": None,
        "vehicle_number": None,
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
        print(f"Error in create_nozzle_sale_entry: {exc}")
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


def get_active_shift_entries_for_salesman(salesman_id: str):
    duty = get_duty_by_salesman(salesman_id)

    if not duty:
        return None, []

    rows = get_entries_by_shift(duty["id"])
    rows = [r for r in rows if r.get("salesman_id") == salesman_id and _is_live_sale(r)]
    return duty, rows


def get_shift_sale_summary_for_salesman(salesman_id: str):
    duty, rows = get_active_shift_entries_for_salesman(salesman_id)

    summary = {
        "shift_id": duty.get("id") if duty else None,
        "total_sale": 0.0,
        "total_liters": 0.0,
        "entry_count": len(rows),
        "pending_count": 0,
        "approved_count": 0,
        "rejected_count": 0,
    }

    for row in rows:
        amount = float(row.get("amount") or 0)
        liters = float(row.get("liters") or 0)
        status = row.get("status") or "pending"

        summary["total_sale"] += amount
        summary["total_liters"] += liters

        if status == "pending":
            summary["pending_count"] += 1
        elif status == "approved":
            summary["approved_count"] += 1
        elif status == "rejected":
            summary["rejected_count"] += 1

    summary["total_sale"] = round(summary["total_sale"], 2)
    summary["total_liters"] = round(summary["total_liters"], 2)

    return summary


def get_salesman_nozzle_sale_summary(salesman_id: str):
    duty, rows = get_active_shift_entries_for_salesman(salesman_id)

    summary = {}

    for row in rows:
        nozzle = row.get("nozzles") or {}
        nozzle_id = row.get("nozzle_id")
        nozzle_name = nozzle.get("nozzle_name") or f"Nozzle {nozzle_id}"

        if nozzle_id not in summary:
            summary[nozzle_id] = {
                "Nozzle": nozzle_name,
                "Liters": 0.0,
                "Amount": 0.0,
                "Entries": 0,
            }

        summary[nozzle_id]["Liters"] += float(row.get("liters") or 0)
        summary[nozzle_id]["Amount"] += float(row.get("amount") or 0)
        summary[nozzle_id]["Entries"] += 1

    for row in summary.values():
        row["Liters"] = round(row["Liters"], 2)
        row["Amount"] = round(row["Amount"], 2)

    return list(summary.values())


def calculate_payment_match(total_sale: float, cash: float, paytm: float, ccms: float, credit: float):
    total_sale = round(float(total_sale or 0), 2)
    cash = round(float(cash or 0), 2)
    paytm = round(float(paytm or 0), 2)
    ccms = round(float(ccms or 0), 2)
    credit = round(float(credit or 0), 2)

    payment_total = round(cash + paytm + ccms + credit, 2)
    difference = round(total_sale - payment_total, 2)

    return {
        "total_sale": total_sale,
        "cash": cash,
        "paytm": paytm,
        "ccms": ccms,
        "credit": credit,
        "payment_total": payment_total,
        "difference": difference,
        "is_matched": abs(difference) < 0.01,
    }


def get_latest_payment_breakup(shift_id: int, salesman_id: str = None):
    """
    settlements.shift_id unique hai.
    Existing breakup ko shift_id se hi find karo.
    """
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .select("*")
            .eq("shift_id", shift_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in get_latest_payment_breakup: {exc}")
        return None


def save_payment_breakup(
    salesman_id: str,
    cash_amount: float,
    paytm_amount: float,
    ccms_amount: float,
    credit_allocations: list,
):
    """
    Shift-level payment breakup save karega.
    Total sale = nozzle sale entries ka sum.
    Cash/Paytm/CCMS/Credit alag se salesman final entry karega.
    Credit allocations creditor ledger me pending entry ke form me jayengi.
    """

    duty, rows = get_active_shift_entries_for_salesman(salesman_id)

    if not duty:
        return None, "No active duty found."

    total_sale = round(sum(float(r.get("amount") or 0) for r in rows), 2)

    valid_credit_allocations = []
    credit_amount = 0.0

    for item in credit_allocations or []:
        party_id = item.get("party_id")
        amount = float(item.get("amount") or 0)
        vehicle_number = item.get("vehicle_number")

        if party_id and amount > 0:
            valid_credit_allocations.append({
                "party_id": party_id,
                "amount": amount,
                "vehicle_number": vehicle_number,
            })
            credit_amount += amount

    match = calculate_payment_match(
        total_sale=total_sale,
        cash=cash_amount,
        paytm=paytm_amount,
        ccms=ccms_amount,
        credit=credit_amount,
    )

    if not match["is_matched"]:
        return None, "Cash + Paytm + CCMS + Credit must match total sale before approval."

    nozzle_rows = get_salesman_nozzle_sale_summary(salesman_id)

    payload = {
        "shift_id": duty["id"],
        "salesman_id": salesman_id,
        "date": date.today().isoformat(),
        "nozzle_readings": nozzle_rows,
        "meter_total": total_sale,
        "entries_total": total_sale,
        "difference": match["difference"],
        "cash_amount": match["cash"],
        "paytm_amount": match["paytm"],
        "ccms_amount": match["ccms"],
        "credit_amount": match["credit"],
        "status": "pending",
        "manager_note": "Salesman payment breakup submitted",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    supabase = get_supabase_client()

    try:
        existing = get_latest_payment_breakup(duty["id"], salesman_id)

        if existing:
            existing_status = existing.get("status")

            if existing_status == "approved":
                return None, "This shift is already approved. Manager must reopen before resubmission."

            if existing_status in ["pending", "hold"]:
                return None, "This breakup is already sent for approval. Manager must approve/reject/reopen."

            update_payload = payload.copy()
            update_payload.pop("created_at", None)

            result = (
                supabase.table("settlements")
                .update(update_payload)
                .eq("id", existing["id"])
                .execute()
            )
            settlement = result.data[0] if result.data else None
        else:
            try:
                result = (
                    supabase.table("settlements")
                    .insert(payload)
                    .execute()
                )
                settlement = result.data[0] if result.data else None
            except Exception as insert_exc:
                msg = str(insert_exc)
                if "settlements_shift_id_key" in msg or "duplicate key" in msg:
                    existing = get_latest_payment_breakup(duty["id"], salesman_id)
                    if existing:
                        if existing.get("status") in ["pending", "hold", "approved"]:
                            return None, "This shift is already submitted/approved. Manager action required."

                        update_payload = payload.copy()
                        update_payload.pop("created_at", None)
                        result = (
                            supabase.table("settlements")
                            .update(update_payload)
                            .eq("id", existing["id"])
                            .execute()
                        )
                        settlement = result.data[0] if result.data else None
                    else:
                        raise insert_exc
                else:
                    raise insert_exc

        if not settlement:
            return None, "Payment breakup save failed."

        # Credit amount creditor ledger me pending reference ke saath post.
        # Note: current_balance approval phase me update hoga.
        for item in valid_credit_allocations:
            create_credit_sale_transaction(
                party_id=item["party_id"],
                amount=item["amount"],
                reference_id=settlement["id"],
                fuel_type=None,
                liters=0,
                vehicle_number=item.get("vehicle_number"),
                status="pending",
            )

        return settlement, None

    except Exception as exc:
        print(f"Error in save_payment_breakup: {exc}")
        return None, str(exc)


def get_credit_party_wise_breakup_from_allocations(credit_allocations: list):
    parties = get_active_parties()
    party_name_by_id = {p.get("id"): p.get("name") for p in parties}

    rows = []
    for item in credit_allocations or []:
        party_id = item.get("party_id")
        amount = float(item.get("amount") or 0)
        if party_id and amount > 0:
            rows.append({
                "Creditor": party_name_by_id.get(party_id) or f"Party ID {party_id}",
                "Credit Amount": round(amount, 2),
                "Vehicle Number": item.get("vehicle_number"),
            })
    return rows
