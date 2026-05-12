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



def _cash_given_rows_for_settlement(settlement_id):
    supabase = get_supabase_client()
    select_cols = "*, credit_parties:party_id(name, phone, vehicles)"

    for ref in [settlement_id, str(settlement_id)]:
        try:
            rows = (
                supabase.table("credit_transactions")
                .select(select_cols)
                .eq("type", "cash_given")
                .eq("reference_id", ref)
                .order("created_at", desc=False)
                .execute()
                .data
                or []
            )
            if rows:
                return rows
        except Exception as exc:
            print("cash given rows reference lookup skipped:", exc)

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



def _has_valid_nozzle_rows(rows):
    """
    PDF/print me blank 0 row ko valid nahi manna.
    Valid row = nozzle name/fuel present and reading/liters/amount meaningful.
    """
    for r in rows or []:
        nozzle_name = str(r.get("nozzle_name") or "").strip()
        fuel_type = str(r.get("fuel_type") or "").strip()
        if (
            nozzle_name not in ["", "-"]
            and fuel_type not in ["", "-"]
            and (
                _safe_float(r.get("closing")) > _safe_float(r.get("opening"))
                or _safe_float(r.get("liters")) > 0
                or _safe_float(r.get("amount")) > 0
            )
        ):
            return True
    return False


