import os
from functools import lru_cache

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def _setting(name: str):
    value = os.getenv(name)
    if value and value.strip():
        return value.strip()
    try:
        import streamlit as st

        value = st.secrets.get(name)
        if value and str(value).strip():
            return str(value).strip()
    except Exception:
        pass
    return None


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Shared data client used for every table query.

    Required env:
    - SUPABASE_URL
    - SUPABASE_SERVICE_KEY (recommended) or SUPABASE_ANON_KEY

    The app enforces roles in Python, so the recommended setup is the
    service key on the server plus RLS enabled with NO anon policies
    (see sql/rls_lockdown.sql). That way the public anon key cannot read
    or write any table. Never expose the service key to the browser.
    """
    url = _setting("SUPABASE_URL")
    key = _setting("SUPABASE_SERVICE_KEY") or _setting("SUPABASE_ANON_KEY")

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY). "
            "Create .env from .env.example."
        )

    return create_client(url, key)


def get_auth_client() -> Client:
    """
    Fresh, throw-away client used only for email/password sign-in.

    The shared data client must never hold a user's login session: it is
    one object for every browser session, so signing in or out on it would
    affect all users at once.
    """
    url = _setting("SUPABASE_URL")
    key = _setting("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY for login.")
    return create_client(url, key)
