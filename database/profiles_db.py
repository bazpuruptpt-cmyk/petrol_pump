from config.supabase_client import get_supabase_client


def get_profile_by_user_id(user_id: str):
    """
    Auth user id ke basis par active profile fetch karega.
    Agar profile nahi milegi to crash nahi karega, None return karega.
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
    """
    Active/inactive dono type ka user fetch karega.
    """

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
    """
    Sabhi profiles fetch karega.
    """

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
    """
    Sirf active salesman users fetch karega.
    Duty start karne ke dropdown me use hoga.
    """

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
    """
    Active managers fetch karega.
    """

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
    Existing Supabase Auth user ke liye profile row create karega.
    Note: Ye auth user create nahi karta. Sirf profiles table me row insert karta hai.
    """

    if role not in ["owner", "manager", "salesman"]:
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
            .insert(data)
            .execute()
        )

        return result.data[0] if result.data else None

    except Exception as exc:
        print(f"Error in create_profile: {exc}")
        return None


def update_user(user_id: str, data: dict):
    """
    User profile update karega.
    Example data:
    {
        "name": "Manager 1",
        "phone": "9999999999",
        "role": "manager"
    }
    """

    if not user_id or not data:
        return None

    allowed_fields = {"name", "role", "phone", "is_active"}
    clean_data = {k: v for k, v in data.items() if k in allowed_fields}

    if "role" in clean_data:
        if clean_data["role"] not in ["owner", "manager", "salesman"]:
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
    """
    User active/inactive toggle karega.
    Hard delete nahi karega.
    """

    user = get_user_by_id(user_id)

    if not user:
        return None

    new_status = not bool(user.get("is_active"))

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("profiles")
            .update({"is_active": new_status})
            .eq("id", user_id)
            .execute()
        )

        return result.data[0] if result.data else None

    except Exception as exc:
        print(f"Error in toggle_user_active: {exc}")
        return None
