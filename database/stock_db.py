from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client

FUEL_TYPES = ["petrol", "diesel"]

def _now(): return datetime.now(timezone.utc).isoformat()
def _today(): return date.today().isoformat()
def _f(v):
    try: return float(v or 0)
    except Exception: return 0.0

def get_all_tanks():
    try:
        return get_supabase_client().table("stock_tanks").select("*").order("fuel_type").execute().data or []
    except Exception as e:
        print("get_all_tanks", e); return []

def get_tank_by_fuel(fuel_type):
    try:
        r = get_supabase_client().table("stock_tanks").select("*").eq("fuel_type", fuel_type).eq("is_active", True).order("id", desc=True).limit(1).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        print("get_tank_by_fuel", e); return None

def get_active_nozzles_for_testing(fuel_type=None):
    try:
        q = get_supabase_client().table("nozzles").select("*").eq("is_active", True)
        if fuel_type:
            q = q.eq("fuel_type", fuel_type)
        return q.order("nozzle_name").execute().data or []
    except Exception as e:
        print("get_active_nozzles_for_testing", e); return []

def create_or_update_tank(fuel_type, tank_name, capacity_liters, opening_stock, current_stock, created_by):
    if fuel_type not in FUEL_TYPES: return None, "Invalid fuel type."
    if _f(capacity_liters) <= 0: return None, "Capacity required."
    supabase = get_supabase_client()
    existing = get_tank_by_fuel(fuel_type)
    payload = {
        "fuel_type": fuel_type,
        "tank_name": tank_name or f"{fuel_type.title()} Tank",
        "capacity_liters": _f(capacity_liters),
        "opening_stock": _f(opening_stock),
        "current_stock": _f(current_stock),
        "is_active": True,
        "created_by": created_by,
        "created_at": _now(),
    }
    try:
        if existing:
            r = supabase.table("stock_tanks").update(payload).eq("id", existing["id"]).execute()
        else:
            r = supabase.table("stock_tanks").insert(payload).execute()
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("create_or_update_tank", e); return None, str(e)

def update_tank_stock(fuel_type, new_stock):
    tank = get_tank_by_fuel(fuel_type)
    if not tank: return None, f"No tank for {fuel_type}."
    try:
        r = get_supabase_client().table("stock_tanks").update({"current_stock": _f(new_stock)}).eq("id", tank["id"]).execute()
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("update_tank_stock", e); return None, str(e)

def create_oil_company_ledger(oil_company, txn_type, amount, reference_no, fuel_type=None, quantity_liters=0, created_by=None):
    if not oil_company: return None, "Oil company required."
    payload = {
        "date": _today(),
        "oil_company": oil_company,
        "type": txn_type,
        "fuel_type": fuel_type,
        "quantity_liters": _f(quantity_liters),
        "amount": _f(amount),
        "reference_no": reference_no,
        "created_by": created_by,
        "created_at": _now(),
    }
    try:
        r = get_supabase_client().table("oil_company_ledger").insert(payload).execute()
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("create_oil_company_ledger", e); return None, str(e)

def create_fuel_inward(data):
    fuel_type = data.get("fuel_type")
    qty = _f(data.get("quantity_liters"))
    rate = _f(data.get("rate"))

    if fuel_type not in FUEL_TYPES: return None, "Invalid fuel type."
    if qty <= 0: return None, "Quantity required."

    tank = get_tank_by_fuel(fuel_type)
    if not tank: return None, "Create tank first."

    new_stock = round(_f(tank.get("current_stock")) + qty, 2)

    if _f(tank.get("capacity_liters")) and new_stock > _f(tank.get("capacity_liters")):
        return None, "Tank capacity exceeded."

    total = round(qty * rate, 2)

    payload = {
        "date": data.get("date") or _today(),
        "oil_company": data.get("oil_company"),
        "invoice_no": data.get("invoice_no"),
        "tanker_no": data.get("tanker_no"),
        "fuel_type": fuel_type,
        "quantity_liters": qty,
        "rate": rate,
        "total_amount": total,
        "created_by": data.get("created_by"),
        "created_at": _now(),
    }

    try:
        r = get_supabase_client().table("fuel_inward").insert(payload).execute()
        inward = r.data[0] if r.data else None

        if inward:
            update_tank_stock(fuel_type, new_stock)
            create_oil_company_ledger(
                data.get("oil_company"),
                "inward",
                total,
                data.get("invoice_no"),
                fuel_type,
                qty,
                data.get("created_by"),
            )

        return inward, None
    except Exception as e:
        print("create_fuel_inward", e); return None, str(e)

