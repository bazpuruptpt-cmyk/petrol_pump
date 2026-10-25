"""Run with:  python -m unittest discover -s tests -v
Streamlit/Supabase are stubbed, so no installs or network are needed."""
import base64, json, os, sys, time, types, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

st = types.ModuleType("streamlit")
st.secrets = {}
st.session_state = {}
comp = types.ModuleType("streamlit.components"); comp1 = types.ModuleType("streamlit.components.v1")
comp1.html = lambda *a, **k: None
sys.modules.update({"streamlit": st, "streamlit.components": comp, "streamlit.components.v1": comp1})
for name in ("database.profiles_db", "database.duties_db"):
    m = types.ModuleType(name)
    m.fetch_active_profile = lambda *_: (None, False)
    m.is_duty_active = lambda *_: True
    sys.modules[name] = m

from auth import persistent_session as ps  # noqa: E402

USER = {"id": "u1", "name": "A", "role": "salesman", "phone": None, "email": "a@b.c"}


class TokenTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("APP_SESSION_SECRET", None)

    def test_roundtrip(self):
        t = ps.make_session_token(USER)
        self.assertEqual(ps.validate_session_token(t)["role"], "salesman")

    def test_tampered_role_rejected(self):
        t = ps.make_session_token(USER)
        payload, sig = t.split(".")
        data = json.loads(ps._unb64(payload)); data["role"] = "owner"
        forged = ps._b64(json.dumps(data).encode()) + "." + sig
        self.assertIsNone(ps.validate_session_token(forged))

    def test_anon_key_cannot_forge(self):
        os.environ["SUPABASE_ANON_KEY"] = "public-anon-key-value"
        import hmac, hashlib
        payload = ps._b64(json.dumps({"id": "x", "role": "owner", "exp": int(time.time()) + 999}).encode())
        sig = hmac.new(b"public-anon-key-value", payload.encode(), hashlib.sha256).hexdigest()
        self.assertIsNone(ps.validate_session_token(f"{payload}.{sig}"))

    def test_hardcoded_default_cannot_forge(self):
        import hmac, hashlib
        payload = ps._b64(json.dumps({"id": "x", "role": "owner", "exp": int(time.time()) + 999}).encode())
        sig = hmac.new(b"pump-local-session-key", payload.encode(), hashlib.sha256).hexdigest()
        self.assertIsNone(ps.validate_session_token(f"{payload}.{sig}"))

    def test_expired_rejected(self):
        os.environ["APP_SESSION_SECRET"] = "x" * 32
        old = ps.SESSION_TTL_SECONDS; ps.SESSION_TTL_SECONDS = -10
        try:
            t = ps.make_session_token(USER)
        finally:
            ps.SESSION_TTL_SECONDS = old
        self.assertIsNone(ps.validate_session_token(t))

    def test_configured_secret_used(self):
        os.environ["APP_SESSION_SECRET"] = "y" * 32
        t = ps.make_session_token(USER)
        os.environ["APP_SESSION_SECRET"] = "z" * 32
        self.assertIsNone(ps.validate_session_token(t))

    def test_garbage(self):
        for bad in (None, "", "abc", "a.b", "....."):
            self.assertIsNone(ps.validate_session_token(bad))


if __name__ == "__main__":
    unittest.main()
