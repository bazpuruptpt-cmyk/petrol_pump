from datetime import date, datetime
from config.supabase_client import get_supabase_client


def _safe_float(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _money(value):
    return round(_safe_float(value), 2)


def _profiles_map():
    try:
        rows = (
            get_supabase_client()
            .table("profiles")
            .select("id, name, role, phone")
            .execute()
            .data
            or []
        )
        return {r.get("id"): r for r in rows}
    except Exception as exc:
        print("profile map skipped:", exc)
        return {}


def _name_for(user_id, profiles=None):
    profiles = profiles or _profiles_map()
    return (profiles.get(user_id) or {}).get("name") or str(user_id or "-")


def _credit_rows_for_settlement(settlement_id):
    supabase = get_supabase_client()
    select_cols = "*, credit_parties:party_id(name, phone, vehicles)"

    try:
        return (
            supabase.table("credit_transactions")
            .select(select_cols)
            .eq("type", "sale")
            .eq("reference_id", settlement_id)
            .order("created_at", desc=False)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print("credit rows by int reference skipped:", exc)

    try:
        return (
            supabase.table("credit_transactions")
            .select(select_cols)
            .eq("type", "sale")
            .eq("reference_id", str(settlement_id))
            .order("created_at", desc=False)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print("credit rows by text reference skipped:", exc)
        return []


def _normalise_nozzle_rows(settlement):
    rows = settlement.get("nozzle_readings") or []

    if not isinstance(rows, list):
        rows = []

    out = []
    for r in rows:
        opening = _safe_float(r.get("opening"))
        closing = _safe_float(r.get("closing"))
        liters = _safe_float(r.get("actual_liters"))
        rate = _safe_float(r.get("rate"))
        amount = _safe_float(r.get("sale_amount"))

        if not liters and closing >= opening:
            liters = closing - opening

        if not amount:
            amount = liters * rate

        out.append({
            "nozzle_name": r.get("nozzle_name") or r.get("nozzle") or r.get("nozzle_id") or "-",
            "fuel_type": r.get("fuel_type") or "-",
            "opening": round(opening, 2),
            "closing": round(closing, 2),
            "liters": round(liters, 2),
            "rate": round(rate, 2),
            "amount": round(amount, 2),
        })

    return out


def get_salesman_settlement_detail(settlement_id):
    """
    Single salesman settlement report data for A4 PDF.

    Required report:
    - date
    - salesman name
    - assigned nozzle names
    - opening/closing reading
    - nozzle-wise liters
    - petrol/diesel rate
    - nozzle-wise rupee sale
    - credit party list, amount, comments
    - total cash/paytm/ccms/credit
    - manager/salesman signature space
    """
    try:
        rows = (
            get_supabase_client()
            .table("settlements")
            .select("*")
            .eq("id", settlement_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        settlement = rows[0] if rows else None
    except Exception as exc:
        print("settlement detail load failed:", exc)
        settlement = None

    if not settlement:
        return {
            "error": f"Settlement {settlement_id} not found.",
            "settlement_id": settlement_id,
        }

    profiles = _profiles_map()
    credit_rows_raw = _credit_rows_for_settlement(settlement_id)

    credit_rows = []
    for c in credit_rows_raw:
        party = c.get("credit_parties") or {}
        credit_rows.append({
            "creditor": party.get("name") or c.get("party_id") or "-",
            "amount": _money(c.get("amount")),
            "vehicle": c.get("vehicle_number") or c.get("vehicle") or "",
            "comment": c.get("note") or c.get("approval_note") or c.get("comment") or "",
            "status": c.get("status") or "",
        })

    nozzle_rows = _normalise_nozzle_rows(settlement)

    total_liters = round(sum(_safe_float(r.get("liters")) for r in nozzle_rows), 2)
    total_nozzle_sale = round(sum(_safe_float(r.get("amount")) for r in nozzle_rows), 2)

    cash = _money(settlement.get("cash_amount"))
    paytm = _money(settlement.get("paytm_amount"))
    ccms = _money(settlement.get("ccms_amount"))
    credit = _money(settlement.get("credit_amount"))
    total_sale = _money(settlement.get("meter_total") or settlement.get("meter_total_calc") or total_nozzle_sale)
    payment_total = round(cash + paytm + ccms + credit, 2)

    return {
        "error": None,
        "settlement_id": settlement.get("id"),
        "date": settlement.get("date"),
        "shift_id": settlement.get("shift_id"),
        "salesman_id": settlement.get("salesman_id"),
        "salesman_name": settlement.get("salesman_name") or _name_for(settlement.get("salesman_id"), profiles),
        "status": settlement.get("status") or "pending",
        "manager_note": settlement.get("manager_note") or "",
        "approved_at": settlement.get("approved_at"),
        "created_at": settlement.get("created_at"),
        "nozzle_rows": nozzle_rows,
        "credit_rows": credit_rows,
        "totals": {
            "total_liters": total_liters,
            "total_nozzle_sale": total_nozzle_sale,
            "total_sale": total_sale,
            "cash": cash,
            "paytm": paytm,
            "ccms": ccms,
            "credit": credit,
            "payment_total": payment_total,
            "difference": _money(settlement.get("difference")),
        },
    }
