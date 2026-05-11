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
            color: #027a48;
            padding: 8px 10px;
            border-radius: 10px;
            font-size: 0.84rem;
            font-weight: 700;
        }
        .warn-box {
            border: 1px solid #fedf89;
            background: #fffaeb;
            color: #93370d;
            padding: 8px 10px;
            border-radius: 10px;
            font-size: 0.84rem;
            font-weight: 700;
        }
        .bad-box {
            border: 1px solid #ffccc7;
            background: #fff1f0;
            color: #b42318;
            padding: 8px 10px;
            border-radius: 10px;
            font-size: 0.84rem;
            font-weight: 700;
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


def _status(latest):
    if not latest:
        return "draft"
    return latest.get("status") or "pending"


def _status_label(status):
    labels = {
        "draft": "DRAFT",
        "pending": "PENDING APPROVAL",
        "hold": "ON HOLD",
        "reopened": "REOPENED",
        "rejected": "REJECTED - FRESH ENTRY",
        "approved": "APPROVED",
    }
    return labels.get(status, str(status).upper())


def _is_locked(status):
    # Pending/hold/approved me salesman edit/save nahi karega.
    # Rejected/reopened me fresh/resubmit allowed.
    return status in ["pending", "hold", "approved"]


@require_role(["salesman"])
def sale_entry_page():
    _css()

    user = get_current_user()
    duty, nozzles = get_assigned_nozzles_for_salesman(user["id"])

    st.title("Sale Entry")

    if not duty:
        st.error("No active duty found.")
        st.stop()

    shift_id = duty["id"]
    latest = get_latest_payment_breakup(shift_id, user["id"])
    status = _status(latest)
    locked = _is_locked(status)

    if not nozzles and not locked:
        st.warning("No assigned nozzles found.")
        return

    render_header(user["id"], shift_id, latest)

    if status == "pending":
        st.info("Breakup approval ke liye manager ke pass pending hai. Difference tabhi show hoga jab sale total aur breakup mismatch hoga.")
    elif status == "approved":
        st.success("This shift is approved. Editing locked.")
    elif status == "hold":
        st.warning("Manager ne entry hold par rakhi hai. Manager action ke baad hi edit possible hoga.")
    elif status == "rejected":
        st.error("Manager ne reject kiya hai. Fresh sale entry aur breakup submit karo.")
    elif status == "reopened":
        st.warning("Manager ne reopen kiya hai. Correction karke breakup resubmit karo.")

    left, right = st.columns([1.05, 1], gap="medium")

    with left:
        render_nozzle_sale_card(user["id"], nozzles, locked)

    with right:
        render_payment_breakup_card(user["id"], shift_id, latest, locked)

    render_bottom_summary(user["id"], shift_id)


def render_header(salesman_id: str, shift_id: int, latest: dict = None):
    summary = get_shift_sale_summary_for_salesman(salesman_id)
    status = _status(latest)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shift", shift_id)
    c2.metric("Sales Entry Total", format_currency(summary["total_sale"]))
    c3.metric("Liters", f"{summary['total_liters']:.2f} L")
    c4.metric("Approval", _status_label(status))


def render_nozzle_sale_card(salesman_id: str, nozzles: list, locked: bool):
    st.markdown("<div class='compact-card'>", unsafe_allow_html=True)
    st.markdown("<div class='mini-title'>1. Add Nozzle Sale</div>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>Nozzle select karo → liters enter karo → amount auto calculate hoga.</div>", unsafe_allow_html=True)

    if not nozzles:
        st.info("No active nozzle available.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    nozzle_labels = {
        f"{n.get('nozzle_name')} · {n.get('fuel_type')}": n
        for n in nozzles
    }

    selected_label = st.selectbox(
        "Nozzle",
        list(nozzle_labels.keys()),
        key="crisp_nozzle_select",
        disabled=locked,
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
            disabled=locked,
        )

    amount = calculate_sale_amount(liters, rate)

    with c3:
        st.metric("Amount", format_currency(amount))

    if locked:
        st.button("Entry locked", disabled=True, use_container_width=True, key="add_nozzle_locked_btn")
    else:
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


def render_payment_breakup_card(salesman_id: str, shift_id: int, latest: dict = None, locked: bool = False):
    try:
        summary = get_shift_sale_summary_for_salesman(salesman_id, shift_id)
    except TypeError:
        summary = get_shift_sale_summary_for_salesman(salesman_id)
    total_sale = float(summary["total_sale"] or 0)
    status = _status(latest)

    st.markdown("<div class='compact-card'>", unsafe_allow_html=True)
    st.markdown("<div class='mini-title'>2. Payment Breakup</div>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>Meter match: Cash + Paytm + CCMS + Fuel Credit = Total Sale. Cash given to creditor alag cash handover se minus hoga.</div>", unsafe_allow_html=True)

    if latest and status in ["pending", "hold", "approved"]:
        render_submitted_breakup(latest, total_sale, status)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    p1, p2, p3 = st.columns(3)
    with p1:
        cash = st.number_input("Cash", min_value=0.0, step=1.0, format="%.2f", key="crisp_cash")
    with p2:
        paytm = st.number_input("Paytm", min_value=0.0, step=1.0, format="%.2f", key="crisp_paytm")
    with p3:
        ccms = st.number_input("CCMS", min_value=0.0, step=1.0, format="%.2f", key="crisp_ccms")

    credit_allocations, credit_errors, entered_credit_total, entered_cash_given_total = render_credit_inputs()
    credit_total = round(sum(float(x.get("amount") or 0) for x in credit_allocations), 2)
    cash_given_total = round(sum(float(x.get("cash_given") or 0) for x in credit_allocations), 2)

    match = calculate_payment_match(
        total_sale=total_sale,
        cash=cash,
        paytm=paytm,
        ccms=ccms,
        credit=credit_total,
    )

    payment_total = float(match["payment_total"] or 0)
    difference = float(match["difference"] or 0)

    if credit_errors:
        for msg in credit_errors:
            st.markdown(f"<div class='bad-box'>{msg}</div>", unsafe_allow_html=True)

    if entered_credit_total > credit_total or entered_cash_given_total > cash_given_total:
        st.caption(
            "Note: Fuel Credit/Cash Given tabhi count hoga jab creditor select hoga. "
            "Blank '-- Select --' creditor wali row ignore nahi hogi; save block rahega."
        )

    # Difference sirf tab show hoga jab sale figure aur breakup total mismatch ho.
    if total_sale <= 0:
        m1, m2 = st.columns(2)
        m1.metric("Sale", format_currency(total_sale))
        m2.metric("Payment", format_currency(payment_total))
        st.markdown("<div class='warn-box'>Sale entry ke baad breakup submit hoga.</div>", unsafe_allow_html=True)

    elif match["is_matched"]:
        m1, m2, m3 = st.columns(3)
        m1.metric("Sale", format_currency(total_sale))
        m2.metric("Payment", format_currency(payment_total))
        m3.metric("Approval", "Ready")
        st.markdown("<div class='ok-box'>MATCHED - Save karne ke baad Manager Approval me jayega.</div>", unsafe_allow_html=True)

    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Sale", format_currency(total_sale))
        m2.metric("Payment", format_currency(payment_total))
        m3.metric("Difference", format_currency(difference))
        st.markdown("<div class='bad-box'>NOT MATCHED - Difference correct karo, phir save karo.</div>", unsafe_allow_html=True)

    st.markdown("**Cash Handover**")
    h1, h2, h3 = st.columns(3)
    h1.metric("Cash Sale", format_currency(cash))
    h2.metric("Less Cash Given to Creditor", format_currency(cash_given_total))
    h3.metric("Cash To Manager", format_currency(round(cash - cash_given_total, 2)))

    save_disabled = total_sale <= 0 or not match["is_matched"] or cash_given_total > cash or bool(credit_errors)
    if cash_given_total > cash:
        st.markdown("<div class='bad-box'>Cash given to creditor cash sale se zyada nahi ho sakta.</div>", unsafe_allow_html=True)

    if st.button(
        "Send for Approval",
        type="primary",
        use_container_width=True,
        key="save_breakup_btn",
        disabled=save_disabled,
    ):
        try:
            settlement, error = save_payment_breakup(
                salesman_id=salesman_id,
                cash_amount=cash,
                paytm_amount=paytm,
                ccms_amount=ccms,
                credit_allocations=credit_allocations,
                shift_id=shift_id,
            )
        except TypeError:
            settlement, error = save_payment_breakup(
                salesman_id=salesman_id,
                cash_amount=cash,
                paytm_amount=paytm,
                ccms_amount=ccms,
                credit_allocations=credit_allocations,
            )

        if settlement:
            st.success("Sent to Manager Approval.")
            st.rerun()
        else:
            st.error(error or "Payment breakup save failed.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_submitted_breakup(latest: dict, total_sale: float, status: str):
    cash = float(latest.get("cash_amount") or 0)
    paytm = float(latest.get("paytm_amount") or 0)
    ccms = float(latest.get("ccms_amount") or 0)
    credit = float(latest.get("credit_amount") or 0)
    cash_given = float(latest.get("cash_given_to_creditor_amount") or 0)
    payment_total = round(cash + paytm + ccms + credit, 2)
    diff = round(float(latest.get("meter_total") or total_sale or 0) - payment_total, 2)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Cash", format_currency(cash))
    c2.metric("Paytm", format_currency(paytm))
    c3.metric("CCMS", format_currency(ccms))
    c4.metric("Fuel Credit", format_currency(credit))
    c5.metric("Cash Given", format_currency(cash_given))

    h1, h2, h3 = st.columns(3)
    h1.metric("Cash Sale", format_currency(cash))
    h2.metric("Less Cash Given", format_currency(cash_given))
    h3.metric("Cash To Manager", format_currency(round(cash - cash_given, 2)))

    m1, m2, m3 = st.columns(3)
    m1.metric("Sale", format_currency(total_sale))
    m2.metric("Payment", format_currency(payment_total))

    if abs(diff) > 0.01:
        m3.metric("Difference", format_currency(diff))
        st.markdown("<div class='bad-box'>Mismatch submitted. Manager reject/reopen karega.</div>", unsafe_allow_html=True)
    else:
        m3.metric("Approval", _status_label(status))
        if status == "pending":
            st.markdown("<div class='warn-box'>Pending Manager Approval</div>", unsafe_allow_html=True)
        elif status == "approved":
            st.markdown("<div class='ok-box'>Approved - Read Only</div>", unsafe_allow_html=True)
        elif status == "hold":
            st.markdown("<div class='warn-box'>On Hold - Manager action required</div>", unsafe_allow_html=True)

    st.button(
        "Manager action required" if status != "approved" else "Approved - Read Only",
        disabled=True,
        use_container_width=True,
        key=f"submitted_breakup_locked_{latest.get('id')}",
    )


def render_credit_inputs():
    parties = get_active_parties()
    credit_allocations = []
    credit_errors = []
    entered_credit_total = 0.0
    entered_cash_given_total = 0.0

    with st.expander("Credit / Creditor", expanded=True):
        if not parties:
            st.info("No active creditor. Owner/Manager must create creditor first.")
            return [], [], 0.0, 0.0

        party_options = {"-- Select Creditor --": None}
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
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 2])
            with c1:
                label = st.selectbox("Creditor", labels, key=f"crisp_credit_party_{i}")
                party = party_options[label]
            with c2:
                amount = st.number_input(
                    "Fuel Credit",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                    key=f"crisp_credit_amount_{i}",
                )
            with c3:
                cash_given = st.number_input(
                    "Cash Given",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                    key=f"crisp_cash_given_{i}",
                )
            with c4:
                vehicle = st.text_input("Vehicle", key=f"crisp_vehicle_{i}")
            with c5:
                comment = st.text_input("Comment", key=f"crisp_credit_comment_{i}")

            amount = float(amount or 0)
            cash_given = float(cash_given or 0)
            entered_credit_total += amount
            entered_cash_given_total += cash_given

            if amount > 0 or cash_given > 0:
                if not party:
                    credit_errors.append(
                        f"Creditor row {i + 1}: Fuel Credit/Cash Given enter kiya hai, lekin creditor select nahi hai."
                    )
                    continue

                credit_allocations.append({
                    "party_id": party["id"],
                    "amount": amount,
                    "cash_given": cash_given,
                    "vehicle_number": vehicle,
                    "comment": comment,
                })

        valid_credit_total = round(sum(float(x.get("amount") or 0) for x in credit_allocations), 2)
        valid_cash_given_total = round(sum(float(x.get("cash_given") or 0) for x in credit_allocations), 2)

        s1, s2, s3 = st.columns(3)
        s1.metric("Fuel Credit Counted", format_currency(valid_credit_total))
        s2.metric("Cash Given Counted", format_currency(valid_cash_given_total))
        s3.metric("Valid Creditor Rows", len(credit_allocations))

    return credit_allocations, credit_errors, round(entered_credit_total, 2), round(entered_cash_given_total, 2)

def render_bottom_summary(salesman_id: str, shift_id: int = None):
    with st.expander("Nozzle-wise Summary", expanded=True):
        try:
            rows = get_salesman_nozzle_sale_summary(salesman_id, shift_id)
        except TypeError:
            rows = get_salesman_nozzle_sale_summary(salesman_id)

        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No sale entry yet.")
