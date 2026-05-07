from datetime import date
import pandas as pd
import streamlit as st


def get_today():
    return date.today()


def running_balance(entries):
    balance = 0
    output = []
    for entry in entries:
        debit = float(entry.get("debit") or 0)
        credit = float(entry.get("credit") or 0)
        balance += credit - debit
        row = dict(entry)
        row["running_balance"] = balance
        output.append(row)
    return output


def to_table(data, columns=None):
    df = pd.DataFrame(data or [])
    if columns:
        existing = [c for c in columns if c in df.columns]
        df = df[existing]
    st.dataframe(df, use_container_width=True)
    return df


def export_csv(df, filename="report.csv"):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        data=csv,
        file_name=filename,
        mime="text/csv"
    )
