from datetime import date, datetime
from config.supabase_client import get_supabase_client


# Phase 3C Complete Reports Fix
# Safe report layer: if any optional table/column is missing, report returns [] instead of crashing Streamlit.


def _today():
    return date.today().isoformat()


def _iso(value):
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return str(value)


def _date_range(from_date=None, to_date=None):
    f = _iso(from_date) or _today()
    t = _iso(to_date) or f
    if t < f:
        f, t = t, f
    return f, t


def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_num(value):
    return round(_safe_float(value), 2)


def _sum(rows, key):
    return round(sum(_safe_float(r.get(key)) for r in rows or []), 2)


def _select(table_name, order_by="created_at", desc=True):
    return get_supabase_client().table(table_name).select("*")


def _rows(table_name, from_date=None, to_date=None, status=None, payment_mode=None, order_by="created_at"):
    """Generic safe date-range loader for report tables."""
    try:
        query = _select(table_name)
        if from_date or to_date:
            f, t = _date_range(from_date, to_date)
            query = query.gte("date", f).lte("date", t)
        if status is not None:
            query = query.eq("status", status)
        if payment_mode is not None:
            query = query.eq("payment_mode", payment_mode)
        try:
            query = query.order(order_by, desc=True)
        except Exception:
            pass
        return query.execute().data or []
    except Exception as exc:
        print(f"Report table load skipped: {table_name}: {exc}")
        return []


def _profiles_map():
    try:
        rows = get_supabase_client().table("profiles").select("id, name, role, phone").execute().data or []
        return {r.get("id"): r for r in rows}
    except Exception as exc:
        print(f"profiles map skipped: {exc}")
        return {}


def _name_for(user_id, profiles=None):
    profiles = profiles or _profiles_map()
    return (profiles.get(user_id) or {}).get("name") or user_id or "-"


def _payment_total(row):
    return round(
        _safe_float(row.get("cash_amount"))
        + _safe_float(row.get("paytm_amount"))
        + _safe_float(row.get("ccms_amount"))
        + _safe_float(row.get("credit_amount")),
        2,
    )


# ---------------- Existing-compatible daily report functions ----------------


def get_settlements_for_date(entry_date=None):
    return _rows("settlements", entry_date or _today(), entry_date or _today())


def get_profiles_map():
    return _profiles_map()



def _credit_payment_rows(from_date=None, to_date=None, status="approved", payment_mode=None):
    try:
        f, t = _date_range(from_date, to_date)
        q = (
            get_supabase_client()
            .table("credit_transactions")
            .select("*, credit_parties:party_id(name)")
            .eq("type", "payment_received")
        )
        if f:
            q = q.gte("date", f)
        if t:
            q = q.lte("date", t)
        if status:
            q = q.eq("status", status)
        if payment_mode:
            q = q.eq("payment_mode", payment_mode)

        return q.order("created_at", desc=True).execute().data or []
    except Exception as exc:
        print(f"credit payment rows skipped: {exc}")
        return []


def _credit_payment_sum(entry_date=None, payment_mode=None):
    rows = _credit_payment_rows(entry_date, entry_date, status="approved", payment_mode=payment_mode)
    return round(sum(_safe_float(r.get("amount")) for r in rows), 2)


def get_daily_closing_report(entry_date=None):
    entry_date = _iso(entry_date) or _today()
    settlements = get_settlements_for_date(entry_date)
    approved = [s for s in settlements if (s.get("status") or "pending") == "approved"]

    cash_sale = _sum(approved, "cash_amount")
    paytm_sale = _sum(approved, "paytm_amount")
    ccms_sale = _sum(approved, "ccms_amount")
    credit_sale = _sum(approved, "credit_amount")
    total_sale = _sum(approved, "meter_total")

    cash_deposits = _rows("cash_deposits", entry_date, entry_date)
    paytm_settlements = _rows("paytm_settlements", entry_date, entry_date)
    ccms_settlements = _rows("ccms_settlements", entry_date, entry_date)
    cash_expenses = _rows("expenses", entry_date, entry_date, status="approved", payment_mode="cash")
    bank_expenses = _rows("expenses", entry_date, entry_date, status="approved", payment_mode="bank")

    status_count = {"pending": 0, "approved": 0, "hold": 0, "reopened": 0, "rejected": 0}
    total_difference = 0.0
    for s in settlements:
        status = s.get("status") or "pending"
        if status in status_count:
            status_count[status] += 1
        total_difference += _safe_float(s.get("difference"))

    cash_deposited = _sum(cash_deposits, "amount")
    paytm_settled = _sum(paytm_settlements, "amount")
    ccms_received = _sum(ccms_settlements, "amount")
    cash_expense = _sum(cash_expenses, "amount")
    bank_expense = _sum(bank_expenses, "amount")

    credit_cash_received = _credit_payment_sum(entry_date, "cash")
    credit_bank_received = _credit_payment_sum(entry_date, "bank")
    credit_paytm_received = _credit_payment_sum(entry_date, "paytm")
    credit_ccms_received = _credit_payment_sum(entry_date, "ccms")
    credit_received_total = round(
        credit_cash_received + credit_bank_received + credit_paytm_received + credit_ccms_received,
        2,
    )

    return {
        "date": entry_date,
        "total_sale": total_sale,
        "cash_sale": cash_sale,
        "paytm_sale": paytm_sale,
        "ccms_sale": ccms_sale,
        "credit_sale": credit_sale,
        "cash_deposited": cash_deposited,
        "cash_expense": cash_expense,
        "bank_expense": bank_expense,
        "credit_cash_received": credit_cash_received,
        "credit_bank_received": credit_bank_received,
        "credit_paytm_received": credit_paytm_received,
        "credit_ccms_received": credit_ccms_received,
        "credit_received_total": credit_received_total,
        "cash_in_hand": round(cash_sale + credit_cash_received - cash_deposited - cash_expense, 2),
        "bank_inflow_total": round(cash_deposited + paytm_settled + ccms_received + credit_bank_received, 2),
        "paytm_settled": paytm_settled,
        "paytm_pending": round(paytm_sale + credit_paytm_received - paytm_settled, 2),
        "ccms_received": ccms_received,
        "ccms_pending": round(ccms_sale + credit_ccms_received - ccms_received, 2),
        "approved_settlements": status_count["approved"],
        "pending_settlements": status_count["pending"],
        "hold_settlements": status_count["hold"],
        "reopened_settlements": status_count["reopened"],
        "rejected_settlements": status_count["rejected"],
        "total_difference": round(total_difference, 2),
    }


