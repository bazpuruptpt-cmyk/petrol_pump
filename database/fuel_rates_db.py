from config.supabase_client import get_supabase_client


VALID_FUEL_TYPES = ["petrol", "diesel", "premium_petrol", "premium_diesel"]


def get_rate_history(fuel_type: str = None):
    supabase = get_supabase_client()

    try:
        query = supabase.table("fuel_rates").select("*")

        if fuel_type:
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


def get_current_rates():
    rows = get_rate_history()
    current = {}

    for row in rows:
        fuel_type = row.get("fuel_type")
        if fuel_type and fuel_type not in current:
            current[fuel_type] = row

    return current


def get_rate_by_fuel(fuel_type: str):
    rates = get_current_rates()
    return rates.get(fuel_type)


def set_rate(fuel_type: str, price: float, effective_from: str, created_by: str):
    if fuel_type not in VALID_FUEL_TYPES:
        raise ValueError("Invalid fuel type.")

    data = {
        "fuel_type": fuel_type,
        "price_per_liter": float(price or 0),
        "effective_from": effective_from,
        "created_by": created_by,
    }

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("fuel_rates")
            .insert(data)
            .execute()
        )

        return result.data[0] if result.data else None

    except Exception as exc:
        print(f"Error in set_rate: {exc}")
        return None
