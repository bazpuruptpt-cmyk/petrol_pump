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


def create_credit_sale_transaction(
    party_id: int,
    amount: float,
    reference_id: int,
    fuel_type: str = None,
    liters: float = 0,
    vehicle_number: str = None,
    status: str = "pending",
):
    """
    Credit amount ko creditor ledger me pending sale entry ke roop me post karega.
    Balance final approval phase me update hoga.
    """

    if not party_id:
        return None, "party_id required."

    if float(amount or 0) <= 0:
        return None, "credit amount must be greater than 0."

    supabase = get_supabase_client()

    payload = {
        "party_id": party_id,
        "date": date.today().isoformat(),
        "type": "sale",
        "fuel_type": fuel_type,
        "liters": float(liters or 0),
        "amount": float(amount or 0),
        "payment_mode": "credit",
        "reference_id": reference_id,
        "status": status,
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
        print(f"Error in create_credit_sale_transaction: {exc}")
        return None, str(exc)


def get_credit_transactions_by_reference(reference_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("credit_transactions")
            .select("*, credit_parties:party_id(name, phone)")
            .eq("reference_id", reference_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_credit_transactions_by_reference: {exc}")
        return []
