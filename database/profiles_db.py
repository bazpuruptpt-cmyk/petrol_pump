from config.supabase_client import get_supabase_client


def get_profile_by_user_id(user_id: str):
    supabase = get_supabase_client()
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .eq("is_active", True)
        .single()
        .execute()
    )
    return result.data


def get_all_users():
    supabase = get_supabase_client()
    result = (
        supabase.table("profiles")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def get_active_salesmen():
    supabase = get_supabase_client()
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("role", "salesman")
        .eq("is_active", True)
        .order("name")
        .execute()
    )
    return result.data or []
