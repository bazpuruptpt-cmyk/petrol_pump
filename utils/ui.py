import streamlit as st


def apply_global_ui():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.1rem;
            padding-bottom: 1rem;
            max-width: 1280px;
        }

        h1 {
            font-size: 1.65rem !important;
            margin-bottom: 0.25rem !important;
        }

        h2, h3 {
            margin-top: 0.5rem !important;
            margin-bottom: 0.35rem !important;
        }

        div[data-testid="stMetric"] {
            border: 1px solid #e8edf3;
            border-radius: 14px;
            padding: 9px 11px;
            background: #ffffff;
            box-shadow: 0 1px 4px rgba(16, 24, 40, 0.045);
        }

        div[data-testid="stMetricLabel"] {
            color: #667085;
            font-size: 0.78rem;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.18rem;
        }

        .status-badge {
            display: inline-block;
            padding: 3px 9px;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 700;
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
            color: #667085;
            font-size: 0.82rem;
            margin-top: -6px;
        }

        .section-card {
            border: 1px solid #e8edf3;
            border-radius: 16px;
            padding: 12px 14px;
            background: #ffffff;
            margin-bottom: 12px;
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
