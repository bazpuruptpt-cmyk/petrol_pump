from config.supabase_client import get_supabase_client


VALID_FUEL_TYPES = ["petrol", "diesel", "premium_petrol", "premium_diesel"]


def get_all_nozzles():
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("nozzles")
            .select("*")
            .order("id", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_all_nozzles: {exc}")
        return []


def get_active_nozzles():
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("nozzles")
            .select("*")
            .eq("is_active", True)
            .order("id", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_active_nozzles: {exc}")
        return []


def get_nozzle_by_id(nozzle_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("nozzles")
            .select("*")
            .eq("id", nozzle_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in get_nozzle_by_id: {exc}")
        return None


def create_nozzle(nozzle_name: str, fuel_type: str, current_reading: float, created_by: str):
    if fuel_type not in VALID_FUEL_TYPES:
        raise ValueError("Invalid fuel type.")

    data = {
        "nozzle_name": nozzle_name,
        "fuel_type": fuel_type,
        "current_reading": float(current_reading or 0),
        "is_active": True,
        "created_by": created_by,
    }

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("nozzles")
            .insert(data)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in create_nozzle: {exc}")
        return None


def update_nozzle(nozzle_id: int, data: dict):
    allowed_fields = {"nozzle_name", "fuel_type", "current_reading", "is_active"}
    clean_data = {k: v for k, v in data.items() if k in allowed_fields}

    if "fuel_type" in clean_data and clean_data["fuel_type"] not in VALID_FUEL_TYPES:
        raise ValueError("Invalid fuel type.")

    if "current_reading" in clean_data:
        clean_data["current_reading"] = float(clean_data["current_reading"] or 0)

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("nozzles")
            .update(clean_data)
            .eq("id", nozzle_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in update_nozzle: {exc}")
        return None


def toggle_nozzle_active(nozzle_id: int):
    nozzle = get_nozzle_by_id(nozzle_id)

    if not nozzle:
        return None

    new_status = not bool(nozzle.get("is_active"))
    return update_nozzle(nozzle_id, {"is_active": new_status})


def update_nozzle_reading(nozzle_id: int, new_reading: float):
    return update_nozzle(nozzle_id, {"current_reading": float(new_reading or 0)})


def get_available_nozzles():
    """
    Active nozzles jinki koi active shift assignment nahi hai.
    One nozzle can only be assigned to one active duty at a time.
    """
    supabase = get_supabase_client()

    try:
        nozzles_result = (
            supabase.table("nozzles")
            .select("*")
            .eq("is_active", True)
            .order("id", desc=False)
            .execute()
        )
        nozzles = nozzles_result.data or []

        assignments_result = (
            supabase.table("shift_assignments")
            .select("nozzle_id")
            .eq("is_active", True)
            .execute()
        )
        assigned_ids = {
            row.get("nozzle_id")
            for row in (assignments_result.data or [])
            if row.get("nozzle_id") is not None
        }

        return [n for n in nozzles if n.get("id") not in assigned_ids]

    except Exception as exc:
        print(f"Error in get_available_nozzles: {exc}")
        return []
