from datetime import date
import streamlit as st
from utils.permissions import require_role, get_current_user
from utils.formatters import format_currency
from database.stock_db import (
    FUEL_TYPES, get_stock_summary, get_all_tanks, create_or_update_tank,
    create_fuel_inward, get_fuel_inward, create_daily_testing, get_daily_testing,
    save_stock_closing, get_stock_closing, create_oil_company_payment,
    get_oil_company_ledger, get_oil_company_summary
)

@require_role(["owner", "manager"])
def stock_management_page():
    st.title("Stock Management")
    st.caption("Tank setup, inward stock, testing, stock closing, oil company ledger.")
    entry_date = str(st.date_input("Date", value=date.today(), key="stock_date"))
    show_summary(entry_date)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Tank Setup", "Fuel Inward", "Daily Testing", "Stock Closing", "Oil Company Ledger"])
    with tab1: tank_tab()
    with tab2: inward_tab(entry_date)
    with tab3: testing_tab(entry_date)
    with tab4: closing_tab(entry_date)
    with tab5: ledger_tab()

def show_summary(entry_date):
    s = get_stock_summary(entry_date)
    p, d = s["petrol"], s["diesel"]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Petrol Current", f"{p['current_stock']:.2f} L")
    c2.metric("Petrol Expected", f"{p['expected_closing_stock']:.2f} L")
    c3.metric("Diesel Current", f"{d['current_stock']:.2f} L")
    c4.metric("Diesel Expected", f"{d['expected_closing_stock']:.2f} L")
    x1,x2 = st.columns(2)
    x1.metric("Petrol Difference", f"{p['stock_difference']:.2f} L")
    x2.metric("Diesel Difference", f"{d['stock_difference']:.2f} L")

def tank_tab():
    user = get_current_user()
    with st.form("tank_form"):
        ft = st.selectbox("Fuel Type", FUEL_TYPES)
        name = st.text_input("Tank Name")
        cap = st.number_input("Capacity Liters", min_value=0.0, step=100.0, format="%.2f")
        opening = st.number_input("Opening Stock", min_value=0.0, step=100.0, format="%.2f")
        current = st.number_input("Current Stock", min_value=0.0, step=100.0, format="%.2f")
        ok = st.form_submit_button("Save Tank")
    if ok:
        row, err = create_or_update_tank(ft, name, cap, opening, current, user["id"])
        if row: st.success("Tank saved."); st.rerun()
        else: st.error(err or "Tank save failed.")
    rows = get_all_tanks()
    st.dataframe(rows, use_container_width=True, hide_index=True) if rows else st.info("No tanks found.")

def inward_tab(entry_date):
    user = get_current_user()
    with st.form("inward_form"):
        company = st.text_input("Oil Company")
        invoice = st.text_input("Invoice No.")
        tanker = st.text_input("Tanker No.")
        ft = st.selectbox("Fuel Type", FUEL_TYPES, key="inward_ft")
        qty = st.number_input("Quantity Liters", min_value=0.0, step=100.0, format="%.2f")
        rate = st.number_input("Rate", min_value=0.0, step=1.0, format="%.2f")
        st.metric("Total Amount", format_currency(qty * rate))
        ok = st.form_submit_button("Save Inward")
    if ok:
        row, err = create_fuel_inward({"date": entry_date, "oil_company": company, "invoice_no": invoice, "tanker_no": tanker, "fuel_type": ft, "quantity_liters": qty, "rate": rate, "created_by": user["id"]})
        if row: st.success("Fuel inward saved and stock increased."); st.rerun()
        else: st.error(err or "Inward failed.")
    show_table(get_fuel_inward(entry_date), "Fuel Inward History")

def testing_tab(entry_date):
    user = get_current_user()
    with st.form("testing_form"):
        ft = st.selectbox("Fuel Type", FUEL_TYPES, key="test_ft")
        density = st.number_input("Density", min_value=0.0, step=0.01, format="%.2f")
        temp = st.number_input("Temperature", min_value=0.0, step=0.1, format="%.1f")
        liters = st.number_input("Testing Liters", min_value=0.0, step=0.01, format="%.2f")
        result = st.selectbox("Result", ["pass", "fail", "hold"])
        remark = st.text_input("Remark")
        ok = st.form_submit_button("Save Testing")
    if ok:
        row, err = create_daily_testing({"date": entry_date, "fuel_type": ft, "density": density, "temperature": temp, "testing_liters": liters, "result": result, "remark": remark, "tested_by": user["id"]})
        if row: st.success("Testing saved and stock adjusted."); st.rerun()
        else: st.error(err or "Testing failed.")
    show_table(get_daily_testing(entry_date), "Testing History")

def closing_tab(entry_date):
    user = get_current_user()
    s = get_stock_summary(entry_date)
    ft = st.selectbox("Fuel Type", FUEL_TYPES, key="closing_ft")
    fs = s[ft]
    c1,c2,c3 = st.columns(3)
    c1.metric("Expected Closing", f"{fs['expected_closing_stock']:.2f} L")
    c2.metric("Current Stock", f"{fs['current_stock']:.2f} L")
    c3.metric("Difference", f"{fs['stock_difference']:.2f} L")
    with st.form("closing_form"):
        physical = st.number_input("Physical Closing Stock", min_value=0.0, step=100.0, format="%.2f")
        remark = st.text_input("Remark")
        ok = st.form_submit_button("Save Stock Closing")
    if ok:
        row, err = save_stock_closing({"date": entry_date, "fuel_type": ft, "physical_stock": physical, "remark": remark, "created_by": user["id"]})
        if row: st.success("Stock closing saved."); st.rerun()
        else: st.error(err or "Closing failed.")
    show_table(get_stock_closing(entry_date), "Stock Closing History")

def ledger_tab():
    user = get_current_user()
    with st.form("oil_payment_form"):
        company = st.text_input("Oil Company")
        amount = st.number_input("Payment Amount", min_value=0.0, step=1000.0, format="%.2f")
        ref = st.text_input("Reference No.")
        ok = st.form_submit_button("Save Payment")
    if ok:
        row, err = create_oil_company_payment(company, amount, ref, user["id"])
        if row: st.success("Oil company payment saved."); st.rerun()
        else: st.error(err or "Payment failed.")
    summary = get_oil_company_summary()
    if summary:
        st.subheader("Company-wise Outstanding")
        st.dataframe(summary, use_container_width=True, hide_index=True)
    show_table(get_oil_company_ledger(), "Oil Company Ledger")

def show_table(rows, title):
    st.divider(); st.subheader(title)
    if rows: st.dataframe(rows, use_container_width=True, hide_index=True)
    else: st.info("No entries found.")
