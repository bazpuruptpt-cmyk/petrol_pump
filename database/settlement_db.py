from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client
from database.profiles_db import get_user_by_id
from database.credit_db import get_credit_transactions_by_reference, approve_credit_transactions_by_reference


SETTLEMENT_STATUSES = ["pending", "approved", "hold", "reopened"]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _enrich_settlement(row: dict):
    if not row:
        return row

    salesman = get_user_by_id(row.get("salesman_id"))
    enriched = dict(row)
    enriched["salesman_name"] = salesman.get("name") if salesman else row.get("salesman_id")
    enriched["salesman_phone"] = salesman.get("phone") if salesman else None
    enriched["payment_total"] = round(
        _safe_float(row.get("cash_amount"))
        + _safe_float(row.get("paytm_amount"))
        + _safe_float(row.get("ccms_amount"))
        + _safe_float(row.get("credit_amount")),
        2,
    )
    enriched["total_sale"] = round(_safe_float(row.get("entries_total") or row.get("meter_total")), 2)
    enriched["match_difference"] = round(enriched["total_sale"] - enriched["payment_total"], 2)
    enriched["is_matched"] = abs(enriched["match_difference"]) < 0.01
    return enriched


def get_settlement_by_id(settlement_id: int):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .select("*")
            .eq("id", settlement_id)
            .limit(1)
            .execute()
        )

        return _enrich_settlement(result.data[0]) if result.data else None
    except Exception as exc:
        print(f"Error in get_settlement_by_id: {exc}")
        return None


def get_pending_settlements():
    return get_settlements_by_status("pending")


def get_settlements_by_status(status: str):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .select("*")
            .eq("status", status)
            .order("created_at", desc=True)
            .execute()
        )

        return [_enrich_settlement(row) for row in (result.data or [])]
    except Exception as exc:
        print(f"Error in get_settlements_by_status: {exc}")
        return []


def get_settlements_by_date(entry_date: str = None):
    supabase = get_supabase_client()

    try:
        query = supabase.table("settlements").select("*")

        if entry_date:
            query = query.eq("date", entry_date)

        result = (
            query
            .order("created_at", desc=True)
            .execute()
        )

        return [_enrich_settlement(row) for row in (result.data or [])]
    except Exception as exc:
        print(f"Error in get_settlements_by_date: {exc}")
        return []


def get_sale_entries_for_settlement(settlement: dict):
    if not settlement:
        return []

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("sale_entries")
            .select("*, nozzles:nozzle_id(nozzle_name)")
            .eq("shift_id", settlement.get("shift_id"))
            .eq("salesman_id", settlement.get("salesman_id"))
            .order("entry_time", desc=True)
            .execute()
        )

        return result.data or []
    except Exception as exc:
        print(f"Error in get_sale_entries_for_settlement: {exc}")
        return []


def get_credit_rows_for_settlement(settlement_id: int):
    return get_credit_transactions_by_reference(settlement_id)


def get_manager_payment_summary(entry_date: str = None):
    rows = get_settlements_by_date(entry_date or date.today().isoformat())

    summary = {
        "pending_count": 0,
        "approved_count": 0,
        "hold_count": 0,
        "reopened_count": 0,
        "total_sale": 0.0,
        "cash": 0.0,
        "paytm": 0.0,
        "ccms": 0.0,
        "credit": 0.0,
    }

    for row in rows:
        status = row.get("status") or "pending"
        if status == "pending":
            summary["pending_count"] += 1
        elif status == "approved":
            summary["approved_count"] += 1
        elif status == "hold":
            summary["hold_count"] += 1
        elif status == "reopened":
            summary["reopened_count"] += 1

        summary["total_sale"] += _safe_float(row.get("entries_total") or row.get("meter_total"))
        summary["cash"] += _safe_float(row.get("cash_amount"))
        summary["paytm"] += _safe_float(row.get("paytm_amount"))
        summary["ccms"] += _safe_float(row.get("ccms_amount"))
        summary["credit"] += _safe_float(row.get("credit_amount"))

    for key in ["total_sale", "cash", "paytm", "ccms", "credit"]:
        summary[key] = round(summary[key], 2)

    return summary


def approve_settlement(settlement_id: int, manager_id: str):
    """
    Settlement approve:
    - settlement status approved
    - related sale_entries status approved
    - related credit_transactions status approved
    - credit_party current_balance update
    """
    settlement = get_settlement_by_id(settlement_id)

    if not settlement:
        return None, "Settlement not found."

    if settlement.get("status") == "approved":
        return None, "Settlement already approved."

    if not settlement.get("is_matched"):
        return None, "Settlement difference is not zero. Hold/reopen instead of approve."

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .update({
                "status": "approved",
                "approved_by": manager_id,
                "approved_at": _now(),
            })
            .eq("id", settlement_id)
            .execute()
        )

        approved_settlement = result.data[0] if result.data else None

        # Lock sale entries
        try:
            supabase.table("sale_entries").update({
                "status": "approved",
                "approved_by": manager_id,
                "approved_at": _now(),
            }).eq("shift_id", settlement.get("shift_id")).eq(
                "salesman_id", settlement.get("salesman_id")
            ).execute()
        except Exception as sale_exc:
            print(f"Error approving sale entries: {sale_exc}")

        # Approve credit transactions and add party balance
        try:
            approve_credit_transactions_by_reference(settlement_id, manager_id)
        except Exception as credit_exc:
            print(f"Error approving credit transactions: {credit_exc}")

        return approved_settlement, None

    except Exception as exc:
        print(f"Error in approve_settlement: {exc}")
        return None, str(exc)


def hold_settlement(settlement_id: int, manager_id: str, note: str = ""):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .update({
                "status": "hold",
                "manager_note": note or "Held by manager",
                "approved_by": manager_id,
                "approved_at": _now(),
            })
            .eq("id", settlement_id)
            .execute()
        )

        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"Error in hold_settlement: {exc}")
        return None, str(exc)


def reopen_settlement(settlement_id: int, manager_id: str, note: str = ""):
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("settlements")
            .update({
                "status": "reopened",
                "manager_note": note or "Reopened by manager",
                "approved_by": manager_id,
                "approved_at": _now(),
            })
            .eq("id", settlement_id)
            .execute()
        )

        return result.data[0] if result.data else None, None
    except Exception as exc:
        print(f"Error in reopen_settlement: {exc}")
        return None, str(exc)
