# Changes in this version

## Bugs / cleanup
- Fixed Stock Management: `create_oil_company_payment`, `get_oil_company_ledger`, `get_oil_company_summary` were used but never imported.
- Removed 10 stale or unused files: root `stock_db.py`, `settlement_db.py`, `money_control.py`, `dashboard.py`; `modules/reports.py`; `database/settlement.py`, `database/reports.py`, `database/sale_db_duplicate_helper.py` (fix already inside `sale_db.py`), `database/sale_summary_db.py`; `utils/helpers.py`.
- Wired the finished but unlinked **Stock Approval** page into the Owner and Manager Stock menu.

## Security
- **Critical:** session tokens were signed with the public Supabase anon key (or a hardcoded string), so anyone could forge an owner login. Now signed only with `APP_SESSION_SECRET`; if missing, a random per-process secret is used.
- Deactivated or deleted users are logged out on the next refresh (before, a valid token kept them in).
- Login and logout no longer use the shared data client, which was one object shared by all users.
- Data client prefers `SUPABASE_SERVICE_KEY`; added `sql/rls_lockdown.sql` so the anon key gets no table access.
- Login throttle: 5 failed attempts lock that browser session for 60 seconds.
- HTML in sidebar/header is escaped; raw error details are shown to owner/manager only.

## Added
- README, `.gitignore`, `.streamlit/config.toml`, updated `.env.example`.
- 9 unit tests (session token forgery, expiry, tampering; formatters).
- Mobile layout CSS; Streamlit footer/menu hidden.

## Not changed / worth knowing
- The session token still travels in the page URL (`?pump_session=`). Do not share screenshots or links of a logged-in page.
- No full `schema.sql`: the database schema is not in the project, so I did not guess it. Export it from Supabase if you want it versioned.
- Business logic (settlement, ledger maths) was not modified, and I could not run the app against your Supabase here. Test the Stock and login flows once after deploy.
