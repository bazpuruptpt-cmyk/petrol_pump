from datetime import date
from config.supabase_client import get_supabase_client


def _today():
    return date.today().isoformat()


def _f(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _money(value):
    return round(_f(value), 2)


def _rows(table, entry_date=None, status=None, payment_mode=None):
    try:
        q = get_supabase_client().table(table).select("*")

        if entry_date:
            q = q.eq("date", entry_date)

        if status:
            q = q.eq("status", status)

        if payment_mode:
            q = q.eq("payment_mode", payment_mode)

        return q.order("created_at", desc=True).execute().data or []

    except Exception as exc:
        print(f"{table} rows skipped:", exc)
        return []


def _profiles_map():
    try:
        rows = get_supabase_client().table("profiles").select("id, name, role").execute().data or []
        return {r.get("id"): r for r in rows}
    except Exception:
        return {}


def _name_for(user_id, profiles=None):
    profiles = profiles or _profiles_map()
    return (profiles.get(user_id) or {}).get("name") or str(user_id or "-")


def _credit_party_map():
    try:
        rows = get_supabase_client().table("credit_parties").select("*").execute().data or []
        return {r.get("id"): r for r in rows}
    except Exception:
        return {}


def get_pump_daily_settlements(entry_date=None):
    entry_date = entry_date or _today()

    try:
        rows = (
            get_supabase_client()
            .table("settlements")
            .select("*")
            .eq("date", entry_date)
            .eq("status", "approved")
            .order("created_at", desc=False)
            .execute()
            .data
            or []
        )
        return rows
    except Exception as exc:
        print("get_pump_daily_settlements error:", exc)
        return []


def get_nozzle_wise_pump_summary(entry_date=None):
    entry_date = entry_date or _today()
    settlements = get_pump_daily_settlements(entry_date)
    profiles = _profiles_map()

    output = []

    for s in settlements:
        salesman_name = s.get("salesman_name") or _name_for(s.get("salesman_id"), profiles)
        nozzle_rows = s.get("nozzle_readings") or []

        if not isinstance(nozzle_rows, list):
            nozzle_rows = []

        for n in nozzle_rows:
            opening = _f(n.get("opening"))
            closing = _f(n.get("closing"))
            liters = _f(n.get("actual_liters"))

            if liters == 0 and closing >= opening:
                liters = closing - opening

            rate = _f(n.get("rate"))
            amount = _f(n.get("sale_amount"))

            if amount == 0:
                amount = liters * rate

            output.append({
                "Date": s.get("date"),
                "Settlement ID": s.get("id"),
                "Shift ID": s.get("shift_id"),
                "Salesman": salesman_name,
                "Nozzle": n.get("nozzle_name") or n.get("nozzle") or n.get("nozzle_id"),
                "Fuel": n.get("fuel_type"),
                "Opening": round(opening, 2),
                "Closing": round(closing, 2),
                "Sale Liters": round(liters, 2),
                "Rate": round(rate, 2),
                "Sale Amount": round(amount, 2),
            })

    return output


def get_salesman_wise_pump_summary(entry_date=None):
    entry_date = entry_date or _today()
    settlements = get_pump_daily_settlements(entry_date)
    profiles = _profiles_map()

    rows = []

    for s in settlements:
        nozzle_rows = s.get("nozzle_readings") or []
        total_liters = 0.0

        if isinstance(nozzle_rows, list):
            for n in nozzle_rows:
                opening = _f(n.get("opening"))
                closing = _f(n.get("closing"))
                liters = _f(n.get("actual_liters"))
                if liters == 0 and closing >= opening:
                    liters = closing - opening
                total_liters += liters

        rows.append({
            "Date": s.get("date"),
            "Settlement ID": s.get("id"),
            "Shift ID": s.get("shift_id"),
            "Salesman": s.get("salesman_name") or _name_for(s.get("salesman_id"), profiles),
            "Total Liters": round(total_liters, 2),
            "Total Sale": _money(s.get("meter_total")),
            "Cash": _money(s.get("cash_amount")),
            "Paytm": _money(s.get("paytm_amount")),
            "CCMS": _money(s.get("ccms_amount")),
            "Credit": _money(s.get("credit_amount")),
            "Difference": _money(s.get("difference")),
            "Status": s.get("status"),
        })

    return rows


def get_credit_sale_details(entry_date=None):
    entry_date = entry_date or _today()
    party_map = _credit_party_map()
    settlements = {s.get("id"): s for s in get_pump_daily_settlements(entry_date)}
    profiles = _profiles_map()

    try:
        rows = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*")
            .eq("date", entry_date)
            .eq("type", "sale")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print("credit sale detail skipped:", exc)
        rows = []

    output = []

    for r in rows:
        ref = r.get("reference_id")
        settlement = None
        try:
            settlement = settlements.get(int(ref))
        except Exception:
            settlement = settlements.get(ref)

        party = party_map.get(r.get("party_id")) or {}
        output.append({
            "Date": r.get("date"),
            "Creditor": party.get("name") or r.get("party_id"),
            "Amount": _money(r.get("amount")),
            "Vehicle": r.get("vehicle_number") or r.get("vehicle") or "",
            "Comment": r.get("note") or r.get("comment") or "",
            "Settlement ID": r.get("reference_id"),
            "Salesman": (settlement or {}).get("salesman_name") or _name_for((settlement or {}).get("salesman_id"), profiles),
            "Status": r.get("status"),
        })

    if not output:
        for s in settlements.values():
            if _f(s.get("credit_amount")) > 0:
                output.append({
                    "Date": s.get("date"),
                    "Creditor": "Credit sale total",
                    "Amount": _money(s.get("credit_amount")),
                    "Vehicle": "",
                    "Comment": "Party-wise credit rows not found",
                    "Settlement ID": s.get("id"),
                    "Salesman": s.get("salesman_name") or _name_for(s.get("salesman_id"), profiles),
                    "Status": s.get("status"),
                })

    return output


def get_daily_expense_details(entry_date=None):
    entry_date = entry_date or _today()

    rows = _rows("expenses", entry_date=entry_date)
    output = []

    for e in rows:
        output.append({
            "Date": e.get("date"),
            "Category": e.get("category"),
            "Payment Mode": e.get("payment_mode"),
            "Amount": _money(e.get("amount")),
            "Description": e.get("description") or e.get("note"),
            "Status": e.get("status"),
            "Reference": e.get("reference_no") or e.get("id"),
            "Created At": e.get("created_at"),
        })

    return output


def get_pump_daily_totals(entry_date=None):
    entry_date = entry_date or _today()

    settlements = get_pump_daily_settlements(entry_date)
    nozzle_rows = get_nozzle_wise_pump_summary(entry_date)
    expenses = get_daily_expense_details(entry_date)

    total_liters = round(sum(_f(r.get("Sale Liters")) for r in nozzle_rows), 2)
    total_sale = round(sum(_f(s.get("meter_total")) for s in settlements), 2)

    cash_total = round(sum(_f(s.get("cash_amount")) for s in settlements), 2)
    paytm_total = round(sum(_f(s.get("paytm_amount")) for s in settlements), 2)
    ccms_total = round(sum(_f(s.get("ccms_amount")) for s in settlements), 2)
    credit_total = round(sum(_f(s.get("credit_amount")) for s in settlements), 2)

    expense_total = round(sum(_f(e.get("Amount")) for e in expenses if (e.get("Status") or "approved") == "approved"), 2)
    cash_expense = round(sum(_f(e.get("Amount")) for e in expenses if e.get("Payment Mode") == "cash" and (e.get("Status") or "approved") == "approved"), 2)
    bank_expense = round(sum(_f(e.get("Amount")) for e in expenses if e.get("Payment Mode") == "bank" and (e.get("Status") or "approved") == "approved"), 2)

    fuel_summary = {}
    for r in nozzle_rows:
        fuel = r.get("Fuel") or "-"
        fuel_summary.setdefault(fuel, {"Fuel": fuel, "Liters": 0.0, "Amount": 0.0})
        fuel_summary[fuel]["Liters"] += _f(r.get("Sale Liters"))
        fuel_summary[fuel]["Amount"] += _f(r.get("Sale Amount"))

    fuel_rows = []
    for fuel, data in fuel_summary.items():
        fuel_rows.append({
            "Fuel": fuel,
            "Liters": round(data["Liters"], 2),
            "Amount": round(data["Amount"], 2),
        })

    return {
        "date": entry_date,
        "settlement_count": len(settlements),
        "total_liters": total_liters,
        "total_sale": total_sale,
        "cash_total": cash_total,
        "paytm_total": paytm_total,
        "ccms_total": ccms_total,
        "credit_total": credit_total,
        "expense_total": expense_total,
        "cash_expense": cash_expense,
        "bank_expense": bank_expense,
        "fuel_rows": fuel_rows,
    }


def get_pump_daily_summary(entry_date=None):
    entry_date = entry_date or _today()

    return {
        "totals": get_pump_daily_totals(entry_date),
        "nozzle_wise": get_nozzle_wise_pump_summary(entry_date),
        "salesman_wise": get_salesman_wise_pump_summary(entry_date),
        "credit_details": get_credit_sale_details(entry_date),
        "expense_details": get_daily_expense_details(entry_date),
    }
