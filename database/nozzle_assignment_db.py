from datetime import datetime, timezone
from config.supabase_client import get_supabase_client

def _now():
    return datetime.now(timezone.utc).isoformat()

def get_active_shift_assignments():
    try:
        r = (get_supabase_client()
             .table("shift_assignments")
             .select("*, profiles:salesman_id(name), nozzles:nozzle_id(nozzle_name, fuel_type)")
             .eq("is_active", True)
             .order("created_at", desc=True)
             .execute())
        return r.data or []
    except Exception as e:
        print("get_active_shift_assignments", e)
        return []

def get_active_nozzle_assignment(nozzle_id):
    try:
        r = (get_supabase_client()
             .table("shift_assignments")
             .select("*, profiles:salesman_id(name), nozzles:nozzle_id(nozzle_name)")
             .eq("nozzle_id", nozzle_id)
             .eq("is_active", True)
             .limit(1)
             .execute())
        return r.data[0] if r.data else None
    except Exception as e:
        print("get_active_nozzle_assignment", e)
        return None

def get_available_nozzles():
    try:
        supabase = get_supabase_client()
        nozzles = (supabase.table("nozzles")
                   .select("*")
                   .eq("is_active", True)
                   .order("nozzle_name")
                   .execute()
                   .data or [])
        assigned_ids = {a.get("nozzle_id") for a in get_active_shift_assignments() if a.get("nozzle_id")}
        return [n for n in nozzles if n.get("id") not in assigned_ids]
    except Exception as e:
        print("get_available_nozzles", e)
        return []

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
        return None, f"Nozzle already assigned: {nozzle.get('nozzle_name') or nozzle_id} to {salesman.get('name') or existing.get('salesman_id')}."

    payload = {
        "shift_id": shift_id,
        "salesman_id": salesman_id,
        "nozzle_id": nozzle_id,
        "is_active": True,
        "assigned_by": assigned_by,
        "created_at": _now(),
    }
    try:
        r = get_supabase_client().table("shift_assignments").insert(payload).execute()
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("assign_nozzle_to_salesman", e)
        return None, str(e)

def end_nozzle_assignment(assignment_id):
    try:
        r = (get_supabase_client()
             .table("shift_assignments")
             .update({"is_active": False, "ended_at": _now()})
             .eq("id", assignment_id)
             .execute())
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("end_nozzle_assignment", e)
        return None, str(e)

def get_duplicate_active_nozzle_assignments():
    grouped = {}
    for row in get_active_shift_assignments():
        nozzle_id = row.get("nozzle_id")
        grouped.setdefault(nozzle_id, []).append(row)
    return [{"nozzle_id": k, "count": len(v), "rows": v} for k, v in grouped.items() if k and len(v) > 1]
