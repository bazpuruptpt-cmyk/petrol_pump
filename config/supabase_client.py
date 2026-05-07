import os
from functools import lru_cache
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Singleton Supabase client.
    Required env:
    - SUPABASE_URL
    - SUPABASE_ANON_KEY
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_ANON_KEY. "
            "Create .env from .env.example."
        )

    return create_client(url, key)
