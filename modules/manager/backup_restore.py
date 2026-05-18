import os
from datetime import datetime

import streamlit as st

from database.backup_restore_db import (
    create_full_backup,
    backup_to_json_bytes,
    parse_backup_file,
    restore_safety_check,
    restore_backup_upsert,
    get_database_latest_timestamp,
)
from utils.permissions import require_role, get_current_user


@require_role(["owner"])
def backup_restore_page():
    st.title("Backup / Restore")
    st.caption("Single pump data backup. Restore is safety-locked by default.")

    user = get_current_user() or {}

    st.subheader("Create Backup")
    st.write("Backup JSON me pump ka operational data export hoga.")

    if st.button("Generate Backup", type="primary", use_container_width=True):
        backup = create_full_backup(created_by=user.get("id"))
        raw = backup_to_json_bytes(backup)
        st.success(f"Backup ready. Rows: {backup.get('metadata', {}).get('total_rows', 0)}")
        filename = f"pump_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        st.download_button(
            "Download Backup JSON",
            data=raw,
            file_name=filename,
            mime="application/json",
            use_container_width=True,
        )

    st.divider()
    st.subheader("Restore Backup")

    st.warning(
        "Restore owner-only hai. Current database me backup se newer entry hogi to restore block hoga."
    )

    latest = get_database_latest_timestamp()
    st.caption(f"Current DB latest timestamp: {latest or '-'}")

    restore_enabled = os.getenv("ENABLE_RESTORE", "false").lower() == "true"
    if not restore_enabled:
        st.info("Restore disabled hai. Enable karne ke liye Streamlit secrets me ENABLE_RESTORE=true set karo.")
        return

    uploaded = st.file_uploader("Upload backup JSON", type=["json"])
    if not uploaded:
        return

    backup, error = parse_backup_file(uploaded.read())
    if error:
        st.error(error)
        return

    meta = backup.get("metadata") or {}
    st.write("Backup generated at:", meta.get("generated_at"))
    st.write("Backup rows:", meta.get("total_rows"))

    ok, message = restore_safety_check(backup)
    if not ok:
        st.error(message)
        return
    st.success(message)

    confirm = st.checkbox("I understand restore will upsert backup rows.")
    if confirm and st.button("Restore Backup", type="primary", use_container_width=True):
        summary, restore_error = restore_backup_upsert(backup, restored_by=user.get("id"))
        if restore_error:
            st.error(restore_error)
        else:
            st.success(f"Restore completed. Rows restored: {summary.get('restored', 0)}")
            st.json(summary)
