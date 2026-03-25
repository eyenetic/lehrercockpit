# Phase 8 Implementation Record

> Created: 2026-03-25

## Goals Achieved

- [x] Fernet encryption for sensitive module credentials (`backend/crypto.py` — AES-128-CBC + HMAC-SHA256)
- [x] `audit_log` table and login event tracking (`backend/migrations.py` + `auth_routes.py`)
- [x] Bootstrap admin hardening (PostgreSQL advisory lock, `system_settings` flags: `bootstrap_completed_at`, `bootstrap_pending_rotation`)
- [x] v1 API isolation with `# LEGACY v1 API ENDPOINTS` comment block and `X-API-Version: v1-legacy` response header
- [x] `window.MULTIUSER_ENABLED = true` in `index.html` — dashboard auth gate is now active
- [x] `src/api-client.js` — unified `window.LehrerAPI` API layer; all requests use `credentials: 'include'`
- [x] `DashboardManager` extracted to `src/modules/dashboard-manager.js`
- [x] `saveItslearningCredentials()` / `saveNextcloudCredentials()` in `src/app.js` always use v2 path (no more if/else)
- [x] `mask_config()` centralized in `backend/api/helpers.py`; applied in both `dashboard_routes.py` and `module_routes.py`
- [x] CI: PostgreSQL 15 service container in `test-db` job; full syntax check for all `backend/**/*.py`; Fernet key generated; `DATABASE_URL` set in CI
- [x] 32 new tests: `tests/test_crypto.py` (21) + `tests/test_frontend_structure.py` (11) + extensions to `test_bootstrap.py`, `test_auth_api.py`, `test_module_registry.py`

## Deferred / Remaining

- [ ] Encrypt existing plaintext records in DB after `ENCRYPTION_KEY` is set — one-time re-save migration (teachers must re-save credentials in settings panel; no automated backfill)
- [ ] `audit_log` viewer in admin panel (`GET /api/v2/admin/audit-log` + new tab in `admin.html`)
- [ ] DB-backed grades/notes v2 endpoints (no v2 equivalent yet — still using legacy `/api/grades`, `/api/notes`)
- [ ] `code_prefix` index for O(1) auth scan on `user_access_codes`
- [ ] Full v1 → v2 migration for `GET /api/dashboard` main payload

## Required Render Actions After Deploy

1. **Set `ENCRYPTION_KEY`** — Generate:
   ```
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Set this as an environment variable on Render. Without it, module passwords are stored as plaintext JSONB.

2. **Re-save teacher module configs** — All existing teacher credentials (itslearning password, WebUntis iCal URL with credentials, etc.) are still stored as plaintext until each teacher re-saves their settings after `ENCRYPTION_KEY` is set. There is no automatic backfill.

3. **Verify bootstrap admin code** — On first deploy the access code appears in Render logs. Copy it before the page scrolls.

## Sub-phase Summary

| Sub-phase | Deliverable |
|---|---|
| 8a | `backend/crypto.py` — Fernet encryption module |
| 8b | `backend/admin/bootstrap.py` — advisory lock + audit log + system_settings flags |
| 8c | `backend/migrations.py` — `audit_log` table + `log_audit_event()` helper |
| 8d | `src/modules/dashboard-manager.js` — DashboardManager extracted from `src/app.js` |
| 8e | `src/api-client.js` — unified `window.LehrerAPI` API layer |
| 8f | `index.html` — `MULTIUSER_ENABLED = true`; script load order fixed |
| 8g | Documentation update (this file + `README.md`, `CLAUDE_HANDOFF.md`, `docs/architecture.md`) |
