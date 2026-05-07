from config.supabase_client import get_supabase_client


def is_duty_active(salesman_id: str) -> bool:
    supabase = get_supabase_client()
    result = (
        supabase.table("shifts")
        .select("id")
        .eq("salesman_id", salesman_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def get_duty_by_salesman(salesman_id: str):
    supabase = get_supabase_client()
    result = (
        supabase.table("shifts")
        .select("*")
        .eq("salesman_id", salesman_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