def get_daily_closing_rows(entry_date=None):
    r = get_daily_closing_report(entry_date)
    return [
        {"Particular": "Total Sale", "Amount": r["total_sale"]},
        {"Particular": "Cash Sale", "Amount": r["cash_sale"]},
        {"Particular": "Credit Payment Received - Cash", "Amount": r.get("credit_cash_received", 0)},
        {"Particular": "Cash Deposited to Bank", "Amount": r["cash_deposited"]},
        {"Particular": "Cash Expense", "Amount": r["cash_expense"]},
        {"Particular": "Cash In Hand", "Amount": r["cash_in_hand"]},
        {"Particular": "Paytm Sale", "Amount": r["paytm_sale"]},
        {"Particular": "Credit Payment Received - Paytm", "Amount": r.get("credit_paytm_received", 0)},
        {"Particular": "Paytm Settled to Bank", "Amount": r["paytm_settled"]},
        {"Particular": "Paytm Pending", "Amount": r["paytm_pending"]},
        {"Particular": "CCMS Sale", "Amount": r["ccms_sale"]},
        {"Particular": "Credit Payment Received - CCMS", "Amount": r.get("credit_ccms_received", 0)},
        {"Particular": "CCMS Received", "Amount": r["ccms_received"]},
        {"Particular": "CCMS Pending", "Amount": r["ccms_pending"]},
        {"Particular": "Credit Sale", "Amount": r["credit_sale"]},
        {"Particular": "Credit Payment Received - Bank", "Amount": r.get("credit_bank_received", 0)},
        {"Particular": "Credit Received Total", "Amount": r.get("credit_received_total", 0)},
        {"Particular": "Bank Inflow Total", "Amount": r.get("bank_inflow_total", 0)},
        {"Particular": "Bank Expense", "Amount": r["bank_expense"]},
        {"Particular": "Approved Settlements", "Amount": r["approved_settlements"]},
        {"Particular": "Pending Settlements", "Amount": r["pending_settlements"]},
        {"Particular": "Hold Settlements", "Amount": r["hold_settlements"]},
        {"Particular": "Reopened Settlements", "Amount": r["reopened_settlements"]},
        {"Particular": "Total Difference", "Amount": r["total_difference"]},
    ]


# ---------------- Sale / settlement reports ----------------


def get_sale_report_by_range(from_date=None, to_date=None, status=None):
    f, t = _date_range(from_date, to_date)
    rows = _rows("settlements", f, t)
    profiles = _profiles_map()
    out = []

    for s in rows:
        if status and status != "all" and (s.get("status") or "pending") != status:
            continue
        payment_total = _payment_total(s)
        out.append({
            "Date": s.get("date"),
            "Settlement ID": s.get("id"),
            "Shift ID": s.get("shift_id"),
            "Salesman": _name_for(s.get("salesman_id"), profiles),
            "Status": s.get("status") or "pending",
            "Meter Sale": _fmt_num(s.get("meter_total")),
            "Entries Total": _fmt_num(s.get("entries_total")),
            "Cash": _fmt_num(s.get("cash_amount")),
            "Paytm": _fmt_num(s.get("paytm_amount")),
            "CCMS": _fmt_num(s.get("ccms_amount")),
            "Credit": _fmt_num(s.get("credit_amount")),
            "Payment Total": payment_total,
            "Difference": _fmt_num(s.get("difference")),
            "Manager Note": s.get("manager_note"),
            "Created At": s.get("created_at"),
            "Approved At": s.get("approved_at"),
        })
    return out


def get_salesman_wise_report(entry_date=None):
    entry_date = _iso(entry_date) or _today()
    return get_salesman_wise_report_by_range(entry_date, entry_date)


def get_salesman_wise_report_by_range(from_date=None, to_date=None):
    rows = get_sale_report_by_range(from_date, to_date)
    summary = {}
    for r in rows:
        sm = r.get("Salesman") or "-"
        summary.setdefault(sm, {
            "Salesman": sm,
            "Settlements": 0,
            "Approved Settlements": 0,
            "Meter Sale": 0.0,
            "Cash": 0.0,
            "Paytm": 0.0,
            "CCMS": 0.0,
            "Credit": 0.0,
            "Difference": 0.0,
        })
        s = summary[sm]
        s["Settlements"] += 1
        if r.get("Status") == "approved":
            s["Approved Settlements"] += 1
        for key in ["Meter Sale", "Cash", "Paytm", "CCMS", "Credit", "Difference"]:
            s[key] += _safe_float(r.get(key))

    for s in summary.values():
        for key in ["Meter Sale", "Cash", "Paytm", "CCMS", "Credit", "Difference"]:
            s[key] = round(s[key], 2)
    return list(summary.values())


def get_nozzle_wise_report(entry_date=None):
    entry_date = _iso(entry_date) or _today()
    return get_nozzle_wise_report_by_range(entry_date, entry_date)


