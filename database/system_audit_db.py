from datetime import date
from utils.app_time import today_ist
from config.supabase_client import get_supabase_client

def _today(): return today_ist()
def _f(v):
    try: return float(v or 0)
    except Exception: return 0.0
def _r(status, area, issue, detail="", fix=""):
    return {"Status": status, "Area": area, "Issue": issue, "Detail": detail, "Suggested Fix": fix}

def _rows(table, filters=None, limit=None):
    try:
        q = get_supabase_client().table(table).select("*")
        for k, v in (filters or {}).items():
            q = q.eq(k, v)
        if limit: q = q.limit(limit)
        return q.execute().data or [], None
    except Exception as e:
        return [], str(e)

def audit_imports():
    mods = [
        ("database.payment_db","get_daily_money_summary"),
        ("database.stock_db","get_stock_summary"),
        ("database.expense_db","get_profit_loss_report"),
        ("database.reports_db","get_daily_closing_report"),
        ("database.stock_approval_db","get_stock_variance_report"),
        ("utils.export_utils","render_export_buttons"),
    ]
    out=[]
    for mod, fn in mods:
        try:
            m = __import__(mod, fromlist=[fn]); getattr(m, fn)
            out.append(_r("PASS","Imports",f"{mod}.{fn} available"))
        except Exception as e:
            out.append(_r("FAIL","Imports",f"{mod}.{fn} missing/error",str(e),"Upload missing file or fix import/function name."))
    return out

def audit_required_tables():
    tables = ["profiles","nozzles","fuel_rates","shifts","shift_assignments","sale_entries","settlements","credit_parties","credit_transactions","cash_deposits","paytm_settlements","ccms_settlements","stock_tanks","fuel_inward","daily_testing","stock_closing","oil_company_ledger","inward_payments","expenses"]
    out=[]
    for t in tables:
        _, err = _rows(t, limit=1)
        if err: out.append(_r("FAIL","Database",f"{t} table missing/inaccessible",err,"Run related SQL or check RLS/table name."))
        else: out.append(_r("PASS","Database",f"{t} table exists"))
    return out

def audit_duplicate_settlements():
    rows, err = _rows("settlements")
    if err: return [_r("FAIL","Settlement","Cannot read settlements",err)]
    g={}
    for x in rows:
        key=(x.get("shift_id"),x.get("salesman_id"),x.get("status"))
        g.setdefault(key,[]).append(x)
    out=[]; found=False
    for (shift,salesman,status), items in g.items():
        if status in ["pending","hold","reopened"] and len(items)>1:
            found=True
            out.append(_r("FAIL","Settlement","Duplicate open settlement",f"shift={shift}, salesman={salesman}, status={status}, count={len(items)}","Keep latest and mark old duplicates reopened/rejected."))
    if not found: out.append(_r("PASS","Settlement","No duplicate open settlement found"))
    return out

def audit_settlement_payment_match(entry_date=None):
    filters = {"date": entry_date} if entry_date else {}
    rows, err = _rows("settlements", filters)
    if err: return [_r("FAIL","Settlement","Cannot read settlements by date",err)]
    out=[]; bad=0
    for s in rows:
        meter=_f(s.get("meter_total"))
        pay=_f(s.get("cash_amount"))+_f(s.get("paytm_amount"))+_f(s.get("ccms_amount"))+_f(s.get("credit_amount"))
        diff=round(meter-pay,2)
        if s.get("status")=="approved" and abs(diff)>0.01:
            bad+=1
            out.append(_r("FAIL","Settlement","Approved settlement mismatch",f"id={s.get('id')}, meter={meter}, payment={pay}, diff={diff}","Reopen/correct closing or payment breakup."))
    if bad==0: out.append(_r("PASS","Settlement","Approved settlements payment match"))
    return out

