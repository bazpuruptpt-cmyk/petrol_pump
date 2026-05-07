from datetime import date
import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.settlement_db import (
    get_pending_settlements,
    get_settlements_by_status,
    get_settlements_by_date,
    get_sale_entries_for_settlement,
    get_credit_rows_for_settlement,
    approve_settlement,
    hold_settlement,
    reopen_settlement,
    get_manager_payment_summary,
)


def _css():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.3rem; max-width: 1220px;}
        div[data-testid="stMetric"] {
            border: 1px solid #e8edf3;
            padding: 9px 11px;
            border-radius: 13px;
            box-shadow: 0 1px 4px rgba(16,24,40,.04);
        }
        div[data-testid="stMetricValue"] {font-size: 1.20rem;}
        .settle-card {
            border: 1px solid #e8edf3;
            border-radius: 14px;
            padding: 12px 14px;
            margin: 10px 0;
            background: #fff;
        }
        .small-muted {font-size:.82rem;color:#667085;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@require_role(["owner", "manager"])
def settlement_page():
    _css()

    st.title("Manager Settlement")
    st.caption("Pending salesman payment breakup approve/hold/reopen.")

    show_today_manager_summary()

    tab1, tab2, tab3 = st.tabs(["Pending Approval", "Hold / Reopened", "History"])

    with tab1:
        show_pending_settlements()

    with tab2:
        show_hold_reopened()

    with tab3:
        show_settlement_history()


def show_today_manager_summary():
    summary = get_manager_payment_summary(str(date.today()))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today Total Sale", format_currency(summary["total_sale"]))
    c2.metric("Cash", format_currency(summary["cash"]))
    c3.metric("Paytm", format_currency(summary["paytm"]))
    c4.metric("CCMS", format_currency(summary["ccms"]))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Credit", format_currency(summary["credit"]))
    c6.metric("Pending", summary["pending_count"])
    c7.metric("Approved", summary["approved_count"])
    c8.metric("Hold", summary["hold_count"])


def show_pending_settlements():
    rows = get_pending_settlements()

    st.subheader("Pending Settlements")

    if not rows:
        st.info("No pending settlements.")
        return

    for row in rows:
        settlement_card(row, mode="pending")


def show_hold_reopened():
    hold_rows = get_settlements_by_status("hold")
    reopened_rows = get_settlements_by_status("reopened")
    rows = hold_rows + reopened_rows

    st.subheader("Hold / Reopened Settlements")

    if not rows:
        st.info("No hold/reopened settlements.")
        return

    for row in rows:
        settlement_card(row, mode="hold_reopened")


def show_settlement_history():
    selected_date = st.date_input("Date", value=date.today())
    rows = get_settlements_by_date(str(selected_date))

    if not rows:
        st.info("No settlements found for selected date.")
        return

    for row in rows:
        settlement_card(row, mode="history")


def settlement_card(row: dict, mode: str):
    user = get_current_user()

    with st.container(border=True):
        top1, top2, top3, top4 = st.columns(4)
        top1.metric("Settlement ID", row.get("id"))
        top2.metric("Salesman", row.get("salesman_name"))
        top3.metric("Total Sale", format_currency(row.get("total_sale")))
        top4.metric("Difference", format_currency(row.get("match_difference")))

        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("Cash", format_currency(row.get("cash_amount")))
        b2.metric("Paytm", format_currency(row.get("paytm_amount")))
        b3.metric("CCMS", format_currency(row.get("ccms_amount")))
        b4.metric("Credit", format_currency(row.get("credit_amount")))
        b5.metric("Status", row.get("status"))

        if row.get("is_matched"):
            st.success("MATCHED")
        else:
            st.error("NOT MATCHED")

        st.markdown(
            f"<div class='small-muted'>Shift: {row.get('shift_id')} · Date: {row.get('date')} · Created: {row.get('created_at')}</div>",
            unsafe_allow_html=True,
        )

        col_action, col_note = st.columns([1, 2])

        with col_note:
            note = st.text_input(
                "Manager note",
                value=row.get("manager_note") or "",
                key=f"note_{row.get('id')}_{mode}",
            )

        with col_action:
            if mode in ["pending", "hold_reopened"]:
                if st.button("Approve", key=f"approve_{row.get('id')}", use_container_width=True):
                    approved, error = approve_settlement(row.get("id"), user["id"])
                    if approved:
                        st.success("Settlement approved.")
                        st.rerun()
                    else:
                        st.error(error or "Approval failed.")

                if st.button("Hold", key=f"hold_{row.get('id')}", use_container_width=True):
                    held, error = hold_settlement(row.get("id"), user["id"], note)
                    if held:
                        st.warning("Settlement put on hold.")
                        st.rerun()
                    else:
                        st.error(error or "Hold failed.")

                if st.button("Reopen", key=f"reopen_{row.get('id')}", use_container_width=True):
                    reopened, error = reopen_settlement(row.get("id"), user["id"], note)
                    if reopened:
                        st.info("Settlement reopened.")
                        st.rerun()
                    else:
                        st.error(error or "Reopen failed.")

        with st.expander("Sale Entries"):
            entries = get_sale_entries_for_settlement(row)
            if entries:
                st.dataframe(
                    [
                        {
                            "Entry Time": e.get("entry_time"),
                            "Nozzle": (e.get("nozzles") or {}).get("nozzle_name"),
                            "Fuel": e.get("fuel_type"),
                            "Liters": e.get("liters"),
                            "Rate": format_currency(e.get("rate")),
                            "Amount": format_currency(e.get("amount")),
                            "Status": e.get("status"),
                        }
                        for e in entries
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No sale entries found.")

        with st.expander("Credit Rows"):
            credits = get_credit_rows_for_settlement(row.get("id"))
            if credits:
                st.dataframe(
                    [
                        {
                            "Creditor": (c.get("credit_parties") or {}).get("name"),
                            "Amount": format_currency(c.get("amount")),
                            "Status": c.get("status"),
                            "Created At": c.get("created_at"),
                        }
                        for c in credits
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No credit entries.")
