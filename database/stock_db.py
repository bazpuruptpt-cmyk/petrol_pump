from datetime import date, datetime, timezone
from config.supabase_client import get_supabase_client

FUEL_TYPES = ["petrol", "diesel"]

def _now():
    return datetime.now(timezone.utc).isoformat()

def _today():
    return date.today().isoformat()

def _f(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


# ---------------- Tank Setup ----------------

def get_all_tanks():
    try:
        return (
            get_supabase_client()
            .table("stock_tanks")
            .select("*")
            .order("fuel_type")
            .execute()
            .data
            or []
        )
    except Exception as e:
        print("get_all_tanks", e)
        return []


def get_tank_by_fuel(fuel_type):
    try:
        r = (
            get_supabase_client()
            .table("stock_tanks")
            .select("*")
            .eq("fuel_type", fuel_type)
            .eq("is_active", True)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None
    except Exception as e:
        print("get_tank_by_fuel", e)
        return None


def get_active_nozzles_for_testing(fuel_type=None):
    try:
        q = get_supabase_client().table("nozzles").select("*").eq("is_active", True)
        if fuel_type:
            q = q.eq("fuel_type", fuel_type)
        return q.order("nozzle_name").execute().data or []
    except Exception as e:
        print("get_active_nozzles_for_testing", e)
        return []


def create_or_update_tank(fuel_type, tank_name, capacity_liters, opening_stock, current_stock, created_by):
    if fuel_type not in FUEL_TYPES:
        return None, "Invalid fuel type."

    if _f(capacity_liters) <= 0:
        return None, "Capacity required."

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
        print("create_or_update_tank", e)
        return None, str(e)


def update_tank_stock(fuel_type, new_stock):
    tank = get_tank_by_fuel(fuel_type)
    if not tank:
        return None, f"No tank for {fuel_type}."

    try:
        r = (
            get_supabase_client()
            .table("stock_tanks")
            .update({"current_stock": _f(new_stock)})
            .eq("id", tank["id"])
            .execute()
        )
        return (r.data[0] if r.data else None), None
    except Exception as e:
        print("update_tank_stock", e)
        return None, str(e)


# ---------------- Oil Company Ledger ----------------

def create_oil_company_ledger(
    oil_company,
    txn_type,
    amount,
    reference_no,
    fuel_type=None,
    quantity_liters=0,
    created_by=None,
    entry_date=None,
    note=None,
):
    if not oil_company:
        return None, "Oil company required."

    if _f(amount) <= 0:
        return None, "Ledger amount required."

    payload = {
        "date": entry_date or _today(),
        "oil_company": oil_company,
        "type": txn_type,
        "fuel_type": fuel_type,
        "quantity_liters": _f(quantity_liters),
        "amount": _f(amount),
        "reference_no": reference_no,
        "created_by": created_by,
        "created_at": _now(),
    }

    # Optional column support. If note column missing, insert retry will remove it.
    if note:
        payload["note"] = note

    try:
        r = get_supabase_client().table("oil_company_ledger").insert(payload).execute()
        return (r.data[0] if r.data else None), None
    except Exception as e:
        # If older schema has no note column, retry without note.
        if "note" in payload:
            try:
                payload.pop("note", None)
                r = get_supabase_client().table("oil_company_ledger").insert(payload).execute()
                return (r.data[0] if r.data else None), None
            except Exception as e2:
                print("create_oil_company_ledger retry", e2)
                return None, str(e2)

        print("create_oil_company_ledger", e)
        return None, str(e)


# ---------------- Pending-only Fuel Inward ----------------

def create_fuel_inward(data):
    """
    Final fuel inward logic:

    1. Fuel inward save hote hi tank stock top-up hoga.
    2. Same invoice amount Oil Company Ledger me inward/payable add hoga.
    3. Stock Approval ki jarurat nahi.
    4. Existing fuel_inward schema ke required columns:
       fuel, liters, amount, type ko bhi fill kiya gaya hai.
    """
    fuel_type = data.get("fuel_type") or data.get("fuel")
    qty = _f(data.get("quantity_liters") or data.get("liters"))
    rate = _f(data.get("rate"))
    invoice_amount = _f(data.get("total_amount") or data.get("invoice_amount") or data.get("amount"))

    oil_company = (data.get("oil_company") or "").strip()
    invoice_no = (data.get("invoice_no") or "").strip()
    tanker_no = (data.get("tanker_no") or "").strip()
    entry_date = data.get("date") or _today()

    if fuel_type not in FUEL_TYPES:
        return None, "Invalid fuel type."

    if qty <= 0:
        return None, "Quantity required."

    if not oil_company:
        return None, "Oil company required."

    tank = get_tank_by_fuel(fuel_type)
    if not tank:
        return None, "Create tank first."

    if invoice_amount <= 0:
        invoice_amount = round(qty * rate, 2)

    if invoice_amount <= 0:
        return None, "Invoice amount required."

    if rate <= 0 and qty > 0:
        rate = round(invoice_amount / qty, 4)

    current_stock = _f(tank.get("current_stock"))
    capacity = _f(tank.get("capacity_liters"))
    new_stock = round(current_stock + qty, 2)

    if capacity > 0 and new_stock > capacity:
        return None, "Inward blocked: tank capacity exceeded."

    # Fill both new and old schema names.
    payload = {
        "date": entry_date,

        # Required in current database schema.
        "type": "inward",
        "fuel": fuel_type,
        "liters": qty,
        "amount": round(invoice_amount, 2),

        # Current app/report fields.
        "oil_company": oil_company,
        "invoice_no": invoice_no,
        "tanker_no": tanker_no,
        "fuel_type": fuel_type,
        "quantity_liters": qty,
        "rate": rate,
        "total_amount": round(invoice_amount, 2),
        "status": "approved",
        "created_by": data.get("created_by"),
        "created_at": _now(),
        "approved_by": data.get("created_by"),
        "approved_at": _now(),
    }

    supabase = get_supabase_client()

    try:
        # 1. Save inward as approved.
        # First insert full payload. If old/new optional columns mismatch, retry minimal required payload.
        try:
            r = supabase.table("fuel_inward").insert(payload).execute()
        except Exception:
            minimal_payload = {
                "date": entry_date,
                "type": "inward",
                "fuel": fuel_type,
                "liters": qty,
                "amount": round(invoice_amount, 2),
                "oil_company": oil_company,
                "invoice_no": invoice_no,
                "tanker_no": tanker_no,
                "status": "approved",
                "created_by": data.get("created_by"),
                "created_at": _now(),
            }
            r = supabase.table("fuel_inward").insert(minimal_payload).execute()

        inward = r.data[0] if r.data else None

        if not inward:
            return None, "Fuel inward save failed."

        # 2. Increase tank stock immediately.
        updated_tank, tank_err = update_tank_stock(fuel_type, new_stock)
        if tank_err:
            return None, tank_err

        # 3. Oil company payable/debit increases by invoice amount.
        ledger, ledger_err = create_oil_company_ledger(
            oil_company=oil_company,
            txn_type="inward",
            amount=invoice_amount,
            reference_no=invoice_no or inward.get("id"),
            fuel_type=fuel_type,
            quantity_liters=qty,
            created_by=data.get("created_by"),
            entry_date=entry_date,
            note=f"Fuel inward invoice | Tanker: {tanker_no}",
        )

        if ledger_err:
            return None, f"Fuel inward saved and stock updated, but oil company ledger failed: {ledger_err}"

        return inward, None

    except Exception as e:
        print("create_fuel_inward", e)
        return None, str(e)


def get_fuel_inward(entry_date=None):
    try:
        q = get_supabase_client().table("fuel_inward").select("*")
        if entry_date:
            q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_fuel_inward", e)
        return []


# ---------------- Pending-only Nozzle-wise Testing ----------------

def create_daily_testing(data):
    """
    Simple nozzle testing logic locked:

    Manager/Owner:
    - Nozzle select karega.
    - Testing quantity enter karega.
    - System nozzle.current_reading ko quantity se immediately aage badhayega.
    - Same quantity tank me wapas maani jayegi.
    - Stock net effect = 0.
    - Entry date/nozzle-wise record hogi.
    - Agar nozzle active shift me assigned hai, entry assignment se link hogi.
    - Settlement me approved testing liters gross meter se minus honge.

    No approval required for this simple testing entry.
    """
    nozzle_id = data.get("nozzle_id")
    if not nozzle_id:
        return None, "Nozzle required for testing."

    nozzle = get_nozzle_for_testing(nozzle_id)
    if not nozzle:
        return None, "Nozzle not found."

    if nozzle.get("is_active") is False:
        return None, "Inactive nozzle testing allowed nahi hai."

    fuel_type = nozzle.get("fuel_type") or data.get("fuel_type")
    if fuel_type not in FUEL_TYPES:
        return None, "Invalid fuel type."

    current_reading = _f(nozzle.get("current_reading"))
    testing_liters = _f(data.get("testing_liters") or data.get("quantity") or data.get("testing_quantity"))

    if testing_liters <= 0:
        return None, "Testing quantity required."

    reading_before = current_reading
    reading_after = round(reading_before + testing_liters, 2)

    active_assignment = get_active_assignment_for_testing_nozzle(nozzle_id) or {}
    remark = (data.get("remark") or data.get("comment") or "").strip()

    payload = {
        "date": data.get("date") or _today(),
        "fuel_type": fuel_type,
        "nozzle_id": nozzle_id,
        "shift_id": active_assignment.get("shift_id"),
        "assignment_id": active_assignment.get("assignment_id"),
        "salesman_id": active_assignment.get("salesman_id"),
        "reading_before": reading_before,
        "reading_after": reading_after,
        "density": 0,
        "temperature": 0,
        "testing_liters": round(testing_liters, 2),
        "meter_adjustment": round(testing_liters, 2),  # Required by existing daily_testing schema.
        "returned_to_tank": True,
        "stock_effect_liters": 0,
        "result": "pass",  # Existing DB check allows pass/fail/hold. returned_to_tank=True carries testing-return logic.
        "remark": remark,
        "status": "approved",
        "tested_by": data.get("tested_by"),
        "approved_by": data.get("tested_by"),
        "approved_at": _now(),
        "created_at": _now(),
    }

    supabase = get_supabase_client()

    try:
        # Record first.
        r = supabase.table("daily_testing").insert(payload).execute()
        row = r.data[0] if r.data else None

        if not row:
            return None, "Testing record save failed."

        # Meter physical reading increased by testing quantity.
        supabase.table("nozzles").update({
            "current_reading": reading_after,
        }).eq("id", nozzle_id).execute()

        return row, None

    except Exception as e:
        print("create_daily_testing", e)
        return None, str(e)


def get_daily_testing(entry_date=None):
    try:
        q = get_supabase_client().table("daily_testing").select("*, nozzles:nozzle_id(nozzle_name, fuel_type)")
        if entry_date:
            q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_daily_testing", e)
        return []



def _truthy(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ["1", "true", "yes", "y", "returned"]
    return bool(value)


def get_nozzle_for_testing(nozzle_id):
    try:
        rows = (
            get_supabase_client()
            .table("nozzles")
            .select("*")
            .eq("id", nozzle_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    except Exception as exc:
        print("get_nozzle_for_testing", exc)
        return None


def get_active_assignment_for_testing_nozzle(nozzle_id):
    """
    Testing ke time agar nozzle kisi active shift me assigned hai,
    to testing entry us shift/assignment/salesman se link hogi.
    Nozzle allotment testing ke liye required nahi hai.
    """
    try:
        rows = (
            get_supabase_client()
            .table("shift_assignments")
            .select("*, shifts:shift_id(id, salesman_id, date, is_active)")
            .eq("nozzle_id", nozzle_id)
            .eq("is_active", True)
            .order("id", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )

        if not rows:
            return None

        row = rows[0]
        shift = row.get("shifts") or {}

        return {
            "assignment_id": row.get("id"),
            "shift_id": row.get("shift_id"),
            "salesman_id": row.get("salesman_id") or shift.get("salesman_id"),
            "shift_date": shift.get("date"),
        }

    except Exception as exc:
        print("get_active_assignment_for_testing_nozzle", exc)
        return None


def get_testing_adjustment_for_assignment(assignment_id, entry_date=None, approved_only=True):
    """
    Settlement calculation me same assignment ki approved testing subtract hogi.
    Net Sale = Closing - Opening - Testing Liters
    """
    if not assignment_id:
        return {
            "testing_liters": 0.0,
            "returned_liters": 0.0,
            "loss_liters": 0.0,
            "rows": [],
        }

    try:
        q = (
            get_supabase_client()
            .table("daily_testing")
            .select("*")
            .eq("assignment_id", assignment_id)
        )

        if entry_date:
            q = q.eq("date", entry_date)

        if approved_only:
            q = q.eq("status", "approved")

        rows = q.execute().data or []

    except Exception as exc:
        print("get_testing_adjustment_for_assignment", exc)
        rows = []

    testing_total = 0.0
    returned_total = 0.0
    loss_total = 0.0

    for row in rows:
        liters = _f(row.get("testing_liters"))
        testing_total += liters

        if _truthy(row.get("returned_to_tank"), default=True):
            returned_total += liters
        else:
            loss_total += liters

    return {
        "testing_liters": round(testing_total, 2),
        "returned_liters": round(returned_total, 2),
        "loss_liters": round(loss_total, 2),
        "rows": rows,
    }


def get_testing_totals_detailed(entry_date=None):
    rows = get_approved_daily_testing(entry_date)

    total = {
        "petrol": {"testing_liters": 0.0, "returned_liters": 0.0, "loss_liters": 0.0},
        "diesel": {"testing_liters": 0.0, "returned_liters": 0.0, "loss_liters": 0.0},
    }

    for row in rows:
        ft = row.get("fuel_type")
        if ft not in total:
            continue

        liters = _f(row.get("testing_liters"))
        total[ft]["testing_liters"] += liters

        if _truthy(row.get("returned_to_tank"), default=True):
            total[ft]["returned_liters"] += liters
        else:
            total[ft]["loss_liters"] += liters

    for ft in total:
        for key in total[ft]:
            total[ft][key] = round(total[ft][key], 2)

    return total



# ---------------- Stock Summary: approved entries only ----------------

def _sum_by_fuel(rows, key):
    total = {"petrol": 0.0, "diesel": 0.0}
    for r in rows:
        ft = r.get("fuel_type")
        if ft in total:
            total[ft] += _f(r.get(key))
    return {k: round(v, 2) for k, v in total.items()}


def get_approved_fuel_inward(entry_date=None):
    try:
        q = get_supabase_client().table("fuel_inward").select("*").eq("status", "approved")
        if entry_date:
            q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_approved_fuel_inward", e)
        return []


def get_approved_daily_testing(entry_date=None):
    try:
        q = get_supabase_client().table("daily_testing").select("*, nozzles:nozzle_id(nozzle_name, fuel_type)").eq("status", "approved")
        if entry_date:
            q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_approved_daily_testing", e)
        return []


def get_inward_totals(entry_date=None):
    return _sum_by_fuel(get_approved_fuel_inward(entry_date), "quantity_liters")


def get_testing_totals(entry_date=None):
    detailed = get_testing_totals_detailed(entry_date)
    return {fuel: values["testing_liters"] for fuel, values in detailed.items()}


def get_testing_returned_totals(entry_date=None):
    detailed = get_testing_totals_detailed(entry_date)
    return {fuel: values["returned_liters"] for fuel, values in detailed.items()}


def get_testing_loss_totals(entry_date=None):
    detailed = get_testing_totals_detailed(entry_date)
    return {fuel: values["loss_liters"] for fuel, values in detailed.items()}


def get_sale_liters_from_settlements(entry_date=None):
    entry_date = entry_date or _today()
    total = {"petrol": 0.0, "diesel": 0.0}

    try:
        r = (
            get_supabase_client()
            .table("settlements")
            .select("nozzle_readings")
            .eq("date", entry_date)
            .eq("status", "approved")
            .execute()
        )

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
    testing = get_testing_totals_detailed(entry_date)
    sales = get_sale_liters_from_settlements(entry_date)

    out = {}
    for ft in FUEL_TYPES:
        tank = next((t for t in tanks if t.get("fuel_type") == ft and bool(t.get("is_active"))), None)

        opening = _f(tank.get("opening_stock")) if tank else 0.0
        current = _f(tank.get("current_stock")) if tank else 0.0
        inward_qty = _f(inward.get(ft))
        sale_qty = _f(sales.get(ft))

        testing_total = _f((testing.get(ft) or {}).get("testing_liters"))
        testing_returned = _f((testing.get(ft) or {}).get("returned_liters"))
        testing_loss = _f((testing.get(ft) or {}).get("loss_liters"))

        # Final stable stock formula:
        # Sale liters from settlements are already NET SALE after testing subtraction.
        # Returned testing has zero stock loss.
        # Not-returned testing is calibration/testing loss and should reduce stock.
        expected = round(opening + inward_qty - sale_qty - testing_loss, 2)

        out[ft] = {
            "fuel_type": ft,
            "tank_name": tank.get("tank_name") if tank else None,
            "capacity_liters": _f(tank.get("capacity_liters")) if tank else 0.0,
            "opening_stock": opening,
            "inward_stock": inward_qty,
            "sale_liters": sale_qty,
            "testing_liters": testing_total,
            "testing_returned_liters": testing_returned,
            "testing_loss_liters": testing_loss,
            "expected_closing_stock": expected,
            "current_stock": current,
            "stock_difference": round(current - expected, 2),
        }

    return out


# ---------------- Pending-only Stock Closing ----------------

def save_stock_closing(data):
    """
    Pending-only logic:
    Physical closing entry save hogi, lekin tank current_stock yahan update nahi hoga.
    Tank current_stock sirf Stock Approval → Approve par physical_stock banega.
    """
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
        "status": "pending",
        "created_by": data.get("created_by"),
        "created_at": _now(),
    }

    try:
        r = get_supabase_client().table("stock_closing").insert(payload).execute()
        row = r.data[0] if r.data else None
        return row, None
    except Exception as e:
        print("save_stock_closing", e)
        return None, str(e)


def get_stock_closing(entry_date=None):
    try:
        q = get_supabase_client().table("stock_closing").select("*")
        if entry_date:
            q = q.eq("date", entry_date)
        return q.order("created_at", desc=True).execute().data or []
    except Exception as e:
        print("get_stock_closing", e)
        return []


# ---------------- Oil Company Payment ----------------

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
        print("get_oil_company_ledger", e)
        return []


def get_oil_company_summary():
    rows = get_oil_company_ledger()
    summary = {}

    for r in rows:
        c = r.get("oil_company") or "Unknown"
        summary.setdefault(
            c,
            {
                "Oil Company": c,
                "Inward Amount": 0.0,
                "CCMS Adjustment": 0.0,
                "Payment Made": 0.0,
                "Outstanding": 0.0,
            },
        )

        txn_type = r.get("type")
        amount = _f(r.get("amount"))

        if txn_type == "inward":
            summary[c]["Inward Amount"] += amount
        elif txn_type in ["payment", "bank_payment"]:
            summary[c]["Payment Made"] += amount
        elif txn_type in ["ccms", "ccms_adjustment"]:
            summary[c]["CCMS Adjustment"] += amount

    for row in summary.values():
        row["Inward Amount"] = round(row["Inward Amount"], 2)
        row["CCMS Adjustment"] = round(row["CCMS Adjustment"], 2)
        row["Payment Made"] = round(row["Payment Made"], 2)
        row["Outstanding"] = round(
            row["Inward Amount"] - row["CCMS Adjustment"] - row["Payment Made"],
            2,
        )

    return list(summary.values())
