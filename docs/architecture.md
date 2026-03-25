# Lehrercockpit — System Architecture

> **Status:** Production (as of 2026-03-25, Phase 9)
> **This document describes the actually implemented system.**

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Browser                                                                     │
│  ┌──────────────────────────────────────────────────────┐                   │
│  │  app.lehrercockpit.com (Netlify)                     │                   │
│  │  index.html    login.html    admin.html    onboarding.html               │
│  │  styles.css    src/app.js    manifest.json           │                   │
│  └──────────────────┬───────────────────────────────────┘                   │
│                     │ HTTPS + lc_session cookie (SameSite=None; Secure)     │
│                     │ credentials: 'include'                                │
└─────────────────────┼───────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  api.lehrercockpit.com (Render — Docker)                                     │
│                                                                              │
│  app.py (Flask WSGI entry)                                                   │
│  ├── /api/*           legacy v1 routes (grades, notes, classwork, dashboard)│
│  └── /api/v2/*        v2 blueprints (multi-user SaaS)                       │
│       ├── /auth/      auth_routes.py   (login, logout, me)                  │
│       ├── /admin/     admin_routes.py  (user CRUD, settings, modules)       │
│       ├── /dashboard/ dashboard_routes.py (layout, config, onboarding)      │
│       └── /modules/   module_routes.py (config CRUD, data endpoints)        │
│                                                                              │
│  backend/                                                                    │
│  ├── auth/         argon2id codes, session management                       │
│  ├── users/        User CRUD, authenticate_by_code()                        │
│  ├── modules/      Module registry, user-module settings                    │
│  ├── admin/        admin_service, bootstrap (advisory-locked)               │
│  ├── api/          Flask blueprints + helpers (decorators, mask_config)     │
│  ├── crypto.py     Fernet encryption for module config sensitive fields     │
│  ├── db.py         psycopg3 connection factory                              │
│  ├── migrations.py idempotent schema + audit_log + log_audit_event()       │
│  ├── persistence.py JsonFileStore / DbStore abstraction                     │
│  ├── dashboard.py  legacy dashboard payload builder                         │
│  └── config.py     AppSettings, env var loading                             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ psycopg3 (PostgreSQL wire protocol)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Render Managed PostgreSQL                                                   │
│  ├── app_state          (legacy key-value: grades, notes, classwork cache)  │
│  ├── users              (teacher/admin accounts)                             │
│  ├── user_access_codes  (argon2id hashes + code_prefix for O(1) lookup)     │
│  ├── sessions           (active sessions, 30-day TTL)                       │
│  ├── modules            (module registry + seed data)                       │
│  ├── user_modules       (per-user visibility and sort order)                 │
│  ├── user_module_configs (per-user module credentials — enc: JSONB)         │
│  ├── grades             (per-user grade entries — Phase 9)                  │
│  ├── class_notes        (per-user class notes, unique per class — Phase 9)  │
│  ├── audit_log           (event_type, user_id, ip_address, details)         │
│  └── system_settings    (central config: orgaplan URL, school name, etc.)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Descriptions

### Frontend (Netlify)

Static files served by Flask from the project root. No build step, no bundler.

| File | Purpose |
|---|---|
| `index.html` | Main cockpit. `window.MULTIUSER_ENABLED = true` — auth gate is active. Script load order: `api-client.js` → `dashboard-manager.js` → `grades.js` → `app.js`. |
| `login.html` | Access code entry. Calls `/api/v2/auth/login`, sets cookie, redirects by role. |
| `admin.html` | Admin panel with four tabs: Users, Settings, Modules, Audit-Log (Phase 9). |
| `onboarding.html` | First-login setup wizard: module selection and credential entry. |
| `src/api-client.js` | Unified API layer (`window.LehrerAPI`). All requests use `credentials: 'include'`. v2 and v1 legacy paths separated. |
| `src/modules/dashboard-manager.js` | `DashboardManager` — module layout management. Depends on `window.LehrerAPI`. Extracted from `src/app.js` in Phase 8d. |
| `src/features/grades.js` | Grades/notes module (Phase 9). Exposes `window.LehrerGrades`. All grade/note CRUD functions extracted from `src/app.js`. Uses `/api/v2/modules/noten/*`. |
| `src/app.js` | IIFE: dashboard logic, rendering, events. Auth check active (`MULTIUSER_ENABLED=true`). Delegates grades/notes to `window.LehrerGrades`. |
| `styles.css` | Visual system including multi-user UI classes. |
| `scripts/backfill_encryption.py` | One-time maintenance script to encrypt existing plaintext module configs. Idempotent, `--dry-run` supported. (Phase 9) |

### Backend (Render)

Flask WSGI app (`app.py`) with:
- Legacy v1 routes registered directly on `app`
- v2 blueprints registered via `backend/api/__init__.py:register_blueprints()`
- Static file serving for all non-API paths (blocked: `.py`, `.pyc`, `.env`)
- CORS via `after_request` hook with explicit origin matching
- OPTIONS preflight via `before_request` hook

### Database (Render PostgreSQL)

Accessed via `backend/db.py:db_connection()` — a psycopg3 context manager with autocommit. Migrations run at startup via `backend/migrations.py:run_all_migrations()`.

The legacy `app_state` table is used by both `backend/persistence.py` (grades, notes, classwork cache) and `dashboard_routes.py` (onboarding completion flags per user).

---

## Auth Flow Sequence

```
Teacher Browser          Netlify             Render (api)          PostgreSQL
     │                      │                     │                     │
     │  GET /login.html      │                     │                     │
     │──────────────────────►│                     │                     │
     │◄──────────────────────│                     │                     │
     │                      │                     │                     │
     │  POST /api/v2/auth/login                    │                     │
     │  {"code": "..."}      │                     │                     │
     │─────────────────────────────────────────────►                     │
     │                      │   rate-limit check (flask-limiter, 5/min)  │
     │                      │                     │                     │
     │                      │  SELECT users + code_hash WHERE is_active  │
     │                      │─────────────────────────────────────────────►
     │                      │◄─────────────────────────────────────────────
     │                      │  argon2id.verify(input_code, stored_hash)  │
     │                      │                     │                     │
     │                      │  INSERT INTO sessions (UUID, user_id, expires_at)
     │                      │─────────────────────────────────────────────►
     │                      │◄─────────────────────────────────────────────
     │                      │                     │                     │
     │  200 OK {"ok":true, "user":{...}}           │                     │
     │  Set-Cookie: lc_session=UUID; HttpOnly; Secure; SameSite=None
     │◄─────────────────────────────────────────────                     │
     │                      │                     │                     │
     │  Subsequent requests: Cookie: lc_session=UUID                    │
     │─────────────────────────────────────────────►                     │
     │                      │  @require_auth decorator:                  │
     │                      │  get_session() + refresh_session() + get_user_by_id()
     │                      │─────────────────────────────────────────────►
     │                      │◄─────────────────────────────────────────────
     │                      │  g.current_user = User(...)                │
     │                      │  → route handler executes                  │
     │◄─────────────────────────────────────────────                     │
```

---

## Module System Design

### Module Types

```
individual  ──► Teacher configures own credentials
                Stored in: user_module_configs.config_data (JSONB, per user)
                Examples: itslearning (URL+user+pass), webuntis (iCal URL), nextcloud

central     ──► Admin configures a shared source
                Stored in: system_settings (single value for all users)
                Examples: orgaplan (PDF URL), klassenarbeitsplan (URL)

local       ──► Only works on local machine, not SaaS
                Example: mail (Apple Mail / IMAP)
                default_visible=FALSE — hidden by default
```

### Module Lifecycle

```
App startup
  │
  ▼
run_all_migrations()
  │
  ├── CREATE TABLE modules IF NOT EXISTS
  ├── INSERT INTO modules ... ON CONFLICT DO NOTHING   (seed data, idempotent)
  │
  ▼
User creation (POST /api/v2/admin/users)
  │
  ├── create_user() → users INSERT
  ├── set_access_code() → user_access_codes INSERT (argon2id hash)
  ├── initialize_user_modules() →
  │       INSERT INTO user_modules (user_id, module_id, is_visible=default, sort_order=default)
  │       SELECT all enabled modules
  │       ON CONFLICT DO NOTHING (idempotent)
  │
  ▼
Teacher first login → onboarding
  │
  ├── GET /api/v2/dashboard/onboarding-status
  │       → finds modules where requires_config=TRUE AND is_configured=FALSE
  │       → returns needs_onboarding: true
  │
  ├── Teacher enters credentials for each required module
  │       PUT /api/v2/modules/<id>/config
  │       → save_user_module_config() → UPSERT user_module_configs
  │       → UPDATE user_modules SET is_configured=TRUE
  │
  ├── POST /api/v2/dashboard/onboarding/complete
  │       → SET system_settings["onboarding_done_{user_id}"] = {"done": true}
  │
  ▼
Teacher loads dashboard
  │
  └── GET /api/v2/dashboard
          → get_user_modules() JOIN modules WHERE is_enabled=TRUE
          → sorted by sort_order
          → returns module list with is_visible, is_configured, requires_config
```

### Credential Encryption

`backend/crypto.py` implements Fernet (AES-128-CBC + HMAC-SHA256) encryption for sensitive module config fields:

```python
# Sensitive field detection: key name contains any of:
_SENSITIVE_PATTERNS = ("password", "secret", "token", "credential")

# Storage format: enc:<base64_ciphertext>
# Backward compat: plaintext values pass through decrypt_config() unchanged
```

Encryption is applied in `save_user_module_config()` and decryption in `get_user_module_config()`. If `ENCRYPTION_KEY` is not set, a one-time warning is logged and values are stored/returned as plaintext.

### Credential Masking

`backend/api/helpers.py` exports `mask_config()` (centralized in Phase 8):

```python
_SENSITIVE_PATTERNS = {"password", "secret", "token", "credential"}
# Any key whose lowercase name contains one of these patterns → value replaced with "***"
```

Masking is applied in both `dashboard_routes.py` **and** `module_routes.py` — no more plaintext leak via the dashboard config endpoint.

---

## Data Model Summary

```
users
  ├─1:1─► user_access_codes  (argon2id hash + code_prefix for O(1) lookup)
  ├─1:N─► sessions            (active sessions, 30-day TTL)
  ├─1:N─► user_modules        (visibility + sort_order per module)
  │            └─ N:1 ─► modules  (global module definitions)
  ├─1:N─► user_module_configs (per-module credentials, enc: JSONB when ENCRYPTION_KEY set)
  │            └─ N:1 ─► modules
  ├─1:N─► grades              (per-user grade entries, Phase 9)
  ├─1:N─► class_notes         (per-user class notes, UNIQUE per class, Phase 9)
  └─(nullable)─► audit_log   (event_type, ip_address, details)

system_settings               (global key-value store)
  └─ "orgaplan_url"           → central module config
  └─ "klassenarbeitsplan_url" → central module config
  └─ "onboarding_done_{uid}"  → per-user onboarding completion flag
  └─ "default_module_order"   → admin-set default module order list
  └─ "default_enabled_modules"→ admin-set default enabled module list
  └─ "bootstrap_completed_at" → ISO timestamp of first bootstrap
  └─ "bootstrap_pending_rotation" → "true" until admin rotates their code

app_state                     (legacy key-value, file store fallback)
  └─ "grades-local"           → grades data (JSON)
  └─ "class-notes-local"      → notes data (JSON)
  └─ "classwork-cache"        → parsed classwork plan
```

**Primary key types:** `users.id` is `SERIAL INTEGER`. `sessions.id` is `TEXT` (UUID string). Module IDs are `TEXT`.

---

## Security Model

### Authentication

| Mechanism | Implementation |
|---|---|
| Access codes | 32-char alphanumeric, argon2id hashed (`time_cost=3, memory_cost=64MB`) |
| Session tokens | UUID v4 (TEXT), stored in DB, 30-day expiry |
| Cookie | `HttpOnly`, `Secure=True` (prod), `SameSite=None` (prod for cross-origin) |
| Rate limiting | 5 login attempts/min, 20/hr per IP (flask-limiter) |
| Auth decorators | `@require_auth` (401 if no valid session), `@require_admin` (403 if not admin) |

### Authorization

```
Teacher role:
  ✅ Own dashboard data (modules, layout, config)
  ✅ Own grades and notes
  ❌ Other teachers' data
  ❌ Admin endpoints

Admin role:
  ✅ Everything teacher can do
  ✅ All /api/v2/admin/* endpoints
  ✅ User CRUD, code rotation
  ✅ System settings (central module config)
  ✅ Module defaults
```

All queries in multi-user routes filter on `user_id = g.current_user.id`. Admins can query any `user_id` via the admin endpoints.

### Data Isolation

- Each teacher's data is scoped by `user_id` in all multi-user tables
- Legacy `app_state` table uses key-prefix naming (`grades-local`, `class-notes-local`) — these are currently NOT scoped per user (single shared value)

### Credential Encryption (Phase 8)

`user_module_configs.config_data` stores credentials encrypted when `ENCRYPTION_KEY` is set:

| State | `config_data` content |
|---|---|
| `ENCRYPTION_KEY` not set | `{"password": "hunter2"}` — plaintext |
| `ENCRYPTION_KEY` set | `{"password": "enc:gAAAAA..."}` — Fernet ciphertext |
| Mixed (key set after save) | Plaintext values pass through `decrypt_config()` unchanged — backward compatible |

**Action required:** Set `ENCRYPTION_KEY` on Render. Existing plaintext records become encrypted only when teachers re-save their module configs (no automatic backfill migration).

### Audit Trail

`audit_log` table records security events:

| Event type | Logged by |
|---|---|
| `login_success` | `auth_routes.py` |
| `login_failure` | `auth_routes.py` |
| `bootstrap_created` | `bootstrap.py` |
| `teacher_created` | `admin_routes.py` (Phase 9) |
| `teacher_deactivated` | `admin_routes.py` (Phase 9) |
| `code_rotated` | `admin_routes.py` (Phase 9) |

Audit log writes never abort the request — failures are logged as warnings.

### CORS

```python
# app.py
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
# Production: CORS_ORIGIN=https://app.lehrercockpit.com

# After each request:
# - Sets Access-Control-Allow-Origin to exact matched origin (not *)
# - Sets Access-Control-Allow-Credentials: true
# - Sets Vary: Origin
```

`Access-Control-Allow-Credentials: true` cannot coexist with wildcard `*` — the current implementation correctly uses explicit origin matching.

---

## Legacy vs. v2 Architecture

### Two parallel API versions

| Version | Path prefix | Auth | Used by |
|---|---|---|---|
| v1 (legacy) | `/api/` | IP guard (localhost only) | `src/app.js` (grades, notes, classwork, dashboard payload) |
| v2 (SaaS) | `/api/v2/` | `lc_session` cookie | `login.html`, `admin.html`, `onboarding.html`; partially `index.html` |

v1 endpoints are retained for backward compatibility. The `GET /api/dashboard` endpoint is still called by `src/app.js` for the main dashboard payload. Full migration to v2 is a planned next step. In Phase 8, all v1 endpoints in `app.py` are clearly marked with a `# LEGACY v1 API ENDPOINTS` comment block and return the `X-API-Version: v1-legacy` response header.

### Two DB connection patterns

| Pattern | Used by | Notes |
|---|---|---|
| `backend/db.py:db_connection()` | All v2 routes | psycopg3 context manager, autocommit=True |
| `backend/persistence.py:store` | Legacy routes + classwork cache | JsonFileStore locally, DbStore in production |

These are independent — do not mix them within a single request context.
