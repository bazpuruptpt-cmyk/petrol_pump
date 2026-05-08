from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client
from database.stock_db import (
    get_tank_by_fuel,
    update_tank_stock,
    get_stock_summary,
    get_fuel_inward,
    get_daily_testing,
    get_stock_closing,
    get_oil_company_ledger,
    create_oil_company_ledger,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _today():
    return date.today().isoformat()


def _f(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


# ---------------- Generic status updates ----------------

def update_row_status(table_name: str, row_id: int, status: str, approved_by: str, note: str = None):
    if status not in ["pending", "approved", "hold", "rejected", "reopened"]:
        return None, "Invalid status."

    payload = {
        "status": status,
        "approved_by": approved_by,
        "approved_at": _now(),
    }

    if note is not None:
        payload["approval_note"] = note

    try:
        result = (
            get_supabase_client()
            .table(table_name)
            .update(payload)
            .eq("id", row_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"Error in update_row_status {table_name}: {exc}")
        return None, str(exc)


# ---------------- Inward Approval ----------------

def get_fuel_inward_by_status(status: str = "pending"):
    try:
        result = (
            get_supabase_client()
            .table("fuel_inward")
            .select("*")
            .eq("status", status)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_fuel_inward_by_status: {exc}")
        return []


def approve_fuel_inward(inward_id: int, manager_id: str, note: str = None):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("fuel_inward")
            .select("*")
            .eq("id", inward_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return None, "Fuel inward not found."

        inward = result.data[0]

        if inward.get("status") == "approved":
            return None, "Fuel inward already approved."

        fuel_type = inward.get("fuel_type")
        qty = _f(inward.get("quantity_liters"))
        amount = _f(inward.get("total_amount"))

        tank = get_tank_by_fuel(fuel_type)
        if not tank:
            return None, f"No active tank found for {fuel_type}."

        new_stock = round(_f(tank.get("current_stock")) + qty, 2)

        if _f(tank.get("capacity_liters")) and new_stock > _f(tank.get("capacity_liters")):
            return None, "Approval blocked: tank capacity exceeded."

        update_tank_stock(fuel_type, new_stock)

        updated, error = update_row_status("fuel_inward", inward_id, "approved", manager_id, note)
        if error:
            return None, error

        # Ledger posting only on approval.
        create_oil_company_ledger(
            oil_company=inward.get("oil_company"),
            txn_type="inward",
            amount=amount,
            reference_no=inward.get("invoice_no"),
            fuel_type=fuel_type,
            quantity_liters=qty,
            created_by=manager_id,
        )

        return updated, None

    except Exception as exc:
        print(f"Error in approve_fuel_inward: {exc}")
        return None, str(exc)


def reject_fuel_inward(inward_id: int, manager_id: str, note: str = None):
    return update_row_status("fuel_inward", inward_id, "rejected", manager_id, note)


def hold_fuel_inward(inward_id: int, manager_id: str, note: str = None):
    return update_row_status("fuel_inward", inward_id, "hold", manager_id, note)


def reopen_fuel_inward(inward_id: int, manager_id: str, note: str = None):
    return update_row_status("fuel_inward", inward_id, "reopened", manager_id, note)


# ---------------- Testing Approval ----------------

def get_testing_by_status(status: str = "pending"):
    try:
        result = (
            get_supabase_client()
            .table("daily_testing")
            .select("*, nozzles:nozzle_id(nozzle_name)")
            .eq("status", status)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_testing_by_status: {exc}")
        return []


def approve_testing(testing_id: int, manager_id: str, note: str = None):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("daily_testing")
            .select("*")
            .eq("id", testing_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return None, "Testing entry not found."

        testing = result.data[0]

        if testing.get("status") == "approved":
            return None, "Testing already approved."

        fuel_type = testing.get("fuel_type")
        liters = _f(testing.get("testing_liters"))
        nozzle_id = testing.get("nozzle_id")
        reading_after = _f(testing.get("reading_after"))

        tank = get_tank_by_fuel(fuel_type)
        if not tank:
            return None, f"No active tank found for {fuel_type}."

        # Testing fuel returns to tank, so add back on approval.
        new_stock = round(_f(tank.get("current_stock")) + liters, 2)
        update_tank_stock(fuel_type, new_stock)

        # Optional nozzle reading update.
        if nozzle_id and reading_after > 0:
            try:
                supabase.table("nozzles").update({"current_reading": reading_after}).eq("id", nozzle_id).execute()
            except Exception as nozzle_exc:
                print(f"Optional nozzle update failed: {nozzle_exc}")

        updated, error = update_row_status("daily_testing", testing_id, "approved", manager_id, note)
        if error:
            return None, error

        return updated, None

    except Exception as exc:
        print(f"Error in approve_testing: {exc}")
        return None, str(exc)


def reject_testing(testing_id: int, manager_id: str, note: str = None):
    return update_row_status("daily_testing", testing_id, "rejected", manager_id, note)


def hold_testing(testing_id: int, manager_id: str, note: str = None):
    return update_row_status("daily_testing", testing_id, "hold", manager_id, note)


def reopen_testing(testing_id: int, manager_id: str, note: str = None):
    return update_row_status("daily_testing", testing_id, "reopened", manager_id, note)


# ---------------- Stock Closing Approval ----------------

def get_stock_closing_by_status(status: str = "pending"):
    try:
        result = (
            get_supabase_client()
            .table("stock_closing")
            .select("*")
            .eq("status", status)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_stock_closing_by_status: {exc}")
        return []


def approve_stock_closing(closing_id: int, manager_id: str, note: str = None):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("stock_closing")
            .select("*")
            .eq("id", closing_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return None, "Stock closing not found."

        closing = result.data[0]

        if closing.get("status") == "approved":
            return None, "Stock closing already approved."

        fuel_type = closing.get("fuel_type")
        physical_stock = _f(closing.get("physical_stock"))

        update_tank_stock(fuel_type, physical_stock)

        updated, error = update_row_status("stock_closing", closing_id, "approved", manager_id, note)
        if error:
            return None, error

        return updated, None

    except Exception as exc:
        print(f"Error in approve_stock_closing: {exc}")
        return None, str(exc)


def reject_stock_closing(closing_id: int, manager_id: str, note: str = None):
    return update_row_status("stock_closing", closing_id, "rejected", manager_id, note)


def hold_stock_closing(closing_id: int, manager_id: str, note: str = None):
    return update_row_status("stock_closing", closing_id, "hold", manager_id, note)


def reopen_stock_closing(closing_id: int, manager_id: str, note: str = None):
    return update_row_status("stock_closing", closing_id, "reopened", manager_id, note)


# ---------------- Reports ----------------

def get_stock_variance_report(entry_date: str = None):
    entry_date = entry_date or _today()
    summary = get_stock_summary(entry_date)

    rows = []

    for fuel_type, row in summary.items():
        rows.append({
            "Date": entry_date,
            "Fuel Type": fuel_type,
            "Opening Stock": row.get("opening_stock"),
            "Inward Stock": row.get("inward_stock"),
            "Meter Sale Liters": row.get("sale_liters"),
            "Testing Return": row.get("testing_liters"),
            "Expected Closing": row.get("expected_closing_stock"),
            "Current/Physical Stock": row.get("current_stock"),
            "Difference": row.get("stock_difference"),
        })

    return rows


def get_stock_movement_report(entry_date: str = None):
    entry_date = entry_date or _today()

    inward = get_fuel_inward(entry_date)
    testing = get_daily_testing(entry_date)
    closing = get_stock_closing(entry_date)

    rows = []

    for r in inward:
        rows.append({
            "Date": r.get("date"),
            "Type": "Inward",
            "Fuel": r.get("fuel_type"),
            "Quantity": _f(r.get("quantity_liters")),
            "Amount": _f(r.get("total_amount")),
            "Status": r.get("status"),
            "Reference": r.get("invoice_no"),
        })

    for r in testing:
        rows.append({
            "Date": r.get("date"),
            "Type": "Testing Return",
            "Fuel": r.get("fuel_type"),
            "Quantity": _f(r.get("testing_liters")),
            "Amount": 0.0,
            "Status": r.get("status"),
            "Reference": r.get("id"),
        })

    for r in closing:
        rows.append({
            "Date": r.get("date"),
            "Type": "Stock Closing",
            "Fuel": r.get("fuel_type"),
            "Quantity": _f(r.get("physical_stock")),
            "Amount": 0.0,
            "Status": r.get("status"),
            "Reference": r.get("id"),
        })

    return rows


def get_stock_approval_summary():
    inward_pending = len(get_fuel_inward_by_status("pending"))
    testing_pending = len(get_testing_by_status("pending"))
    closing_pending = len(get_stock_closing_by_status("pending"))

    return {
        "pending_inward": inward_pending,
        "pending_testing": testing_pending,
        "pending_stock_closing": closing_pending,
        "total_pending": inward_pending + testing_pending + closing_pending,
    }
