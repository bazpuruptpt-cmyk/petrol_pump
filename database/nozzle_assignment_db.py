
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


def _profiles_map():
    try:
        rows = get_supabase_client().table("profiles").select("*").execute().data or []
        return {r.get("id"): r for r in rows}
    except Exception:
        return {}


def _nozzles_map():
    try:
        rows = get_supabase_client().table("nozzles").select("*").execute().data or []
        return {r.get("id"): r for r in rows}
    except Exception:
        return {}


def _shifts_map():
    try:
        rows = get_supabase_client().table("shifts").select("*").execute().data or []
        return {r.get("id"): r for r in rows}
    except Exception:
        return {}


def _attach_names_and_filter(rows, require_valid=True):
    profiles = _profiles_map()
    nozzles = _nozzles_map()
    shifts = _shifts_map()

    output = []
    for row in rows or []:
        r = dict(row)
        shift = shifts.get(r.get("shift_id")) or {}
        nozzle = nozzles.get(r.get("nozzle_id")) or {}

        shift_salesman_id = shift.get("salesman_id")
        assignment_salesman_id = r.get("salesman_id") or r.get("attendant_id")

        if require_valid:
            if not _truthy_active(shift):
                continue
            if not _truthy_active(nozzle):
                continue
            if shift_salesman_id and assignment_salesman_id and shift_salesman_id != assignment_salesman_id:
                continue

        r["shifts"] = shift
        r["profiles"] = profiles.get(assignment_salesman_id or shift_salesman_id) or {}
        r["duty_profile"] = profiles.get(shift_salesman_id) or {}
        r["nozzles"] = nozzle
        output.append(r)

    return output


def get_active_salesmen_for_assignment():
    try:
        rows = (
            get_supabase_client()
            .table("profiles")
            .select("*")
            .in_("role", ["salesman", "attendant"])
            .order("name")
            .execute()
            .data
            or []
        )
        return [r for r in rows if _truthy_active(r)]
    except Exception as exc:
        print(f"get_active_salesmen_for_assignment error: {exc}")
        return []


def get_active_duties_for_assignment():
    """
    Duty is the source of salesman. Assignment page should not choose different salesman.
    """
    try:
        rows = (
            get_supabase_client()
            .table("shifts")
            .select("*")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )

        profiles = _profiles_map()
        output = []

        for r in rows:
            salesman_id = r.get("salesman_id") or r.get("attendant_id")
            if not salesman_id:
                continue

            r["profiles"] = profiles.get(salesman_id) or {}
            output.append(r)

        return output
    except Exception as exc:
        print(f"get_active_duties_for_assignment error: {exc}")
        return []


def get_active_nozzles_for_assignment():
    try:
        rows = (
            get_supabase_client()
            .table("nozzles")
            .select("*")
            .order("nozzle_name")
            .execute()
            .data
            or []
        )
        return [r for r in rows if _truthy_active(r)]
    except Exception as exc:
        print(f"get_active_nozzles_for_assignment error: {exc}")
        return []


