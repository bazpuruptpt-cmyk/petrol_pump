from datetime import date
from config.supabase_client import get_supabase_client
from database.fuel_rates_db import get_rate_by_fuel


def _f(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _today():
    return date.today().isoformat()


def get_shift_date(shift_id):
    try:
        rows = (get_supabase_client().table("shifts").select("date").eq("id", shift_id).limit(1).execute().data or [])
        return (rows[0] if rows else {}).get("date")
    except Exception:
        return None


def get_locked_rate_for_sale(fuel_type, shift_date=None):
    """Pick rate for a new sale, then save it in sale_entries.locked_rate."""
    shift_date = shift_date or _today()
    row = get_rate_by_fuel(fuel_type, shift_date)
    if not row:
        return None, None
    rate = _f(row.get("price_per_liter"))
    snapshot = {
        "fuel_type": fuel_type,
        "locked_rate": rate,
        "rate_date": row.get("effective_from") or shift_date,
        "source": "fuel_rates",
        "rate_id": row.get("id"),
    }
    return rate, snapshot


def get_locked_rate_for_nozzle_assignment(assignment, settlement_date=None):
    """
    Manager closing reading uses the already-frozen sale-entry rate.
    It does not recalculate old sale by the current fuel_rates table.
    """
    shift_id = assignment.get("shift_id")
    nozzle_id = assignment.get("nozzle_id")
    fuel_type = (assignment.get("nozzles") or {}).get("fuel_type") or assignment.get("fuel_type")
    try:
        rows = (get_supabase_client().table("sale_entries").select("*").eq("shift_id", shift_id).eq("nozzle_id", nozzle_id).neq("status", "rejected").order("entry_time", desc=False).execute().data or [])
    except Exception:
        rows = []
    rows = [r for r in rows if (r.get("status") or "pending") not in ["rejected", "cancelled"]]
    if rows:
        total_liters = sum(_f(r.get("liters")) for r in rows)
        total_amount = sum(_f(r.get("amount")) for r in rows)
        if total_liters > 0 and total_amount > 0:
            rate = round(total_amount / total_liters, 6)
        else:
            rate = _f(rows[0].get("locked_rate") or rows[0].get("rate"))
        return rate, {
            "fuel_type": fuel_type or rows[0].get("fuel_type"),
            "locked_rate": rate,
            "rate_date": rows[0].get("rate_date") or rows[0].get("date"),
            "source": "sale_entries_locked_snapshot",
            "sale_entry_ids": [r.get("id") for r in rows],
        }
    shift_date = settlement_date or get_shift_date(shift_id) or _today()
    return get_locked_rate_for_sale(fuel_type, shift_date)
