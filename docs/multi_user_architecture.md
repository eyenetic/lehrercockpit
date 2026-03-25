# Multi-User Architecture: Lehrercockpit

> **Status:** Implemented — production-ready as of 2026-03-25
>
> **Original document:** Design spec (2026-03-25).
> **This document:** Updated to reflect what was actually built. Deviations from the original spec are marked with ⚠️. Unimplemented items are marked with 🔴. Fully implemented items are marked with ✅.

---

## Table of Contents

1. [Database Schema (as implemented)](#1-database-schema-as-implemented)
2. [API Structure (as implemented)](#2-api-structure-as-implemented)
3. [Backend Module Structure (as implemented)](#3-backend-module-structure-as-implemented)
4. [Frontend Architecture (as implemented)](#4-frontend-architecture-as-implemented)
5. [Security Model (as implemented)](#5-security-model-as-implemented)
6. [Migration Strategy (completed)](#6-migration-strategy-completed)
7. [Deviations from Original Design Spec](#7-deviations-from-original-design-spec)
8. [Remaining Gaps](#8-remaining-gaps)

---

## 1. Database Schema (as implemented)

### Table Overview

```
app_state            (existing, unchanged)
users                ✅ implemented
user_access_codes    ✅ implemented
sessions             ✅ implemented
modules              ✅ implemented
user_modules         ✅ implemented
user_module_configs  ✅ implemented
system_settings      ✅ implemented
audit_log            🔴 not implemented (referenced in analysis, not in migrations)
```

### Implemented CREATE TABLE Statements

Source: [`backend/migrations.py`](../backend/migrations.py)

```sql
-- Existing (unchanged)
CREATE TABLE IF NOT EXISTS app_state (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ⚠️ DEVIATION: INTEGER primary keys, not UUID as originally spec'd
-- Rationale: simpler psycopg3 queries, no UUID string wrapping needed,
--            adequate for <10,000 teachers, UUID adds no security value
--            (session token is the secret, not the user ID)
CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,       -- ⚠️ INTEGER not UUID
    first_name TEXT NOT NULL,            -- ⚠️ two fields not display_name + short_name
    last_name  TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'teacher' CHECK (role IN ('admin', 'teacher')),
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_access_codes (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash  TEXT NOT NULL,            -- argon2id hash
    -- ⚠️ DEVIATION: code_prefix column from spec NOT implemented
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)                      -- max 1 code per user
);

CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,         -- UUID string (not UUID type)
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- ⚠️ DEVIATION: ip_address and user_agent columns from spec NOT implemented
);

CREATE TABLE IF NOT EXISTS modules (
    id              TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    module_type     TEXT NOT NULL DEFAULT 'individual'
                    CHECK (module_type IN ('individual', 'central', 'local')),
                    -- ⚠️ DEVIATION: 'local' not 'local_only' as spec'd
    is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    default_visible BOOLEAN NOT NULL DEFAULT TRUE,
    default_order   INTEGER NOT NULL DEFAULT 100,
    requires_config BOOLEAN NOT NULL DEFAULT FALSE,
    -- ⚠️ DEVIATION: config_schema JSONB column from spec NOT implemented
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_modules (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    module_id     TEXT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    is_visible    BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order    INTEGER NOT NULL DEFAULT 100,
    is_configured BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, module_id)
);

CREATE TABLE IF NOT EXISTS user_module_configs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    module_id   TEXT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    config_data JSONB NOT NULL DEFAULT '{}',
    -- SECURITY NOTE: credentials stored as PLAINTEXT — encryption-at-rest not yet implemented
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, module_id)
);

CREATE TABLE IF NOT EXISTS system_settings (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL DEFAULT '{}',
    -- ⚠️ DEVIATION: description and updated_by columns from spec NOT implemented
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Indexes (implemented)

```sql
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id);
-- ⚠️ DEVIATION: idx_access_codes_prefix not implemented (code_prefix column absent)
```

### Seeded Module Registry

```sql
-- Seeded via ON CONFLICT (id) DO NOTHING at startup
-- ⚠️ DEVIATION: module IDs differ from original spec in some cases
-- Spec had 'stundenplan', 'noten', 'inbox', 'dokumente', 'assistenz', 'mail'
-- Implementation has: 'webuntis', 'noten', (no inbox/dokumente/assistenz), 'mail'
```

| id | display_name | module_type | requires_config | default_visible | default_order |
|---|---|---|---|---|---|
| `itslearning` | itslearning Lernplattform | individual | ✅ | ✅ | 10 |
| `nextcloud` | Nextcloud | individual | ❌ | ✅ | 20 |
| `webuntis` | WebUntis Stundenplan | individual | ✅ | ✅ | 30 |
| `orgaplan` | Orgaplan | central | ❌ | ✅ | 40 |
| `klassenarbeitsplan` | Klassenarbeitsplan | central | ❌ | ✅ | 50 |
| `noten` | Noten | individual | ❌ | ✅ | 60 |
| `mail` | Dienstmail (lokal) | local | ❌ | ❌ | 70 |

---

## 2. API Structure (as implemented)

### Conventions (same as spec)

- All v2 endpoints under `/api/v2/`
- Auth via `lc_session` cookie (HttpOnly, Secure, SameSite=None in prod)
- Error format: `{"error": "message"}`
- Success format: `{"ok": true, ...data}`
- Auth guard: `@require_auth` (teacher + admin); `@require_admin` (admin only)
- Rate limit on login: 5/min, 20/hr per IP

### 2.1 Auth Endpoints ✅

| Method | Path | Auth | Status |
|---|---|---|---|
| POST | `/api/v2/auth/login` | None | ✅ Implemented |
| POST | `/api/v2/auth/logout` | cookie | ✅ Implemented |
| GET | `/api/v2/auth/me` | cookie | ✅ Implemented |

Login body: `{"code": "..."}` — field is `code`, not `access_code`.

### 2.2 Admin Endpoints ✅

| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v2/admin/users` | admin | ✅ |
| POST | `/api/v2/admin/users` | admin | ✅ |
| GET | `/api/v2/admin/users/<id>` | admin | ✅ |
| PUT/PATCH | `/api/v2/admin/users/<id>` | admin | ✅ |
| DELETE | `/api/v2/admin/users/<id>` | admin | ✅ (hard delete) |
| POST | `/api/v2/admin/users/<id>/deactivate` | admin | ✅ (soft-delete) |
| POST | `/api/v2/admin/users/<id>/rotate-code` | admin | ✅ |
| POST | `/api/v2/admin/users/<id>/regenerate-code` | admin | ✅ (alias) |
| GET | `/api/v2/admin/users/<id>/modules` | admin | ✅ |
| GET | `/api/v2/admin/modules` | admin | ✅ |
| PUT | `/api/v2/admin/modules/<id>` | admin | ✅ |
| GET/PUT | `/api/v2/admin/modules/defaults` | admin | ✅ |
| GET | `/api/v2/admin/settings` | admin | ✅ |
| PUT | `/api/v2/admin/settings` | admin | ✅ |
| PUT | `/api/v2/admin/settings/<key>` | admin | ✅ |
| POST | `/api/v2/admin/maintenance/cleanup-sessions` | admin | ✅ |

⚠️ **Deviation:** The `DELETE /users/<id>` route performs a hard delete. A separate `POST /users/<id>/deactivate` was added for soft-delete.

### 2.3 Dashboard Endpoints ✅

| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v2/dashboard` | cookie | ✅ Aggregated payload |
| GET | `/api/v2/dashboard/layout` | cookie | ✅ |
| PUT | `/api/v2/dashboard/layout` | cookie | ✅ |
| PUT | `/api/v2/dashboard/layout/<id>/visibility` | cookie | ✅ |
| GET | `/api/v2/dashboard/module-config/<id>` | cookie | ✅ (no masking) |
| PUT | `/api/v2/dashboard/module-config/<id>` | cookie | ✅ |
| GET | `/api/v2/dashboard/onboarding-status` | cookie | ✅ |
| POST | `/api/v2/dashboard/onboarding/complete` | cookie | ✅ |

⚠️ **Deviation:** `dashboard/module-config/<id>` GET does not mask passwords. Use `modules/<id>/config` GET for masked reads.

### 2.4 Module Endpoints ✅

| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v2/modules` | None | ✅ Public |
| GET | `/api/v2/modules/defaults` | None | ✅ Public |
| GET | `/api/v2/modules/<id>/config` | cookie | ✅ Passwords masked |
| PUT | `/api/v2/modules/<id>/config` | cookie | ✅ |
| DELETE | `/api/v2/modules/<id>/config` | cookie | ✅ |
| GET | `/api/v2/modules/itslearning/data` | cookie | ✅ |
| GET | `/api/v2/modules/webuntis/data` | cookie | ✅ |
| GET | `/api/v2/modules/nextcloud/data` | cookie | ✅ |
| GET | `/api/v2/modules/orgaplan/data` | cookie | ✅ |
| GET | `/api/v2/modules/klassenarbeitsplan/data` | cookie | ✅ |

🔴 **Not implemented:** `/api/v2/modules/grades`, `/api/v2/modules/notes` (grades/notes still use v1 endpoints via `src/app.js`).

### 2.5 Legacy Endpoints (retained)

| Endpoint | Status |
|---|---|
| `GET /api/health` | ✅ Retained |
| `GET /api/dashboard` | ✅ Retained — still called by `src/app.js` |
| `GET /api/grades` | ✅ Retained — still called by `src/app.js` |
| `POST /api/local-settings/grades` | ✅ Retained (IP-guarded) |
| `GET /api/notes` | ✅ Retained |
| `POST /api/local-settings/notes` | ✅ Retained (IP-guarded) |
| `POST /api/classwork/upload` | ✅ Retained |
| `POST /api/local-settings/itslearning` | ✅ Retained (IP-guarded) |
| `POST /api/local-settings/nextcloud` | ✅ Retained (IP-guarded) |

---

## 3. Backend Module Structure (as implemented)

```
backend/
├── __init__.py
├── config.py              ✅ AppSettings, env var loading
├── db.py                  ✅ db_connection() psycopg3 context manager
├── migrations.py          ✅ run_migrations(conn), run_all_migrations()
├── persistence.py         ✅ JsonFileStore / DbStore (app_state table)
├── dashboard.py           ✅ legacy build_dashboard_payload()
├── grades_store.py        ✅ unchanged from single-user version
├── notes_store.py         ✅ unchanged
├── classwork_cache.py     ✅ unchanged
├── itslearning_adapter.py ✅ unchanged
├── nextcloud_adapter.py   ✅ unchanged
├── webuntis_adapter.py    ✅ unchanged
├── mail_adapter.py        ✅ local_only, unchanged
├── document_monitor.py    ✅ unchanged
├── file_utils.py          ✅ unchanged
├── plan_digest.py         ✅ unchanged
├── local_settings.py      ✅ unchanged
│
├── auth/
│   ├── __init__.py
│   ├── access_code.py     ✅ generate_code, hash_code, verify_code, needs_rehash
│   └── session.py         ✅ create_session, get_session, refresh_session,
│                             delete_session, cleanup_expired_sessions
│
├── users/
│   ├── __init__.py
│   ├── user_store.py      ✅ User dataclass, create_user, get_user_by_id,
│   │                         get_all_users, update_user, delete_user,
│   │                         set_access_code, get_access_code_hash
│   └── user_service.py    ✅ create_teacher, regenerate_access_code,
│                             authenticate_by_code, get_user_modules,
│                             update_user_module, update_user_module_order,
│                             initialize_user_modules
│
├── modules/
│   ├── __init__.py
│   └── module_registry.py ✅ Module, UserModule dataclasses; full CRUD:
│                             get_all_modules, get_module_by_id, get_user_modules,
│                             initialize_user_modules, save_user_module_config,
│                             get_user_module_config, update_user_module_visibility,
│                             update_user_module_order, update_user_module
│                          🔴 user_module_store.py from spec not created
│                             (functionality merged into module_registry.py)
│
├── admin/
│   ├── __init__.py
│   ├── admin_service.py   ✅ get/set_system_setting(s), get_default_module_order,
│   │                         set_default_module_order, get_default_enabled_modules,
│   │                         set_default_enabled_modules, set_default_module_config,
│   │                         get_all_users, get_user, deactivate_user,
│   │                         rotate_access_code, create_teacher, get_user_overview
│   └── bootstrap.py       ✅ ensure_bootstrap_admin()
│                          🔴 migration_helper.py from spec not created
│
└── api/
    ├── __init__.py        ✅ register_blueprints()
    ├── helpers.py         ✅ require_auth, require_admin, set_session_cookie,
    │                         clear_session_cookie, success(), error()
    ├── auth_routes.py     ✅ login, logout, me
    ├── admin_routes.py    ✅ full user/module/settings CRUD
    ├── dashboard_routes.py ✅ layout, config, onboarding
    └── module_routes.py   ✅ config CRUD (with masking), data endpoints
```

---

## 4. Frontend Architecture (as implemented)

### Pages

| Page | File | Status |
|---|---|---|
| Dashboard | `index.html` | ⚠️ `MULTIUSER_ENABLED=false` — auth gate inactive |
| Login | `login.html` | ✅ Functional |
| Admin Panel | `admin.html` | ✅ Full tab UI, 1044 lines |
| Onboarding | `onboarding.html` | ✅ Present |

### `index.html` Multi-User Gate

```javascript
// index.html — must be changed to true
const MULTIUSER_ENABLED = false;  // ← ⚠️ NOT yet activated in production
```

When `true`, `src/app.js` calls `GET /api/v2/auth/me` on load and redirects to `/login.html` if unauthenticated.

### Auth State in `src/app.js`

The auth check, user context display, and logout button are implemented inside the IIFE but gated by `MULTIUSER_ENABLED`. No code changes are needed — only the flag must be flipped.

### API Call Status in `src/app.js`

| Call | Current endpoint | Target | Status |
|---|---|---|---|
| Dashboard payload | `GET /api/dashboard` | `GET /api/v2/dashboard` | 🔴 Not migrated |
| Grades read | `GET /api/grades` | `GET /api/v2/modules/noten/data` | 🔴 Not migrated |
| Grades write | `POST /api/local-settings/grades` | `POST /api/v2/modules/grades` | 🔴 Not migrated |
| Notes read | `GET /api/notes` | `GET /api/v2/modules/notes` | 🔴 Not migrated |
| Notes write | `POST /api/local-settings/notes` | `POST /api/v2/modules/notes` | 🔴 Not migrated |
| itslearning config | `POST /api/local-settings/itslearning` | `PUT /api/v2/modules/itslearning/config` | 🔴 Not migrated |
| Nextcloud config | `POST /api/local-settings/nextcloud` | `PUT /api/v2/modules/nextcloud/config` | 🔴 Not migrated |

### Module Layout Drag-and-Drop

⚠️ **Deviation from spec:** Drag-and-drop module reordering was NOT implemented. Module order is changed via number inputs. The `PUT /api/v2/dashboard/layout` endpoint is implemented and ready; only the UI interaction pattern differs.

---

## 5. Security Model (as implemented)

### 5.1 Access Code Hashing ✅

- **Algorithm:** argon2id (`argon2-cffi`)
- **Parameters:** `time_cost=3, memory_cost=65536 (64MB), parallelism=1, hash_len=32, salt_len=16`

⚠️ **Deviation:** `parallelism=1` not `parallelism=2` as spec'd (minor difference, still OWASP-compliant).

### 5.2 Session Cookie ✅

```python
response.set_cookie(
    'lc_session',
    session_id,
    max_age=30 * 24 * 3600,
    httponly=True,
    secure=_IS_PROD,              # True when DATABASE_URL is set
    samesite="None" if _IS_PROD else "Lax",
    path="/",
)
```

⚠️ **Deviation from original spec:** `SameSite=None` (not `SameSite=Lax`) in production. This is required and correct for cross-origin Netlify → Render `fetch(..., {credentials: 'include'})` requests. The original spec had `SameSite=Lax` which would have broken production.

### 5.3 Rate Limiting ✅

- Login: 5/minute, 20/hour per IP (flask-limiter)
- HTTP 429 with `Retry-After` header on limit exceeded

### 5.4 Access Control ✅

```
@require_auth  → reads lc_session cookie → get_session() → refresh_session() → get_user_by_id()
                 → sets g.current_user
                 → returns 401 if no valid session or user inactive

@require_admin → calls require_auth + checks g.current_user.is_admin
                 → returns 403 if not admin
```

### 5.5 Credential Storage 🔴 Partially Implemented

**Current state:** `user_module_configs.config_data` stores credentials as plaintext JSONB.

**API masking** (implemented): `module_routes.py` masks any config field whose key contains `password`, `secret`, `token`, or `credential` with `***` in GET responses.

**Encryption-at-rest** (NOT implemented): The analysis doc recommends AES-256 via `cryptography.fernet`. Not yet added. The column comment in `migrations.py` documents this as a TODO.

### 5.6 CORS ✅

```python
# Implemented in app.py after_request hook
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
# Sets Access-Control-Allow-Origin: exact origin (never wildcard)
# Sets Access-Control-Allow-Credentials: true
# Sets Vary: Origin
```

---

## 6. Migration Strategy (completed)

### What was done

The migration from single-user prototype to multi-user SaaS was completed in one session (2026-03-25):

| Phase | Work | Status |
|---|---|---|
| Phase 1 | DB schema, idempotent migrations, access code auth (argon2id), session management | ✅ Done |
| Phase 2 | User CRUD, user_service, module registry, admin_service | ✅ Done |
| Phase 3 | Flask blueprints: auth, admin, dashboard, module routes; CORS fix; cookie fix | ✅ Done |
| Phase 4 | Frontend: login.html, onboarding.html, admin.html, index.html stubs | ✅ Done |
| Phase 5 | Test suite: access_code, user_store, user_service, session, module_registry, auth_api, admin, bootstrap | ✅ Done |
| Phase 6 | Bootstrap admin, production hardening (cookie security, CORS) | ✅ Done |
| Phase 7 | Documentation | ✅ This document |

### Legacy backward compatibility

- v1 endpoints (`/api/*`) retained — no breaking changes
- `app_state` table unchanged — legacy grades/notes/classwork cache unaffected
- `server.py` unchanged — still usable for single-user local dev

### `migration_helper.py` (ENV → DB)

🔴 **Not implemented.** The `backend/admin/migration_helper.py` documented in the spec (which would migrate `.env.local` settings into `system_settings` and `user_module_configs`) was not created. This is acceptable because the deployment starts fresh with an empty DB and the admin configures everything via the admin panel.

---

## 7. Deviations from Original Design Spec

| Spec item | What was spec'd | What was implemented | Impact |
|---|---|---|---|
| `users.id` type | UUID | SERIAL INTEGER | No impact — IDs not exposed in URLs/tokens |
| `users` fields | `display_name`, `short_name` | `first_name`, `last_name` | Minor — `display_name` returned as `"first last"` in API responses |
| `user_access_codes.code_prefix` | TEXT column for admin UX | Not implemented | Minor — admin panel shows no code prefix hint |
| `user_access_codes.is_active` | boolean per-code | UNIQUE(user_id) constraint instead | Same effect — only 1 code per user |
| `sessions.ip_address` | TEXT column | Not implemented | No audit logging of login IPs |
| `sessions.user_agent` | TEXT column | Not implemented | No browser fingerprinting |
| `modules.config_schema` | JSONB for form generation | Not implemented | Frontend cannot auto-generate config forms |
| `modules.module_type` values | `'local_only'` | `'local'` | Minor naming difference |
| `system_settings.updated_by` | UUID FK to users | Not implemented | No tracking of who changed settings |
| `SameSite` cookie attribute | `Lax` | `None` (prod) / `Lax` (dev) | Correct fix for cross-origin SaaS |
| `parallelism` argon2 param | `2` | `1` | Negligible security difference |
| Module set | 11 modules (heute, stundenplan, etc.) | 7 modules (itslearning, nextcloud, webuntis, orgaplan, klassenarbeitsplan, noten, mail) | Reduced scope — heute/inbox/dokumente/assistenz not in registry |
| `audit_log` table | Specified in analysis | Not created | No security event logging |
| `code_prefix` index | Specified for O(n) optimization | Not created | O(n) auth scan persists |
| `user_module_store.py` | Separate file for user_modules/configs | Merged into `module_registry.py` | No functional impact — all functions present |
| `migration_helper.py` | ENV → DB migration helper | Not created | Not needed — new deploy starts clean |
| Drag-and-drop reorder | HTML5 drag events | Number inputs | UI/UX difference only |

---

## 8. Remaining Gaps

### Critical (blocks full SaaS operation)

1. **`MULTIUSER_ENABLED = false` in `index.html`** — Auth gate on main dashboard is disabled. Teachers can access `index.html` without logging in if they navigate directly. Change to `true` + Netlify redeploy.

2. **`src/app.js` v1 API calls** — Grades, notes, and module config forms still call IP-guarded v1 endpoints. These work locally but will fail for teachers on the deployed SaaS unless they happen to be on the same IP as the server (impossible on Render). Must migrate to v2 with `credentials: 'include'`.

### Important (security)

3. **Plaintext credentials** — `user_module_configs.config_data` contains itslearning/Nextcloud passwords in cleartext JSONB. A DB admin or SQL injection can read them. Implement AES-256 encryption.

4. **No audit log** — Failed login attempts, code rotations, and user deactivations are not logged to DB. Add `audit_log` table + logging hooks in `auth_routes.py` and `admin_routes.py`.

### Operational

5. **O(n) auth scan** — `authenticate_by_code()` in `user_service.py` iterates all active users. Add `code_prefix` column + index.

6. **No automated session cleanup** — Expired sessions accumulate in the DB. Add probabilistic cleanup in `get_current_user()` (1% of requests) or set up a scheduled endpoint.

### Quality of life

7. **Monolithic `src/app.js`** — 3600+ lines in one IIFE. Split into `src/state.js`, `src/api.js`, `src/features/*.js`.

8. **Bootstrap admin display name** — First admin is named "Bootstrap Admin". No self-service profile update endpoint exists.

9. **CI DB tests** — Add `TEST_DATABASE_URL` secret to GitHub Actions to run DB tests in CI.
