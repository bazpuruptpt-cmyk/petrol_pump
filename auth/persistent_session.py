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
LOCAL_STORAGE_KEY = "pump_control_session_v3"
COOKIE_NAME = "pump_control_session_v3"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


# ---------------- Secrets ----------------
def _read_secret(name: str):
    value = os.getenv(name)
    if value:
        return value
    try:
        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass
    return None


def _secret_key() -> bytes:
    # APP_SESSION_SECRET must remain same after deploy/restart.
    secret = _read_secret("APP_SESSION_SECRET") or _read_secret("SUPABASE_ANON_KEY")
    if not secret:
        # Development fallback only. Production must set APP_SESSION_SECRET.
        secret = "pump-local-session-key"
    return secret.encode("utf-8")


# ---------------- Token helpers ----------------
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
    return f"{payload_b64}.{_sign(payload_b64)}"


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
        if not payload.get("id") or not payload.get("role"):
            return None
        return payload
    except Exception:
        return None


# ---------------- Query param helpers ----------------
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
    if not value:
        return
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
    # Old builds used pump_logout=1. It created false logout loops on refresh.
    _clear_query_param(LOGOUT_PARAM)


# ---------------- Browser persistence bridge ----------------
def render_session_bridge(token=None, clear=False):
    """
    Browser refresh me st.session_state reset ho sakta hai. Is bridge ka kaam:
    - login ke baad signed token ko browser localStorage + cookie me save karna
    - refresh/base URL par token missing ho to browser se token URL me wapas dalna
    - logout par browser storage clear karna

    Note: Python cannot directly read browser localStorage, so JS URL me token restore
    karta hai, phir Streamlit next run me signed token validate karta hai.
    """
    try:
        token_js = json.dumps(token or "")
        clear_js = "true" if clear else "false"
        key_js = json.dumps(LOCAL_STORAGE_KEY)
        cookie_js = json.dumps(COOKIE_NAME)
        param_js = json.dumps(SESSION_PARAM)

        components.html(
            f"""
            <script>
            (function() {{
                const KEY = {key_js};
                const COOKIE = {cookie_js};
                const PARAM = {param_js};
                const TOKEN = {token_js};
                const CLEAR = {clear_js};

                function getParentWindow() {{ return window.parent || window; }}
                function getUrl() {{ return new URL(getParentWindow().location.href); }}

                function setCookie(value) {{
                    try {{
                        getParentWindow().document.cookie = COOKIE + '=' + encodeURIComponent(value) + '; path=/; max-age=' + (7*24*60*60) + '; SameSite=Lax';
                    }} catch (e) {{}}
                }}

                function getCookie() {{
                    try {{
                        const all = getParentWindow().document.cookie || '';
                        const parts = all.split(';').map(x => x.trim());
                        for (const p of parts) {{
                            if (p.startsWith(COOKIE + '=')) return decodeURIComponent(p.substring(COOKIE.length + 1));
                        }}
                    }} catch (e) {{}}
                    return '';
                }}

                function clearCookie() {{
                    try {{
                        getParentWindow().document.cookie = COOKIE + '=; path=/; max-age=0; SameSite=Lax';
                    }} catch (e) {{}}
                }}

                function setStore(value) {{
                    try {{ getParentWindow().localStorage.setItem(KEY, value); }} catch (e) {{}}
                    setCookie(value);
                }}

                function getStore() {{
                    try {{
                        const v = getParentWindow().localStorage.getItem(KEY);
                        if (v) return v;
                    }} catch (e) {{}}
                    return getCookie();
                }}

                function clearStore() {{
                    try {{ getParentWindow().localStorage.removeItem(KEY); }} catch (e) {{}}
                    clearCookie();
                }}

                if (CLEAR) {{
                    clearStore();
                    const url = getUrl();
                    if (url.searchParams.has(PARAM)) {{
                        url.searchParams.delete(PARAM);
                        getParentWindow().history.replaceState(null, '', url.toString());
                    }}
                    return;
                }}

                if (TOKEN) {{
                    setStore(TOKEN);
                    return;
                }}

                const stored = getStore();
                if (stored) {{
                    const url = getUrl();
                    if (!url.searchParams.get(PARAM)) {{
                        url.searchParams.set(PARAM, stored);
                        getParentWindow().location.replace(url.toString());
                    }}
                }}
            }})();
            </script>
            """,
            height=0,
            width=0,
        )
    except Exception:
        return None


# ---------------- Login/logout/restore ----------------
def save_persistent_login(user: dict):
    token = make_session_token(user)
    st.session_state["current_user"] = user
    st.session_state["_pump_session_token"] = token
    _remove_old_logout_flag()
    _set_query_param_if_needed(SESSION_PARAM, token)
    render_session_bridge(token=token)
    return token


def clear_persistent_login():
    st.session_state.pop("current_user", None)
    st.session_state.pop("_pump_session_token", None)
    _clear_query_param(SESSION_PARAM)
    _remove_old_logout_flag()
    render_session_bridge(clear=True)


def _build_user_from_payload(payload: dict):
    return {
        "id": payload.get("id"),
        "name": payload.get("name") or "User",
        "role": payload.get("role"),
        "phone": payload.get("phone"),
        "email": payload.get("email"),
    }


def _build_user_from_profile(profile: dict, payload: dict):
    return {
        "id": profile.get("id"),
        "name": profile.get("name") or payload.get("name") or "User",
        "role": profile.get("role") or payload.get("role"),
        "phone": profile.get("phone") or payload.get("phone"),
        "email": payload.get("email"),
    }


def restore_persistent_login():
    """
    Restore login after Streamlit rerun/refresh/tab switch.
    Priority:
    1. current st.session_state user
    2. signed token from session_state or URL
    3. browser bridge restores token into URL and reloads
    """
    try:
        _remove_old_logout_flag()

        user = st.session_state.get("current_user")
        if user:
            keep_session_alive()
            return user

        token = st.session_state.get("_pump_session_token") or _get_query_param(SESSION_PARAM)
        if not token:
            render_session_bridge()
            return None

        payload = validate_session_token(token)
        if not payload:
            clear_persistent_login()
            return None

        # Signed payload gives immediate restore. DB profile refresh is used when available.
        fallback_user = _build_user_from_payload(payload)

        profile = get_profile_by_user_id(payload.get("id"))
        if profile:
            if profile.get("role") == "salesman" and not is_duty_active(profile.get("id")):
                clear_persistent_login()
                return None
            user = _build_user_from_profile(profile, payload)
        else:
            # Profile read can fail on refresh due temporary network/RLS startup.
            # Do not destroy a valid signed manager/owner token because of that.
            user = fallback_user

        st.session_state["current_user"] = user
        st.session_state["_pump_session_token"] = token
        _set_query_param_if_needed(SESSION_PARAM, token)
        render_session_bridge(token=token)
        return user

    except Exception:
        # Restore should never crash or force logout.
        return st.session_state.get("current_user")


def keep_session_alive():
    """
    Keep token in URL + browser storage while user is logged in.
    """
    try:
        _remove_old_logout_flag()
        user = st.session_state.get("current_user")
        if not user:
            render_session_bridge()
            return None

        token = st.session_state.get("_pump_session_token") or _get_query_param(SESSION_PARAM)
        if not validate_session_token(token):
            token = make_session_token(user)
            st.session_state["_pump_session_token"] = token

        _set_query_param_if_needed(SESSION_PARAM, token)
        render_session_bridge(token=token)
        return token

    except Exception:
        return None
