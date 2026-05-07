from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client


def vehicle_text_to_list(vehicle_text: str):
    if not vehicle_text:
        return []
    return [v.strip().upper() for v in vehicle_text.split(",") if v.strip()]


def get_all_parties():
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("credit_parties")
            .select("*")
            .order("name")
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_all_parties: {exc}")
        return []


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


def create_party(data: dict):
    name = (data.get("name") or "").strip()

    if not name:
        return None, "Creditor name required."

    payload = {
        "name": name,
        "phone": data.get("phone"),
        "vehicle_numbers": data.get("vehicle_numbers") or [],
        "credit_limit": float(data.get("credit_limit") or 0),
        "current_balance": float(data.get("current_balance") or 0),
        "is_active": bool(data.get("is_active", True)),
        "created_by": data.get("created_by"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("credit_parties")
            .insert(payload)
            .execute()
        )
        party = result.data[0] if result.data else None
        return party, None
    except Exception as exc:
        print(f"Error in create_party: {exc}")
        return None, str(exc)


def update_party(party_id: int, data: dict):
    allowed_fields = {
        "name",
        "phone",
        "vehicle_numbers",
        "credit_limit",
        "current_balance",
        "is_active",
    }

    clean_data = {k: v for k, v in data.items() if k in allowed_fields}

    if "name" in clean_data and not clean_data["name"]:
        return None, "Creditor name required."

    if "credit_limit" in clean_data:
        clean_data["credit_limit"] = float(clean_data["credit_limit"] or 0)

    if "current_balance" in clean_data:
        clean_data["current_balance"] = float(clean_data["current_balance"] or 0)

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("credit_parties")
            .update(clean_data)
            .eq("id", party_id)
            .execute()
        )
        party = result.data[0] if result.data else None
        return party, None
    except Exception as exc:
        print(f"Error in update_party: {exc}")
        return None, str(exc)


def toggle_party_active(party_id: int):
    party = get_party_by_id(party_id)

    if not party:
        return None, "Creditor not found."

    new_status = not bool(party.get("is_active"))
    return update_party(party_id, {"is_active": new_status})


def create_credit_sale_transaction(
    party_id: int,
    amount: float,
    reference_id: int,
    fuel_type: str = None,
    liters: float = 0,
    vehicle_number: str = None,
    status: str = "pending",
):
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


def get_party_ledger(party_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("credit_transactions")
            .select("*")
            .eq("party_id", party_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_party_ledger: {exc}")
        return []


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
