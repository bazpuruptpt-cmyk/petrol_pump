from config.supabase_client import get_supabase_client


def is_duty_active(salesman_id: str) -> bool:
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shifts")
            .select("id")
            .eq("salesman_id", salesman_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception as exc:
        print(f"Error in is_duty_active: {exc}")
        return False


def get_duty_by_salesman(salesman_id: str):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shifts")
            .select("*")
            .eq("salesman_id", salesman_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in get_duty_by_salesman: {exc}")
        return None


def get_duty_by_id(shift_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shifts")
            .select("*")
            .eq("id", shift_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in get_duty_by_id: {exc}")
        return None


def get_active_duties():
    """
    Active duties with salesman profile.
    """
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shifts")
            .select("*, profiles:salesman_id(id, name, role, phone)")
            .eq("is_active", True)
            .order("started_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_active_duties: {exc}")
        return []


def get_duty_history(limit: int = 50):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shifts")
            .select("*, profiles:salesman_id(id, name, role, phone)")
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_duty_history: {exc}")
        return []


def start_duty(salesman_id: str, manager_id: str):
    """
    Duty start karega.
    Same salesman ki ek active duty hi allowed hogi.
    """
    if is_duty_active(salesman_id):
        return None, "This salesman already has an active duty."

    supabase = get_supabase_client()

    data = {
        "salesman_id": salesman_id,
        "started_by": manager_id,
        "is_active": True,
    }

    try:
        result = (
            supabase.table("shifts")
            .insert(data)
            .execute()
        )
        duty = result.data[0] if result.data else None
        return duty, None
    except Exception as exc:
        print(f"Error in start_duty: {exc}")
        return None, str(exc)


def end_duty(shift_id: int):
    """
    Shift ko inactive karega aur linked active assignments bhi inactive karega.
    """
    supabase = get_supabase_client()

    try:
        shift_result = (
            supabase.table("shifts")
            .update({
                "is_active": False,
                "ended_at": "now()",
            })
            .eq("id", shift_id)
            .execute()
        )

        try:
            supabase.table("shift_assignments").update({
                "is_active": False,
            }).eq("shift_id", shift_id).execute()
        except Exception as assign_exc:
            print(f"Assignment inactive error: {assign_exc}")

        return shift_result.data[0] if shift_result.data else None

    except Exception as exc:
        print(f"Error in end_duty: {exc}")
        return None


def get_shift_assignments(shift_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shift_assignments")
            .select("*, nozzles:nozzle_id(*)")
            .eq("shift_id", shift_id)
            .eq("is_active", True)
            .order("id", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_shift_assignments: {exc}")
        return []


def is_nozzle_assigned_active(nozzle_id: int) -> bool:
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shift_assignments")
            .select("id")
            .eq("nozzle_id", nozzle_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception as exc:
        print(f"Error in is_nozzle_assigned_active: {exc}")
        return True


def assign_nozzle_to_shift(shift_id: int, nozzle_id: int):
    """
    Nozzle ko active duty me assign karega.
    Opening reading nozzles.current_reading se auto fetch hoga.
    """
    if is_nozzle_assigned_active(nozzle_id):
        return None, "This nozzle is already assigned to an active duty."

    supabase = get_supabase_client()

    try:
        nozzle_result = (
            supabase.table("nozzles")
            .select("current_reading")
            .eq("id", nozzle_id)
            .limit(1)
            .execute()
        )

        if not nozzle_result.data:
            return None, "Nozzle not found."

        opening_reading = nozzle_result.data[0].get("current_reading") or 0

        data = {
            "shift_id": shift_id,
            "nozzle_id": nozzle_id,
            "opening_reading": opening_reading,
            "is_active": True,
        }

        result = (
            supabase.table("shift_assignments")
            .insert(data)
            .execute()
        )

        assignment = result.data[0] if result.data else None
        return assignment, None

    except Exception as exc:
        print(f"Error in assign_nozzle_to_shift: {exc}")
        return None, str(exc)


def remove_nozzle_assignment(assignment_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("shift_assignments")
            .update({"is_active": False})
            .eq("id", assignment_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in remove_nozzle_assignment: {exc}")
        return None