def _rate_for_fuel(fuel_type, entry_date=None):
    if not fuel_type:
        return 0.0

    try:
        q = (
            get_supabase_client()
            .table("fuel_rates")
            .select("*")
            .eq("fuel_type", fuel_type)
        )

        if entry_date:
            q = q.lte("effective_from", entry_date)

        rows = (
            q.order("effective_from", desc=True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return _safe_float(rows[0].get("price_per_liter")) if rows else 0.0
    except Exception as exc:
        print("rate fallback skipped:", exc)
        return 0.0


def _nozzle_rows_from_assignments(settlement):
    """
    Primary fallback for PDF:
    settlement.nozzle_readings blank/0 ho to shift_assignments se opening/closing uthao.
    Manager closing save ke baad yahi table actual reading lock karta hai.
    """
    shift_id = settlement.get("shift_id")
    if not shift_id:
        return []

    try:
        rows = (
            get_supabase_client()
            .table("shift_assignments")
            .select("*, nozzles:nozzle_id(nozzle_name, fuel_type)")
            .eq("shift_id", shift_id)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print("assignment nozzle fallback failed:", exc)
        rows = []

    out = []
    entry_date = settlement.get("date")

    for a in rows:
        nozzle = a.get("nozzles") or {}
        fuel_type = nozzle.get("fuel_type") or a.get("fuel_type") or "-"

        opening = _safe_float(a.get("opening_reading"))
        closing = _safe_float(a.get("closing_reading"))

        # अगर closing_reading missing है तो current_reading fallback use मत करो;
        # current_reading next shift me बदल सकता है. Report me locked closing ही चाहिए.
        liters = round(closing - opening, 2) if closing >= opening and closing > 0 else 0.0
        rate = _rate_for_fuel(fuel_type, entry_date)
        amount = round(liters * rate, 2)

        out.append({
            "nozzle_name": nozzle.get("nozzle_name") or a.get("nozzle_id") or "-",
            "fuel_type": fuel_type,
            "opening": round(opening, 2),
            "closing": round(closing, 2),
            "liters": round(liters, 2),
            "rate": round(rate, 2),
            "amount": round(amount, 2),
        })

    return out


def _nozzle_rows_from_sale_entries(settlement):
    """
    Last fallback:
    Agar assignment reading rows bhi missing hon, sale_entries se nozzle-wise liters/amount show karo.
    Opening/closing unknown honge, par PDF me sale 0 nahi दिखेगी.
    """
    shift_id = settlement.get("shift_id")
    if not shift_id:
        return []

    try:
        rows = (
            get_supabase_client()
            .table("sale_entries")
            .select("*, nozzles:nozzle_id(nozzle_name, fuel_type)")
            .eq("shift_id", shift_id)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print("sale entry nozzle fallback failed:", exc)
        rows = []

    grouped = {}

    for e in rows:
        status = (e.get("status") or "pending").lower()
        if status in ["rejected", "cancelled"]:
            continue

        nozzle = e.get("nozzles") or {}
        nozzle_id = e.get("nozzle_id")
        key = nozzle_id or nozzle.get("nozzle_name") or "unknown"
        fuel_type = e.get("fuel_type") or nozzle.get("fuel_type") or "-"

        if key not in grouped:
            grouped[key] = {
                "nozzle_name": nozzle.get("nozzle_name") or nozzle_id or "-",
                "fuel_type": fuel_type,
                "opening": 0.0,
                "closing": 0.0,
                "liters": 0.0,
                "rate": _safe_float(e.get("rate")),
                "amount": 0.0,
            }

        grouped[key]["liters"] += _safe_float(e.get("liters"))
        grouped[key]["amount"] += _safe_float(e.get("amount"))

        if not grouped[key]["rate"] and _safe_float(e.get("rate")):
            grouped[key]["rate"] = _safe_float(e.get("rate"))

    out = []
    for r in grouped.values():
        out.append({
            "nozzle_name": r.get("nozzle_name"),
            "fuel_type": r.get("fuel_type"),
            "opening": round(_safe_float(r.get("opening")), 2),
            "closing": round(_safe_float(r.get("closing")), 2),
            "liters": round(_safe_float(r.get("liters")), 2),
            "rate": round(_safe_float(r.get("rate")), 2),
            "amount": round(_safe_float(r.get("amount")), 2),
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
    cash_given_rows_raw = _cash_given_rows_for_settlement(settlement_id)

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

    cash_given_rows = []
    for c in cash_given_rows_raw:
        party = c.get("credit_parties") or {}
        cash_given_rows.append({
            "creditor": party.get("name") or c.get("party_id") or "-",
            "amount": _money(c.get("amount")),
            "vehicle": c.get("vehicle_number") or c.get("vehicle") or "",
            "comment": c.get("note") or c.get("approval_note") or c.get("comment") or "",
            "status": c.get("status") or "",
        })

    nozzle_rows = _normalise_nozzle_rows(settlement)

    # PDF/print report must not show blank 0 nozzle row while payment sale exists.
    # Priority:
    # 1. settlements.nozzle_readings
    # 2. shift_assignments opening/closing
    # 3. sale_entries nozzle-wise totals
    if not _has_valid_nozzle_rows(nozzle_rows):
        nozzle_rows = _nozzle_rows_from_assignments(settlement)

    if not _has_valid_nozzle_rows(nozzle_rows):
        nozzle_rows = _nozzle_rows_from_sale_entries(settlement)

    total_liters = round(sum(_safe_float(r.get("liters")) for r in nozzle_rows), 2)
    total_nozzle_sale = round(sum(_safe_float(r.get("amount")) for r in nozzle_rows), 2)

    cash = _money(settlement.get("cash_amount"))
    paytm = _money(settlement.get("paytm_amount"))
    ccms = _money(settlement.get("ccms_amount"))
    credit = _money(settlement.get("credit_amount"))
    cash_given = _money(settlement.get("cash_given_to_creditor_amount"))

    if cash_given <= 0 and cash_given_rows:
        cash_given = round(sum(_safe_float(r.get("amount")) for r in cash_given_rows), 2)

    cash_to_manager = settlement.get("cash_transfer_expected")
    if cash_to_manager is None:
        cash_to_manager = round(cash - cash_given, 2)
    cash_to_manager = _money(cash_to_manager)

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
        "cash_given_rows": cash_given_rows,
        "totals": {
            "total_liters": total_liters,
            "total_nozzle_sale": total_nozzle_sale,
            "total_sale": total_sale,
            "cash": cash,
            "paytm": paytm,
            "ccms": ccms,
            "credit": credit,
            "cash_given": cash_given,
            "cash_to_manager": cash_to_manager,
            "payment_total": payment_total,
            "difference": _money(settlement.get("difference")),
        },
    }
