from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client

PAYMENT_MODES = ["cash", "bank", "paytm", "ccms"]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _today():
    return date.today().isoformat()


def _f(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _safe_int_or_none(value):
    """
    credit_transactions.reference_id schema me integer ho sakta hai.
    Blank/text UTR ko integer column me insert nahi karna.
    """
    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    if value.isdigit():
        return int(value)

    return None


def _merge_reference_into_note(note, reference_text):
    note = (note or "").strip()
    reference_text = (reference_text or "").strip()

    if not reference_text:
        return note

    if reference_text.isdigit():
        return note

    ref_line = f"Reference/UTR: {reference_text}"

    if note:
        return f"{ref_line} | Note: {note}"

    return ref_line


def get_active_credit_parties():
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
        print(f"get_active_credit_parties error: {exc}")
        return []


def create_credit_payment(data: dict):
    party_id = data.get("party_id")
    amount = _f(data.get("amount"))
    mode = data.get("payment_mode")

    if not party_id:
        return None, "Creditor required."

    if amount <= 0:
        return None, "Payment amount must be greater than 0."

    if mode not in PAYMENT_MODES:
        return None, "Payment mode must be cash, bank, paytm or ccms."

    reference_text = data.get("reference_id")
    note = _merge_reference_into_note(data.get("note"), reference_text)

    payload = {
        "date": data.get("date") or _today(),
        "party_id": party_id,
        "type": "payment_received",
        "amount": amount,
        "payment_mode": mode,
        "bank_name": data.get("bank_name") or None,
        "reference_id": _safe_int_or_none(reference_text),
        "note": note or None,
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


def get_credit_payments(entry_date=None, status=None, payment_mode=None):
    try:
        query = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*, credit_parties:party_id(name, phone, current_balance)")
            .eq("type", "payment_received")
        )

        if entry_date:
            query = query.eq("date", entry_date)

        if status:
            query = query.eq("status", status)

        if payment_mode:
            query = query.eq("payment_mode", payment_mode)

        result = query.order("created_at", desc=True).execute()
        return result.data or []
    except Exception as exc:
        print(f"get_credit_payments error: {exc}")
        return []


def get_approved_credit_collection_summary(entry_date=None):
    rows = get_credit_payments(entry_date=entry_date, status="approved")

    summary = {
        "cash": 0.0,
        "bank": 0.0,
        "paytm": 0.0,
        "ccms": 0.0,
        "total": 0.0,
    }

    for row in rows:
        mode = row.get("payment_mode")
        amount = _f(row.get("amount"))

        if mode in summary:
            summary[mode] += amount
            summary["total"] += amount

    return {k: round(v, 2) for k, v in summary.items()}


def get_credit_collection_rows(entry_date=None, status=None):
    rows = get_credit_payments(entry_date=entry_date, status=status)

    output = []
    for row in rows:
        party = row.get("credit_parties") or {}
        output.append({
            "ID": row.get("id"),
            "Date": row.get("date"),
            "Creditor": party.get("name"),
            "Amount": round(_f(row.get("amount")), 2),
            "Mode": row.get("payment_mode"),
            "Bank/Source": row.get("bank_name"),
            "Reference": row.get("reference_id"),
            "Status": row.get("status"),
            "Narration": row.get("note"),
            "Created At": row.get("created_at"),
        })

    return output