def get_nozzle_wise_report_by_range(from_date=None, to_date=None):
    f, t = _date_range(from_date, to_date)
    settlements = _rows("settlements", f, t)
    profiles = _profiles_map()
    out = []

    for s in settlements:
        salesman = _name_for(s.get("salesman_id"), profiles)
        readings = s.get("nozzle_readings") or []
        if not isinstance(readings, list):
            continue
        for r in readings:
            out.append({
                "Date": s.get("date"),
                "Settlement ID": s.get("id"),
                "Shift ID": s.get("shift_id"),
                "Salesman": salesman,
                "Nozzle": r.get("nozzle_name") or r.get("nozzle_id"),
                "Fuel": r.get("fuel_type"),
                "Opening": _fmt_num(r.get("opening")),
                "Closing": _fmt_num(r.get("closing")),
                "Testing Adj": _fmt_num(r.get("testing_adj") or r.get("testing_adjustment")),
                "Actual Liters": _fmt_num(r.get("actual_liters")),
                "Rate": _fmt_num(r.get("rate")),
                "Sale Amount": _fmt_num(r.get("sale_amount")),
                "Status": s.get("status") or "pending",
            })
    return out


def get_payment_mode_report(entry_date=None):
    entry_date = _iso(entry_date) or _today()
    r = get_daily_closing_report(entry_date)
    return [
        {
            "Payment Mode": "Cash",
            "Sale Amount": r["cash_sale"],
            "Credit Received": r.get("credit_cash_received", 0),
            "Received/Settled": r["cash_deposited"],
            "Expense": r["cash_expense"],
            "Pending/In Hand": r["cash_in_hand"],
        },
        {
            "Payment Mode": "Bank",
            "Sale Amount": 0.0,
            "Credit Received": r.get("credit_bank_received", 0),
            "Received/Settled": r.get("bank_inflow_total", 0),
            "Expense": r["bank_expense"],
            "Pending/In Hand": 0.0,
        },
        {
            "Payment Mode": "Paytm",
            "Sale Amount": r["paytm_sale"],
            "Credit Received": r.get("credit_paytm_received", 0),
            "Received/Settled": r["paytm_settled"],
            "Expense": 0.0,
            "Pending/In Hand": r["paytm_pending"],
        },
        {
            "Payment Mode": "CCMS",
            "Sale Amount": r["ccms_sale"],
            "Credit Received": r.get("credit_ccms_received", 0),
            "Received/Settled": r["ccms_received"],
            "Expense": 0.0,
            "Pending/In Hand": r["ccms_pending"],
        },
        {
            "Payment Mode": "Credit",
            "Sale Amount": r["credit_sale"],
            "Credit Received": r.get("credit_received_total", 0),
            "Received/Settled": r.get("credit_received_total", 0),
            "Expense": 0.0,
            "Pending/In Hand": round(r["credit_sale"] - r.get("credit_received_total", 0), 2),
        },
    ]


# ---------------- Cash / Paytm / CCMS / Bank reports ----------------


def _ledger_running(rows, inflow_key="Inflow", outflow_key="Outflow"):
    balance = 0.0
    for r in rows:
        balance += _safe_float(r.get(inflow_key)) - _safe_float(r.get(outflow_key))
        r["Running Balance"] = round(balance, 2)
    return rows


def get_cash_report(from_date=None, to_date=None):
    f, t = _date_range(from_date, to_date)
    sale_rows = [r for r in get_sale_report_by_range(f, t, status="approved") if _safe_float(r.get("Cash"))]
    deposits = _rows("cash_deposits", f, t)
    expenses = _rows("expenses", f, t, status="approved", payment_mode="cash")
    credit_payments = _credit_payment_rows(f, t, status="approved", payment_mode="cash")

    rows = []
    for r in sale_rows:
        rows.append({
            "Date": r.get("Date"), "Type": "Cash Sale", "Reference": f"Settlement {r.get('Settlement ID')}",
            "Particular": r.get("Salesman"), "Inflow": _fmt_num(r.get("Cash")), "Outflow": 0.0, "Note": r.get("Status"),
        })
    for c in credit_payments:
        party = c.get("credit_parties") or {}
        rows.append({
            "Date": c.get("date"), "Type": "Creditor Payment - Cash", "Reference": c.get("reference_id") or c.get("id"),
            "Particular": party.get("name") or c.get("party_id"), "Inflow": _fmt_num(c.get("amount")), "Outflow": 0.0, "Note": c.get("note"),
        })
    for d in deposits:
        rows.append({
            "Date": d.get("date"), "Type": "Cash Deposit to Bank", "Reference": d.get("reference_no") or d.get("utr_ref") or d.get("id"),
            "Particular": d.get("bank_name") or d.get("bank") or "Bank", "Inflow": 0.0, "Outflow": _fmt_num(d.get("amount")), "Note": d.get("note"),
        })
    for e in expenses:
        rows.append({
            "Date": e.get("date"), "Type": "Cash Expense", "Reference": e.get("reference_no") or e.get("id"),
            "Particular": e.get("category"), "Inflow": 0.0, "Outflow": _fmt_num(e.get("amount")), "Note": e.get("description"),
        })
    rows.sort(key=lambda x: str(x.get("Date") or ""))
    return _ledger_running(rows)


def get_paytm_report(from_date=None, to_date=None):
    f, t = _date_range(from_date, to_date)
    sale_rows = [r for r in get_sale_report_by_range(f, t, status="approved") if _safe_float(r.get("Paytm"))]
    settlements = _rows("paytm_settlements", f, t)
    credit_payments = _credit_payment_rows(f, t, status="approved", payment_mode="paytm")

    rows = []
    for r in sale_rows:
        rows.append({
            "Date": r.get("Date"), "Type": "Paytm Sale", "Reference": f"Settlement {r.get('Settlement ID')}",
            "Particular": r.get("Salesman"), "Inflow": _fmt_num(r.get("Paytm")), "Outflow": 0.0, "Note": r.get("Status"),
        })
    for c in credit_payments:
        party = c.get("credit_parties") or {}
        rows.append({
            "Date": c.get("date"), "Type": "Creditor Payment - Paytm", "Reference": c.get("reference_id") or c.get("id"),
            "Particular": party.get("name") or c.get("party_id"), "Inflow": _fmt_num(c.get("amount")), "Outflow": 0.0, "Note": c.get("note"),
        })
    for s in settlements:
        rows.append({
            "Date": s.get("date"), "Type": "Paytm Settled to Bank", "Reference": s.get("reference_no") or s.get("utr_ref") or s.get("id"),
            "Particular": s.get("bank_name") or s.get("bank") or "Bank", "Inflow": 0.0, "Outflow": _fmt_num(s.get("amount")), "Note": s.get("note"),
        })
    rows.sort(key=lambda x: str(x.get("Date") or ""))
    return _ledger_running(rows)


