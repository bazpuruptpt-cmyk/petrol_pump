import base64
import hashlib
import hmac
import json
import os
import time

import streamlit as st
import streamlit.components.v1 as components

from database.profiles_db import get_profile_by_user_id
from database.duties_db import is_duty_active


SESSION_PARAM = "pump_session"
LOGOUT_PARAM = "pump_logout"
LOCAL_STORAGE_KEY = "pump_control_session_v2"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


def _secret_key() -> bytes:
    secret = os.getenv("APP_SESSION_SECRET") or os.getenv("SUPABASE_ANON_KEY") or "pump-local-session-key"
    return secret.encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def _sign(payload_b64: str) -> str:
    return hmac.new(_secret_key(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session_token(user: dict) -> str:
    payload = {
        "id": user.get("id"),
        "name": user.get("name"),
        "role": user.get("role"),
        "phone": user.get("phone"),
        "email": user.get("email"),
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }

    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _sign(payload_b64)
    return f"{payload_b64}.{sig}"


def validate_session_token(token: str):
    if not token or "." not in str(token):
        return None

    try:
        payload_b64, sig = str(token).split(".", 1)
        expected = _sign(payload_b64)

        if not hmac.compare_digest(sig, expected):
            return None

        payload = json.loads(_unb64(payload_b64).decode("utf-8"))

        if int(payload.get("exp", 0)) < int(time.time()):
            return None

        return payload

    except Exception:
        return None


def _get_query_param(name: str):
    try:
        value = st.query_params.get(name)
        if isinstance(value, list):
            return value[0] if value else None
        return value
    except Exception:
        try:
            params = st.experimental_get_query_params()
            value = params.get(name)
            return value[0] if isinstance(value, list) and value else value
        except Exception:
            return None


def _set_query_param(name: str, value: str):
    try:
        st.query_params[name] = value
    except Exception:
        try:
            params = st.experimental_get_query_params()
            params[name] = value
            st.experimental_set_query_params(**params)
        except Exception:
            pass


def _clear_query_param(name: str):
    try:
        if name in st.query_params:
            del st.query_params[name]
    except Exception:
        try:
            params = st.experimental_get_query_params()
            params.pop(name, None)
            st.experimental_set_query_params(**params)
        except Exception:
            pass


def _has_logout_flag():
    return str(_get_query_param(LOGOUT_PARAM) or "") == "1"


def render_session_bridge(token=None, clear=False):
    """
    Browser localStorage bridge:
    - token available: save token to localStorage
    - no URL token but localStorage token exists: put it back in URL and reload
    - clear=True: remove token from localStorage
    """
    token_js = json.dumps(token or "")
    clear_js = "true" if clear else "false"
    session_param = json.dumps(SESSION_PARAM)
    logout_param = json.dumps(LOGOUT_PARAM)
    storage_key = json.dumps(LOCAL_STORAGE_KEY)

    components.html(
        f"""
        <script>
        (function() {{
            const storageKey = {storage_key};
            const sessionParam = {session_param};
            const logoutParam = {logout_param};
            const token = {token_js};
            const clear = {clear_js};

            const url = new URL(window.parent.location.href);
            const params = url.searchParams;

            if (clear || params.get(logoutParam) === "1") {{
                localStorage.removeItem(storageKey);
                if (params.has(sessionParam)) params.delete(sessionParam);
                if (params.has(logoutParam)) params.delete(logoutParam);
                const newUrl = url.pathname + (params.toString() ? "?" + params.toString() : "");
                window.parent.history.replaceState(null, "", newUrl);
                return;
            }}

            if (token) {{
                localStorage.setItem(storageKey, token);
                if (params.get(sessionParam) !== token) {{
                    params.set(sessionParam, token);
                    const newUrl = url.pathname + "?" + params.toString();
                    window.parent.history.replaceState(null, "", newUrl);
                }}
                return;
            }}

            const saved = localStorage.getItem(storageKey);
            if (saved && !params.get(sessionParam)) {{
                params.set(sessionParam, saved);
                const newUrl = url.pathname + "?" + params.toString();
                window.parent.location.replace(newUrl);
            }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def save_persistent_login(user: dict):
    token = make_session_token(user)
    st.session_state["current_user"] = user
    st.session_state["_pump_session_token"] = token
    _clear_query_param(LOGOUT_PARAM)
    _set_query_param(SESSION_PARAM, token)


def clear_persistent_login():
    st.session_state.pop("current_user", None)
    st.session_state.pop("_pump_session_token", None)
    _clear_query_param(SESSION_PARAM)
    _set_query_param(LOGOUT_PARAM, "1")


def restore_persistent_login():
    """
    Refresh/reload ke baad st.session_state clear ho jata hai.
    First URL signed token se restore karega.
    Agar URL token missing hai to localStorage bridge URL me token wapas set karega.
    """
    if _has_logout_flag():
        render_session_bridge(clear=True)
        return None

    if st.session_state.get("current_user"):
        return st.session_state.get("current_user")

    token = _get_query_param(SESSION_PARAM)

    if not token:
        render_session_bridge()
        return None

    payload = validate_session_token(token)

    if not payload:
        clear_persistent_login()
        render_session_bridge(clear=True)
        return None

    profile = get_profile_by_user_id(payload.get("id"))

    if not profile:
        clear_persistent_login()
        render_session_bridge(clear=True)
        return None

    if profile.get("role") == "salesman":
        if not is_duty_active(profile.get("id")):
            clear_persistent_login()
            render_session_bridge(clear=True)
            return None

    user = {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "role": profile.get("role"),
        "phone": profile.get("phone"),
        "email": payload.get("email"),
    }

    st.session_state["current_user"] = user
    st.session_state["_pump_session_token"] = token
    render_session_bridge(token=token)
    return user


def keep_session_alive():
    user = st.session_state.get("current_user")
    token = st.session_state.get("_pump_session_token") or _get_query_param(SESSION_PARAM)

    if user and not token:
        token = make_session_token(user)
        st.session_state["_pump_session_token"] = token
        _set_query_param(SESSION_PARAM, token)

    if token:
        render_session_bridge(token=token)