def get_fuel_inward(entry_date=None):
    try:
        q = get_supabase_client().table("fuel_inward").select("*")
        if entry_date: q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_fuel_inward", e); return []

def create_daily_testing(data):
    fuel_type = data.get("fuel_type")
    liters = _f(data.get("testing_liters"))
    nozzle_id = data.get("nozzle_id")
    reading_before = _f(data.get("reading_before"))
    reading_after = _f(data.get("reading_after"))

    if fuel_type not in FUEL_TYPES:
        return None, "Invalid fuel type."

    if not nozzle_id:
        return None, "Nozzle required for testing."

    if liters <= 0:
        return None, "Testing liters must be greater than 0."

    if reading_after and reading_before and reading_after < reading_before:
        return None, "Reading after cannot be less than reading before."

    tank = get_tank_by_fuel(fuel_type)
    if not tank:
        return None, "Create tank first."

    payload = {
        "date": data.get("date") or _today(),
        "fuel_type": fuel_type,
        "nozzle_id": nozzle_id,
        "reading_before": reading_before,
        "reading_after": reading_after,
        "density": _f(data.get("density")),
        "temperature": _f(data.get("temperature")),
        "testing_liters": liters,
        "result": data.get("result"),
        "remark": data.get("remark"),
        "tested_by": data.get("tested_by"),
        "created_at": _now(),
    }

    try:
        r = get_supabase_client().table("daily_testing").insert(payload).execute()
        row = r.data[0] if r.data else None

        if row:
            # Correct logic: testing meter reading badhata hai, par fuel tank me wapas jata hai.
            # Isliye stock balance me testing liters ADD BACK hoga.
            new_stock = round(_f(tank.get("current_stock")) + liters, 2)
            update_tank_stock(fuel_type, new_stock)

            # Optional: nozzle current reading ko testing reading after tak update kar do.
            if reading_after > 0:
                try:
                    get_supabase_client().table("nozzles").update({"current_reading": reading_after}).eq("id", nozzle_id).execute()
                except Exception as nozzle_error:
                    print("optional nozzle reading update failed", nozzle_error)

        return row, None
    except Exception as e:
        print("create_daily_testing", e); return None, str(e)

def get_daily_testing(entry_date=None):
    try:
        q = get_supabase_client().table("daily_testing").select("*, nozzles:nozzle_id(nozzle_name)")
        if entry_date: q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_daily_testing", e); return []

def _sum_by_fuel(rows, key):
    total = {"petrol": 0.0, "diesel": 0.0}
    for r in rows:
        ft = r.get("fuel_type")
        if ft in total:
            total[ft] += _f(r.get(key))
    return {k: round(v, 2) for k, v in total.items()}

def get_inward_totals(entry_date=None):
    return _sum_by_fuel(get_fuel_inward(entry_date), "quantity_liters")

def get_testing_totals(entry_date=None):
    return _sum_by_fuel(get_daily_testing(entry_date), "testing_liters")

def get_sale_liters_from_settlements(entry_date=None):
    entry_date = entry_date or _today()
    total = {"petrol": 0.0, "diesel": 0.0}
    try:
        r = get_supabase_client().table("settlements").select("nozzle_readings").eq("date", entry_date).eq("status", "approved").execute()
        for s in r.data or []:
            for row in (s.get("nozzle_readings") or []):
                ft = row.get("fuel_type")
                if ft in total:
                    total[ft] += _f(row.get("actual_liters"))
    except Exception as e:
        print("get_sale_liters_from_settlements", e)
    return {k: round(v, 2) for k, v in total.items()}

