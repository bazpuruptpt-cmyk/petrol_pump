from config.supabase_client import get_supabase_client


VALID_ROLES = ["owner", "manager", "salesman"]


def get_profile_by_user_id(user_id: str):
    """
    Auth user id ke basis par active profile fetch karega.
    Profile missing hone par crash nahi karega.
    """

    if not user_id:
        return None

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .eq("id", user_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        if not result.data:
            return None

        return result.data[0]

    except Exception as exc:
        print(f"Error in get_profile_by_user_id: {exc}")
        return None


def get_user_by_id(user_id: str):
    if not user_id:
        return None

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return None

        return result.data[0]

    except Exception as exc:
        print(f"Error in get_user_by_id: {exc}")
        return None


def get_all_users():
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return result.data or []

    except Exception as exc:
        print(f"Error in get_all_users: {exc}")
        return []


def get_active_salesmen():
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .eq("role", "salesman")
            .eq("is_active", True)
            .order("name")
            .execute()
        )

        return result.data or []

    except Exception as exc:
        print(f"Error in get_active_salesmen: {exc}")
        return []


def get_active_managers():
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .eq("role", "manager")
            .eq("is_active", True)
            .order("name")
            .execute()
        )

        return result.data or []

    except Exception as exc:
        print(f"Error in get_active_managers: {exc}")
        return []


def create_profile(user_id: str, name: str, role: str, phone: str = None):
    """
    Existing Supabase Auth user ke UUID ke liye profile create karega.
    Ye Auth user create nahi karta.
    Pehle Supabase Dashboard > Authentication > Users me user banao.
    """

    if not user_id:
        raise ValueError("user_id required.")

    if role not in VALID_ROLES:
        raise ValueError("Invalid role. Use owner, manager, or salesman.")

    supabase = get_supabase_client()

    data = {
        "id": user_id,
        "name": name,
        "role": role,
        "phone": phone,
        "is_active": True,
    }

    try:
        result = (
            supabase.table("profiles")
            .upsert(data, on_conflict="id")
            .execute()
        )

        return result.data[0] if result.data else None

    except Exception as exc:
        print(f"Error in create_profile: {exc}")
        return None


def update_user(user_id: str, data: dict):
    if not user_id or not data:
        return None

    allowed_fields = {"name", "role", "phone", "is_active"}
    clean_data = {k: v for k, v in data.items() if k in allowed_fields}

    if "role" in clean_data and clean_data["role"] not in VALID_ROLES:
        raise ValueError("Invalid role. Use owner, manager, or salesman.")

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("profiles")
            .update(clean_data)
            .eq("id", user_id)
            .execute()
        )

        return result.data[0] if result.data else None

    except Exception as exc:
        print(f"Error in update_user: {exc}")
        return None


def toggle_user_active(user_id: str):
    user = get_user_by_id(user_id)

    if not user:
        return None

    new_status = not bool(user.get("is_active"))

    return update_user(user_id, {"is_active": new_status})
