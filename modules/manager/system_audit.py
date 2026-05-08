from datetime import date
import streamlit as st
from utils.permissions import require_role
from database.system_audit_db import run_full_audit

try:
    from utils.export_utils import render_export_buttons, print_view
except Exception:
    render_export_buttons = None
    print_view = None

@require_role(["owner", "manager"])
def system_audit_page():
    st.title("System Audit")
    st.caption("Database, imports, settlement, money, credit, stock, expense and approval checks.")
    selected_date = str(st.date_input("Audit Date", value=date.today(), key="system_audit_date"))
    if st.button("Run Full Audit", type="primary", use_container_width=True):
        st.session_state["audit_ran"] = True
    if not st.session_state.get("audit_ran"):
        st.info("Run Full Audit button दबाएं.")
        return

    summary, rows = run_full_audit(selected_date)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Checks", summary["TOTAL"])
    c2.metric("PASS", summary["PASS"])
    c3.metric("WARNING", summary["WARNING"])
    c4.metric("FAIL", summary["FAIL"])

    if summary["FAIL"] > 0:
        st.error("Critical issues found. FAIL rows pehle fix karo.")
    elif summary["WARNING"] > 0:
        st.warning("Warnings found. Business review required.")
    else:
        st.success("No critical issue detected.")

    tab1,tab2,tab3,tab4 = st.tabs(["All","FAIL","WARNING","PASS"])
    with tab1: show_rows(rows, "All Audit Results", "audit_all")
    with tab2: show_rows([r for r in rows if r.get("Status")=="FAIL"], "FAIL Results", "audit_fail")
    with tab3: show_rows([r for r in rows if r.get("Status")=="WARNING"], "WARNING Results", "audit_warning")
    with tab4: show_rows([r for r in rows if r.get("Status")=="PASS"], "PASS Results", "audit_pass")

def show_rows(rows, title, key):
    st.subheader(title)
    if not rows:
        st.info("No rows.")
        return
    if render_export_buttons:
        render_export_buttons(rows, key, title, key)
    st.dataframe(rows, use_container_width=True, hide_index=True)
    if print_view:
        with st.expander("Print View"):
            print_view(rows, title)