def get_ccms_report(from_date=None, to_date=None):
    f, t = _date_range(from_date, to_date)
    sale_rows = [r for r in get_sale_report_by_range(f, t, status="approved") if _safe_float(r.get("CCMS"))]
    receipts = _rows("ccms_settlements", f, t)
    credit_payments = _credit_payment_rows(f, t, status="approved", payment_mode="ccms")

    rows = []
    for r in sale_rows:
        rows.append({
            "Date": r.get("Date"), "Type": "CCMS Sale", "Reference": f"Settlement {r.get('Settlement ID')}",
            "Particular": r.get("Salesman"), "Inflow": _fmt_num(r.get("CCMS")), "Outflow": 0.0, "Note": r.get("Status"),
        })
    for c in credit_payments:
        party = c.get("credit_parties") or {}
        rows.append({
            "Date": c.get("date"), "Type": "Creditor Payment - CCMS", "Reference": c.get("reference_id") or c.get("id"),
            "Particular": party.get("name") or c.get("party_id"), "Inflow": _fmt_num(c.get("amount")), "Outflow": 0.0, "Note": c.get("note"),
        })
    for s in receipts:
        rows.append({
            "Date": s.get("date"), "Type": "CCMS Received", "Reference": s.get("reference_no") or s.get("utr_ref") or s.get("id"),
            "Particular": s.get("bank_name") or s.get("bank") or "Source", "Inflow": 0.0, "Outflow": _fmt_num(s.get("amount")), "Note": s.get("note"),
        })
    rows.sort(key=lambda x: str(x.get("Date") or ""))
    return _ledger_running(rows)


def get_bank_report(from_date=None, to_date=None):
    f, t = _date_range(from_date, to_date)
    cash_deposits = _rows("cash_deposits", f, t)
    paytm_settlements = _rows("paytm_settlements", f, t)
    ccms_receipts = _rows("ccms_settlements", f, t)
    bank_expenses = _rows("expenses", f, t, status="approved", payment_mode="bank")
    inward_payments = _rows("inward_payments", f, t)
    credit_bank_payments = _credit_payment_rows(f, t, status="approved", payment_mode="bank")

    rows = []
    for r in cash_deposits:
        rows.append({"Date": r.get("date"), "Type": "Cash Deposit", "Reference": r.get("reference_no") or r.get("id"), "Bank": r.get("bank_name") or r.get("bank"), "Inflow": _fmt_num(r.get("amount")), "Outflow": 0.0, "Note": r.get("note")})
    for r in paytm_settlements:
        rows.append({"Date": r.get("date"), "Type": "Paytm Settlement", "Reference": r.get("reference_no") or r.get("id"), "Bank": r.get("bank_name") or r.get("bank"), "Inflow": _fmt_num(r.get("amount")), "Outflow": 0.0, "Note": r.get("note")})
    for r in ccms_receipts:
        rows.append({"Date": r.get("date"), "Type": "CCMS Received", "Reference": r.get("reference_no") or r.get("id"), "Bank": r.get("bank_name") or r.get("bank"), "Inflow": _fmt_num(r.get("amount")), "Outflow": 0.0, "Note": r.get("note")})
    for r in credit_bank_payments:
        party = r.get("credit_parties") or {}
        rows.append({"Date": r.get("date"), "Type": "Creditor Payment - Bank", "Reference": r.get("reference_id") or r.get("id"), "Bank": r.get("bank_name") or "Bank", "Inflow": _fmt_num(r.get("amount")), "Outflow": 0.0, "Note": f"{party.get('name') or r.get('party_id')} | {r.get('note') or ''}"})
    for r in bank_expenses:
        rows.append({"Date": r.get("date"), "Type": "Bank Expense", "Reference": r.get("reference_no") or r.get("id"), "Bank": r.get("bank_name"), "Inflow": 0.0, "Outflow": _fmt_num(r.get("amount")), "Note": r.get("description")})
    for r in inward_payments:
        amount = _safe_float(r.get("amount")) or _safe_float(r.get("neft_amount")) or _safe_float(r.get("total_paid"))
        rows.append({"Date": r.get("date") or r.get("payment_date"), "Type": "Oil Company Payment", "Reference": r.get("reference_no") or r.get("utr_number") or r.get("id"), "Bank": r.get("bank"), "Inflow": 0.0, "Outflow": round(amount, 2), "Note": r.get("oil_company") or r.get("inward_id")})
    rows.sort(key=lambda x: str(x.get("Date") or ""))
    return _ledger_running(rows)


# ---------------- Credit reports ----------------


def get_creditor_report():
    parties = _rows("credit_parties", order_by="name")
    txns = get_credit_ledger_report()
    report = {}

    for p in parties:
        pid = p.get("id")
        report[pid] = {
            "Creditor ID": pid,
            "Creditor": p.get("name"),
            "Phone": p.get("phone"),
            "Credit Limit": _fmt_num(p.get("credit_limit")),
            "Current Balance": _fmt_num(p.get("current_balance")),
            "Approved Sales": 0.0,
            "Approved Payments": 0.0,
            "Pending Sales": 0.0,
            "Pending Payments": 0.0,
            "Status": "Active" if p.get("is_active") else "Inactive",
        }

    for t in txns:
        pid = t.get("Party ID")
        report.setdefault(pid, {
            "Creditor ID": pid, "Creditor": t.get("Creditor") or f"Party {pid}", "Phone": None,
            "Credit Limit": 0.0, "Current Balance": 0.0,
            "Approved Sales": 0.0, "Approved Payments": 0.0,
            "Pending Sales": 0.0, "Pending Payments": 0.0, "Status": "Unknown",
        })
        amount = _safe_float(t.get("Amount"))
        status = t.get("Status") or "pending"
        typ = t.get("Type")
        if status == "approved" and typ == "sale":
            report[pid]["Approved Sales"] += amount
        elif status == "approved" and typ == "payment_received":
            report[pid]["Approved Payments"] += amount
        elif status == "pending" and typ == "sale":
            report[pid]["Pending Sales"] += amount
        elif status == "pending" and typ == "payment_received":
            report[pid]["Pending Payments"] += amount

    for row in report.values():
        for key in ["Approved Sales", "Approved Payments", "Pending Sales", "Pending Payments"]:
            row[key] = round(row[key], 2)
    return list(report.values())


