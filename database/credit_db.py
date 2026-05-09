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


# ---------------- Parties ----------------

def get_all_parties():
    try:
        result = (
            get_supabase_client()
            .table("credit_parties")
            .select("*")
            .order("name")
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"get_all_parties error: {exc}")
        return []


def get_active_parties():
    try:
        result = (
            get_supabase_client()
            .table("credit_parties")
            .select("*")
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"get_active_parties error: {exc}")
        return []


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
        print(f"create_credit_party error: {exc}")
        return None, str(exc)


def update_credit_party(party_id, data):
    try:
        result = (
            get_supabase_client()
            .table("credit_parties")
            .update(data)
            .eq("id", party_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"update_credit_party error: {exc}")
        return None, str(exc)


# ---------------- Ledger ----------------

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

        result = query.order("created_at", desc=True).execute()
        return result.data or []
    except Exception as exc:
        print(f"get_credit_transactions error: {exc}")
        return []


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
        print(f"get_credit_txn_by_id error: {exc}")
        return None


def get_existing_credit_sale(party_id, reference_id):
    """
    One credit sale should exist only once for same:
    party_id + type='sale' + reference_id.
    reference_id usually settlement_id / sale reference.
    """
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
        print(f"get_existing_credit_sale error: {exc}")
        return None


def create_or_update_pending_credit_sale(
    party_id,
    amount,
    reference_id=None,
    note=None,
    created_by=None,
    entry_date=None,
):
    """
    Duplicate guard:
    - Same party + same reference_id + type=sale par new duplicate create nahi hoga.
    - Pending/hold/reopened row milne par update hoga.
    - Approved row milne par same row return hogi, balance dobara post nahi hoga.
    """
    if not party_id:
        return None, "Creditor required."
    if _f(amount) <= 0:
        return None, "Credit sale amount required."

    supabase = get_supabase_client()
    reference_id = str(reference_id) if reference_id is not None else None

    try:
        existing = get_existing_credit_sale(party_id, reference_id)

        if existing:
            if existing.get("status") == "approved":
                return existing, None

            result = (
                supabase.table("credit_transactions")
                .update({
                    "amount": _f(amount),
                    "note": note,
                    "created_by": created_by,
                })
                .eq("id", existing.get("id"))
                .execute()
            )
            return result.data[0] if result.data else None, None

        payload = {
            "date": entry_date or _today(),
            "party_id": party_id,
            "type": "sale",
            "amount": _f(amount),
            "payment_mode": "credit",
            "reference_id": reference_id,
            "note": note,
            "status": "pending",
            "created_by": created_by,
            "created_at": _now(),
        }

        result = supabase.table("credit_transactions").insert(payload).execute()
        return result.data[0] if result.data else None, None

    except Exception as exc:
        print(f"create_or_update_pending_credit_sale error: {exc}")
        return None, str(exc)


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

    payload = {
        "date": data.get("date") or _today(),
        "party_id": party_id,
        "type": "payment_received",
        "amount": amount,
        "payment_mode": mode,
        "bank_name": data.get("bank_name"),
        "reference_id": data.get("reference_id"),
        "note": data.get("note"),
        "status": "pending",
        "created_by": data.get("created_by"),
        "created_at": _now(),
    }

    try:
        result = get_supabase_client().table("credit_transactions").insert(payload).execute()
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"create_credit_payment error: {exc}")
        return None, str(exc)


# ---------------- Approval + balance guard ----------------

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
        print(f"_set_txn_status error: {exc}")
        return None, str(exc)


def _adjust_party_balance(party_id, delta):
    try:
        rows = (
            get_supabase_client()
            .table("credit_parties")
            .select("*")
            .eq("id", party_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return None, "Credit party not found."

        current = _f(rows[0].get("current_balance"))
        new_balance = round(current + _f(delta), 2)

        result = (
            get_supabase_client()
            .table("credit_parties")
            .update({"current_balance": new_balance})
            .eq("id", party_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"_adjust_party_balance error: {exc}")
        return None, str(exc)


def approve_credit_transaction(txn_id, approved_by=None, note=None):
    """
    Critical guard:
    - Already approved transaction ko dobara approve karne par balance dobara adjust nahi hoga.
    - Duplicate approved sale for same party/reference ko block karta hai.
    """
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
            dup = (
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
            if dup:
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


# ---------------- Duplicate cleanup helpers ----------------

def recalculate_all_credit_party_balances():
    """
    Approved ledger se current_balance rebuild karta hai.
    Duplicate rows remove/reject karne ke baad run karna useful hai.
    """
    parties = get_all_parties()
    txns = get_credit_transactions(status="approved")

    calc = {}
    for party in parties:
        calc[party.get("id")] = 0.0

    for txn in txns:
        pid = txn.get("party_id")
        if pid not in calc:
            calc[pid] = 0.0

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
            print(f"recalculate balance error for {pid}: {exc}")

    return updated


# aliases for old modules
get_all_credit_parties = get_all_parties
get_active_credit_parties = get_active_parties
