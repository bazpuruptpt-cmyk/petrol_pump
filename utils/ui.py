import streamlit as st



def apply_global_ui():
    st.markdown(
        """
        <style>
        :root {
            --primary: #0f766e;
            --primary-dark: #115e59;
            --ink: #0f172a;
            --muted: #64748b;
            --line: #e2e8f0;
            --soft: #f8fafc;
        }

        .block-container {
            padding-top: 0.8rem;
            padding-bottom: 1.2rem;
            max-width: 1360px;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
            border-right: 1px solid rgba(255,255,255,0.08);
        }

        section[data-testid="stSidebar"] * {
            color: #f8fafc;
        }

        .sidebar-brand {
            display: flex;
            gap: 10px;
            align-items: center;
            padding: 8px 4px 12px 4px;
        }

        .brand-icon {
            width: 38px;
            height: 38px;
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(20, 184, 166, 0.18);
            border: 1px solid rgba(94, 234, 212, 0.3);
            font-size: 20px;
        }

        .brand-title {
            font-size: 1.05rem;
            font-weight: 800;
            line-height: 1.1;
        }

        .brand-subtitle {
            color: #cbd5e1;
            font-size: 0.75rem;
            margin-top: 2px;
        }

        .sidebar-user {
            border: 1px solid rgba(148,163,184,0.25);
            border-radius: 16px;
            padding: 10px 12px;
            background: rgba(15, 23, 42, 0.55);
            margin: 4px 0 12px 0;
        }

        .sidebar-user-name {
            font-weight: 800;
            font-size: 0.95rem;
        }

        .sidebar-user-role {
            color: #cbd5e1;
            font-size: 0.74rem;
            margin-top: 2px;
            letter-spacing: 0.04em;
        }

        .nav-label {
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin: 8px 0 5px 0;
        }

        section[data-testid="stSidebar"] .stButton > button {
            background: rgba(255,255,255,0.06);
            color: #f8fafc;
            border: 1px solid rgba(148,163,184,0.18);
            border-radius: 12px;
            font-weight: 700;
            justify-content: flex-start;
            min-height: 37px;
        }

        section[data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(20,184,166,0.22);
            border-color: rgba(94,234,212,0.45);
            color: #ffffff;
        }

        section[data-testid="stSidebar"] details {
            border: 1px solid rgba(148,163,184,0.14);
            border-radius: 14px;
            padding: 2px 6px;
            background: rgba(255,255,255,0.03);
            margin-bottom: 7px;
        }

        section[data-testid="stSidebar"] summary {
            font-weight: 800;
            color: #e2e8f0;
        }

        .app-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            border: 1px solid #e2e8f0;
            border-radius: 20px;
            padding: 14px 18px;
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            box-shadow: 0 8px 22px rgba(15,23,42,0.06);
            margin-bottom: 14px;
        }

        .app-page-title {
            color: #0f172a;
            font-size: 1.25rem;
            font-weight: 900;
            line-height: 1.1;
        }

        .app-page-caption {
            color: #64748b;
            font-size: 0.86rem;
            margin-top: 4px;
        }

        .app-user-chip {
            color: #115e59;
            font-weight: 800;
            border: 1px solid #99f6e4;
            background: #f0fdfa;
            border-radius: 999px;
            padding: 8px 12px;
            white-space: nowrap;
            font-size: 0.82rem;
        }

        h1 {
            font-size: 1.45rem !important;
            margin-bottom: 0.35rem !important;
        }

        h2, h3 {
            margin-top: 0.65rem !important;
            margin-bottom: 0.4rem !important;
        }

        div[data-testid="stMetric"] {
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 11px 13px;
            background: #ffffff;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.055);
        }

        div[data-testid="stMetricLabel"] {
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 700;
        }

        div[data-testid="stMetricValue"] {
            color: #0f172a;
            font-size: 1.12rem;
            font-weight: 900;
        }

        div[data-testid="stAlert"] {
            border-radius: 15px;
        }

        .stButton > button {
            border-radius: 13px;
            font-weight: 800;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid #e2e8f0;
        }

        .status-badge {
            display: inline-block;
            padding: 3px 9px;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 800;
            border: 1px solid #e5e7eb;
        }

        .status-approved {
            color: #027a48;
            background: #ecfdf3;
            border-color: #abefc6;
        }

        .status-pending {
            color: #b54708;
            background: #fffaeb;
            border-color: #fedf89;
        }

        .status-hold {
            color: #175cd3;
            background: #eff8ff;
            border-color: #b2ddff;
        }

        .status-rejected {
            color: #b42318;
            background: #fef3f2;
            border-color: #fecdca;
        }

        .status-reopened {
            color: #5925dc;
            background: #f4f3ff;
            border-color: #d9d6fe;
        }

        .mini-help {
            color: #64748b;
            font-size: 0.82rem;
            margin-top: -6px;
        }

        .section-card {
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 14px 16px;
            background: #ffffff;
            margin-bottom: 12px;
            box-shadow: 0 4px 14px rgba(15,23,42,0.04);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def status_badge(status):
    status = (status or "pending").lower()
    css = {
        "approved": "status-approved",
        "pending": "status-pending",
        "hold": "status-hold",
        "rejected": "status-rejected",
        "reopened": "status-reopened",
    }.get(status, "status-pending")

    st.markdown(
        f"<span class='status-badge {css}'>{status.upper()}</span>",
        unsafe_allow_html=True,
    )


def page_title(title, caption=None):
    st.title(title)
    if caption:
        st.caption(caption)


def empty_state(message="No data found."):
    st.info(message)


def safe_dataframe(rows, empty_message="No data found."):
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        empty_state(empty_message)


def confirm_button(label, key, type="secondary"):
    return st.button(label, key=key, type=type, use_container_width=True)
