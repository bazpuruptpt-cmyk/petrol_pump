from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client


def _now():
    return datetime.now(timezone.utc).isoformat()


def _today():
    return date.today().isoformat()


def _f(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


# ============================================================
# PARTIES
# ============================================================

def get_all_parties():
    try:
        return (
            get_supabase_client()
            .table("credit_parties")
            .select("*")
            .order("name")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print("get_all_parties error:", exc)
        return []


def get_active_parties():
    try:
        return (
            get_supabase_client()
            .table("credit_parties")
            .select("*")
            .eq("is_active", True)
            .order("name")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print("get_active_parties error:", exc)
        return []


def get_credit_party_by_id(party_id):
    try:
        result = (
            get_supabase_client()
            .table("credit_parties")
            .select("*")
            .eq("id", party_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print("get_credit_party_by_id error:", exc)
        return None


def create_credit_party(name, phone=None, credit_limit=0, created_by=None):
    if not name:
        return None, "Creditor name required."

    payload = {
        "name": name,
        "phone": phone,
        "credit_limit": _f(credit_limit),
        "current_balance": 0,
        "is_active": True,
        "created_by": created_by,
        "created_at": _now(),
    }

    try:
        result = get_supabase_client().table("credit_parties").insert(payload).execute()
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print("create_credit_party error:", exc)
        return None, str(exc)


def update_credit_party(party_id, data=None, name=None, phone=None, credit_limit=None, is_active=None):
    payload = data.copy() if isinstance(data, dict) else {}

    if name is not None:
        payload["name"] = name
    if phone is not None:
        payload["phone"] = phone
    if credit_limit is not None:
        payload["credit_limit"] = _f(credit_limit)
    if is_active is not None:
        payload["is_active"] = bool(is_active)

    if not payload:
        return None, "No data to update."

    try:
        result = (
            get_supabase_client()
            .table("credit_parties")
            .update(payload)
            .eq("id", party_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print("update_credit_party error:", exc)
        return None, str(exc)


def delete_credit_party(party_id):
    # safer than hard delete
    return update_credit_party(party_id, {"is_active": False})


def set_credit_party_active(party_id, is_active=True):
    return update_credit_party(party_id, {"is_active": bool(is_active)})


# ============================================================
# TRANSACTIONS / LEDGER
# ============================================================

def get_credit_transactions(status=None, txn_type=None, party_id=None):
    try:
        query = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*, credit_parties:party_id(name, phone, current_balance)")
        )

        if status:
            query = query.eq("status", status)
        if txn_type:
            query = query.eq("type", txn_type)
        if party_id:
            query = query.eq("party_id", party_id)

        return query.order("created_at", desc=True).execute().data or []
    except Exception as exc:
        print("get_credit_transactions error:", exc)
        return []


def get_credit_transactions_by_party(party_id):
    return get_credit_transactions(party_id=party_id)


def get_credit_ledger_by_party(party_id):
    return get_credit_transactions(party_id=party_id)


def get_credit_txn_by_id(txn_id):
    try:
        result = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*")
            .eq("id", txn_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print("get_credit_txn_by_id error:", exc)
        return None


def get_existing_credit_sale(party_id, reference_id):
    if not party_id or reference_id is None:
        return None

    try:
        result = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*")
            .eq("party_id", party_id)
            .eq("type", "sale")
            .eq("reference_id", str(reference_id))
            .in_("status", ["pending", "approved", "hold", "reopened"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print("get_existing_credit_sale error:", exc)
        return None


def create_credit_transaction(
    party_id,
    txn_type,
    amount,
    payment_mode=None,
    reference_id=None,
    note=None,
    created_by=None,
    entry_date=None,
    status="pending",
    bank_name=None,
):
    if not party_id:
        return None, "Creditor required."
    if _f(amount) <= 0:
        return None, "Amount must be greater than 0."
    if txn_type not in ["sale", "payment_received"]:
        return None, "Invalid credit transaction type."

    payload = {
        "date": entry_date or _today(),
        "party_id": party_id,
        "type": txn_type,
        "amount": _f(amount),
        "payment_mode": payment_mode or ("credit" if txn_type == "sale" else None),
        "bank_name": bank_name,
        "reference_id": str(reference_id) if reference_id is not None else None,
        "note": note,
        "status": status,
        "created_by": created_by,
        "created_at": _now(),
    }

    try:
        result = get_supabase_client().table("credit_transactions").insert(payload).execute()
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print("create_credit_transaction error:", exc)
        return None, str(exc)


def create_or_update_pending_credit_sale(party_id, amount, reference_id=None, note=None, created_by=None, entry_date=None):
    if not party_id:
        return None, "Creditor required."
    if _f(amount) <= 0:
        return None, "Credit sale amount required."

    reference_id = str(reference_id) if reference_id is not None else None

    existing = get_existing_credit_sale(party_id, reference_id)
    if existing:
        if existing.get("status") == "approved":
            return existing, None

        try:
            result = (
                get_supabase_client()
                .table("credit_transactions")
                .update({"amount": _f(amount), "note": note, "created_by": created_by})
                .eq("id", existing.get("id"))
                .execute()
            )
            return result.data[0] if result.data else None, None
        except Exception as exc:
            print("create_or_update_pending_credit_sale update error:", exc)
            return None, str(exc)

    return create_credit_transaction(
        party_id=party_id,
        txn_type="sale",
        amount=amount,
        payment_mode="credit",
        reference_id=reference_id,
        note=note,
        created_by=created_by,
        entry_date=entry_date,
        status="pending",
    )


def create_credit_payment(data):
    party_id = data.get("party_id")
    amount = _f(data.get("amount"))
    mode = data.get("payment_mode")

    if not party_id:
        return None, "Creditor required."
    if amount <= 0:
        return None, "Payment amount must be greater than 0."
    if mode not in ["cash", "bank", "paytm", "ccms"]:
        return None, "Payment mode must be cash/bank/paytm/ccms."

    return create_credit_transaction(
        party_id=party_id,
        txn_type="payment_received",
        amount=amount,
        payment_mode=mode,
        bank_name=data.get("bank_name"),
        reference_id=data.get("reference_id"),
        note=data.get("note"),
        created_by=data.get("created_by"),
        entry_date=data.get("date"),
        status="pending",
    )


# ============================================================
# APPROVAL
# ============================================================

def _set_txn_status(txn_id, status, approved_by=None, note=None):
    try:
        result = (
            get_supabase_client()
            .table("credit_transactions")
            .update({
                "status": status,
                "approved_by": approved_by,
                "approved_at": _now(),
                "approval_note": note,
            })
            .eq("id", txn_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print("_set_txn_status error:", exc)
        return None, str(exc)


def _adjust_party_balance(party_id, delta):
    party = get_credit_party_by_id(party_id)
    if not party:
        return None, "Credit party not found."

    current = _f(party.get("current_balance"))
    new_balance = round(current + _f(delta), 2)

    try:
        result = (
            get_supabase_client()
            .table("credit_parties")
            .update({"current_balance": new_balance})
            .eq("id", party_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print("_adjust_party_balance error:", exc)
        return None, str(exc)


def approve_credit_transaction(txn_id, approved_by=None, note=None):
    txn = get_credit_txn_by_id(txn_id)
    if not txn:
        return None, "Credit transaction not found."

    if txn.get("status") == "approved":
        return txn, "Already approved."

    txn_type = txn.get("type")
    party_id = txn.get("party_id")
    reference_id = txn.get("reference_id")
    amount = _f(txn.get("amount"))

    if txn_type == "sale" and reference_id is not None:
        try:
            duplicate = (
                get_supabase_client()
                .table("credit_transactions")
                .select("*")
                .eq("party_id", party_id)
                .eq("type", "sale")
                .eq("reference_id", str(reference_id))
                .eq("status", "approved")
                .neq("id", txn_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if duplicate:
                _set_txn_status(txn_id, "rejected", approved_by, "Duplicate sale reference auto-rejected")
                return None, "Duplicate approved credit sale found. This row auto-rejected."
        except Exception as exc:
            return None, str(exc)

    if txn_type == "sale":
        delta = amount
    elif txn_type == "payment_received":
        delta = -amount
    else:
        return None, "Invalid credit transaction type."

    _, balance_error = _adjust_party_balance(party_id, delta)
    if balance_error:
        return None, balance_error

    return _set_txn_status(txn_id, "approved", approved_by, note)


def reject_credit_transaction(txn_id, approved_by=None, note=None):
    return _set_txn_status(txn_id, "rejected", approved_by, note)


def hold_credit_transaction(txn_id, approved_by=None, note=None):
    return _set_txn_status(txn_id, "hold", approved_by, note)


def reopen_credit_transaction(txn_id, approved_by=None, note=None):
    return _set_txn_status(txn_id, "reopened", approved_by, note)


def recalculate_all_credit_party_balances():
    parties = get_all_parties()
    txns = get_credit_transactions(status="approved")
    calc = {p.get("id"): 0.0 for p in parties}

    for txn in txns:
        pid = txn.get("party_id")
        calc.setdefault(pid, 0.0)

        if txn.get("type") == "sale":
            calc[pid] += _f(txn.get("amount"))
        elif txn.get("type") == "payment_received":
            calc[pid] -= _f(txn.get("amount"))

    updated = 0
    for pid, balance in calc.items():
        try:
            get_supabase_client().table("credit_parties").update(
                {"current_balance": round(balance, 2)}
            ).eq("id", pid).execute()
            updated += 1
        except Exception as exc:
            print(f"recalculate balance error for {pid}:", exc)

    return updated


# ============================================================
# DIRECT ALIASES FOR OLD IMPORTS
# ============================================================

get_all_credit_parties = get_all_parties
get_active_credit_parties = get_active_parties
get_party_by_id = get_credit_party_by_id
get_credit_party = get_credit_party_by_id
create_party = create_credit_party
update_party = update_credit_party
delete_party = delete_credit_party

create_pending_credit_sale = create_or_update_pending_credit_sale
create_credit_sale = create_or_update_pending_credit_sale

approve_credit_txn = approve_credit_transaction
reject_credit_txn = reject_credit_transaction
hold_credit_txn = hold_credit_transaction
reopen_credit_txn = reopen_credit_transaction

approve_transaction = approve_credit_transaction
reject_transaction = reject_credit_transaction
hold_transaction = hold_credit_transaction
reopen_transaction = reopen_credit_transaction


# ============================================================
# LAST-RESORT IMPORT COMPATIBILITY
# Prevents ImportError when older pages import old function names.
# ============================================================

def _safe_stub_return_list(*args, **kwargs):
    return []


def _safe_stub_return_tuple(*args, **kwargs):
    return None, "Function alias not implemented in credit_db.py"


def __getattr__(name):
    if name.startswith("get_") or name.startswith("list_"):
        return _safe_stub_return_list

    if name.startswith("create_") or name.startswith("update_") or name.startswith("delete_"):
        return _safe_stub_return_tuple

    if name.startswith("approve_") or name.startswith("reject_") or name.startswith("hold_") or name.startswith("reopen_"):
        return _safe_stub_return_tuple

    raise AttributeError(f"module database.credit_db has no attribute {name}")
