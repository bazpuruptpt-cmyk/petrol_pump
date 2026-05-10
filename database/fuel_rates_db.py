
from datetime import date
from config.supabase_client import get_supabase_client


VALID_FUEL_TYPES = ["petrol", "diesel", "premium_petrol", "premium_diesel"]


def _today():
    return date.today().isoformat()


def get_rate_history(fuel_type: str = None):
    supabase = get_supabase_client()

    try:
        query = supabase.table("fuel_rates").select("*")

        if fuel_type and fuel_type != "all":
            query = query.eq("fuel_type", fuel_type)

        result = (
            query
            .order("effective_from", desc=True)
            .order("created_at", desc=True)
            .execute()
        )

        return result.data or []
    except Exception as exc:
        print(f"Error in get_rate_history: {exc}")
        return []


def get_current_rates(as_of_date: str = None):
    """
    Date-wise rate logic:
    For each fuel type, return latest rate where effective_from <= as_of_date.
    """
    as_of_date = as_of_date or _today()
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("fuel_rates")
            .select("*")
            .lte("effective_from", as_of_date)
            .order("effective_from", desc=True)
            .order("created_at", desc=True)
            .execute()
        )

        current = {}
        for row in result.data or []:
            fuel_type = row.get("fuel_type")
            if fuel_type and fuel_type not in current:
                current[fuel_type] = row

        return current
    except Exception as exc:
        print(f"Error in get_current_rates: {exc}")
        return {}


def get_rate_by_fuel(fuel_type: str, as_of_date: str = None):
    if not fuel_type:
        return None

    rates = get_current_rates(as_of_date)
    return rates.get(fuel_type)


def has_activity_on_or_after(effective_from: str):
    """
    Used only as warning support. Rate correction should be controlled by owner process.
    """
    try:
        supabase = get_supabase_client()

        sale_rows = (
            supabase.table("sale_entries")
            .select("id")
            .gte("date", effective_from)
            .limit(1)
            .execute()
            .data
            or []
        )
        if sale_rows:
            return True

        settlement_rows = (
            supabase.table("settlements")
            .select("id")
            .gte("date", effective_from)
            .limit(1)
            .execute()
            .data
            or []
        )
        return bool(settlement_rows)
    except Exception:
        return False


def set_rate(fuel_type: str, price: float, effective_from: str, created_by: str):
    if fuel_type not in VALID_FUEL_TYPES:
        raise ValueError("Invalid fuel type.")

    if float(price or 0) <= 0:
        return None

    data = {
        "fuel_type": fuel_type,
        "price_per_liter": float(price or 0),
        "effective_from": effective_from,
        "created_by": created_by,
    }

    supabase = get_supabase_client()

    try:
        # Upsert: one rate per fuel type per date.
        result = (
            supabase.table("fuel_rates")
            .upsert(data, on_conflict="fuel_type,effective_from")
            .execute()
        )

        return result.data[0] if result.data else None

    except Exception as exc:
        print(f"Error in set_rate: {exc}")
        return None
