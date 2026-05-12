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
# Helpers required by modules/manager/credit_parties.py
# ============================================================

def vehicle_text_to_list(text):
    if not text:
        return []
    if isinstance(text, list):
        return [str(x).strip() for x in text if str(x).strip()]
    return [x.strip() for x in str(text).replace(",", "\n").splitlines() if x.strip()]


def list_to_vehicle_text(items):
    if not items:
        return ""
    if isinstance(items, str):
        return items
    return "\n".join(str(x).strip() for x in items if str(x).strip())


# ============================================================
# Credit parties
# ============================================================

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
        print("get_all_parties error:", exc)
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


def create_party(name, phone=None, credit_limit=0, vehicles_text=None, created_by=None):
    return create_credit_party(name, phone, credit_limit, vehicles_text, created_by)


def create_credit_party(name, phone=None, credit_limit=0, vehicles_text=None, created_by=None):
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
        party = result.data[0] if result.data else None

        # vehicles column optional hai. Missing ho to ignore.
        if party and vehicles_text:
            try:
                get_supabase_client().table("credit_parties").update(
                    {"vehicles": vehicle_text_to_list(vehicles_text)}
                ).eq("id", party.get("id")).execute()
            except Exception:
                pass

        return party, None
    except Exception as exc:
        print("create_credit_party error:", exc)
        return None, str(exc)


def update_party(party_id, name=None, phone=None, credit_limit=None, vehicles_text=None, is_active=None):
    return update_credit_party(
        party_id=party_id,
        name=name,
        phone=phone,
        credit_limit=credit_limit,
        vehicles_text=vehicles_text,
        is_active=is_active,
    )


def update_credit_party(party_id, data=None, name=None, phone=None, credit_limit=None, vehicles_text=None, is_active=None):
    payload = data.copy() if isinstance(data, dict) else {}

    if name is not None:
        payload["name"] = name
    if phone is not None:
        payload["phone"] = phone
    if credit_limit is not None:
        payload["credit_limit"] = _f(credit_limit)
    if is_active is not None:
        payload["is_active"] = bool(is_active)
    if vehicles_text is not None:
        payload["vehicles"] = vehicle_text_to_list(vehicles_text)

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
        # optional vehicles column missing ho to retry.
        if "vehicles" in payload:
            payload.pop("vehicles", None)
            try:
                result = (
                    get_supabase_client()
                    .table("credit_parties")
                    .update(payload)
                    .eq("id", party_id)
                    .execute()
                )
                return result.data[0] if result.data else None, None
            except Exception as exc2:
                print("update_credit_party retry error:", exc2)
                return None, str(exc2)

        print("update_credit_party error:", exc)
        return None, str(exc)


def toggle_party_active(party_id, is_active):
    return update_credit_party(party_id, {"is_active": bool(is_active)})


def set_credit_party_active(party_id, is_active=True):
    return toggle_party_active(party_id, is_active)


def delete_party(party_id):
    return toggle_party_active(party_id, False)


# ============================================================
# Credit transactions / ledger
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

        result = query.order("created_at", desc=True).execute()
        return result.data or []
    except Exception as exc:
        print("get_credit_transactions error:", exc)
        return []


def get_credit_transactions_by_party(party_id):
    return get_credit_transactions(party_id=party_id)


def get_credit_ledger_by_party(party_id):
    return get_credit_transactions(party_id=party_id)


def get_credit_transactions_by_reference(reference_id, txn_type=None, status=None):
    try:
        query = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*, credit_parties:party_id(name, phone, current_balance)")
            .eq("reference_id", str(reference_id))
        )

        if txn_type:
            query = query.eq("type", txn_type)
        if status:
            query = query.eq("status", status)

        result = query.order("created_at", desc=True).execute()
        return result.data or []
    except Exception as exc:
        print("get_credit_transactions_by_reference error:", exc)
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




