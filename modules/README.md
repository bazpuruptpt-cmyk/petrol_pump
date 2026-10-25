# Petrol Pump Management System

Streamlit + Supabase app for running a petrol pump: sales, settlement, money control, credit parties, stock and reports.

## Roles
| Role | Can do |
|---|---|
| Owner | Everything, plus Users, Nozzles, Fuel Rates, System Audit, Backup/Restore |
| Manager | Dashboard, Money Control, Reports, Sale Approval, Settlement, Credit, Stock (+ Stock Approval), Duty and Nozzle Assignment |
| Salesman | Own Sale Entry, My Entries, My Summary (login only while duty is active) |

## Setup
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in all four values (see comments inside).
3. Create users in Supabase → Authentication, then add the profile in the app (Owner → Users) using the auth UUID.
4. `streamlit run main.py`

On Streamlit Cloud put the same keys in **Secrets**.

## Security setup (do this before real use)
1. Set `APP_SESSION_SECRET` to a long random string. Without it everyone is logged out on each restart.
2. Set `SUPABASE_SERVICE_KEY`, redeploy, confirm the app works, then run `sql/rls_lockdown.sql`. After that the public anon key cannot read or write any table. Roles are enforced in the app code, so this is what protects your data.
3. Never commit `.env`.

## Layout
- `main.py` – navigation per role
- `auth/` – login, signed session token
- `modules/` – pages (`owner/`, `manager/`, `attendant/`)
- `database/` – all Supabase queries
- `utils/` – permissions, formatters, export/PDF, UI
- `tests/` – `python -m unittest discover -s tests -v`
- `sql/rls_lockdown.sql` – locks tables to the server key

## Tables used
profiles, shifts, shift_assignments, nozzles, fuel_rates, sale_entries, settlements, credit_parties, credit_transactions, oil_company_ledger, stock_tanks, stock_closing, daily_testing, fuel_inward, inward_payments, expenses, whatsapp_messages, paytm_settlements, ccms_settlements, cash_deposits.
