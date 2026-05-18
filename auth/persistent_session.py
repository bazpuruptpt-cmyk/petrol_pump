import base64
import hashlib
import hmac
import json
import os
import time

import streamlit as st

from database.profiles_db import get_profile_by_user_id
from database.duties_db import is_duty_active


SESSION_PARAM = "pump_session"
# Old builds used pump_logout=1 in the URL. That flag can survive browser/tab
# navigation and force logout on every rerun. This fixed build removes it.
LOGOUT_PARAM = "pump_logout"
LOCAL_STORAGE_KEY = "pump_control_session_v2"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


def _secret_key() -> bytes:
    secret = os.getenv("APP_SESSION_SECRET") or os.getenv("SUPABASE_ANON_KEY")
    if not secret:
        # Development fallback only. Production must set APP_SESSION_SECRET.
        secret = "pump-local-session-key"
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


def _set_query_param_if_needed(name: str, value: str):
    try:
        if st.query_params.get(name) != value:
            st.query_params[name] = value
        return
    except Exception:
        pass

    try:
        params = st.experimental_get_query_params()
        old = params.get(name)
        old_value = old[0] if isinstance(old, list) and old else old
        if old_value != value:
            params[name] = value
            st.experimental_set_query_params(**params)
    except Exception:
        pass


def _clear_query_param(name: str):
    try:
        if name in st.query_params:
            del st.query_params[name]
        return
    except Exception:
        pass

    try:
        params = st.experimental_get_query_params()
        if name in params:
            params.pop(name, None)
            st.experimental_set_query_params(**params)
    except Exception:
        pass


def _remove_old_logout_flag():
    # Important: never use pump_logout=1 for restore decisions. It creates a
    # false logout loop when the browser changes tab/page and Streamlit reruns.
    _clear_query_param(LOGOUT_PARAM)


def render_session_bridge(token=None, clear=False):
    """
    No JavaScript bridge. Keeping it as a no-op so old imports do not break.
    Session persistence is handled by Streamlit session_state + signed URL token.
    """
    return None


def save_persistent_login(user: dict):
    token = make_session_token(user)
    st.session_state["current_user"] = user
    st.session_state["_pump_session_token"] = token
    _remove_old_logout_flag()
    _set_query_param_if_needed(SESSION_PARAM, token)
    return token


def clear_persistent_login():
    st.session_state.pop("current_user", None)
    st.session_state.pop("_pump_session_token", None)
    _clear_query_param(SESSION_PARAM)
    _remove_old_logout_flag()


def _build_user_from_profile(profile: dict, payload: dict):
    return {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "role": profile.get("role"),
        "phone": profile.get("phone"),
        "email": payload.get("email"),
    }


def restore_persistent_login():
    """
    Restore manager/owner/salesman login after Streamlit rerun, refresh, or tab
    switch. The old pump_logout flag is ignored and removed to stop false logout.
    """
    try:
        _remove_old_logout_flag()

        user = st.session_state.get("current_user")
        if user:
            keep_session_alive()
            return user

        token = st.session_state.get("_pump_session_token") or _get_query_param(SESSION_PARAM)
        if not token:
            return None

        payload = validate_session_token(token)
        if not payload:
            clear_persistent_login()
            return None

        profile = get_profile_by_user_id(payload.get("id"))
        if not profile:
            # Do not clear the URL token here. A temporary Supabase/network/RLS
            # read failure should not permanently log the manager out.
            return None

        if profile.get("role") == "salesman" and not is_duty_active(profile.get("id")):
            clear_persistent_login()
            return None

        user = _build_user_from_profile(profile, payload)
        st.session_state["current_user"] = user
        st.session_state["_pump_session_token"] = token
        _set_query_param_if_needed(SESSION_PARAM, token)
        return user

    except Exception:
        # Restore must never crash or force logout during page/tab changes.
        return st.session_state.get("current_user")


def keep_session_alive():
    """
    Ensure a valid token remains available across Streamlit reruns. This is
    called after login and on every authenticated page render.
    """
    try:
        _remove_old_logout_flag()
        user = st.session_state.get("current_user")
        if not user:
            return None

        token = st.session_state.get("_pump_session_token") or _get_query_param(SESSION_PARAM)
        if not validate_session_token(token):
            token = make_session_token(user)
            st.session_state["_pump_session_token"] = token

        _set_query_param_if_needed(SESSION_PARAM, token)
        return token

    except Exception:
        return None
