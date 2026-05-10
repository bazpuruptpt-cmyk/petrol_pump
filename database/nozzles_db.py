
from datetime import datetime, timezone
from config.supabase_client import get_supabase_client


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
    return [r for r in get_all_nozzles() if _truthy_active(r)]


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


def create_nozzle(nozzle_name: str, fuel_type: str, current_reading: float = 0, created_by=None):
    payload = {
        "nozzle_name": nozzle_name,
        "fuel_type": fuel_type,
        "current_reading": float(current_reading or 0),
        "is_active": True,
        "created_by": created_by,
        "created_at": _now(),
    }

    try:
        result = get_supabase_client().table("nozzles").insert(payload).execute()
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"create_nozzle error: {exc}")
        return None, str(exc)


def update_nozzle(nozzle_id: int, data: dict):
    """
    Stable rule:
    Nozzle inactive hoti hai to linked active assignment auto-end hoga.
    """
    try:
        supabase = get_supabase_client()

        old_nozzle = get_nozzle_by_id(nozzle_id)
        old_active = _truthy_active(old_nozzle)

        result = (
            supabase.table("nozzles")
            .update(data)
            .eq("id", nozzle_id)
            .execute()
        )

        updated = result.data[0] if result.data else None
        new_active = _truthy_active(updated)

        if old_active and not new_active:
            end_active_assignments_for_nozzle(nozzle_id)

        return updated, None

    except Exception as exc:
        print(f"update_nozzle error: {exc}")
        return None, str(exc)


def toggle_nozzle_active(nozzle_id: int):
    nozzle = get_nozzle_by_id(nozzle_id)

    if not nozzle:
        return None, "Nozzle not found."

    new_status = not _truthy_active(nozzle)
    return update_nozzle(nozzle_id, {"is_active": new_status})


def end_active_assignments_for_nozzle(nozzle_id: int):
    try:
        result = (
            get_supabase_client()
            .table("shift_assignments")
            .update({
                "is_active": False,
                "ended_at": _now(),
            })
            .eq("nozzle_id", nozzle_id)
            .eq("is_active", True)
            .execute()
        )
        return result.data or [], None
    except Exception as exc:
        print(f"end_active_assignments_for_nozzle error: {exc}")
        return [], str(exc)


def set_nozzle_current_reading(nozzle_id: int, current_reading: float):
    try:
        result = (
            get_supabase_client()
            .table("nozzles")
            .update({"current_reading": float(current_reading or 0)})
            .eq("id", nozzle_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"set_nozzle_current_reading error: {exc}")
        return None, str(exc)


def cleanup_inactive_nozzle_assignments():
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

        for a in assignments:
            nozzle = get_nozzle_by_id(a.get("nozzle_id"))
            if nozzle and not _truthy_active(nozzle):
                result = (
                    supabase.table("shift_assignments")
                    .update({"is_active": False, "ended_at": _now()})
                    .eq("id", a.get("id"))
                    .execute()
                )
                if result.data:
                    ended.extend(result.data)

        return ended, None
    except Exception as exc:
        print(f"cleanup_inactive_nozzle_assignments error: {exc}")
        return [], str(exc)
