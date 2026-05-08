from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client


def vehicle_text_to_list(vehicle_text: str):
    if not vehicle_text:
        return []
    return [v.strip().upper() for v in vehicle_text.split(",") if v.strip()]


_vehicle_text_to_list = vehicle_text_to_list


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


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
        "credit_limit": _safe_float(data.get("credit_limit")),
        "current_balance": _safe_float(data.get("current_balance")),
        "is_active": bool(data.get("is_active", True)),
        "created_by": data.get("created_by"),
        "created_at": _now(),
    }

    supabase = get_supabase_client()

    try:
        result = supabase.table("credit_parties").insert(payload).execute()
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
        clean_data["credit_limit"] = _safe_float(clean_data["credit_limit"])

    if "current_balance" in clean_data:
        clean_data["current_balance"] = _safe_float(clean_data["current_balance"])

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
    """
    Salesman/settlement credit amount ko pending sale ke roop me post karega.
    Approval ke baad party balance increase hoga.
    """
    if not party_id:
        return None, "party_id required."

    if _safe_float(amount) <= 0:
        return None, "credit amount must be greater than 0."

    supabase = get_supabase_client()

    payload = {
        "party_id": party_id,
        "date": date.today().isoformat(),
        "type": "sale",
        "fuel_type": fuel_type,
        "liters": _safe_float(liters),
        "amount": _safe_float(amount),
        "payment_mode": "credit",
        "reference_id": reference_id,
        "status": status,
        "created_at": _now(),
    }

    try:
        result = supabase.table("credit_transactions").insert(payload).execute()
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"Error in create_credit_sale_transaction: {exc}")
        return None, str(exc)


def create_credit_payment_received(
    party_id: int,
    amount: float,
    payment_mode: str,
    created_by: str,
    note: str = None,
):
    """
    Manager/Owner creditor se payment receive karega.
    Approved hone ke baad party balance decrease hoga.
    """
    if not party_id:
        return None, "Creditor required."

    if _safe_float(amount) <= 0:
        return None, "Payment amount must be greater than 0."

    if payment_mode not in ["cash", "paytm", "ccms", "bank", "neft", "upi"]:
        return None, "Invalid payment mode."

    supabase = get_supabase_client()

    payload = {
        "party_id": party_id,
        "date": date.today().isoformat(),
        "type": "payment_received",
        "fuel_type": None,
        "liters": 0,
        "amount": _safe_float(amount),
        "payment_mode": payment_mode,
        "reference_id": None,
        "status": "pending",
        "created_at": _now(),
    }

    try:
        result = supabase.table("credit_transactions").insert(payload).execute()
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"Error in create_credit_payment_received: {exc}")
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
            .select("*, credit_parties:party_id(name, phone, current_balance, credit_limit)")
            .eq("reference_id", reference_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_credit_transactions_by_reference: {exc}")
        return []


def get_credit_transactions(status: str = None, txn_type: str = None):
    supabase = get_supabase_client()

    try:
        query = supabase.table("credit_transactions").select(
            "*, credit_parties:party_id(name, phone, current_balance, credit_limit)"
        )

        if status:
            query = query.eq("status", status)

        if txn_type:
            query = query.eq("type", txn_type)

        result = query.order("created_at", desc=True).execute()
        return result.data or []
    except Exception as exc:
        print(f"Error in get_credit_transactions: {exc}")
        return []


def get_credit_summary():
    parties = get_all_parties()
    txns = get_credit_transactions()

    summary = {
        "total_creditors": len(parties),
        "active_creditors": sum(1 for p in parties if bool(p.get("is_active"))),
        "outstanding": round(sum(_safe_float(p.get("current_balance")) for p in parties), 2),
        "pending_sales": 0.0,
        "pending_payments": 0.0,
        "pending_count": 0,
    }

    for txn in txns:
        if (txn.get("status") or "pending") == "pending":
            summary["pending_count"] += 1
            if txn.get("type") == "sale":
                summary["pending_sales"] += _safe_float(txn.get("amount"))
            elif txn.get("type") == "payment_received":
                summary["pending_payments"] += _safe_float(txn.get("amount"))

    summary["pending_sales"] = round(summary["pending_sales"], 2)
    summary["pending_payments"] = round(summary["pending_payments"], 2)

    return summary


def approve_credit_transaction(txn_id: int, manager_id: str):
    """
    Sale approve: balance += amount
    Payment_received approve: balance -= amount
    """
    supabase = get_supabase_client()

    try:
        txn_result = (
            supabase.table("credit_transactions")
            .select("*")
            .eq("id", txn_id)
            .limit(1)
            .execute()
        )

        if not txn_result.data:
            return None, "Credit transaction not found."

        txn = txn_result.data[0]

        if txn.get("status") == "approved":
            return None, "Already approved."

        party = get_party_by_id(txn.get("party_id"))

        if not party:
            return None, "Creditor not found."

        amount = _safe_float(txn.get("amount"))
        current_balance = _safe_float(party.get("current_balance"))

        if txn.get("type") == "sale":
            new_balance = current_balance + amount
        elif txn.get("type") == "payment_received":
            new_balance = current_balance - amount
            if new_balance < 0:
                new_balance = 0
        else:
            return None, "Invalid credit transaction type."

        # Update party balance.
        supabase.table("credit_parties").update({
            "current_balance": round(new_balance, 2)
        }).eq("id", party["id"]).execute()

        # Approve transaction.
        result = (
            supabase.table("credit_transactions")
            .update({
                "status": "approved",
                "approved_by": manager_id,
                "approved_at": _now(),
            })
            .eq("id", txn_id)
            .execute()
        )

        return result.data[0] if result.data else None, None

    except Exception as exc:
        print(f"Error in approve_credit_transaction: {exc}")
        return None, str(exc)


def reject_credit_transaction(txn_id: int, manager_id: str, reason: str = None):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("credit_transactions")
            .update({
                "status": "rejected",
                "approved_by": manager_id,
                "approved_at": _now(),
            })
            .eq("id", txn_id)
            .execute()
        )

        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"Error in reject_credit_transaction: {exc}")
        return None, str(exc)


def approve_credit_transactions_by_reference(reference_id: int, manager_id: str):
    txns = get_credit_transactions_by_reference(reference_id)
    pending_txns = [t for t in txns if (t.get("status") or "pending") != "approved"]

    approved = []

    for txn in pending_txns:
        updated, error = approve_credit_transaction(txn.get("id"), manager_id)
        if updated:
            approved.append(updated)

    return approved