def get_credit_ledger_report(status=None, txn_type=None, from_date=None, to_date=None):
    f, t = _date_range(from_date, to_date) if (from_date or to_date) else (None, None)
    rows = _rows("credit_transactions", f, t) if f else _rows("credit_transactions")
    party_map = {p.get("id"): p for p in _rows("credit_parties", order_by="name")}
    out = []
    for r in rows:
        if status and status != "all" and (r.get("status") or "pending") != status:
            continue
        if txn_type and txn_type != "all" and r.get("type") != txn_type:
            continue
        party = party_map.get(r.get("party_id")) or {}
        out.append({
            "Txn ID": r.get("id"),
            "Date": r.get("date"),
            "Party ID": r.get("party_id"),
            "Creditor": party.get("name"),
            "Type": r.get("type"),
            "Fuel": r.get("fuel_type"),
            "Liters": _fmt_num(r.get("liters")),
            "Amount": _fmt_num(r.get("amount")),
            "Mode": r.get("payment_mode"),
            "Status": r.get("status") or "pending",
            "Reference": r.get("reference_id"),
            "Created At": r.get("created_at"),
            "Approved At": r.get("approved_at"),
        })
    return out


def get_credit_report(from_date=None, to_date=None, status="all", txn_type="all"):
    return get_credit_ledger_report(status=status, txn_type=txn_type, from_date=from_date, to_date=to_date)


# ---------------- Testing / Stock / Inward / Expense reports ----------------


def get_testing_report(from_date=None, to_date=None, status="all"):
    f, t = _date_range(from_date, to_date)
    rows = _rows("daily_testing", f, t)
    try:
        nozzles = {n.get("id"): n for n in _rows("nozzles", order_by="id")}
    except Exception:
        nozzles = {}
    out = []
    for r in rows:
        if status and status != "all" and (r.get("status") or "pending") != status:
            continue
        nozzle = nozzles.get(r.get("nozzle_id")) or {}
        out.append({
            "Date": r.get("date"),
            "Testing ID": r.get("id"),
            "Nozzle": nozzle.get("nozzle_name") or r.get("nozzle_id"),
            "Fuel": r.get("fuel_type"),
            "Reading Before": _fmt_num(r.get("reading_before")),
            "Reading After": _fmt_num(r.get("reading_after")),
            "Testing Liters": _fmt_num(r.get("testing_liters")),
            "Density": _fmt_num(r.get("density")),
            "Temperature": _fmt_num(r.get("temperature")),
            "Result": r.get("result"),
            "Status": r.get("status") or "pending",
            "Remark": r.get("remark"),
            "Created At": r.get("created_at"),
        })
    return out


def get_stock_report(entry_date=None):
    entry_date = _iso(entry_date) or _today()
    try:
        from database.stock_db import get_stock_summary, get_stock_closing
        summary = get_stock_summary(entry_date)
        closing = get_stock_closing(entry_date)
    except Exception as exc:
        print(f"stock summary skipped: {exc}")
        summary = {}
        closing = []

    rows = []
    for fuel, r in (summary or {}).items():
        rows.append({
            "Date": entry_date,
            "Type": "Stock Summary",
            "Fuel": fuel,
            "Tank": r.get("tank_name"),
            "Opening Stock": _fmt_num(r.get("opening_stock")),
            "Inward Stock": _fmt_num(r.get("inward_stock")),
            "Sale Liters": _fmt_num(r.get("sale_liters")),
            "Testing Liters": _fmt_num(r.get("testing_liters")),
            "Expected Closing": _fmt_num(r.get("expected_closing_stock")),
            "Physical/Current Stock": _fmt_num(r.get("current_stock")),
            "Difference": _fmt_num(r.get("stock_difference")),
            "Status": "summary",
            "Remark": None,
        })
    for c in closing:
        rows.append({
            "Date": c.get("date"),
            "Type": "Physical Closing",
            "Fuel": c.get("fuel_type"),
            "Tank": None,
            "Opening Stock": None,
            "Inward Stock": None,
            "Sale Liters": None,
            "Testing Liters": None,
            "Expected Closing": _fmt_num(c.get("expected_stock")),
            "Physical/Current Stock": _fmt_num(c.get("physical_stock")),
            "Difference": _fmt_num(c.get("difference")),
            "Status": c.get("status") or "pending",
            "Remark": c.get("remark"),
        })
    return rows


def get_stock_movement_report(from_date=None, to_date=None):
    f, t = _date_range(from_date, to_date)
    rows = []
    for r in _rows("fuel_inward", f, t):
        rows.append({"Date": r.get("date"), "Type": "Fuel Inward", "Fuel": r.get("fuel_type"), "Quantity": _fmt_num(r.get("quantity_liters") or r.get("received_qty")), "Amount": _fmt_num(r.get("total_amount") or r.get("invoice_amount")), "Status": r.get("status"), "Reference": r.get("invoice_no")})
    for r in _rows("daily_testing", f, t):
        rows.append({"Date": r.get("date"), "Type": "Testing", "Fuel": r.get("fuel_type"), "Quantity": _fmt_num(r.get("testing_liters")), "Amount": 0.0, "Status": r.get("status"), "Reference": r.get("id")})
    for r in _rows("stock_closing", f, t):
        rows.append({"Date": r.get("date"), "Type": "Stock Closing", "Fuel": r.get("fuel_type"), "Quantity": _fmt_num(r.get("physical_stock")), "Amount": 0.0, "Status": r.get("status"), "Reference": r.get("id")})
    rows.sort(key=lambda x: str(x.get("Date") or ""))
    return rows


