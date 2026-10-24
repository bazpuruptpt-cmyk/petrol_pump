import uuid
import hashlib
import secrets
from config.supabase_client import get_supabase_client

VALID_ROLES = ["owner", "manager", "salesman"]


def hash_password(plain_password: str) -> str:
    """Python की इन-बिल्ट PBKDF2-SHA256 सुरक्षा (किसी बाहरी लाइब्रेरी की ज़रूरत नहीं)"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000
    ).hex()
    return f"{salt}${pwd_hash}"


def verify_password(plain_password: str, stored_password: str) -> bool:
    if not plain_password or not stored_password:
        return False
    try:
        if "$" not in stored_password:
            return False
        salt, pwd_hash = stored_password.split("$", 1)
        check_hash = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000
        ).hex()
        return secrets.compare_digest(pwd_hash, check_hash)
    except Exception:
        return False


def get_profile_by_user_id(user_id: str):
    if not user_id:
        return None
    supabase = get_supabase_client()
    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .eq("id", user_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in get_profile_by_user_id: {exc}")
        return None


def get_profile_by_username(login_id: str):
    """Username, Email या Phone से सीधे प्रोफ़ाइल ढूँढने के लिए"""
    if not login_id:
        return None
    supabase = get_supabase_client()
    clean_id = login_id.strip().lower()
    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .eq("username", clean_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]

        result_phone = (
            supabase.table("profiles")
            .select("*")
            .eq("phone", login_id.strip())
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return result_phone.data[0] if result_phone.data else None
    except Exception as exc:
        print(f"Error in get_profile_by_username: {exc}")
        return None


def get_user_by_id(user_id: str):
    if not user_id:
        return None
    supabase = get_supabase_client()
    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in get_user_by_id: {exc}")
        return None


def get_all_users():
    supabase = get_supabase_client()
    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_all_users: {exc}")
        return []


def get_active_salesmen():
    supabase = get_supabase_client()
    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .eq("role", "salesman")
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_active_salesmen: {exc}")
        return []


def get_active_managers():
    supabase = get_supabase_client()
    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .eq("role", "manager")
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"Error in get_active_managers: {exc}")
        return []


def create_profile(
    name: str,
    role: str,
    phone: str = None,
    username: str = None,
    password: str = None,
    allowed_pages: list = None,
    user_id: str = None,
):
    if role not in VALID_ROLES:
        raise ValueError("Invalid role. Use owner, manager, or salesman.")

    final_user_id = user_id.strip() if user_id and user_id.strip() else str(uuid.uuid4())
    supabase = get_supabase_client()

    data = {
        "id": final_user_id,
        "name": name.strip(),
        "role": role,
        "phone": phone.strip() if phone else None,
        "is_active": True,
    }

    if username:
        data["username"] = username.strip().lower()
    if password:
        data["password_hash"] = hash_password(password)
    if allowed_pages is not None:
        data["allowed_pages"] = allowed_pages

    try:
        result = (
            supabase.table("profiles")
            .upsert(data, on_conflict="id")
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in create_profile: {exc}")
        return None


def update_user(user_id: str, data: dict):
    if not user_id or not data:
        return None

    allowed_fields = {"name", "role", "phone", "is_active", "username", "allowed_pages"}
    clean_data = {k: v for k, v in data.items() if k in allowed_fields}

    if "username" in clean_data and clean_data["username"]:
        clean_data["username"] = clean_data["username"].strip().lower()

    if data.get("new_password"):
        clean_data["password_hash"] = hash_password(data["new_password"])

    if "role" in clean_data and clean_data["role"] not in VALID_ROLES:
        raise ValueError("Invalid role. Use owner, manager, or salesman.")

    supabase = get_supabase_client()
    try:
        result = (
            supabase.table("profiles")
            .update(clean_data)
            .eq("id", user_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"Error in update_user: {exc}")
        return None


def toggle_user_active(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        return None
    new_status = not bool(user.get("is_active"))
    return update_user(user_id, {"is_active": new_status})