def get_active_shift_assignments():
    try:
        rows = (
            get_supabase_client()
            .table("shift_assignments")
            .select("*")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        return _attach_names_and_filter(rows, require_valid=True)
    except Exception as exc:
        print(f"get_active_shift_assignments error: {exc}")
        return []


def get_assignments_for_shift(shift_id):
    try:
        rows = (
            get_supabase_client()
            .table("shift_assignments")
            .select("*")
            .eq("shift_id", shift_id)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        return _attach_names_and_filter(rows, require_valid=True)
    except Exception as exc:
        print(f"get_assignments_for_shift error: {exc}")
        return []


def get_active_nozzle_assignment(nozzle_id):
    try:
        rows = (
            get_supabase_client()
            .table("shift_assignments")
            .select("*")
            .eq("nozzle_id", nozzle_id)
            .eq("is_active", True)
            .limit(10)
            .execute()
            .data
            or []
        )
        enriched = _attach_names_and_filter(rows, require_valid=True)
        return enriched[0] if enriched else None
    except Exception as exc:
        print(f"get_active_nozzle_assignment error: {exc}")
        return None


def get_available_nozzles():
    active_nozzles = get_active_nozzles_for_assignment()
    active_assignments = get_active_shift_assignments()
    assigned_ids = {a.get("nozzle_id") for a in active_assignments if a.get("nozzle_id")}
    return [n for n in active_nozzles if n.get("id") not in assigned_ids]


def _get_nozzle(nozzle_id):
    try:
        rows = (
            get_supabase_client()
            .table("nozzles")
            .select("*")
            .eq("id", nozzle_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _get_shift(shift_id):
    try:
        rows = (
            get_supabase_client()
            .table("shifts")
            .select("*")
            .eq("id", shift_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _current_nozzle_reading(nozzle_id):
    nozzle = _get_nozzle(nozzle_id)
    return float((nozzle or {}).get("current_reading") or 0)


def assign_nozzle_to_salesman(shift_id, salesman_id=None, nozzle_id=None, assigned_by=None):
    """
    Hard lock:
    Selected duty/shift decides salesman.
    Passed salesman_id is ignored if mismatched; mismatch is blocked.
    """
    if not shift_id:
        return None, "Active duty/shift required."
    if not nozzle_id:
        return None, "Nozzle required."

    shift = _get_shift(shift_id)
    if not shift or not _truthy_active(shift):
        return None, "Active shift not found."

    duty_salesman_id = shift.get("salesman_id") or shift.get("attendant_id")
    if not duty_salesman_id:
        return None, "Selected duty has no salesman."

    if salesman_id and salesman_id != duty_salesman_id:
        return None, "Assignment salesman must match selected duty salesman."

    nozzle = _get_nozzle(nozzle_id)
    if not nozzle:
        return None, "Nozzle not found."

    if not _truthy_active(nozzle):
        return None, "Inactive nozzle cannot be assigned."

    existing = get_active_nozzle_assignment(nozzle_id)
    if existing:
        salesman = existing.get("profiles") or {}
        nozzle_info = existing.get("nozzles") or {}
        return None, (
            f"Nozzle already assigned: {nozzle_info.get('nozzle_name') or nozzle_id} "
            f"to {salesman.get('name') or existing.get('salesman_id')}."
        )

    payload = {
        "shift_id": shift_id,
        "salesman_id": duty_salesman_id,
        "nozzle_id": nozzle_id,
        "opening_reading": _current_nozzle_reading(nozzle_id),
        "is_active": True,
        "assigned_by": assigned_by,
        "created_at": _now(),
    }

    try:
        result = get_supabase_client().table("shift_assignments").insert(payload).execute()
        return result.data[0] if result.data else None, None
    except Exception as exc:
        msg = str(exc)
        print(f"assign_nozzle_to_salesman error: {exc}")

        if "uniq_active_nozzle_assignment" in msg or "duplicate key" in msg:
            return None, "This nozzle already has an active assignment."

        if "Nozzle assignment salesman must match duty salesman" in msg:
            return None, "Assignment salesman must match selected duty salesman."

        return None, msg


def end_nozzle_assignment(assignment_id):
    try:
        result = (
            get_supabase_client()
            .table("shift_assignments")
            .update({
                "is_active": False,
                "ended_at": _now(),
            })
            .eq("id", assignment_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"end_nozzle_assignment error: {exc}")
        return None, str(exc)


def get_duplicate_active_nozzle_assignments():
    rows = get_active_shift_assignments()
    grouped = {}

    for row in rows:
        nozzle_id = row.get("nozzle_id")
        grouped.setdefault(nozzle_id, []).append(row)

    return [
        {"nozzle_id": nozzle_id, "count": len(items), "rows": items}
        for nozzle_id, items in grouped.items()
        if nozzle_id and len(items) > 1
    ]