def get_existing_credit_transaction_by_type(party_id, reference_id, txn_type):
    if not party_id or reference_id is None or not txn_type:
        return None

    try:
        result = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*")
            .eq("party_id", party_id)
            .eq("type", txn_type)
            .eq("reference_id", str(reference_id))
            .in_("status", ["pending", "approved", "hold", "reopened", "rejected"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print("get_existing_credit_transaction_by_type error:", exc)
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
    vehicle_number=None,
    fuel_type=None,
    liters=None,
):
    if not party_id:
        return None, "Creditor required."
    if _f(amount) <= 0:
        return None, "Amount must be greater than 0."
    if txn_type not in ["sale", "payment_received", "cash_given", "transfer_out", "transfer_in"]:
        return None, "Invalid credit transaction type."

    final_note = note
    extra = []
    if vehicle_number:
        extra.append(f"Vehicle: {vehicle_number}")
    if fuel_type:
        extra.append(f"Fuel: {fuel_type}")
    if liters is not None:
        extra.append(f"Liters: {liters}")
    if extra:
        final_note = (final_note + " | " if final_note else "") + ", ".join(extra)

    payload = {
        "date": entry_date or _today(),
        "party_id": party_id,
        "type": txn_type,
        "amount": _f(amount),
        "payment_mode": payment_mode or ("credit" if txn_type in ["sale", "cash_given", "transfer_out", "transfer_in"] else None),
        "bank_name": bank_name,
        "reference_id": str(reference_id) if reference_id is not None else None,
        "note": final_note,
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


def create_or_update_pending_credit_sale(
    party_id,
    amount,
    reference_id=None,
    note=None,
    created_by=None,
    entry_date=None,
    vehicle_number=None,
    fuel_type=None,
    liters=None,
    status="pending",
):
    """
    Duplicate guard:
    sale_db.py payment breakup dobara save kare to same party + reference_id par duplicate row nahi banegi.
    """
    if not party_id:
        return None, "Creditor required."
    if _f(amount) <= 0:
        return None, "Credit sale amount required."

    reference_id = str(reference_id) if reference_id is not None else None
    existing = get_existing_credit_sale(party_id, reference_id)

    final_note = note
    extra = []
    if vehicle_number:
        extra.append(f"Vehicle: {vehicle_number}")
    if fuel_type:
        extra.append(f"Fuel: {fuel_type}")
    if liters is not None:
        extra.append(f"Liters: {liters}")
    if extra:
        final_note = (final_note + " | " if final_note else "") + ", ".join(extra)

    if existing:
        if existing.get("status") == "approved":
            return existing, None

        try:
            result = (
                get_supabase_client()
                .table("credit_transactions")
                .update({
                    "amount": _f(amount),
                    "note": final_note,
                    "status": status or existing.get("status") or "pending",
                })
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
        note=final_note,
        created_by=created_by,
        entry_date=entry_date,
        status=status or "pending",
        vehicle_number=vehicle_number,
        fuel_type=fuel_type,
        liters=liters,
    )


def create_credit_sale_transaction(
    party_id,
    amount,
    reference_id=None,
    fuel_type=None,
    liters=0,
    vehicle_number=None,
    status="pending",
    created_by=None,
    entry_date=None,
    note=None,
):
    """
    Required by database/sale_db.py.
    This is the exact missing function from uploaded project.
    """
    return create_or_update_pending_credit_sale(
        party_id=party_id,
        amount=amount,
        reference_id=reference_id,
        note=note,
        created_by=created_by,
        entry_date=entry_date,
        vehicle_number=vehicle_number,
        fuel_type=fuel_type,
        liters=liters,
        status=status or "pending",
    )



def create_credit_cash_given_transaction(
    party_id,
    amount,
    reference_id=None,
    vehicle_number=None,
    status="pending",
    created_by=None,
    entry_date=None,
    note=None,
):
    """
    Salesman ne daily cash se creditor ko cash diya.
    Yeh sale matching ka part nahi hai; yeh creditor-wise recoverable ledger row hai.

    Required for manager display:
    - kis creditor ko cash diya
    - kitna cash diya
    """
    if not party_id:
        return None, "Creditor required for cash given."
    if _f(amount) <= 0:
        return None, "Cash given amount required."

    reference_id = str(reference_id) if reference_id is not None else None
    existing = get_existing_credit_transaction_by_type(party_id, reference_id, "cash_given")

    final_note = note or "Cash given to creditor by salesman"
    if vehicle_number:
        final_note = (final_note + " | " if final_note else "") + f"Vehicle: {vehicle_number}"

    if existing:
        if existing.get("status") == "approved":
            return existing, None

        try:
            result = (
                get_supabase_client()
                .table("credit_transactions")
                .update({
                    "amount": _f(amount),
                    "note": final_note,
                    "status": status or "pending",
                    "payment_mode": "credit",
                    "vehicle_number": vehicle_number,
                })
                .eq("id", existing.get("id"))
                .execute()
            )
            return result.data[0] if result.data else None, None
        except Exception as exc:
            print("create_credit_cash_given_transaction update error:", exc)
            return None, str(exc)

    return create_credit_transaction(
        party_id=party_id,
        txn_type="cash_given",
        amount=amount,
        payment_mode="credit",
        reference_id=reference_id,
        note=final_note,
        created_by=created_by,
        entry_date=entry_date,
        status=status or "pending",
        vehicle_number=vehicle_number,
    )


def create_credit_payment(data):
    mode = data.get("payment_mode")
    if mode not in ["cash", "bank", "paytm", "ccms"]:
        return None, "Payment mode must be cash/bank/paytm/ccms."

    return create_credit_transaction(
        party_id=data.get("party_id"),
        txn_type="payment_received",
        amount=data.get("amount"),
        payment_mode=mode,
        bank_name=data.get("bank_name"),
        reference_id=data.get("reference_id"),
        note=data.get("note"),
        created_by=data.get("created_by"),
        entry_date=data.get("date"),
        status="pending",
    )


# ============================================================
# Approval
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

    if txn_type in ["sale", "cash_given", "transfer_in"]:
        delta = amount
    elif txn_type in ["payment_received", "transfer_out"]:
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


def approve_credit_transactions_by_reference(reference_id, approved_by=None, note=None):
    rows = []
    rows.extend(get_credit_transactions_by_reference(reference_id, txn_type="sale"))
    rows.extend(get_credit_transactions_by_reference(reference_id, txn_type="cash_given"))
    approved = []
    errors = []

    for row in rows:
        if row.get("status") == "approved":
            approved.append(row)
            continue

        if row.get("status") in ["pending", "hold", "reopened"]:
            updated, error = approve_credit_transaction(row.get("id"), approved_by, note)
            if updated:
                approved.append(updated)
            else:
                errors.append({"id": row.get("id"), "error": error or "Approval failed"})

    return approved, (errors if errors else None)


def reject_credit_transactions_by_reference(reference_id, approved_by=None, note=None):
    """
    Full rejection cleanup:
    - Fuel credit rows: type='sale'
    - Cash given rows: type='cash_given'

    Approved rows cannot be rejected here.
    Pending/hold/reopened/rejected rows are safely moved to rejected.
    """
    rejected = []
    errors = []

    rows = []
    for txn_type in ["sale", "cash_given"]:
        rows.extend(get_credit_transactions_by_reference(reference_id, txn_type=txn_type) or [])

    seen = set()
    clean_rows = []
    for row in rows:
        rid = row.get("id")
        if rid in seen:
            continue
        seen.add(rid)
        clean_rows.append(row)

    for row in clean_rows:
        if row.get("status") == "approved":
            errors.append({"id": row.get("id"), "error": "Approved row cannot be rejected here."})
            continue

        if row.get("status") == "rejected":
            rejected.append(row)
            continue

        updated, error = reject_credit_transaction(row.get("id"), approved_by, note)
        if updated:
            rejected.append(updated)
        else:
            errors.append({"id": row.get("id"), "error": error or "Reject failed"})

    return rejected, (errors if errors else None)


def recalculate_all_credit_party_balances():
    parties = get_all_parties()
    txns = get_credit_transactions(status="approved")
    calc = {p.get("id"): 0.0 for p in parties}

    for txn in txns:
        pid = txn.get("party_id")
        calc.setdefault(pid, 0.0)
        if txn.get("type") in ["sale", "cash_given", "transfer_in"]:
            calc[pid] += _f(txn.get("amount"))
        elif txn.get("type") in ["payment_received", "transfer_out"]:
            calc[pid] -= _f(txn.get("amount"))

    updated = 0
    for pid, balance in calc.items():
        try:
            get_supabase_client().table("credit_parties").update(
                {"current_balance": round(balance, 2)}
            ).eq("id", pid).execute()
            updated += 1
        except Exception as exc:
            print("recalculate balance error:", exc)

    return updated




# ============================================================
# Creditor Correction: Wrong creditor -> Correct creditor
# ============================================================

def get_correctable_credit_transactions(limit=100):
    """
    Approved fuel credit / cash given rows only.
    Payment modes/cash/paytm/ccms are untouched.
    """
    try:
        rows = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*, credit_parties:party_id(name, phone, current_balance)")
            .in_("type", ["sale", "cash_given"])
            .eq("status", "approved")
            .order("created_at", desc=True)
            .limit(limit or 100)
            .execute()
            .data
            or []
        )
        return rows
    except Exception as exc:
        print("get_correctable_credit_transactions error:", exc)
        return []


def create_creditor_transfer_correction(
    original_txn_id,
    correct_party_id,
    amount,
    reason,
    created_by=None,
):
    """
    Atomic correction through SQL RPC.

    Effect:
    Wrong creditor: transfer_out => balance minus
    Correct creditor: transfer_in => balance plus

    Total sale / cash / paytm / ccms untouched.
    """
    if not original_txn_id:
        return None, "Original transaction required."

    if not correct_party_id:
        return None, "Correct creditor required."

    if _f(amount) <= 0:
        return None, "Correction amount must be greater than 0."

    if not (reason or "").strip():
        return None, "Reason required."

    try:
        result = (
            get_supabase_client()
            .rpc(
                "creditor_transfer_correction",
                {
                    "p_original_txn_id": int(original_txn_id),
                    "p_correct_party_id": correct_party_id,
                    "p_amount": _f(amount),
                    "p_reason": reason.strip(),
                    "p_created_by": created_by,
                },
            )
            .execute()
        )
        return result.data, None
    except Exception as exc:
        print("create_creditor_transfer_correction error:", exc)
        return None, str(exc)


def get_creditor_transfer_corrections(limit=100):
    try:
        rows = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*, credit_parties:party_id(name, phone, current_balance)")
            .in_("type", ["transfer_out", "transfer_in"])
            .order("created_at", desc=True)
            .limit(limit or 100)
            .execute()
            .data
            or []
        )
        return rows
    except Exception as exc:
        print("get_creditor_transfer_corrections error:", exc)
        return []



# ============================================================
# Aliases
# ============================================================

get_all_credit_parties = get_all_parties
get_active_credit_parties = get_active_parties
get_party_by_id = get_credit_party_by_id
get_credit_party = get_credit_party_by_id

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

approve_credit_by_reference = approve_credit_transactions_by_reference
reject_credit_by_reference = reject_credit_transactions_by_reference

create_cash_given_to_creditor = create_credit_cash_given_transaction
