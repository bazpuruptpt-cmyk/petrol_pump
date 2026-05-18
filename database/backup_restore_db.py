import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from config.supabase_client import get_supabase_client


BACKUP_VERSION = "single-pump-v1"

# Parent tables first; dependent ledgers after masters.
BACKUP_TABLES = [
    "profiles",
    "nozzles",
    "fuel_rates",
    "stock_tanks",
    "shifts",
    "shift_assignments",
    "sale_entries",
    "settlements",
    "credit_parties",
    "credit_transactions",
    "cash_ledger",
    "bank_ledger",
    "paytm_settlements",
    "ccms_settlements",
    "oil_company_ledger",
    "expenses",
    "system_audit",
]


DATE_COLUMNS = ["updated_at", "created_at", "approved_at", "started_at", "ended_at"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_table_rows(table_name: str) -> Tuple[List[Dict[str, Any]], str | None]:
    try:
        rows = (
            get_supabase_client()
            .table(table_name)
            .select("*")
            .execute()
            .data
            or []
        )
        return rows, None
    except Exception as exc:
        # Some installs may not have every optional table. Backup should still work.
        print(f"backup read skipped {table_name}: {exc}")
        return [], str(exc)


def create_full_backup(created_by: str | None = None) -> Dict[str, Any]:
    tables: Dict[str, List[Dict[str, Any]]] = {}
    errors: Dict[str, str] = {}
    total_rows = 0

    for table in BACKUP_TABLES:
        rows, error = _safe_table_rows(table)
        tables[table] = rows
        total_rows += len(rows)
        if error:
            errors[table] = error

    return {
        "metadata": {
            "backup_version": BACKUP_VERSION,
            "generated_at": _now_iso(),
            "created_by": created_by,
            "table_order": BACKUP_TABLES,
            "total_rows": total_rows,
            "errors": errors,
        },
        "tables": tables,
    }


def backup_to_json_bytes(backup: Dict[str, Any]) -> bytes:
    return json.dumps(backup, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def parse_backup_file(raw: bytes | str) -> Tuple[Dict[str, Any] | None, str | None]:
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None, "Invalid backup format."
        if "metadata" not in data or "tables" not in data:
            return None, "Backup metadata/tables missing."
        return data, None
    except Exception as exc:
        return None, str(exc)


def _parse_dt(value: Any):
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _row_latest_dt(row: Dict[str, Any]):
    latest = None
    for col in DATE_COLUMNS:
        dt = _parse_dt(row.get(col))
        if dt and (latest is None or dt > latest):
            latest = dt
    return latest


def get_database_latest_timestamp() -> str | None:
    latest = None
    for table in BACKUP_TABLES:
        rows, _error = _safe_table_rows(table)
        for row in rows:
            dt = _row_latest_dt(row)
            if dt and (latest is None or dt > latest):
                latest = dt
    return latest.isoformat() if latest else None


def restore_safety_check(backup: Dict[str, Any]) -> Tuple[bool, str]:
    backup_time = _parse_dt((backup.get("metadata") or {}).get("generated_at"))
    current_latest = _parse_dt(get_database_latest_timestamp())

    if backup_time and current_latest and current_latest > backup_time:
        return False, (
            "Restore blocked: current database has entries newer than this backup. "
            "Create a fresh backup first or use a newer backup file."
        )

    return True, "Restore allowed."


def _clean_row(row: Dict[str, Any]) -> Dict[str, Any]:
    # Remove nested relationship payloads if any backup was made from select with joins.
    clean = {}
    for k, v in (row or {}).items():
        if isinstance(v, (dict, list)) and k.endswith("s"):
            # Keep JSON columns that are known business data.
            if k in ["nozzle_readings", "stock_effect", "vehicles"]:
                clean[k] = v
            continue
        clean[k] = v
    return clean


def restore_backup_upsert(backup: Dict[str, Any], restored_by: str | None = None) -> Tuple[Dict[str, Any], str | None]:
    """
    Safe restore: upsert rows present in backup; does not delete newer/extra rows.

    Destructive full restore should be done from Supabase dashboard/SQL backup, not
    from a customer-facing app button.
    """
    ok, message = restore_safety_check(backup)
    if not ok:
        return {"restored": 0, "tables": {}, "restored_by": restored_by}, message

    tables = backup.get("tables") or {}
    summary = {"restored": 0, "tables": {}, "restored_by": restored_by, "restored_at": _now_iso()}

    for table in (backup.get("metadata") or {}).get("table_order") or BACKUP_TABLES:
        rows = tables.get(table) or []
        if not rows:
            summary["tables"][table] = {"rows": 0, "status": "empty/skipped"}
            continue

        cleaned = [_clean_row(r) for r in rows if isinstance(r, dict)]
        try:
            get_supabase_client().table(table).upsert(cleaned).execute()
            summary["tables"][table] = {"rows": len(cleaned), "status": "restored"}
            summary["restored"] += len(cleaned)
        except Exception as exc:
            print(f"restore skipped {table}: {exc}")
            summary["tables"][table] = {"rows": len(cleaned), "status": "failed", "error": str(exc)}

    return summary, None
