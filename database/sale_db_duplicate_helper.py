
# PATCH NOTE:
# Is file me sirf duplicate-settlement fix ke liye helper functions hain.
# Agar aap existing database/sale_db.py replace nahi karna chahte, to apne sale_db.py me:
# 1. _get_latest_settlement_for_shift_salesman
# 2. _upsert_settlement_for_shift_salesman
# functions add karo
# aur save_payment_breakup me direct insert ki jagah _upsert_settlement_for_shift_salesman use karo.

from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client


def _now():
    return datetime.now(timezone.utc).isoformat()


def _get_latest_settlement_for_shift_salesman(shift_id: int, salesman_id: str):
    """
    Same shift + salesman ke liye latest settlement row.
    Duplicate rows avoid karne ke liye hamesha isi row ko update karo.
    """
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .select("*")
            .eq("shift_id", shift_id)
            .eq("salesman_id", salesman_id)
            .order("created_at", desc=True)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in _get_latest_settlement_for_shift_salesman: {exc}")
        return None


def _upsert_settlement_for_shift_salesman(shift_id: int, salesman_id: str, payload: dict):
    """
    IMPORTANT:
    settlement insert karne se pehle check karo ki same shift+salesman ki row hai ya nahi.
    Agar row hai to UPDATE, nahi hai to INSERT.
    """
    supabase = get_supabase_client()

    existing = _get_latest_settlement_for_shift_salesman(shift_id, salesman_id)

    if existing:
        result = (
            supabase.table("settlements")
            .update(payload)
            .eq("id", existing["id"])
            .execute()
        )
        return result.data[0] if result.data else None

    payload["shift_id"] = shift_id
    payload["salesman_id"] = salesman_id
    payload["created_at"] = _now()

    result = supabase.table("settlements").insert(payload).execute()
    return result.data[0] if result.data else None