def get_stock_summary(entry_date=None):
    entry_date = entry_date or _today()
    tanks = get_all_tanks()
    inward = get_inward_totals(entry_date)
    testing = get_testing_totals(entry_date)
    sales = get_sale_liters_from_settlements(entry_date)

    out = {}
    for ft in FUEL_TYPES:
        tank = next((t for t in tanks if t.get("fuel_type") == ft and bool(t.get("is_active"))), None)
        opening = _f(tank.get("opening_stock")) if tank else 0.0
        current = _f(tank.get("current_stock")) if tank else 0.0
        inward_qty = _f(inward.get(ft))
        sale_qty = _f(sales.get(ft))
        testing_qty = _f(testing.get(ft))

        # Correct formula:
        # Meter sale includes testing reading, but testing fuel returns to tank.
        # Therefore testing liters are added back.
        expected = round(opening + inward_qty - sale_qty + testing_qty, 2)

        out[ft] = {
            "fuel_type": ft,
            "tank_name": tank.get("tank_name") if tank else None,
            "capacity_liters": _f(tank.get("capacity_liters")) if tank else 0.0,
            "opening_stock": opening,
            "inward_stock": inward_qty,
            "sale_liters": sale_qty,
            "testing_liters": testing_qty,
            "expected_closing_stock": expected,
            "current_stock": current,
            "stock_difference": round(current - expected, 2),
        }

    return out

def save_stock_closing(data):
    fuel_type = data.get("fuel_type")
    physical = _f(data.get("physical_stock"))

    if fuel_type not in FUEL_TYPES:
        return None, "Invalid fuel type."

    summary = get_stock_summary(data.get("date") or _today())[fuel_type]
    expected = _f(summary.get("expected_closing_stock"))
    diff = round(physical - expected, 2)

    payload = {
        "date": data.get("date") or _today(),
        "fuel_type": fuel_type,
        "expected_stock": expected,
        "physical_stock": physical,
        "difference": diff,
        "remark": data.get("remark"),
        "created_by": data.get("created_by"),
        "created_at": _now(),
    }

    try:
        r = get_supabase_client().table("stock_closing").insert(payload).execute()
        row = r.data[0] if r.data else None
        if row:
            update_tank_stock(fuel_type, physical)
        return row, None
    except Exception as e:
        print("save_stock_closing", e); return None, str(e)

def get_stock_closing(entry_date=None):
    try:
        q = get_supabase_client().table("stock_closing").select("*")
        if entry_date:
            q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_stock_closing", e); return []

def create_oil_company_payment(oil_company, amount, reference_no, created_by):
    if _f(amount) <= 0:
        return None, "Payment amount required."

    ledger, err = create_oil_company_ledger(
        oil_company,
        "payment",
        amount,
        reference_no,
        created_by=created_by,
    )

    payload = {
        "date": _today(),
        "oil_company": oil_company,
        "amount": _f(amount),
        "reference_no": reference_no,
        "created_by": created_by,
        "created_at": _now(),
    }

    try:
        get_supabase_client().table("inward_payments").insert(payload).execute()
    except Exception as e:
        print("inward_payments optional", e)

    return ledger, err

def get_oil_company_ledger(oil_company=None):
    try:
        q = get_supabase_client().table("oil_company_ledger").select("*")
        if oil_company:
            q = q.eq("oil_company", oil_company)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_oil_company_ledger", e); return []

def get_oil_company_summary():
    rows = get_oil_company_ledger()
    summary = {}

    for r in rows:
        c = r.get("oil_company") or "Unknown"
        summary.setdefault(c, {"Oil Company": c, "Inward Amount": 0.0, "Payment Made": 0.0, "Outstanding": 0.0})

        if r.get("type") == "inward":
            summary[c]["Inward Amount"] += _f(r.get("amount"))
        elif r.get("type") == "payment":
            summary[c]["Payment Made"] += _f(r.get("amount"))

    for row in summary.values():
        row["Inward Amount"] = round(row["Inward Amount"], 2)
        row["Payment Made"] = round(row["Payment Made"], 2)
        row["Outstanding"] = round(row["Inward Amount"] - row["Payment Made"], 2)

    return list(summary.values())