def get_inward_report(from_date=None, to_date=None, status="all"):
    f, t = _date_range(from_date, to_date)
    rows = _rows("fuel_inward", f, t)
    out = []
    for r in rows:
        if status and status != "all" and (r.get("status") or "pending") != status:
            continue
        qty = _safe_float(r.get("quantity_liters") or r.get("received_qty"))
        rate = _safe_float(r.get("rate") or r.get("rate_per_litre"))
        out.append({
            "Date": r.get("date"),
            "Inward ID": r.get("id"),
            "Oil Company": r.get("oil_company"),
            "Invoice No": r.get("invoice_no"),
            "Tanker No": r.get("tanker_no") or r.get("tanker_number"),
            "Fuel": r.get("fuel_type"),
            "Quantity Liters": round(qty, 2),
            "Rate": round(rate, 2),
            "Total Amount": _fmt_num(r.get("total_amount") or r.get("invoice_amount") or (qty * rate)),
            "Status": r.get("status") or r.get("payment_status") or "pending",
            "Created At": r.get("created_at"),
        })
    return out


def get_oil_company_report(company_name=None, from_date=None, to_date=None):
    f, t = _date_range(from_date, to_date)
    rows = _rows("oil_company_ledger", f, t)
    out = []
    for r in rows:
        company = r.get("oil_company") or r.get("company_name")
        if company_name and company_name != "all" and company != company_name:
            continue
        out.append({
            "Date": r.get("date"),
            "Company": company,
            "Type": r.get("type") or r.get("entry_type"),
            "Amount": _fmt_num(r.get("amount") or r.get("credit") or r.get("debit")),
            "Debit": _fmt_num(r.get("debit")),
            "Credit": _fmt_num(r.get("credit")),
            "Running Balance": _fmt_num(r.get("running_balance")),
            "Reference": r.get("reference_no") or r.get("reference_id"),
            "Note": r.get("note"),
        })
    return out


def get_expense_report(from_date=None, to_date=None, status="all", payment_mode="all"):
    f, t = _date_range(from_date, to_date)
    rows = _rows("expenses", f, t)
    out = []
    for r in rows:
        if status and status != "all" and (r.get("status") or "pending") != status:
            continue
        if payment_mode and payment_mode != "all" and r.get("payment_mode") != payment_mode:
            continue
        out.append({
            "Date": r.get("date"),
            "Expense ID": r.get("id"),
            "Category": r.get("category"),
            "Description": r.get("description"),
            "Amount": _fmt_num(r.get("amount")),
            "Payment Mode": r.get("payment_mode"),
            "Bank": r.get("bank_name") or r.get("bank"),
            "Reference": r.get("reference_no"),
            "Status": r.get("status") or "pending",
            "Created At": r.get("created_at"),
            "Approved At": r.get("approved_at"),
        })
    return out


def get_expense_summary_report(from_date=None, to_date=None):
    rows = get_expense_report(from_date, to_date, status="approved")
    summary = {}
    for r in rows:
        cat = r.get("Category") or "misc"
        mode = r.get("Payment Mode") or "-"
        key = (cat, mode)
        summary.setdefault(key, {"Category": cat, "Payment Mode": mode, "Amount": 0.0, "Count": 0})
        summary[key]["Amount"] += _safe_float(r.get("Amount"))
        summary[key]["Count"] += 1
    for r in summary.values():
        r["Amount"] = round(r["Amount"], 2)
    return list(summary.values())



# ---------------- Daily Sales Master / Owner Daily Sales Report ----------------

def _credit_party_map():
    try:
        rows = get_supabase_client().table("credit_parties").select("id, name, phone, current_balance").execute().data or []
        return {str(r.get("id")): r for r in rows}
    except Exception as exc:
        print(f"credit party map skipped: {exc}")
        return {}


def _nozzle_actual_liters(nozzle_row):
    liters = _safe_float(nozzle_row.get("actual_liters"))
    if liters <= 0:
        liters = _safe_float(nozzle_row.get("net_sale_liters"))
    if liters <= 0:
        gross = _safe_float(nozzle_row.get("gross_liters"))
        if gross <= 0:
            opening = _safe_float(nozzle_row.get("opening"))
            closing = _safe_float(nozzle_row.get("closing"))
            gross = round(closing - opening, 2)
        testing = _safe_float(
            nozzle_row.get("testing_liters")
            or nozzle_row.get("testing_adj")
            or nozzle_row.get("testing_adjustment")
        )
        liters = round(gross - testing, 2)
    return round(max(liters, 0), 2)


def _nozzle_sale_amount(nozzle_row, liters=None):
    amount = _safe_float(nozzle_row.get("sale_amount"))
    if amount <= 0:
        liters = _safe_float(liters)
        rate = _safe_float(nozzle_row.get("rate"))
        amount = round(liters * rate, 2)
    return round(amount, 2)


