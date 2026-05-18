import os

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None


def _read_setting(name: str, default=None):
    if st is not None:
        try:
            value = st.secrets.get(name)
            if value is not None and str(value).strip() != "":
                return str(value).strip()
        except Exception:
            pass

    value = os.getenv(name)
    if value is not None and str(value).strip() != "":
        return str(value).strip()

    return default


def env_bool(name: str, default: bool = False) -> bool:
    value = _read_setting(name, None)
    if value is None:
        return bool(default)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def whatsapp_enabled() -> bool:
    return env_bool("ENABLE_WHATSAPP", False)


def show_technical_errors() -> bool:
    return env_bool("SHOW_TECHNICAL_ERRORS", False)
