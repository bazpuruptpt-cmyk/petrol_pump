from config.supabase_client import get_supabase_client


def get_active_parties():
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("credit_parties")
            .select("*")
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_active_parties: {exc}")
        return []


def get_party_by_id(party_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("credit_parties")
            .select("*")
            .eq("id", party_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in get_party_by_id: {exc}")
        return None
