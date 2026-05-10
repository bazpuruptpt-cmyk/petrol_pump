from datetime import date, timedelta
from config.supabase_client import get_supabase_client


def _f(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _today():
    return date.today().isoformat()


def _date_range(days=30):
    end = date.today()
    start = end - timedelta(days=int(days or 30) - 1)
    return start.isoformat(), end.isoformat()


def _get_sale_entries(salesman_id, entry_date=None, start_date=None, end_date=None):
    try:
        query = (
            get_supabase_client()
            .table("sale_entries")
            .select("*, nozzles:nozzle_id(nozzle_name, fuel_type)")
            .eq("salesman_id", salesman_id)
        )

        if entry_date:
            query = query.eq("date", entry_date)

        if start_date:
            query = query.gte("date", start_date)

        if end_date:
            query = query.lte("date", end_date)

        result = query.order("date", desc=True).execute()
        return result.data or []
    except Exception as exc:
        print(f"_get_sale_entries error: {exc}")
        return []


def _get_settlements(salesman_id, entry_date=None, start_date=None, end_date=None):
    try:
        query = (
            get_supabase_client()
            .table("settlements")
            .select("*")
            .eq("salesman_id", salesman_id)
        )

        if entry_date:
            query = query.eq("date", entry_date)

        if start_date:
            query = query.gte("date", start_date)

        if end_date:
            query = query.lte("date", end_date)

        result = query.order("created_at", desc=True).execute()
        return result.data or []
    except Exception as exc:
        print(f"_get_settlements error: {exc}")
        return []


def _latest_settlements_by_shift(rows):
    """
    Same shift ki repeated/reopened rows me latest row use karo.
    """
    latest = {}

    for row in rows or []:
        shift_id = row.get("shift_id")
        if shift_id not in latest:
            latest[shift_id] = row

    return list(latest.values())


def _settlement_totals(rows):
    rows = _latest_settlements_by_shift(rows)

    total = {
        "cash": 0.0,
        "paytm": 0.0,
        "ccms": 0.0,
        "credit": 0.0,
        "payment_total": 0.0,
        "statuses": [],
        "settlement_count": len(rows),
    }

    for row in rows:
        cash = _f(row.get("cash_amount"))
        paytm = _f(row.get("paytm_amount"))
        ccms = _f(row.get("ccms_amount"))
        credit = _f(row.get("credit_amount"))

        total["cash"] += cash
        total["paytm"] += paytm
        total["ccms"] += ccms
        total["credit"] += credit
        total["payment_total"] += cash + paytm + ccms + credit

        status = row.get("status")
        if status:
            total["statuses"].append(status)

    for key in ["cash", "paytm", "ccms", "credit", "payment_total"]:
        total[key] = round(total[key], 2)

    total["status"] = ", ".join(sorted(set(total["statuses"]))) if total["statuses"] else "not submitted"
    return total


def get_salesman_daily_summary(salesman_id, entry_date=None):
    """
    One selected date ka exact daily summary.
    """
    entry_date = entry_date or _today()

    entries = _get_sale_entries(salesman_id, entry_date=entry_date)
    settlements = _get_settlements(salesman_id, entry_date=entry_date)
    payment = _settlement_totals(settlements)

    total_sale = round(sum(_f(r.get("amount")) for r in entries), 2)
    total_liters = round(sum(_f(r.get("liters")) for r in entries), 2)
    payment_total = payment["payment_total"]
    difference = round(total_sale - payment_total, 2)

    return {
        "date": entry_date,
        "total_sale": total_sale,
        "total_liters": total_liters,
        "entry_count": len(entries),
        "cash": payment["cash"],
        "paytm": payment["paytm"],
        "ccms": payment["ccms"],
        "credit": payment["credit"],
        "payment_total": payment_total,
        "difference": difference,
        "is_matched": abs(difference) < 0.01,
        "status": payment["status"],
        "settlement_count": payment["settlement_count"],
    }


def get_salesman_daily_nozzle_summary(salesman_id, entry_date=None):
    entry_date = entry_date or _today()
    entries = _get_sale_entries(salesman_id, entry_date=entry_date)

    grouped = {}

    for row in entries:
        nozzle = row.get("nozzles") or {}
        nozzle_id = row.get("nozzle_id")
        nozzle_name = nozzle.get("nozzle_name") or f"Nozzle {nozzle_id}"
        fuel_type = nozzle.get("fuel_type") or row.get("fuel_type")

        if nozzle_id not in grouped:
            grouped[nozzle_id] = {
                "Nozzle": nozzle_name,
                "Fuel": fuel_type,
                "Liters": 0.0,
                "Amount": 0.0,
                "Entries": 0,
            }

        grouped[nozzle_id]["Liters"] += _f(row.get("liters"))
        grouped[nozzle_id]["Amount"] += _f(row.get("amount"))
        grouped[nozzle_id]["Entries"] += 1

    output = []
    for row in grouped.values():
        row["Liters"] = round(row["Liters"], 2)
        row["Amount"] = round(row["Amount"], 2)
        output.append(row)

    return output


def get_salesman_day_wise_summary(salesman_id, days=30, start_date=None, end_date=None):
    """
    Date-wise summary. Total all-time summary nahi.
    """
    if not start_date or not end_date:
        start_date, end_date = _date_range(days)

    entries = _get_sale_entries(salesman_id, start_date=start_date, end_date=end_date)
    settlements = _get_settlements(salesman_id, start_date=start_date, end_date=end_date)

    by_date = {}

    for row in entries:
        d = row.get("date")
        if not d:
            continue

        if d not in by_date:
            by_date[d] = {
                "Date": d,
                "Sale": 0.0,
                "Liters": 0.0,
                "Entries": 0,
                "Cash": 0.0,
                "Paytm": 0.0,
                "CCMS": 0.0,
                "Credit": 0.0,
                "Payment Total": 0.0,
                "Difference": 0.0,
                "Status": "not submitted",
            }

        by_date[d]["Sale"] += _f(row.get("amount"))
        by_date[d]["Liters"] += _f(row.get("liters"))
        by_date[d]["Entries"] += 1

    settlements_by_date = {}
    for row in _latest_settlements_by_shift(settlements):
        d = row.get("date")
        if not d:
            continue
        settlements_by_date.setdefault(d, []).append(row)

    for d, rows in settlements_by_date.items():
        if d not in by_date:
            by_date[d] = {
                "Date": d,
                "Sale": 0.0,
                "Liters": 0.0,
                "Entries": 0,
                "Cash": 0.0,
                "Paytm": 0.0,
                "CCMS": 0.0,
                "Credit": 0.0,
                "Payment Total": 0.0,
                "Difference": 0.0,
                "Status": "not submitted",
            }

        p = _settlement_totals(rows)
        by_date[d]["Cash"] = p["cash"]
        by_date[d]["Paytm"] = p["paytm"]
        by_date[d]["CCMS"] = p["ccms"]
        by_date[d]["Credit"] = p["credit"]
        by_date[d]["Payment Total"] = p["payment_total"]
        by_date[d]["Status"] = p["status"]

    output = []

    for d in sorted(by_date.keys(), reverse=True):
        row = by_date[d]
        row["Sale"] = round(row["Sale"], 2)
        row["Liters"] = round(row["Liters"], 2)
        row["Difference"] = round(row["Sale"] - row["Payment Total"], 2)

        for key in ["Cash", "Paytm", "CCMS", "Credit", "Payment Total"]:
            row[key] = round(_f(row.get(key)), 2)

        output.append(row)

    return output