def audit_money(entry_date=None):
    entry_date=entry_date or _today()
    try:
        from database.payment_db import get_daily_money_summary
        s=get_daily_money_summary(entry_date)
    except Exception as e:
        return [_r("FAIL","Money Control","Cannot calculate money summary",str(e))]
    out=[]; bad=0
    for name,key in [("Cash In Hand negative","cash_in_hand"),("Paytm Pending negative","paytm_pending"),("CCMS Pending negative","ccms_pending")]:
        val=_f(s.get(key))
        if val < -0.01:
            bad+=1
            out.append(_r("FAIL","Money Control",name,f"{key}={val}","Check duplicate settlement/deposit/expense/received entries."))
    if bad==0: out.append(_r("PASS","Money Control","No negative money balances"))
    return out

def audit_credit():
    parties, e1 = _rows("credit_parties"); txns, e2 = _rows("credit_transactions")
    if e1: return [_r("FAIL","Credit","Cannot read credit_parties",e1)]
    if e2: return [_r("FAIL","Credit","Cannot read credit_transactions",e2)]
    calc={}
    for t in txns:
        if t.get("status")!="approved": continue
        pid=t.get("party_id"); calc.setdefault(pid,0.0)
        if t.get("type")=="sale": calc[pid]+=_f(t.get("amount"))
        elif t.get("type")=="payment_received": calc[pid]-=_f(t.get("amount"))
    out=[]; bad=0
    for p in parties:
        stored=round(_f(p.get("current_balance")),2); computed=round(calc.get(p.get("id"),0),2)
        if abs(stored-computed)>0.01:
            bad+=1
            out.append(_r("WARNING","Credit","Credit party balance mismatch",f"{p.get('name')}: stored={stored}, calculated={computed}","Recalculate current_balance from approved credit ledger."))
    if bad==0: out.append(_r("PASS","Credit","Credit balances match approved ledger"))
    return out

def audit_stock(entry_date=None):
    entry_date=entry_date or _today()
    try:
        from database.stock_db import get_stock_summary
        s=get_stock_summary(entry_date)
    except Exception as e:
        return [_r("FAIL","Stock","Cannot calculate stock summary",str(e))]
    out=[]; bad=0
    for fuel,row in (s or {}).items():
        diff=_f(row.get("stock_difference"))
        if abs(diff)>0.01:
            bad+=1
            out.append(_r("WARNING","Stock","Stock variance found",f"{fuel}: current={row.get('current_stock')}, expected={row.get('expected_closing_stock')}, diff={diff}","Verify inward, sales, testing return and stock closing."))
    if bad==0: out.append(_r("PASS","Stock","Stock current and expected values match"))
    return out

def audit_pending():
    tables=[("settlements","Settlement"),("credit_transactions","Credit"),("fuel_inward","Fuel Inward"),("daily_testing","Testing"),("stock_closing","Stock Closing"),("expenses","Expense")]
    out=[]
    for t,area in tables:
        rows,err=_rows(t,{"status":"pending"})
        if err: out.append(_r("WARNING",area,f"Cannot check pending in {t}",err)); continue
        if rows: out.append(_r("WARNING",area,"Pending approvals exist",f"{t}: {len(rows)} pending rows","Open approval screen and approve/hold/reject."))
        else: out.append(_r("PASS",area,f"No pending approvals in {t}"))
    return out

def audit_expense_modes():
    rows,err=_rows("expenses")
    if err: return [_r("WARNING","Expense","Cannot read expenses",err)]
    invalid=[(x.get("id"),x.get("payment_mode")) for x in rows if x.get("payment_mode") and x.get("payment_mode") not in ["cash","bank"]]
    if invalid:
        return [_r("WARNING","Expense","Old/invalid expense payment modes found",str(invalid[:10]),"New UI allows only cash/bank. Correct old rows if needed.")]
    return [_r("PASS","Expense","Expense modes are cash/bank only")]

def run_full_audit(entry_date=None):
    entry_date=entry_date or _today()
    checks=[]
    for fn in [audit_imports, audit_required_tables, audit_duplicate_settlements, lambda: audit_settlement_payment_match(entry_date), lambda: audit_money(entry_date), audit_credit, lambda: audit_stock(entry_date), audit_pending, audit_expense_modes]:
        checks.extend(fn())
    summary={"PASS":0,"WARNING":0,"FAIL":0,"TOTAL":len(checks)}
    for x in checks:
        if x.get("Status") in summary: summary[x.get("Status")]+=1
    return summary, checks
