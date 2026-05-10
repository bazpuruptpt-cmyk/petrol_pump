from datetime import datetime, timezone
from config.supabase_client import get_supabase_client


def _now():
    return datetime.now(timezone.utc).isoformat()


def _truthy_active(row):
    """
    Some old rows may not have is_active column or may store null.
    Missing/null is treated as active for profiles/nozzles.
    """
    if row is None:
        return False
    if "is_active" not in row:
        return True
    if row.get("is_active") is None:
        return True
    return bool(row.get("is_active"))


# ============================================================
# Direct robust lookups
# ============================================================

def get_active_salesmen_for_assignment():
    """
    Fix:
    Old page was depending on user_db.get_active_salesmen().
    In some projects it returns empty because role names differ.
    This function directly checks profiles for salesman/attendant roles.
    """
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
    Active shift/duty rows.
    """
    try:
        rows = (
            get_supabase_client()
            .table("shifts")
            .select("*, profiles:salesman_id(name, role)")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        return rows
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


# ============================================================
# Assignments
# ============================================================

def get_active_shift_assignments():
    try:
        result = (
            get_supabase_client()
            .table("shift_assignments")
            .select("*, profiles:salesman_id(name, role), nozzles:nozzle_id(nozzle_name, fuel_type)")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"get_active_shift_assignments error: {exc}")
        return []


def get_assignments_for_shift(shift_id):
    try:
        result = (
            get_supabase_client()
            .table("shift_assignments")
            .select("*, profiles:salesman_id(name, role), nozzles:nozzle_id(nozzle_name, fuel_type)")
            .eq("shift_id", shift_id)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"get_assignments_for_shift error: {exc}")
        return []


def get_active_nozzle_assignment(nozzle_id):
    try:
        result = (
            get_supabase_client()
            .table("shift_assignments")
            .select("*, profiles:salesman_id(name, role), nozzles:nozzle_id(nozzle_name, fuel_type)")
            .eq("nozzle_id", nozzle_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"get_active_nozzle_assignment error: {exc}")
        return None


def get_available_nozzles():
    """
    Active nozzles minus nozzles that already have an active assignment.
    """
    nozzles = get_active_nozzles_for_assignment()
    assignments = get_active_shift_assignments()
    assigned_ids = {a.get("nozzle_id") for a in assignments if a.get("nozzle_id")}

    return [n for n in nozzles if n.get("id") not in assigned_ids]


def assign_nozzle_to_salesman(shift_id, salesman_id, nozzle_id, assigned_by=None):
    if not shift_id:
        return None, "Active duty/shift required."
    if not salesman_id:
        return None, "Salesman required."
    if not nozzle_id:
        return None, "Nozzle required."

    existing = get_active_nozzle_assignment(nozzle_id)
    if existing:
        salesman = existing.get("profiles") or {}
        nozzle = existing.get("nozzles") or {}
        return None, (
            f"Nozzle already assigned: {nozzle.get('nozzle_name') or nozzle_id} "
            f"to {salesman.get('name') or existing.get('salesman_id')}."
        )

    # Opening reading = current nozzle reading at assignment time.
    try:
        nozzle_rows = (
            get_supabase_client()
            .table("nozzles")
            .select("*")
            .eq("id", nozzle_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        opening_reading = nozzle_rows[0].get("current_reading") if nozzle_rows else 0
    except Exception:
        opening_reading = 0

    payload = {
        "shift_id": shift_id,
        "salesman_id": salesman_id,
        "nozzle_id": nozzle_id,
        "opening_reading": float(opening_reading or 0),
        "is_active": True,
        "assigned_by": assigned_by,
        "created_at": _now(),
    }

    try:
        result = get_supabase_client().table("shift_assignments").insert(payload).execute()
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"assign_nozzle_to_salesman error: {exc}")
        return None, str(exc)


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

    duplicates = []
    for nozzle_id, items in grouped.items():
        if nozzle_id and len(items) > 1:
            duplicates.append({
                "nozzle_id": nozzle_id,
                "count": len(items),
                "rows": items,
            })

    return duplicates