def get_daily_sales_master_report(entry_date=None):
    """
    One-day complete sales report for owner.

    Sections:
    - Summary cards
    - Fuel-wise petrol/diesel liters + amount
    - Salesman/nozzle-wise sale
    - Salesman-wise payment summary
    - Payment mode summary
    - Expense of the day
    - Creditor list: credit sale + cash given
    - Final ledger balances: cash, paytm, ccms, OD, CC
    """
    entry_date = _iso(entry_date) or _today()

    profiles = _profiles_map()
    settlements = _rows("settlements", entry_date, entry_date)
    approved = [s for s in settlements if (s.get("status") or "pending") == "approved"]

    # 1. Nozzle-wise sale rows + fuel summary
    nozzle_rows = []
    fuel_summary_map = {
        "petrol": {"Fuel": "petrol", "Liters": 0.0, "Amount": 0.0, "Nozzle Rows": 0},
        "diesel": {"Fuel": "diesel", "Liters": 0.0, "Amount": 0.0, "Nozzle Rows": 0},
    }

    for s in approved:
        salesman = _name_for(s.get("salesman_id"), profiles)
        readings = s.get("nozzle_readings") or []
        if not isinstance(readings, list):
            continue

        for r in readings:
            fuel = r.get("fuel_type") or r.get("fuel")
            liters = _nozzle_actual_liters(r)
            sale_amount = _nozzle_sale_amount(r, liters)

            row = {
                "Date": s.get("date"),
                "Salesman": salesman,
                "Shift ID": s.get("shift_id"),
                "Settlement ID": s.get("id"),
                "Nozzle": r.get("nozzle_name") or r.get("nozzle_id"),
                "Fuel": fuel,
                "Opening": _fmt_num(r.get("opening")),
                "Closing": _fmt_num(r.get("closing")),
                "Gross Liters": _fmt_num(r.get("gross_liters") or (_safe_float(r.get("closing")) - _safe_float(r.get("opening")))),
                "Testing Liters": _fmt_num(r.get("testing_liters") or r.get("testing_adj") or r.get("testing_adjustment")),
                "Net Sale Liters": liters,
                "Rate": _fmt_num(r.get("rate")),
                "Sale Amount": sale_amount,
                "Status": s.get("status") or "pending",
            }
            nozzle_rows.append(row)

            if fuel in fuel_summary_map:
                fuel_summary_map[fuel]["Liters"] += liters
                fuel_summary_map[fuel]["Amount"] += sale_amount
                fuel_summary_map[fuel]["Nozzle Rows"] += 1

    for row in fuel_summary_map.values():
        row["Liters"] = round(row["Liters"], 2)
        row["Amount"] = round(row["Amount"], 2)

    fuel_summary = list(fuel_summary_map.values())
    total_liters = round(sum(r["Liters"] for r in fuel_summary), 2)
    fuel_sale_amount = round(sum(r["Amount"] for r in fuel_summary), 2)

    # 2. Salesman-wise settlement/payment summary
    salesman_summary = []
    for s in approved:
        salesman_summary.append({
            "Date": s.get("date"),
            "Salesman": _name_for(s.get("salesman_id"), profiles),
            "Shift ID": s.get("shift_id"),
            "Settlement ID": s.get("id"),
            "Meter Sale": _fmt_num(s.get("meter_total")),
            "Cash": _fmt_num(s.get("cash_amount")),
            "Paytm": _fmt_num(s.get("paytm_amount")),
            "CCMS": _fmt_num(s.get("ccms_amount")),
            "Credit": _fmt_num(s.get("credit_amount")),
            "Payment Total": _payment_total(s),
            "Difference": _fmt_num(s.get("difference")),
            "Status": s.get("status") or "pending",
        })

    # 3. Payment mode summary
    cash_sale = _sum(approved, "cash_amount")
    paytm_sale = _sum(approved, "paytm_amount")
    ccms_sale = _sum(approved, "ccms_amount")
    credit_sale = _sum(approved, "credit_amount")
    total_sale = _sum(approved, "meter_total")
    payment_total = round(cash_sale + paytm_sale + ccms_sale + credit_sale, 2)

    payment_summary = [
        {"Particular": "Cash Sale", "Amount": cash_sale},
        {"Particular": "Paytm Sale", "Amount": paytm_sale},
        {"Particular": "CCMS Sale", "Amount": ccms_sale},
        {"Particular": "Credit Sale", "Amount": credit_sale},
        {"Particular": "Payment Total", "Amount": payment_total},
        {"Particular": "Meter Sale Total", "Amount": total_sale},
        {"Particular": "Difference", "Amount": round(total_sale - payment_total, 2)},
    ]

    # 4. Expenses of the day
    expenses = _rows("expenses", entry_date, entry_date, status="approved")
    expense_rows = []
    expense_total = 0.0
    for e in expenses:
        amount = _safe_float(e.get("amount"))
        expense_total += amount
        expense_rows.append({
            "Date": e.get("date"),
            "Category": e.get("category"),
            "Description": e.get("description"),
            "Payment Mode": e.get("payment_mode"),
            "Bank": e.get("bank_name") or e.get("bank"),
            "Amount": round(amount, 2),
            "Reference": e.get("reference_no"),
            "Status": e.get("status") or "approved",
        })
    expense_total = round(expense_total, 2)

    expense_summary = []
    expense_by_mode = {}
    for e in expense_rows:
        mode = e.get("Payment Mode") or "-"
        expense_by_mode[mode] = expense_by_mode.get(mode, 0.0) + _safe_float(e.get("Amount"))
    for mode, amount in expense_by_mode.items():
        expense_summary.append({"Payment Mode": mode, "Amount": round(amount, 2)})

    # 5. Creditors: credit sale + cash given for the date
    parties = _credit_party_map()
    credit_txns = _rows("credit_transactions", entry_date, entry_date)
    creditor_rows = []
    creditor_credit_total = 0.0
    creditor_cash_given_total = 0.0

    for tx in credit_txns:
        tx_type = tx.get("type")
        if tx_type not in ["sale", "cash_given"]:
            continue

        # Daily report should show business entry even if pending,
        # but totals are useful with status column visible.
        amount = _safe_float(tx.get("amount"))
        party = parties.get(str(tx.get("party_id"))) or {}
        label = "Fuel Credit" if tx_type == "sale" else "Cash Given"

        if tx_type == "sale" and (tx.get("status") or "pending") == "approved":
            creditor_credit_total += amount
        if tx_type == "cash_given" and (tx.get("status") or "pending") == "approved":
            creditor_cash_given_total += amount

        creditor_rows.append({
            "Date": tx.get("date"),
            "Creditor": party.get("name") or tx.get("party_id"),
            "Entry Type": label,
            "Amount": round(amount, 2),
            "Payment Mode": tx.get("payment_mode"),
            "Reference": tx.get("reference_id"),
            "Note": tx.get("note"),
            "Status": tx.get("status") or "pending",
            "Current Balance": _fmt_num(party.get("current_balance")),
        })

    creditor_summary = [
        {"Particular": "Approved Fuel Credit", "Amount": round(creditor_credit_total, 2)},
        {"Particular": "Approved Cash Given", "Amount": round(creditor_cash_given_total, 2)},
        {"Particular": "Total Creditor Increase", "Amount": round(creditor_credit_total + creditor_cash_given_total, 2)},
    ]

    # 6. Final ledger balances
    ledger_balances = []
    try:
        from database.payment_db import get_account_summary, get_bank_account_summary

        for account in ["cash", "paytm", "ccms"]:
            summary = get_account_summary(account, None, entry_date)
            ledger_balances.append({
                "Ledger": account.upper(),
                "Credit/Inflow": _fmt_num(summary.get("Credit")),
                "Debit/Outflow": _fmt_num(summary.get("Debit")),
                "Balance": _fmt_num(summary.get("Balance")),
            })

        for bank_name in ["Canara Bank OD Account", "Canara Bank CC Account"]:
            summary = get_bank_account_summary(bank_name, None, entry_date)
            ledger_balances.append({
                "Ledger": bank_name,
                "Credit/Inflow": _fmt_num(summary.get("Credit")),
                "Debit/Outflow": _fmt_num(summary.get("Debit")),
                "Balance": _fmt_num(summary.get("Balance")),
            })

    except Exception as exc:
        print(f"ledger balance skipped: {exc}")

    # Top summary
    summary_cards = {
        "date": entry_date,
        "total_sale": total_sale,
        "fuel_sale_amount": fuel_sale_amount,
        "total_liters": total_liters,
        "petrol_liters": fuel_summary_map["petrol"]["Liters"],
        "petrol_amount": fuel_summary_map["petrol"]["Amount"],
        "diesel_liters": fuel_summary_map["diesel"]["Liters"],
        "diesel_amount": fuel_summary_map["diesel"]["Amount"],
        "cash_sale": cash_sale,
        "paytm_sale": paytm_sale,
        "ccms_sale": ccms_sale,
        "credit_sale": credit_sale,
        "payment_total": payment_total,
        "sale_difference": round(total_sale - payment_total, 2),
        "expense_total": expense_total,
        "creditor_credit_total": round(creditor_credit_total, 2),
        "creditor_cash_given_total": round(creditor_cash_given_total, 2),
        "approved_settlements": len(approved),
        "total_settlements": len(settlements),
    }

    return {
        "summary": summary_cards,
        "fuel_summary": fuel_summary,
        "nozzle_sales": nozzle_rows,
        "salesman_summary": salesman_summary,
        "payment_summary": payment_summary,
        "expense_rows": expense_rows,
        "expense_summary": expense_summary,
        "creditor_rows": creditor_rows,
        "creditor_summary": creditor_summary,
        "ledger_balances": ledger_balances,
    }

