from datetime import date, datetime, timezone
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


def add_pending_credit_sale(
    party_id: int,
    sale_entry_id: int,
    fuel_type: str,
    liters: float,
    amount: float,
):
    """
    Credit sale ko credit_transactions ledger me pending status ke saath post karega.
    Balance update manager approval phase me hoga.
    """

    if not party_id:
        return None, "party_id required."

    supabase = get_supabase_client()

    payload = {
        "party_id": party_id,
        "date": date.today().isoformat(),
        "type": "sale",
        "fuel_type": fuel_type,
        "liters": float(liters or 0),
        "amount": float(amount or 0),
        "payment_mode": "credit",
        "reference_id": sale_entry_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = (
            supabase.table("credit_transactions")
            .insert(payload)
            .execute()
        )

        return result.data[0] if result.data else None, None

    except Exception as exc:
        print(f"Error in add_pending_credit_sale: {exc}")
        return None, str(exc)
