from datetime import date, datetime, timezone
import json
import os
import urllib.request
import urllib.error

import streamlit as st

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


def _secret(name, default=None):
    """
    Reads Streamlit secrets first, then environment variables.
    """
    try:
        value = st.secrets.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    except Exception:
        pass

    value = os.environ.get(name)
    if value is not None and str(value).strip() != "":
        return str(value).strip()

    return default


def normalize_india_phone(phone):
    """
    WhatsApp Cloud API expects international phone number without '+'.
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

    return raw


def build_credit_sale_approval_text(txn, party):
    party_name = (party or {}).get("name") or "Customer"
    date_text = txn.get("date") or _today()
    amount = _money(txn.get("amount"))
    current_balance = _money((party or {}).get("current_balance"))
    ref = txn.get("reference_id") or "-"
    note = txn.get("note") or ""

    msg = (
        f"Dear {party_name},\n"
        f"Your credit sale has been approved.\n\n"
        f"Date: {date_text}\n"
        f"Credit Sale Amount: {amount}\n"
        f"Reference: {ref}\n"
        f"Current Outstanding Balance: {current_balance}\n"
    )

    if note:
        msg += f"Note: {note}\n"

    msg += "\nThank you."
    return msg


def _credit_sale_template_components(txn, party):
    """
    Default approved template variables expected:

    {{1}} creditor name
    {{2}} date
    {{3}} amount
    {{4}} reference
    {{5}} current balance

    Create/approve a WhatsApp template with same variable order.
    Template name is read from WHATSAPP_TEMPLATE_NAME.
    """
    party_name = (party or {}).get("name") or "Customer"
    date_text = txn.get("date") or _today()
    amount = _money(txn.get("amount"))
    ref = txn.get("reference_id") or "-"
    current_balance = _money((party or {}).get("current_balance"))

    return [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": str(party_name)},
                {"type": "text", "text": str(date_text)},
                {"type": "text", "text": str(amount)},
                {"type": "text", "text": str(ref)},
                {"type": "text", "text": str(current_balance)},
            ],
        }
    ]


def _graph_post(path, payload):
    token = _secret("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = _secret("WHATSAPP_PHONE_NUMBER_ID")
    api_version = _secret("WHATSAPP_API_VERSION", "v20.0")

    if not token or not phone_number_id:
        return None, "WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID missing in Streamlit secrets."

    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/{path}"

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
            return json.loads(body or "{}"), None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return None, body or str(exc)
    except Exception as exc:
        return None, str(exc)


def send_whatsapp_template(phone, template_name, language_code, components):
    to_phone = normalize_india_phone(phone)

    if not to_phone:
        return None, "Creditor phone number missing."

    if not template_name:
        return None, "WHATSAPP_TEMPLATE_NAME missing in Streamlit secrets."

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code or "en_US"},
            "components": components or [],
        },
    }

    return _graph_post("messages", payload)


def send_whatsapp_text(phone, message):
    """
    Free-form text usually works only inside WhatsApp's customer service window.
    For automatic business-initiated approval notifications, use template mode.
    """
    to_phone = normalize_india_phone(phone)

    if not to_phone:
        return None, "Creditor phone number missing."

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": False, "body": message or ""},
    }

    return _graph_post("messages", payload)


def _extract_message_id(api_response):
    try:
        messages = (api_response or {}).get("messages") or []
        if messages:
            return messages[0].get("id")
    except Exception:
        pass
    return None


def create_whatsapp_log(txn, party, message, status, provider_response=None, error_message=None, created_by=None):
    supabase = get_supabase_client()
    provider_response = provider_response or {}

    payload = {
        "date": txn.get("date") or _today(),
        "party_id": str(txn.get("party_id")),
        "party_name": (party or {}).get("name"),
        "phone": (party or {}).get("phone"),
        "txn_id": str(txn.get("id")),
        "txn_type": txn.get("type"),
        "amount": _f(txn.get("amount")),
        "message": message,
        "status": status,
        "provider": "whatsapp_cloud_api",
        "provider_message_id": _extract_message_id(provider_response),
        "provider_response": provider_response,
        "error_message": error_message,
        "created_by": created_by,
        "created_at": _now(),
        "sent_by": created_by if status == "sent" else None,
        "sent_at": _now() if status == "sent" else None,
        "failed_at": _now() if status == "failed" else None,
    }

    try:
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
            result = (
                supabase.table("whatsapp_messages")
                .update(payload)
                .eq("id", existing[0].get("id"))
                .execute()
            )
            return (result.data[0] if result.data else existing[0]), None

        result = supabase.table("whatsapp_messages").insert(payload).execute()
        return (result.data[0] if result.data else None), None

    except Exception as exc:
        print("create_whatsapp_log", exc)
        return None, str(exc)


def auto_send_credit_sale_approval_whatsapp(txn_id, created_by=None):
    """
    Automatic WhatsApp on credit sale approval.

    Required Streamlit secrets:
    WHATSAPP_ACCESS_TOKEN
    WHATSAPP_PHONE_NUMBER_ID
    WHATSAPP_TEMPLATE_NAME
    Optional:
    WHATSAPP_TEMPLATE_LANG = en_US / hi / en
    WHATSAPP_SEND_MODE = template or text

    Default is template, because credit approval is business-initiated.
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
            return None, "WhatsApp auto-send only for credit sale approval."

        if txn.get("status") != "approved":
            return None, "WhatsApp auto-send only after approval."

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
        message = build_credit_sale_approval_text(txn, party)

        if not phone:
            row, _log_err = create_whatsapp_log(
                txn,
                party,
                message,
                status="failed",
                error_message="Creditor phone missing.",
                created_by=created_by,
            )
            return row, "Creditor phone missing."

        send_mode = (_secret("WHATSAPP_SEND_MODE", "template") or "template").lower()

        if send_mode == "text":
            api_response, api_error = send_whatsapp_text(phone, message)
        else:
            template_name = _secret("WHATSAPP_TEMPLATE_NAME")
            language_code = _secret("WHATSAPP_TEMPLATE_LANG", "en_US")
            api_response, api_error = send_whatsapp_template(
                phone,
                template_name,
                language_code,
                _credit_sale_template_components(txn, party),
            )

        if api_error:
            row, _log_err = create_whatsapp_log(
                txn,
                party,
                message,
                status="failed",
                provider_response={"error": api_error},
                error_message=api_error,
                created_by=created_by,
            )
            return row, api_error

        row, log_err = create_whatsapp_log(
            txn,
            party,
            message,
            status="sent",
            provider_response=api_response,
            error_message=None,
            created_by=created_by,
        )

        if log_err:
            return row, log_err

        return row, None

    except Exception as exc:
        print("auto_send_credit_sale_approval_whatsapp", exc)
        return None, str(exc)


def get_whatsapp_messages(status="all", limit=100):
    try:
        q = get_supabase_client().table("whatsapp_messages").select("*")

        if status and status != "all":
            q = q.eq("status", status)

        return q.order("created_at", desc=True).limit(limit).execute().data or []

    except Exception as exc:
        print("get_whatsapp_messages", exc)
        return []


def retry_whatsapp_message(message_id, retried_by=None):
    """
    Retry by txn_id using latest transaction data.
    """
    try:
        rows = (
            get_supabase_client()
            .table("whatsapp_messages")
            .select("*")
            .eq("id", message_id)
            .limit(1)
            .execute()
            .data
            or []
        )

        if not rows:
            return None, "WhatsApp message log not found."

        txn_id = rows[0].get("txn_id")
        return auto_send_credit_sale_approval_whatsapp(txn_id, retried_by)

    except Exception as exc:
        return None, str(exc)
