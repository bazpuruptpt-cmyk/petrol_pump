
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


def _attach_names_and_filter(rows, require_nozzle_active=True):
    profiles = _profiles_map()
    nozzles = _nozzles_map()
    output = []

    for row in rows or []:
        r = dict(row)
        salesman_id = r.get("salesman_id") or r.get("attendant_id")
        nozzle = nozzles.get(r.get("nozzle_id")) or {}

        if require_nozzle_active and not _truthy_active(nozzle):
            continue

        r["profiles"] = profiles.get(salesman_id) or {}
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
        return _attach_names_and_filter(rows, require_nozzle_active=True)
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
        return _attach_names_and_filter(rows, require_nozzle_active=True)
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
        enriched = _attach_names_and_filter(rows, require_nozzle_active=True)
        return enriched[0] if enriched else None
    except Exception as exc:
        print(f"get_active_nozzle_assignment error: {exc}")
        return None


def get_available_nozzles():
    nozzles = get_active_nozzles_for_assignment()
    assignments = get_active_shift_assignments()
    assigned_ids = {a.get("nozzle_id") for a in assignments if a.get("nozzle_id")}
    return [n for n in nozzles if n.get("id") not in assigned_ids]


def _current_nozzle_reading(nozzle_id):
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
        return float((rows[0] if rows else {}).get("current_reading") or 0)
    except Exception:
        return 0.0


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


def assign_nozzle_to_salesman(shift_id, salesman_id, nozzle_id, assigned_by=None):
    if not shift_id:
        return None, "Active duty/shift required."
    if not salesman_id:
        return None, "Salesman required."
    if not nozzle_id:
        return None, "Nozzle required."

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
            f"to {salesman.get('name') or existing.get('salesman_id') or existing.get('attendant_id')}."
        )

    payload = {
        "shift_id": shift_id,
        "salesman_id": salesman_id,
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

        if "duplicate key" in msg or "uniq_active_nozzle_assignment" in msg:
            return None, "This nozzle already has an active assignment."

        return None, msg


def end_nozzle_assignment(assignment_id):
    try:
        result = (
            get_supabase_client()
            .table("shift_assignments")
            .update({"is_active": False, "ended_at": _now()})
            .eq("id", assignment_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"end_nozzle_assignment error: {exc}")
        return None, str(exc)


def end_assignments_for_inactive_nozzles():
    try:
        assignments = (
            get_supabase_client()
            .table("shift_assignments")
            .select("*")
            .eq("is_active", True)
            .execute()
            .data
            or []
        )
        nozzles = _nozzles_map()
        ended = []

        for a in assignments:
            nozzle = nozzles.get(a.get("nozzle_id")) or {}
            if not _truthy_active(nozzle):
                row, err = end_nozzle_assignment(a.get("id"))
                if row:
                    ended.append(row)

        return ended, None
    except Exception as exc:
        return [], str(exc)


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
