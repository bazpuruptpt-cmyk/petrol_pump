import streamlit as st

from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.sale_db import (
    get_assigned_nozzles_for_salesman,
    get_current_rate_for_nozzle,
    calculate_sale_amount,
    create_nozzle_sale_entry,
    get_shift_sale_summary_for_salesman,
    get_salesman_nozzle_sale_summary,
    calculate_payment_match,
    save_payment_breakup,
    get_latest_payment_breakup,
)
from database.credit_db import get_active_parties


def _css():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.1rem;
            padding-bottom: 1rem;
            max-width: 1180px;
        }

        h1 {
            font-size: 1.65rem !important;
            margin-bottom: 0.25rem !important;
        }

        h2, h3 {
            margin-top: 0.3rem !important;
            margin-bottom: 0.35rem !important;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e8edf3;
            padding: 8px 10px;
            border-radius: 12px;
            box-shadow: 0 1px 4px rgba(16, 24, 40, 0.04);
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.74rem;
            color: #667085;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.18rem;
        }

        .mini-title {
            font-size: 0.92rem;
            font-weight: 700;
            margin: 2px 0 6px 0;
        }

        .muted {
            color: #667085;
            font-size: 0.78rem;
            margin-top: -4px;
            margin-bottom: 4px;
        }

        .ok-box {
            border: 1px solid #b7ebc6;
            background: #f0fff4;
            padding: 8px 10px;
            border-radius: 10px;
            font-size: 0.84rem;
            font-weight: 600;
        }

        .bad-box {
            border: 1px solid #ffccc7;
            background: #fff1f0;
            padding: 8px 10px;
            border-radius: 10px;
            font-size: 0.84rem;
            font-weight: 600;
        }

        .compact-card {
            border: 1px solid #e8edf3;
            background: #ffffff;
            border-radius: 14px;
            padding: 10px 12px;
            margin-bottom: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@require_role(["salesman"])
def sale_entry_page():
    _css()

    user = get_current_user()
    duty, nozzles = get_assigned_nozzles_for_salesman(user["id"])

    st.title("Sale Entry")

    if not duty:
        st.error("No active duty found.")
        st.stop()

    if not nozzles:
        st.warning("No assigned nozzles found.")
        return

    render_header(user["id"], duty["id"])

    left, right = st.columns([1.05, 1], gap="medium")

    with left:
        render_nozzle_sale_card(user["id"], nozzles)

    with right:
        render_payment_breakup_card(user["id"])

    render_bottom_summary(user["id"])


def render_header(salesman_id: str, shift_id: int):
    summary = get_shift_sale_summary_for_salesman(salesman_id)
    latest = get_latest_payment_breakup(shift_id, salesman_id)

    diff_text = "Not saved"
    if latest:
        diff_text = format_currency(latest.get("difference"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shift", shift_id)
    c2.metric("Total Sale", format_currency(summary["total_sale"]))
    c3.metric("Liters", f"{summary['total_liters']:.2f} L")
    c4.metric("Difference", diff_text)


def render_nozzle_sale_card(salesman_id: str, nozzles: list):
    st.markdown("<div class='compact-card'>", unsafe_allow_html=True)
    st.markdown("<div class='mini-title'>1. Add Nozzle Sale</div>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>Nozzle select karo → liters enter karo → amount auto calculate hoga.</div>", unsafe_allow_html=True)

    nozzle_labels = {
        f"{n.get('nozzle_name')} · {n.get('fuel_type')}": n
        for n in nozzles
    }

    selected_label = st.selectbox(
        "Nozzle",
        list(nozzle_labels.keys()),
        key="crisp_nozzle_select",
    )
    selected_nozzle = nozzle_labels[selected_label]

    rate = get_current_rate_for_nozzle(selected_nozzle)

    if not rate:
        st.error(f"Rate missing for {selected_nozzle.get('fuel_type')}.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Rate", format_currency(rate))

    with c2:
        liters = st.number_input(
            "Liters",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="crisp_liters",
        )

    amount = calculate_sale_amount(liters, rate)

    with c3:
        st.metric("Amount", format_currency(amount))

    if st.button("Add Sale", type="primary", use_container_width=True, key="add_nozzle_sale_btn"):
        if liters <= 0:
            st.error("Liters greater than 0 required.")
        else:
            sale, error = create_nozzle_sale_entry({
                "shift_id": selected_nozzle["shift_id"],
                "nozzle_id": selected_nozzle["nozzle_id"],
                "salesman_id": salesman_id,
                "fuel_type": selected_nozzle["fuel_type"],
                "liters": liters,
                "rate": rate,
            })

            if sale:
                st.success(f"Sale added: {format_currency(sale.get('amount'))}")
                st.rerun()
            else:
                st.error(error or "Sale entry failed.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_payment_breakup_card(salesman_id: str):
    summary = get_shift_sale_summary_for_salesman(salesman_id)
    total_sale = float(summary["total_sale"] or 0)

    st.markdown("<div class='compact-card'>", unsafe_allow_html=True)
    st.markdown("<div class='mini-title'>2. Payment Breakup</div>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>Cash + Paytm + CCMS + Credit total sale ke barabar hona chahiye.</div>", unsafe_allow_html=True)

    p1, p2, p3 = st.columns(3)
    with p1:
        cash = st.number_input("Cash", min_value=0.0, step=1.0, format="%.2f", key="crisp_cash")
    with p2:
        paytm = st.number_input("Paytm", min_value=0.0, step=1.0, format="%.2f", key="crisp_paytm")
    with p3:
        ccms = st.number_input("CCMS", min_value=0.0, step=1.0, format="%.2f", key="crisp_ccms")

    credit_allocations = render_credit_inputs()

    credit_total = round(sum(float(x.get("amount") or 0) for x in credit_allocations), 2)

    match = calculate_payment_match(
        total_sale=total_sale,
        cash=cash,
        paytm=paytm,
        ccms=ccms,
        credit=credit_total,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Sale", format_currency(match["total_sale"]))
    m2.metric("Payment", format_currency(match["payment_total"]))
    m3.metric("Diff", format_currency(match["difference"]))

    if match["is_matched"]:
        st.markdown("<div class='ok-box'>MATCHED</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='bad-box'>NOT MATCHED</div>", unsafe_allow_html=True)

    if st.button("Save Breakup", type="primary", use_container_width=True, key="save_breakup_btn"):
        settlement, error = save_payment_breakup(
            salesman_id=salesman_id,
            cash_amount=cash,
            paytm_amount=paytm,
            ccms_amount=ccms,
            credit_allocations=credit_allocations,
        )

        if settlement:
            st.success("Saved. Pending manager approval.")
            st.rerun()
        else:
            st.error(error or "Payment breakup save failed.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_credit_inputs():
    parties = get_active_parties()
    credit_allocations = []

    with st.expander("Credit / Creditor", expanded=False):
        if not parties:
            st.info("No active creditor. Owner/Manager must create creditor first.")
            return []

        party_options = {"-- Select --": None}
        for p in parties:
            party_options[f"{p.get('name')} · Bal {p.get('current_balance')}"] = p

        labels = list(party_options.keys())

        rows = st.number_input(
            "Creditor entries",
            min_value=0,
            max_value=5,
            value=0,
            step=1,
            key="crisp_credit_rows",
        )

        for i in range(int(rows)):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                label = st.selectbox("Creditor", labels, key=f"crisp_credit_party_{i}")
                party = party_options[label]
            with c2:
                amount = st.number_input(
                    "Amount",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                    key=f"crisp_credit_amount_{i}",
                )
            with c3:
                vehicle = st.text_input("Vehicle", key=f"crisp_vehicle_{i}")

            if party and amount > 0:
                credit_allocations.append({
                    "party_id": party["id"],
                    "amount": amount,
                    "vehicle_number": vehicle,
                })

    return credit_allocations


def render_bottom_summary(salesman_id: str):
    with st.expander("Nozzle-wise Summary", expanded=True):
        rows = get_salesman_nozzle_sale_summary(salesman_id)

        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No sale entry yet.")