# ---------------- Monthly summary ----------------


def get_monthly_summary(month=None, year=None):
    today = date.today()
    month = int(month or today.month)
    year = int(year or today.year)
    first = date(year, month, 1)
    import calendar
    last = date(year, month, calendar.monthrange(year, month)[1])
    f, t = first.isoformat(), last.isoformat()

    approved_sales = get_sale_report_by_range(f, t, status="approved")
    expenses = get_expense_report(f, t, status="approved")
    inward = get_inward_report(f, t, status="approved")
    cash = get_cash_report(f, t)
    paytm = get_paytm_report(f, t)
    ccms = get_ccms_report(f, t)
    credit = get_credit_report(f, t, status="approved")

    total_sale = _sum(approved_sales, "Meter Sale")
    cash_sale = _sum(approved_sales, "Cash")
    paytm_sale = _sum(approved_sales, "Paytm")
    ccms_sale = _sum(approved_sales, "CCMS")
    credit_sale = _sum(approved_sales, "Credit")
    expense_total = _sum(expenses, "Amount")
    inward_total = _sum(inward, "Total Amount")

    return [
        {"Month": f"{year}-{month:02d}", "Particular": "Total Sale", "Amount": total_sale},
        {"Month": f"{year}-{month:02d}", "Particular": "Cash Sale", "Amount": cash_sale},
        {"Month": f"{year}-{month:02d}", "Particular": "Paytm Sale", "Amount": paytm_sale},
        {"Month": f"{year}-{month:02d}", "Particular": "CCMS Sale", "Amount": ccms_sale},
        {"Month": f"{year}-{month:02d}", "Particular": "Credit Sale", "Amount": credit_sale},
        {"Month": f"{year}-{month:02d}", "Particular": "Cash Ledger Net", "Amount": round(_sum(cash, "Inflow") - _sum(cash, "Outflow"), 2)},
        {"Month": f"{year}-{month:02d}", "Particular": "Paytm Pending Net", "Amount": round(_sum(paytm, "Inflow") - _sum(paytm, "Outflow"), 2)},
        {"Month": f"{year}-{month:02d}", "Particular": "CCMS Pending Net", "Amount": round(_sum(ccms, "Inflow") - _sum(ccms, "Outflow"), 2)},
        {"Month": f"{year}-{month:02d}", "Particular": "Approved Credit Transactions", "Amount": _sum(credit, "Amount")},
        {"Month": f"{year}-{month:02d}", "Particular": "Fuel Inward Cost", "Amount": inward_total},
        {"Month": f"{year}-{month:02d}", "Particular": "Approved Expenses", "Amount": expense_total},
        {"Month": f"{year}-{month:02d}", "Particular": "Basic Net Before Stock Margin", "Amount": round(total_sale - inward_total - expense_total, 2)},
    ]
