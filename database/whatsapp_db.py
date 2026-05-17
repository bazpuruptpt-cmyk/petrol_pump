from datetime import date, datetime, timezone
from urllib.parse import quote

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


def _money(value):
    return f"₹{_f(value):,.2f}"


def normalize_india_phone(phone):
    """
    WhatsApp wa.me requires country code without +.
    Default India:
    - 9876543210 -> 919876543210
    - 09876543210 -> 919876543210
    - +919876543210 -> 919876543210
    """
    raw = "".join(ch for ch in str(phone or "") if ch.isdigit())

    if not raw:
        return ""

    if len(raw) == 10:
        return "91" + raw

    if len(raw) == 11 and raw.startswith("0"):
        return "91" + raw[1:]

    if len(raw) == 12 and raw.startswith("91"):
        return raw

    # keep as entered if already has country code length
    return raw


def build_whatsapp_url(phone, message):
    mobile = normalize_india_phone(phone)
    if not mobile:
        return ""
    return f"https://wa.me/{mobile}?text={quote(message or '')}"


def build_credit_sale_approval_message(txn, party):
    party_name = (party or {}).get("name") or "Sir"
    date_text = txn.get("date") or _today()
    amount = _money(txn.get("amount"))
    current_balance = _money((party or {}).get("current_balance"))
    ref = txn.get("reference_id") or "-"
    note = txn.get("note") or ""

    msg = (
        f"Dear {party_name},\\n"
        f"Your credit sale has been approved.\\n\\n"
        f"Date: {date_text}\\n"
        f"Credit Sale Amount: {amount}\\n"
        f"Reference: {ref}\\n"
        f"Current Outstanding Balance: {current_balance}\\n"
    )

    if note:
        msg += f"Note: {note}\\n"

    msg += "\\nThank you."
    return msg


def create_credit_sale_whatsapp_queue(txn_id, created_by=None):
    """
    Creates/updates pending WhatsApp message for approved credit sale.

    This is intentionally manual-send through WhatsApp Web link.
    Real automatic WhatsApp sending requires WhatsApp Business API credentials.
    """
    supabase = get_supabase_client()

    try:
        txn_rows = (
            supabase.table("credit_transactions")
            .select("*")
            .eq("id", txn_id)
            .limit(1)
            .execute()
            .data
            or []
        )

        if not txn_rows:
            return None, "Credit transaction not found."

        txn = txn_rows[0]

        if txn.get("type") != "sale":
            return None, "WhatsApp only for credit sale approval."

        if txn.get("status") != "approved":
            return None, "WhatsApp queue only after approval."

        party_rows = (
            supabase.table("credit_parties")
            .select("*")
            .eq("id", txn.get("party_id"))
            .limit(1)
            .execute()
            .data
            or []
        )

        party = party_rows[0] if party_rows else {}

        phone = party.get("phone")
        message = build_credit_sale_approval_message(txn, party)
        whatsapp_url = build_whatsapp_url(phone, message)

        payload = {
            "date": txn.get("date") or _today(),
            "party_id": str(txn.get("party_id")),
            "party_name": party.get("name"),
            "phone": phone,
            "txn_id": str(txn.get("id")),
            "txn_type": txn.get("type"),
            "amount": _f(txn.get("amount")),
            "message": message,
            "whatsapp_url": whatsapp_url,
            "status": "pending",
            "created_by": created_by,
            "created_at": _now(),
        }

        # Duplicate guard: one message per credit transaction.
        existing = (
            supabase.table("whatsapp_messages")
            .select("*")
            .eq("txn_id", str(txn.get("id")))
            .limit(1)
            .execute()
            .data
            or []
        )

        if existing:
            row_id = existing[0].get("id")
            result = (
                supabase.table("whatsapp_messages")
                .update(payload)
                .eq("id", row_id)
                .execute()
            )
            return (result.data[0] if result.data else existing[0]), None

        result = supabase.table("whatsapp_messages").insert(payload).execute()
        return (result.data[0] if result.data else None), None

    except Exception as exc:
        print("create_credit_sale_whatsapp_queue", exc)
        return None, str(exc)


def get_whatsapp_messages(status="pending", limit=100):
    try:
        q = get_supabase_client().table("whatsapp_messages").select("*")

        if status and status != "all":
            q = q.eq("status", status)

        rows = q.order("created_at", desc=True).limit(limit).execute().data or []
        return rows
    except Exception as exc:
        print("get_whatsapp_messages", exc)
        return []


def mark_whatsapp_sent(message_id, sent_by=None):
    try:
        result = (
            get_supabase_client()
            .table("whatsapp_messages")
            .update({
                "status": "sent",
                "sent_by": sent_by,
                "sent_at": _now(),
            })
            .eq("id", message_id)
            .execute()
        )
        return (result.data[0] if result.data else None), None
    except Exception as exc:
        print("mark_whatsapp_sent", exc)
        return None, str(exc)


def mark_whatsapp_pending(message_id):
    try:
        result = (
            get_supabase_client()
            .table("whatsapp_messages")
            .update({
                "status": "pending",
                "sent_by": None,
                "sent_at": None,
            })
            .eq("id", message_id)
            .execute()
        )
        return (result.data[0] if result.data else None), None
    except Exception as exc:
        print("mark_whatsapp_pending", exc)
        return None, str(exc)
