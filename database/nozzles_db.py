from datetime import datetime, timezone
from config.supabase_client import get_supabase_client


VALID_FUEL_TYPES = [
    "petrol",
    "diesel",
    "premium_petrol",
    "premium_diesel",
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _truthy_active(row):
    if row is None:
        return False

    if "is_active" not in row:
        return True

    if row.get("is_active") is None:
        return True

    return bool(row.get("is_active"))


def get_all_nozzles():
    try:
        result = (
            get_supabase_client()
            .table("nozzles")
            .select("*")
            .order("id")
            .execute()
        )
        return result.data or []

    except Exception as exc:
        print(f"get_all_nozzles error: {exc}")
        return []


def get_active_nozzles():
    try:
        rows = get_all_nozzles()
        return [r for r in rows if _truthy_active(r)]

    except Exception as exc:
        print(f"get_active_nozzles error: {exc}")
        return []


def get_nozzle_by_id(nozzle_id: int):
    try:
        result = (
            get_supabase_client()
            .table("nozzles")
            .select("*")
            .eq("id", nozzle_id)
            .limit(1)
            .execute()
        )

        return result.data[0] if result.data else None

    except Exception as exc:
        print(f"get_nozzle_by_id error: {exc}")
        return None


def create_nozzle(
    nozzle_name: str,
    fuel_type: str,
    current_reading: float = 0,
    created_by=None,
):
    """
    New nozzle create karega.

    Rules:
    1. Fuel type valid hona chahiye.
    2. New nozzle by default active hogi.
    3. Current reading initial opening base hogi.
    """

    if not nozzle_name:
        return None, "Nozzle name required."

    if fuel_type not in VALID_FUEL_TYPES:
        return None, f"Invalid fuel type: {fuel_type}"

    try:
        current_reading = float(current_reading or 0)
    except Exception:
        return None, "Invalid current reading."

    payload = {
        "nozzle_name": nozzle_name,
        "fuel_type": fuel_type,
        "current_reading": current_reading,
        "is_active": True,
        "created_by": created_by,
        "created_at": _now(),
    }

    try:
        result = (
            get_supabase_client()
            .table("nozzles")
            .insert(payload)
            .execute()
        )

        return result.data[0] if result.data else None, None

    except Exception as exc:
        print(f"create_nozzle error: {exc}")
        return None, str(exc)


def update_nozzle(nozzle_id: int, data: dict):
    """
    Nozzle update karega.

    Stable rule:
    Agar nozzle active se inactive hoti hai,
    to us nozzle ki active assignment auto-end hogi.
    """

    if not nozzle_id:
        return None, "Nozzle ID required."

    if not isinstance(data, dict):
        return None, "Invalid update data."

    if "fuel_type" in data and data.get("fuel_type") not in VALID_FUEL_TYPES:
        return None, f"Invalid fuel type: {data.get('fuel_type')}"

    if "current_reading" in data:
        try:
            data["current_reading"] = float(data.get("current_reading") or 0)
        except Exception:
            return None, "Invalid current reading."

    try:
        supabase = get_supabase_client()

        old_nozzle = get_nozzle_by_id(nozzle_id)

        if not old_nozzle:
            return None, "Nozzle not found."

        old_active = _truthy_active(old_nozzle)

        result = (
            supabase.table("nozzles")
            .update(data)
            .eq("id", nozzle_id)
            .execute()
        )

        updated = result.data[0] if result.data else None

        if not updated:
            return None, "Nozzle update failed."

        new_active = _truthy_active(updated)

        # अगर nozzle inactive हुई है, तो active assignment close करो
        if old_active and not new_active:
            end_active_assignments_for_nozzle(nozzle_id)

        return updated, None

    except Exception as exc:
        print(f"update_nozzle error: {exc}")
        return None, str(exc)


def toggle_nozzle_active(nozzle_id: int):
    """
    Nozzle active/inactive toggle karega.

    Important:
    Inactive karte hi active assignment auto-end hogi.
    """

    nozzle = get_nozzle_by_id(nozzle_id)

    if not nozzle:
        return None, "Nozzle not found."

    new_status = not _truthy_active(nozzle)

    return update_nozzle(nozzle_id, {"is_active": new_status})


def end_active_assignments_for_nozzle(nozzle_id: int):
    """
    Kisi nozzle ki active assignments end karega.

    Use case:
    Nozzle inactive karte waqt stale assignment remove karna.
    """

    try:
        result = (
            get_supabase_client()
            .table("shift_assignments")
            .update(
                {
                    "is_active": False,
                    "ended_at": _now(),
                }
            )
            .eq("nozzle_id", nozzle_id)
            .eq("is_active", True)
            .execute()
        )

        return result.data or [], None

    except Exception as exc:
        print(f"end_active_assignments_for_nozzle error: {exc}")
        return [], str(exc)


def set_nozzle_current_reading(nozzle_id: int, current_reading: float):
    """
    Nozzle current reading update karega.

    Use case:
    Manager approval ke baad:
    nozzle.current_reading = manager closing_reading
    """

    if not nozzle_id:
        return None, "Nozzle ID required."

    try:
        current_reading = float(current_reading or 0)
    except Exception:
        return None, "Invalid current reading."

    try:
        result = (
            get_supabase_client()
            .table("nozzles")
            .update({"current_reading": current_reading})
            .eq("id", nozzle_id)
            .execute()
        )

        return result.data[0] if result.data else None, None

    except Exception as exc:
        print(f"set_nozzle_current_reading error: {exc}")
        return None, str(exc)


def cleanup_inactive_nozzle_assignments():
    """
    Safety cleanup.

    Agar database me koi active assignment aisi hai
    jiska linked nozzle inactive hai, to assignment end karega.
    """

    try:
        supabase = get_supabase_client()

        assignments = (
            supabase.table("shift_assignments")
            .select("*")
            .eq("is_active", True)
            .execute()
            .data
            or []
        )

        ended = []

        for assignment in assignments:
            nozzle_id = assignment.get("nozzle_id")
            nozzle = get_nozzle_by_id(nozzle_id)

            if nozzle and not _truthy_active(nozzle):
                result = (
                    supabase.table("shift_assignments")
                    .update(
                        {
                            "is_active": False,
                            "ended_at": _now(),
                        }
                    )
                    .eq("id", assignment.get("id"))
                    .execute()
                )

                if result.data:
                    ended.extend(result.data)

        return ended, None

    except Exception as exc:
        print(f"cleanup_inactive_nozzle_assignments error: {exc}")
        return [], str(exc)


def get_nozzle_stats():
    """
    Nozzle page ke summary cards ke liye stats.
    """

    rows = get_all_nozzles()

    total = len(rows)
    active = len([r for r in rows if _truthy_active(r)])
    inactive = total - active

    return {
        "total": total,
        "active": active,
        "inactive": inactive,
    }
