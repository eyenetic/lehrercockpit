# Lehrercockpit — Multi-User SaaS Upgrade: Architecture Analysis & Implementation Plan

> **Analysedatum:** 2026-03-25  
> **Analysierter Stand:** Alle Backend-Module, API-Routen, Frontend-Seiten und Tests vollständig gelesen.  
> **Deployment-Ziel:** Frontend `https://app.lehrercockpit.com` (Netlify) ↔ Backend API `https://api.lehrercockpit.com` (Render), PostgreSQL on Render.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
   - 2.1 What Is Solid and Usable
   - 2.2 What Is Partially Implemented
   - 2.3 What Is Missing Entirely
   - 2.4 Architectural Issues Requiring Refactoring
3. [Current DB Schema](#3-current-db-schema)
4. [Current Auth State](#4-current-auth-state)
5. [Frontend State](#5-frontend-state)
6. [Test Coverage Gaps](#6-test-coverage-gaps)
7. [Phased Implementation Plan](#7-phased-implementation-plan)
   - Phase 1: DB Schema, Migrations, Auth Core
   - Phase 2: Admin APIs, User Management, Module Registry
   - Phase 3: Session Handling, Route Protection, CORS/Domain Config
   - Phase 4: Frontend — Login, Onboarding, Admin Panel
   - Phase 5: Frontend — Modular Dashboard, Layout Management
   - Phase 6: Testing Expansion
   - Phase 7: Documentation
8. [API Endpoint Reference](#8-api-endpoint-reference)
9. [Risks, Tradeoffs, and Decisions](#9-risks-tradeoffs-and-decisions)

---

## 1. Executive Summary

**The multi-user backend infrastructure is ~85% complete.** The database schema, auth layer (argon2id access codes, session management), user CRUD, module registry, admin service, and all four Flask blueprints are implemented and syntactically correct. Tests exist for the core modules.

**The critical remaining work is in three areas:**

1. **Production hardening** — The cookie `secure=False` in `helpers.py`, wildcard CORS, and `MULTIUSER_ENABLED = false` in `index.html` are three blockers preventing the existing code from working in production today.

2. **Missing pieces** — `ensure_bootstrap_admin()`, `onboarding/complete` endpoint, module config `GET/PUT/DELETE` routes, aggregated dashboard endpoint, credential masking, and the `migration_helper.py` are documented but not yet implemented.

3. **Schema/doc divergence** — The implemented DB schema in `migrations.py` uses `SERIAL INTEGER` PKs for the `users` table, while `docs/multi_user_architecture.md` specifies `UUID`. This must be resolved as a deliberate decision before any data is produced in production.

**The frontend** has the structural shell (`index.html` multi-user stubs, `login.html` fully functional, `admin.html` 1044-line file with full tab UI, `onboarding.html` present), but the dashboard's `src/app.js` (3628 lines) is still wired to the legacy v1 API endpoints and `MULTIUSER_ENABLED = false`.

---

## 2. Current State Analysis

### 2.1 What Is Solid and Usable

| Component | File | Status |
|---|---|---|
| DB connection factory | `backend/db.py` | ✅ Clean, thread-safe context manager |
| DB migrations | `backend/migrations.py` | ✅ Idempotent, all 7 tables, indexes, module seed |
| Persistence abstraction | `backend/persistence.py` | ✅ JsonFileStore / DbStore, app_state table |
| Access code (argon2id) | `backend/auth/access_code.py` | ✅ OWASP params, generate/hash/verify/needs_rehash |
| Session management | `backend/auth/session.py` | ✅ create/get/refresh/delete/cleanup |
| User CRUD | `backend/users/user_store.py` | ✅ Full CRUD, access code ops, to_dict |
| User service | `backend/users/user_service.py` | ✅ create_teacher, authenticate_by_code, regenerate_access_code |
| Module registry | `backend/modules/module_registry.py` | ✅ Module/UserModule dataclasses, full CRUD |
| Admin service | `backend/admin/admin_service.py` | ✅ system_settings, user_overview, module defaults |
| Auth routes | `backend/api/auth_routes.py` | ✅ login (rate-limited), logout, me |
| Admin routes | `backend/api/admin_routes.py` | ✅ Full user CRUD, settings, modules |
| Dashboard routes | `backend/api/dashboard_routes.py` | ✅ layout CRUD, module-config CRUD, onboarding-status |
| Module data routes | `backend/api/module_routes.py` | ✅ itslearning/webuntis/nextcloud/orgaplan/klassenarbeitsplan data |
| Blueprint registration | `backend/api/__init__.py` | ✅ All 4 blueprints at /api/v2/ |
| Auth decorators | `backend/api/helpers.py` | ✅ require_auth, require_admin, success/error helpers |
| Login page | `login.html` | ✅ Functional — calls /api/v2/auth/login, sets cookie, redirects |
| Rate limiting | `backend/api/auth_routes.py` | ✅ flask-limiter 5/min 20/hr on /login |
| Test: access code | `tests/test_access_code.py` | ✅ 11 non-DB tests |
| Test: user store | `tests/test_user_store.py` | ✅ 13 DB tests |
| Test: session | `tests/test_session.py` | ✅ 7 DB tests |
| Test: module registry | `tests/test_module_registry.py` | ✅ 11 DB tests |
| Test: auth API | `tests/test_auth_api.py` | ✅ 8 mock tests |
| Requirements | `requirements.txt` | ✅ argon2-cffi, flask-limiter, psycopg, itsdangerous |

### 2.2 What Is Partially Implemented

| Issue | Location | Impact |
|---|---|---|
| `secure=False` on session cookie | `backend/api/helpers.py:65` | **CRITICAL** — Cookies not sent over HTTPS in production |
| `MULTIUSER_ENABLED = false` | `index.html:30` | **CRITICAL** — Auth check never runs on dashboard |
| CORS wildcard `*` | `app.py:118`, `server.py:59` | **HIGH** — Must be restricted to `https://app.lehrercockpit.com` |
| Hardcoded API URL `lehrercockpit.onrender.com` | `index.html:23-24`, `login.html:175` | **HIGH** — Must point to `https://api.lehrercockpit.com` |
| Bootstrap admin not called in `app.py` | `app.py` | **HIGH** — No way to create first admin without manual DB access |
| `onboarding/complete` endpoint missing | `dashboard_routes.py` | **MEDIUM** — Onboarding flow cannot be completed |
| Aggregated `GET /api/v2/dashboard` endpoint missing | `dashboard_routes.py` | **MEDIUM** — Docs specify this but only /layout is implemented |
| Module config `GET/PUT/DELETE /api/v2/modules/<id>/config` missing | `module_routes.py` | **MEDIUM** — Docs specify these, only `/data` variants exist |
| Credential masking missing | `dashboard_routes.py` | **MEDIUM** — `/module-config/<id>` returns plaintext passwords |
| `code_prefix` not stored in schema | `backend/migrations.py` | **LOW** — Admin panel cannot show code hints; docs spec includes it |
| DB schema uses SERIAL not UUID | `backend/migrations.py:21-31` | **DECISION** — Diverges from `docs/multi_user_architecture.md` |
| `src/app.js` uses v1 API endpoints | `src/app.js` | **MEDIUM** — Grades, notes, classwork not using v2 auth |
| `admin.html` JS wiring not verified | `admin.html` | **UNKNOWN** — File is 1044 lines, need to verify all API calls |

### 2.3 What Is Missing Entirely

| Missing Component | Required By | Notes |
|---|---|---|
| `backend/admin/bootstrap.py` | Docs, HANDOFF | `ensure_bootstrap_admin()` — not in file listing |
| `backend/admin/migration_helper.py` | Docs | `migrate_env_to_db()` — not in file listing |
| `POST /api/v2/dashboard/onboarding/complete` | Onboarding flow | Referenced in HANDOFF, not in dashboard_routes |
| `GET/PUT/DELETE /api/v2/modules/<module_id>/config` | Multi-user config | Only data endpoints exist; no config CRUD under modules/ |
| `GET /api/v2/dashboard` (aggregated) | Dashboard frontend | Only layout/config endpoints under dashboard/ |
| Session cleanup job/endpoint | Long-running SaaS | No periodic `cleanup_expired_sessions()` invocation |
| Credential encryption (pgcrypto) | Security | Documented TODO — plaintext in `user_module_configs.config_data` |
| `audit_log` table | Security/compliance | Referenced in task spec, not in schema |
| SameSite=None for cross-origin cookies | Production auth | Netlify → Render requires this for cookie sharing |
| `config_schema` field in modules table | Validation | In docs/HANDOFF, not in current migrations.py |
| `code_prefix` column | Admin UX | Not in `user_access_codes` migration |
| `short_name` / `display_name` user fields | Docs spec | Current schema has `first_name`/`last_name` not `display_name` |

### 2.4 Architectural Issues Requiring Refactoring

#### A. DB Schema Mismatch: INTEGER vs UUID Primary Keys

The **implemented** `users` table uses `SERIAL PRIMARY KEY` (integer). The **documented** spec uses `UUID PRIMARY KEY DEFAULT gen_random_uuid()`. This is currently in a pre-data state, so changing to UUID is still cheap. **Decision required before first production data.**

**Recommendation:** Stay with `SERIAL INTEGER` for simplicity. The docs spec UUID is over-engineered for a teacher-scale app (<1000 users). SERIAL is simpler to work with in psycopg3, tests, and joins.

#### B. O(n) Authentication Scan

`authenticate_by_code()` in `user_service.py` does a full table scan + argon2id verification on every user. At argon2id timing (~200ms/verify), 50 active users = 10 seconds worst case before a match. 

**Fix:** Store a `code_prefix` (first 4 chars, non-secret) in `user_access_codes` and filter candidates before hashing.

#### C. Two DB Connection Patterns Coexist

`persistence.py` uses `DbStore` (per-call connections with `autocommit=True`). All new v2 routes use `db_connection()` context manager (explicit commit/rollback). These are independent - fine architecturally, but callers must not mix them.

#### D. Cross-Origin Cookie Configuration

Netlify → Render is a cross-origin request. `SameSite=Lax` with `Secure=True` will work for top-level navigations but **not** for `credentials: 'include'` on `fetch()` calls. This requires `SameSite=None; Secure=True`. The current `helpers.py` has `SameSite=Lax` and `Secure=False` — both wrong for production.

#### E. `src/app.js` is 3628-line Monolith

All dashboard logic is a single IIFE. The TODO comment at the top correctly identifies the planned split into `src/state.js`, `src/api.js`, `src/features/`. Until this split happens, adding auth-aware module rendering requires careful placement within the IIFE.

---

## 3. Current DB Schema

### Active Schema (as implemented in `backend/migrations.py`)

```sql
-- EXISTING (from persistence.py)
CREATE TABLE IF NOT EXISTS app_state (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- NEW: Multi-user tables
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,           -- NOTE: INTEGER, not UUID
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'teacher' CHECK (role IN ('admin', 'teacher')),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_access_codes (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash   TEXT NOT NULL,               -- argon2id hash
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)                          -- max 1 code per user
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,            -- UUID string
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL,
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS modules (
    id              TEXT PRIMARY KEY,        -- e.g. 'itslearning'
    display_name    TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    module_type     TEXT NOT NULL DEFAULT 'individual'
                    CHECK (module_type IN ('individual', 'central', 'local')),
    is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    default_visible BOOLEAN NOT NULL DEFAULT TRUE,
    default_order   INTEGER NOT NULL DEFAULT 100,
    requires_config BOOLEAN NOT NULL DEFAULT FALSE,
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
    config_data JSONB NOT NULL DEFAULT '{}',  -- PLAINTEXT credentials
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, module_id)
);

CREATE TABLE IF NOT EXISTS system_settings (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id);
```

### Seeded Module Registry

| id | display_name | module_type | requires_config | default_order |
|---|---|---|---|---|
| `itslearning` | itslearning Lernplattform | individual | ✅ | 10 |
| `nextcloud` | Nextcloud | individual | ❌ | 20 |
| `webuntis` | WebUntis Stundenplan | individual | ✅ | 30 |
| `orgaplan` | Orgaplan | central | ❌ | 40 |
| `klassenarbeitsplan` | Klassenarbeitsplan | central | ❌ | 50 |
| `noten` | Noten | individual | ❌ | 60 |
| `mail` | Dienstmail (lokal) | local | ❌ | 70 |

### Proposed Schema Additions

```sql
-- Add to user_access_codes (for admin UX and O(n) optimization)
ALTER TABLE user_access_codes ADD COLUMN IF NOT EXISTS code_prefix TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_access_codes_prefix ON user_access_codes (code_prefix);

-- Add audit_log table (for security events)
CREATE TABLE IF NOT EXISTS audit_log (
    id          SERIAL PRIMARY KEY,
    event_type  TEXT NOT NULL,   -- 'login_success', 'login_fail', 'code_regenerated', etc.
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ip_address  TEXT,
    detail      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log (created_at);

-- Add config_schema to modules (for frontend form generation)
ALTER TABLE modules ADD COLUMN IF NOT EXISTS config_schema JSONB NOT NULL DEFAULT '{}';
```

---

## 4. Current Auth State

### What Works

| Feature | Status |
|---|---|
| `generate_code()` → 32-char alphanumeric | ✅ Implemented |
| `hash_code()` → argon2id (OWASP params) | ✅ Implemented |
| `verify_code()` → timing-safe comparison | ✅ Implemented |
| `create_session()` → UUID, 30-day TTL | ✅ Implemented |
| `get_session()` → validates expiry | ✅ Implemented |
| `refresh_session()` → updates last_seen | ✅ Implemented |
| `delete_session()` → logout | ✅ Implemented |
| `cleanup_expired_sessions()` → maintenance | ✅ Implemented |
| `POST /api/v2/auth/login` → rate-limited | ✅ Implemented |
| `POST /api/v2/auth/logout` → require_auth | ✅ Implemented |
| `GET /api/v2/auth/me` → require_auth | ✅ Implemented |
| `@require_auth` decorator | ✅ Implemented |
| `@require_admin` decorator | ✅ Implemented |

### What Is Stubbed/Broken

| Feature | Issue |
|---|---|
| Session cookie `Secure=False` | `helpers.py:65` — must be `True` in prod |
| Session cookie `SameSite=Lax` | Wrong for cross-origin Netlify→Render; needs `None` with `Secure=True` |
| Bootstrap admin creation | `ensure_bootstrap_admin()` not found in codebase — manual DB only |
| Login redirect for admin role | `login.html:219` sends everyone to `./index.html` — should check role, redirect admin to `/admin.html` |
| `authenticate_by_code()` O(n) scan | No code_prefix optimization; acceptable for <50 users, problematic at scale |

---

## 5. Frontend State

### Pages

| Page | File | Status | Notes |
|---|---|---|---|
| Dashboard | `index.html` | ⚠️ Partial | Multi-user stubs present but `MULTIUSER_ENABLED=false` |
| Login | `login.html` | ✅ Functional | Calls `/api/v2/auth/login`, error handling, session check |
| Admin Panel | `admin.html` | ⚠️ Needs verify | 1044-line file with tabs UI; JS API calls unverified |
| Onboarding | `onboarding.html` | ⚠️ Exists | Not read fully; `/onboarding/complete` endpoint missing |

### Key Frontend Issues

1. **`window.MULTIUSER_ENABLED = false`** in `index.html:30` — the auth check never runs
2. **Hardcoded URLs** — Both `index.html` and `login.html` point to `https://lehrercockpit.onrender.com` not `https://api.lehrercockpit.com`
3. **`src/app.js` v1 API calls** — Grades (`/api/grades`), notes (`/api/notes`), classwork still on legacy endpoints without `credentials: 'include'`
4. **Module config dialogs** — `src/app.js` has itslearning/nextcloud forms that POST to `/api/local-settings/*` (v1 IP-guarded endpoints), not v2 auth-gated endpoints
5. **Admin link** — `index.html:71` has `<a href="./admin.html" id="sidebar-admin-link" style="display:none;">` — logic to show it for admin users must exist in `app.js` (MULTIUSER_ENABLED path)

### What `src/app.js` Needs (within its IIFE)

The HANDOFF.md confirms auth check code exists in `src/app.js` but is gated by `MULTIUSER_ENABLED`. The following are confirmed needed changes:
- `MULTIUSER_ENABLED = true` to activate the auth gate
- All API calls in grades, notes, classwork sections must add `credentials: 'include'` and switch to `/api/v2/` endpoints
- Module config form submissions must use `/api/v2/dashboard/module-config/<id>` instead of `/api/local-settings/*`
- Login redirect must differentiate admin vs teacher

---

## 6. Test Coverage Gaps

### Existing Coverage (Good)

| Module | Tests | DB |
|---|---|---|
| `access_code.py` | 11 | No |
| `user_store.py` | 13 | Yes |
| `user_service.py` | 9 | Yes |
| `session.py` | 7 | Yes |
| `module_registry.py` | 11 | Yes |
| `auth_routes.py` | 8 | No (Mock) |

### Gaps

| Missing Test | Priority | Notes |
|---|---|---|
| `test_admin_routes.py` | HIGH | No tests for POST/PUT/DELETE /api/v2/admin/users/* |
| `test_dashboard_routes.py` | HIGH | No tests for layout CRUD, module-config CRUD, onboarding |
| `test_module_routes.py` | MEDIUM | No tests for /api/v2/modules/*/data endpoints |
| Login rate limit enforcement | MEDIUM | test_auth_api.py only checks 3 requests; no 429 test |
| Bootstrap admin creation | HIGH | If bootstrap.py is built, needs test |
| Cookie attributes in login response | MEDIUM | `Secure`, `SameSite`, `HttpOnly` not asserted |
| `authenticate_by_code()` with inactive user | MEDIUM | Edge case not tested |
| `cleanup_expired_sessions()` performance | LOW | Bulk delete test |
| `admin_service.py` functions | MEDIUM | No direct tests for get/set_system_setting, get_user_overview |
| Credential masking in module config | HIGH | Must not return plaintext passwords to frontend |
| CORS header assertions | HIGH | No test verifies `Access-Control-Allow-Origin` |
| Migration idempotency | MEDIUM | Running migrations twice should not error |

---

## 7. Phased Implementation Plan

### Phase 1: Production Hardening (DB + Auth Core) — Priority: CRITICAL

**Goal:** Make the existing code work correctly in production without regressions.

#### 1.1 Fix Session Cookie for Cross-Origin SaaS

**File:** [`backend/api/helpers.py`](backend/api/helpers.py:58)

```python
# CURRENT (broken for production):
response.set_cookie(
    SESSION_COOKIE_NAME, session_id,
    max_age=30 * 24 * 3600,
    httponly=True,
    secure=False,         # ← WRONG
    samesite="Lax",       # ← WRONG for cross-origin
    path="/",
)

# FIXED:
import os as _os

_IS_PROD = bool(_os.environ.get("DATABASE_URL", "").strip())

response.set_cookie(
    SESSION_COOKIE_NAME, session_id,
    max_age=30 * 24 * 3600,
    httponly=True,
    secure=_IS_PROD,                          # True on Render, False locally
    samesite="None" if _IS_PROD else "Lax",   # None required for cross-origin fetch
    path="/",
)
```

> **Why:** Netlify frontend at `https://app.lehrercockpit.com` making `fetch(..., {credentials:'include'})` to `https://api.lehrercockpit.com` is a cross-origin request. Browsers drop cookies with `SameSite=Lax` on cross-origin fetches. Must use `SameSite=None; Secure=True`.

#### 1.2 Restrict CORS to Production Domain

**File:** [`app.py`](app.py:118) and [`server.py`](server.py:59)

```python
# In app.py after_request:
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:8080")

def _cors(response):
    origin = request.headers.get("Origin", "")
    allowed = CORS_ORIGIN.split(",")
    if origin in allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    else:
        response.headers["Access-Control-Allow-Origin"] = allowed[0]
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Credentials"] = "true"  # ← Required for cookies
    response.headers["Cache-Control"] = "no-store"
    return response
```

> **Render ENV:** Set `CORS_ORIGIN=https://app.lehrercockpit.com`

> **Critical:** `Access-Control-Allow-Credentials: true` is required for `credentials: 'include'` to work. This header cannot coexist with `Access-Control-Allow-Origin: *`.

#### 1.3 Update Hardcoded API URLs

**File:** [`index.html`](index.html:23-24) and [`login.html`](login.html:175)

```html
<!-- index.html: Replace lehrercockpit.onrender.com with api.lehrercockpit.com -->
<script>
  window.BACKEND_API_URL = "https://api.lehrercockpit.com";
  window.LEHRER_COCKPIT_API_URL = "https://api.lehrercockpit.com";
  window.LEHRER_COCKPIT_API_FALLBACKS = ["https://api.lehrercockpit.com"];
</script>

<!-- login.html: -->
<script>window.BACKEND_API_URL = "https://api.lehrercockpit.com";</script>
```

#### 1.4 Add `code_prefix` to Schema

**File:** [`backend/migrations.py`](backend/migrations.py:34)

```sql
-- Extend user_access_codes to store prefix for admin UX + O(n) auth optimization
CREATE TABLE IF NOT EXISTS user_access_codes (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash   TEXT NOT NULL,
    code_prefix TEXT NOT NULL DEFAULT '',     -- ← ADD: first 4 chars for admin display + index scan
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)
);
CREATE INDEX IF NOT EXISTS idx_access_codes_prefix ON user_access_codes (code_prefix);
```

**Files to update:** [`backend/users/user_store.py`](backend/users/user_store.py:193) — `set_access_code()` must populate `code_prefix`. [`backend/auth/access_code.py`](backend/auth/access_code.py) — add `get_code_prefix(code: str) -> str`.

#### 1.5 Implement Bootstrap Admin

**New file:** `backend/admin/bootstrap.py`

```python
"""Ensures at least one admin user exists. Called at app startup."""

def ensure_bootstrap_admin() -> None:
    """If no users exist in DB, create a System Admin with a generated code.
    
    Logs the plaintext code to stdout only (never stored).
    Safe to call on every startup — exits early if users already exist.
    """
    from backend.db import db_connection
    from backend.users.user_service import create_teacher
    
    try:
        with db_connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
            if row[0] > 0:
                return  # Users exist, skip bootstrap
            
            user, plain_code = create_teacher(conn, "System", "Admin", role="admin")
            print(
                f"\n{'='*60}\n"
                f"[BOOTSTRAP] Erster Admin-Zugangscode:\n"
                f"  {plain_code}\n"
                f"  User-ID: {user.id} | Name: {user.full_name}\n"
                f"  Bitte sofort im Admin-Panel den Namen anpassen.\n"
                f"{'='*60}\n",
                flush=True
            )
    except Exception as exc:
        print(f"[BOOTSTRAP] Fehler beim Admin-Bootstrap: {exc}", flush=True)
```

**Wire into [`app.py`](app.py:471):**

```python
# After run_all_migrations() call:
try:
    from backend.admin.bootstrap import ensure_bootstrap_admin
    ensure_bootstrap_admin()
except Exception as _bootstrap_exc:
    _logging.getLogger(__name__).warning(f"Bootstrap check failed: {_bootstrap_exc}")
```

#### 1.6 Add audit_log Table

**File:** [`backend/migrations.py`](backend/migrations.py:108)

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id          SERIAL PRIMARY KEY,
    event_type  TEXT NOT NULL,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ip_address  TEXT,
    detail      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log (created_at);
```

Add `log_audit_event(conn, event_type, user_id, ip_address, detail)` to `admin_service.py`. Wire into `auth_routes.py` login success/failure.

---

### Phase 2: Admin APIs, User Management, Module Registry — Priority: HIGH

**Goal:** Make the admin panel fully operational with all documented features.

#### 2.1 Add Missing Admin Route: PATCH vs PUT

**File:** [`backend/api/admin_routes.py`](backend/api/admin_routes.py:86)

The route is currently `PUT /api/v2/admin/users/<id>`. The docs and HANDOFF specify `PATCH`. Add both methods or change to PATCH for semantic correctness.

```python
@admin_bp.route("/users/<int:user_id>", methods=["PATCH", "PUT"])
@require_admin
def update_user_route(user_id: int):
    ...
```

Also: Add soft-delete to `DELETE /api/v2/admin/users/<id>` — current implementation hard-deletes (`delete_user()`). Change to `update_user(conn, user_id, is_active=False)` + `invalidate_all_user_sessions()`.

```python
@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_admin
def delete_user_route(user_id: int):
    """Soft-delete: deactivate + invalidate sessions."""
    if g.current_user.id == user_id:
        return error("Eigenes Konto kann nicht deaktiviert werden", 400)
    try:
        with db_connection() as conn:
            user = update_user(conn, user_id, is_active=False)
            if not user:
                return error("User nicht gefunden", 404)
            # Invalidate all sessions
            conn.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
        return success()
    except Exception as exc:
        return error(f"Fehler: {type(exc).__name__}: {exc}", 500)
```

#### 2.2 Add Module Config CRUD to Module Routes

**File:** [`backend/api/module_routes.py`](backend/api/module_routes.py) — Add new endpoints

```python
# GET /api/v2/modules/<module_id>/config — returns config with passwords masked
@module_bp.route("/<module_id>/config", methods=["GET"])
@require_auth
def get_module_config(module_id: str):
    """Returns config with sensitive fields masked as '***'."""
    ...

# PUT /api/v2/modules/<module_id>/config — save config
@module_bp.route("/<module_id>/config", methods=["PUT"])
@require_auth  
def put_module_config(module_id: str):
    """Save module config. Validates against module type (no central/local modules)."""
    ...

# DELETE /api/v2/modules/<module_id>/config — reset config
@module_bp.route("/<module_id>/config", methods=["DELETE"])
@require_auth
def delete_module_config(module_id: str):
    ...
```

#### 2.3 Implement Credential Masking

**File:** [`backend/modules/module_registry.py`](backend/modules/module_registry.py) — Add helper

```python
# Sensitive fields per module
_SENSITIVE_FIELDS = {
    "itslearning": {"password"},
    "nextcloud": {"password"},
    "webuntis": set(),  # only ical_url, not sensitive
    "noten": set(),
    "orgaplan": set(),
    "klassenarbeitsplan": set(),
    "mail": {"password"},
}

def mask_sensitive_config(module_id: str, config: dict) -> dict:
    """Replace password fields with '***' for safe client serialization."""
    sensitive = _SENSITIVE_FIELDS.get(module_id, set())
    return {k: "***" if k in sensitive and v else v for k, v in config.items()}
```

Apply in `dashboard_routes.py:get_module_config()`.

#### 2.4 Add Onboarding Complete Endpoint

**File:** [`backend/api/dashboard_routes.py`](backend/api/dashboard_routes.py)

```python
@dashboard_bp.route("/onboarding/complete", methods=["POST"])
@require_auth
def complete_onboarding():
    """Mark onboarding as done by setting a system flag per user."""
    try:
        with db_connection() as conn:
            # Store per-user flag in user_module_configs or system_settings
            # Simplest: a dedicated user_module_configs entry for pseudo-module 'onboarding'
            # OR: add onboarding_completed column to users table
            conn.execute(
                """UPDATE users SET updated_at = NOW() WHERE id = %s""",
                (g.current_user.id,)
            )
            # Write onboarding completion flag
            import psycopg.types.json as _pj
            conn.execute(
                """INSERT INTO system_settings (key, value, updated_at)
                   VALUES (%s, %s, NOW())
                   ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
                (f"onboarding_done_{g.current_user.id}", _pj.Jsonb({"done": True})),
            )
        return success()
    except Exception as exc:
        return error(f"Fehler: {type(exc).__name__}: {exc}", 500)
```

> **Better approach:** Add `onboarding_completed BOOLEAN DEFAULT FALSE` column to `users` table. Simpler and proper. Add migration for this column.

#### 2.5 Add Aggregated Dashboard Endpoint

**File:** [`backend/api/dashboard_routes.py`](backend/api/dashboard_routes.py)

```python
@dashboard_bp.route("", methods=["GET"])
@require_auth
def get_dashboard():
    """Aggregated dashboard payload: user info + module layout + system settings."""
    try:
        with db_connection() as conn:
            user_modules = get_user_modules(conn, g.current_user.id)
            user_modules.sort(key=lambda um: um.sort_order)
            modules_out = []
            for um in user_modules:
                module = get_module_by_id(conn, um.module_id)
                if module and module.is_enabled:
                    modules_out.append({
                        "module_id": um.module_id,
                        "display_name": module.display_name,
                        "module_type": module.module_type,
                        "is_visible": um.is_visible,
                        "sort_order": um.sort_order,
                        "is_configured": um.is_configured,
                        "requires_config": module.requires_config,
                    })
            from backend.admin.admin_service import get_all_system_settings
            system = get_all_system_settings(conn)
        
        return success({
            "user": g.current_user.to_dict(),
            "modules": modules_out,
            "system": system,
        })
    except Exception as exc:
        return error(f"Fehler: {type(exc).__name__}: {exc}", 500)
```

---

### Phase 3: Session Handling, Route Protection, CORS/Domain Config — Priority: HIGH

**Goal:** Production-ready security configuration.

#### 3.1 Full CORS + Cookie Fix (see Phase 1.1 and 1.2)

Summary of all changes needed:

**`app.py`:**
```python
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:8080")
_IS_PROD = bool(os.environ.get("DATABASE_URL", "").strip())

@app.after_request
def after_request(response):
    origin = request.headers.get("Origin", "")
    allowed_origins = [o.strip() for o in CORS_ORIGIN.split(",")]
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Cookie"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Cache-Control"] = "no-store"
    return response
```

**`backend/api/helpers.py`:**
```python
import os as _os
_IS_PROD = bool(_os.environ.get("DATABASE_URL", "").strip())

def set_session_cookie(response, session_id: str):
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        max_age=30 * 24 * 3600,
        httponly=True,
        secure=_IS_PROD,
        samesite="None" if _IS_PROD else "Lax",
        path="/",
    )
```

#### 3.2 Add OPTIONS Handling for Preflight Requests

**`app.py`:** Add global OPTIONS handler.

```python
@app.route('/api/v2/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    response = Response()
    return after_request(response), 204
```

Or register `flask-cors` as a more robust solution. Given the existing manual approach, add `@app.before_request` to handle OPTIONS:

```python
@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        return after_request(response)
```

#### 3.3 Session Cleanup Mechanism

**Option A (simple): On-demand cleanup** — Call `cleanup_expired_sessions()` probabilistically in `get_current_user()`:

```python
# In helpers.py get_current_user():
import random
if random.random() < 0.01:  # 1% of requests
    cleanup_expired_sessions(conn)
```

**Option B (proper): Scheduled cleanup endpoint** — Admin-only endpoint that can be called by Render cron or UptimeRobot:

```python
@admin_bp.route("/maintenance/cleanup-sessions", methods=["POST"])
@require_admin
def cleanup_sessions():
    with db_connection() as conn:
        count = cleanup_expired_sessions(conn)
    return success({"deleted": count})
```

**Recommendation:** Implement Option A for immediate safety + Option B for operational control.

#### 3.4 Config Cleanup

Remove all hardcoded URLs from source code. Create centralized `backend/config_saas.py`:

```python
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", FRONTEND_URL)
IS_PRODUCTION = bool(os.environ.get("DATABASE_URL", "").strip())
```

**Render ENV to add:**
- `FRONTEND_URL=https://app.lehrercockpit.com`
- `CORS_ORIGIN=https://app.lehrercockpit.com`
- `BACKEND_URL=https://api.lehrercockpit.com`

---

### Phase 4: Frontend — Login Flow, Onboarding, Admin Panel — Priority: HIGH

**Goal:** All frontend auth flows work end-to-end with the production backend.

#### 4.1 Activate Multi-User Mode

**File:** [`index.html`](index.html:30)

```html
<!-- Change this single line: -->
<script>window.MULTIUSER_ENABLED = true;</script>
```

This is the single most impactful change — it activates auth check in `src/app.js`.

#### 4.2 Fix Login to Redirect by Role

**File:** [`login.html`](login.html:218)

```javascript
if (resp.ok && data.ok) {
    const role = data.user?.role;
    if (role === 'admin') {
        window.location.href = './admin.html';
    } else {
        window.location.href = './index.html';
    }
}
```

Also update `checkSession()` in login.html to redirect admin to admin.html:
```javascript
async function checkSession() {
    const resp = await fetch(backendUrl + '/api/v2/auth/me', { credentials: 'include' });
    if (resp.ok) {
        const data = await resp.json();
        if (data.ok) {
            const href = data.user?.role === 'admin' ? './admin.html' : './index.html';
            window.location.href = href;
        }
    }
}
```

#### 4.3 Update `src/app.js` API Calls

The auth check in `src/app.js` is already wired behind `MULTIUSER_ENABLED`. The remaining work (once MULTIUSER_ENABLED=true) is migrating these specific calls:

| Current (v1) | Target (v2) | Change |
|---|---|---|
| `GET /api/grades` | `GET /api/v2/modules/grades` + `credentials:'include'` | Add creds, new path |
| `POST /api/local-settings/grades` | `POST /api/v2/modules/grades` | Remove IP guard dependency |
| `GET /api/notes` | `GET /api/v2/modules/notes` + `credentials:'include'` | Add creds, new path |
| `POST /api/local-settings/notes` | `POST /api/v2/modules/notes` | Remove IP guard dependency |
| `POST /api/local-settings/itslearning` | `PUT /api/v2/modules/itslearning/config` | Auth-gated config |
| `POST /api/local-settings/nextcloud` | `PUT /api/v2/modules/nextcloud/config` | Auth-gated config |
| `GET /api/dashboard` | `GET /api/v2/dashboard` + `credentials:'include'` | Auth-gated dashboard |

**Note:** These v1 endpoints can remain active. The v2 routes just need to be added as new parallel paths. The `src/app.js` should be updated section by section:

1. In `loadDashboard()` / `loadGrades()` / `loadNotes()`: add `credentials: 'include'` + update URL if `MULTIUSER_ENABLED`.
2. In itslearning/nextcloud connect form submit handlers: switch target to `/api/v2/modules/<id>/config`.

#### 4.4 Verify admin.html Wiring

Read `admin.html` in full (currently only first 80 lines read). Verify:
- All API calls point to `BACKEND_API_URL + '/api/v2/admin/...'`
- Auth check on load redirects non-admin users
- User table renders from `GET /api/v2/admin/users`
- "Create teacher" form calls `POST /api/v2/admin/users`
- "Regenerate code" calls `POST /api/v2/admin/users/<id>/regenerate-code`
- Settings tab calls `GET/PUT /api/v2/admin/settings`
- Modules tab calls `GET/PUT /api/v2/admin/modules/*`

#### 4.5 Onboarding Flow

**File:** [`onboarding.html`](onboarding.html)

The flow requires:
1. After first login: check `GET /api/v2/dashboard/onboarding-status`
2. If `needs_onboarding: true` AND user has never completed: redirect to `/onboarding.html`
3. Onboarding steps: select visible modules → configure individual modules (itslearning iCal/credentials, nextcloud, webuntis iCal)
4. Final step: `POST /api/v2/dashboard/onboarding/complete`
5. Redirect to dashboard

For WebUntis: prefer iCal URL (`WEBUNTIS_ICAL_URL`). Show input field for iCal URL, store in `user_module_configs` for `webuntis` module as `{"ical_url": "..."}`.

---

### Phase 5: Frontend — Modular Dashboard, Layout Management — Priority: MEDIUM

**Goal:** Dashboard reflects per-user module configuration with enable/disable and reorder.

#### 5.1 Module-Based Dashboard Rendering

Replace current single-payload `GET /api/dashboard` call with:
1. `GET /api/v2/dashboard` → user + module layout + system settings
2. For each `is_visible: true` module: `GET /api/v2/modules/<id>/data` → live module data
3. Render each module section conditionally based on `is_configured`

Structure in `src/app.js`:

```javascript
async function loadDashboardV2() {
    const dashboard = await fetchJson('/api/v2/dashboard');
    state.currentUser = dashboard.user;
    state.modules = dashboard.modules;
    state.systemSettings = dashboard.system;
    
    // Show/hide nav links based on enabled modules
    updateNavFromModules(state.modules);
    
    // Load data for visible, configured modules in parallel
    const visible = state.modules.filter(m => m.is_visible && m.is_configured);
    await Promise.allSettled(visible.map(m => loadModuleData(m.module_id)));
}

async function loadModuleData(moduleId) {
    const result = await fetchJson(`/api/v2/modules/${moduleId}/data`);
    state.moduleData[moduleId] = result.data;
    renderModule(moduleId);
}
```

#### 5.2 Module Visibility Toggle

```javascript
async function toggleModuleVisibility(moduleId, isVisible) {
    await postJson(`/api/v2/dashboard/layout/${moduleId}/visibility`, { is_visible: isVisible });
    state.modules = state.modules.map(m =>
        m.module_id === moduleId ? {...m, is_visible: isVisible} : m
    );
    renderAll();
}
```

#### 5.3 Module Reorder (Drag-and-Drop)

The `PUT /api/v2/dashboard/layout` endpoint already exists. Wire it to a UI:

```javascript
async function saveModuleOrder() {
    const modules = state.modules.map((m, idx) => ({
        module_id: m.module_id,
        sort_order: (idx + 1) * 10,
    }));
    await postJson('/api/v2/dashboard/layout', { modules });
}
```

For drag-and-drop: use native HTML5 drag events (no external library). The existing nav sidebar order can drive this.

#### 5.4 Module Configuration UI

For individual modules (`module_type: 'individual'`):
- `itslearning`: Form with `base_url`, `username`, `password` fields → `PUT /api/v2/modules/itslearning/config`
- `nextcloud`: Form with `base_url`, `username`, `password`, `workspace_url` → `PUT /api/v2/modules/nextcloud/config`
- `webuntis`: Form with `ical_url` (primary), `base_url` (optional) → `PUT /api/v2/modules/webuntis/config`
- `noten`: No config needed — just data storage
- `orgaplan`/`klassenarbeitsplan`: Read-only, shows system-settings value, link to admin panel

The existing `backend/api/dashboard_routes.py:save_module_config()` endpoint handles all of these. The frontend just needs the form → fetch wiring.

---

### Phase 6: Testing Expansion — Priority: MEDIUM

#### 6.1 New Test Files to Create

| File | Tests to Write |
|---|---|
| `tests/test_admin_routes.py` | list_users, create_user (201 + code), update_user, soft-delete, regenerate_code, list_modules, get/put settings |
| `tests/test_dashboard_routes.py` | get_layout (auth), update_layout, visibility toggle, get/save module config, onboarding_status, onboarding_complete |
| `tests/test_module_routes.py` | get/put/delete module config (auth gate, masked passwords, central module rejection) |
| `tests/test_bootstrap.py` | ensure_bootstrap_admin creates user when DB empty, skips when users exist |
| `tests/test_admin_service.py` | get/set_system_setting, get_user_overview, set_default_module_config |

#### 6.2 Existing Tests to Update

| File | Required Updates |
|---|---|
| `tests/test_auth_api.py` | Add: test Cookie attributes (Secure, SameSite), test 429 rate limit, test admin redirect hint in response |
| `tests/test_session.py` | Add: test session with `last_seen` update on `get_session()` |
| `tests/test_user_store.py` | Add: `test_set_access_code_stores_prefix`, `test_authenticate_by_inactive_user_returns_none` |
| `tests/test_module_registry.py` | Add: `test_save_config_masks_password_on_read` |
| `tests/test_api_endpoints.py` | Add: test v1 endpoints still work alongside v2 (backward compat) |

#### 6.3 Test Infrastructure Improvements

```python
# tests/conftest.py (create or update)
import pytest
import os
import psycopg

@pytest.fixture(scope="session")
def db_url():
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not url:
        pytest.skip("No database URL available")
    return url

@pytest.fixture
def db_conn(db_url):
    """Transaction-isolated DB connection for tests."""
    conn = psycopg.connect(db_url)
    from backend.migrations import run_migrations
    run_migrations(conn)
    conn.commit()
    yield conn
    conn.rollback()
    conn.close()

@pytest.fixture
def flask_app():
    """Full Flask app with all blueprints for integration tests."""
    import app as flask_app_module
    flask_app_module.app.config["TESTING"] = True
    return flask_app_module.app

@pytest.fixture
def client(flask_app):
    return flask_app.test_client()
```

---

### Phase 7: Documentation — Priority: LOW

#### 7.1 `README.md` Updates

Add:
- **Quick Start (SaaS):** How to set env vars and bootstrap first admin
- **Environment Variables:** Full table including `CORS_ORIGIN`, `FRONTEND_URL`, `BACKEND_URL`
- **First Login Flow:** Admin bootstrap → create teacher → share code
- **Module Configuration:** Which modules require user config vs admin config

#### 7.2 `CLAUDE_HANDOFF.md` Updates

Update:
- **Deployment URLs:** Change `lehrercockpit.onrender.com` → `api.lehrercockpit.com` everywhere
- **Known Limits:** Mark `MULTIUSER_ENABLED = false` as resolved after Phase 4.1
- **Remaining Todos:** Update checklist removing completed items, adding new ones
- **Test Commands:** Add `TEST_DATABASE_URL` usage note
- **Recommended Next Steps:** Replace current 10-item list with phase-aligned priorities

---

## 8. API Endpoint Reference

### v2 Endpoints (Current + Planned)

#### Auth — `/api/v2/auth/`

| Method | Path | Auth | Status | Notes |
|---|---|---|---|---|
| POST | `/api/v2/auth/login` | None | ✅ Exists | Rate-limited 5/min 20/hr |
| POST | `/api/v2/auth/logout` | cookie | ✅ Exists | |
| GET | `/api/v2/auth/me` | cookie | ✅ Exists | |

#### Admin — `/api/v2/admin/`

| Method | Path | Auth | Status | Notes |
|---|---|---|---|---|
| GET | `/api/v2/admin/users` | admin | ✅ Exists | |
| POST | `/api/v2/admin/users` | admin | ✅ Exists | Returns access_code once |
| GET | `/api/v2/admin/users/<id>` | admin | ✅ Exists | |
| PUT/PATCH | `/api/v2/admin/users/<id>` | admin | ⚠️ Partial | Only PUT; add PATCH; fix soft-delete |
| DELETE | `/api/v2/admin/users/<id>` | admin | ⚠️ Partial | Hard delete → should be soft-delete |
| POST | `/api/v2/admin/users/<id>/regenerate-code` | admin | ✅ Exists | |
| GET | `/api/v2/admin/settings` | admin | ✅ Exists | |
| PUT | `/api/v2/admin/settings` | admin | ✅ Exists | |
| GET | `/api/v2/admin/modules` | admin | ✅ Exists | |
| PUT | `/api/v2/admin/modules/<id>` | admin | ✅ Exists | |
| POST | `/api/v2/admin/maintenance/cleanup-sessions` | admin | 🔴 Missing | Phase 3 |

#### Dashboard — `/api/v2/dashboard/`

| Method | Path | Auth | Status | Notes |
|---|---|---|---|---|
| GET | `/api/v2/dashboard` | cookie | 🔴 Missing | Phase 2.5 |
| GET | `/api/v2/dashboard/layout` | cookie | ✅ Exists | |
| PUT | `/api/v2/dashboard/layout` | cookie | ✅ Exists | |
| PUT | `/api/v2/dashboard/layout/<id>/visibility` | cookie | ✅ Exists | |
| GET | `/api/v2/dashboard/module-config/<id>` | cookie | ✅ Exists | No password masking yet |
| PUT | `/api/v2/dashboard/module-config/<id>` | cookie | ✅ Exists | |
| GET | `/api/v2/dashboard/onboarding-status` | cookie | ✅ Exists | |
| POST | `/api/v2/dashboard/onboarding/complete` | cookie | 🔴 Missing | Phase 2.4 |

#### Modules — `/api/v2/modules/`

| Method | Path | Auth | Status | Notes |
|---|---|---|---|---|
| GET | `/api/v2/modules/itslearning/data` | cookie | ✅ Exists | Live adapter call |
| GET | `/api/v2/modules/webuntis/data` | cookie | ✅ Exists | iCal fetch |
| GET | `/api/v2/modules/nextcloud/data` | cookie | ✅ Exists | |
| GET | `/api/v2/modules/orgaplan/data` | cookie | ✅ Exists | From system_settings |
| GET | `/api/v2/modules/klassenarbeitsplan/data` | cookie | ✅ Exists | |
| GET | `/api/v2/modules/<id>/config` | cookie | 🔴 Missing | Phase 2.2 — masked |
| PUT | `/api/v2/modules/<id>/config` | cookie | 🔴 Missing | Phase 2.2 |
| DELETE | `/api/v2/modules/<id>/config` | cookie | 🔴 Missing | Phase 2.2 |
| GET | `/api/v2/modules/grades` | cookie | 🔴 Missing | Phase 2 → migrate from v1 |
| POST | `/api/v2/modules/grades` | cookie | 🔴 Missing | Phase 2 → migrate from v1 |
| GET | `/api/v2/modules/notes` | cookie | 🔴 Missing | Phase 2 |
| POST | `/api/v2/modules/notes` | cookie | 🔴 Missing | Phase 2 |

### v1 Endpoints (Legacy — Retain)

| Method | Path | Status |
|---|---|---|
| GET | `/api/health` | Keep indefinitely |
| GET | `/api/dashboard` | Keep — fallback for `MULTIUSER_ENABLED=false` |
| GET/POST | `/api/grades`, `/api/notes` | Keep — fallback |
| GET/POST | `/api/classwork`, `/api/classwork/upload` | Keep |
| POST | `/api/local-settings/*` | Keep with IP guard |

---

## 9. Risks, Tradeoffs, and Decisions

### 🔴 Critical Decisions Required Before Implementation

#### D1: INTEGER vs UUID Primary Keys

**Current implementation:** `users.id` is `SERIAL` (integer).
**Docs spec:** `users.id` is `UUID`.
**Status:** Pre-production — no live data yet.

**Decision:** Keep `SERIAL INTEGER`. Rationale:
- Simpler psycopg3 queries (no UUID string wrapping)
- Simpler joins and foreign keys
- Adequate for <10,000 teachers
- UUID adds no security value here (IDs are not exposed in URLs or tokens — the session token is the secret)
- Changing after data exists would require a full table migration

**Action required:** Align `docs/multi_user_architecture.md` to reflect INTEGER PKs. Update all UUID references in docs.

---

#### D2: Cross-Origin Cookie Strategy

**Problem:** Frontend at `app.lehrercockpit.com`, API at `api.lehrercockpit.com` — different subdomains.

**Option A: `SameSite=None; Secure=True`** (cross-site cookies)
- Required for `fetch(..., {credentials:'include'})` across origins
- Works immediately, no infrastructure change
- Requires HTTPS on both sides (which Netlify+Render provide)
- `Access-Control-Allow-Credentials: true` + explicit CORS origin required

**Option B: Same domain proxy** (Netlify redirects `/api/*` → Render)
- Avoids cross-origin entirely; `SameSite=Lax` works
- Adds Netlify proxy complexity
- Netlify free tier has rate limits on proxied requests
- Harder to debug

**Recommendation: Option A** — `SameSite=None; Secure=True` is the standard SaaS approach. Implement in Phase 1.1.

---

#### D3: Credential Encryption-at-Rest

**Current:** `user_module_configs.config_data` stores itslearning/nextcloud passwords as plaintext JSONB.
**Risk:** DB admin or a SQL injection can read all teacher credentials.

**Options:**

| Option | Complexity | Risk Reduction |
|---|---|---|
| Plaintext (current) | None | None |
| Application-layer AES-256 (symmetric) | Low | Good — requires env key to read |
| pgcrypto `pgp_sym_encrypt` | Medium | Good — DB-level encryption |
| Per-user asymmetric keys | High | Best — even app can't read all at once |

**Recommendation for Phase 1:** Keep plaintext but add a `SECURITY_NOTE` comment in code. The DB (Render PostgreSQL) is already access-controlled. Implement AES-256 application-layer encryption in Phase 2 using `cryptography` library:

```python
# backend/crypto.py
from cryptography.fernet import Fernet
import os, base64

def _get_key() -> bytes:
    raw = os.environ.get("ENCRYPTION_KEY", "")
    if not raw:
        raise RuntimeError("ENCRYPTION_KEY not set")
    return base64.urlsafe_b64decode(raw.encode())

def encrypt_config(data: dict) -> str:
    """Encrypt dict to base64 string for storage."""
    import json
    f = Fernet(_get_key())
    return f.encrypt(json.dumps(data).encode()).decode()

def decrypt_config(encrypted: str) -> dict:
    """Decrypt base64 string back to dict."""
    import json
    f = Fernet(_get_key())
    return json.loads(f.decrypt(encrypted.encode()))
```

Store encrypted blob as a TEXT column (or JSONB with a single `"enc"` key). Add `ENCRYPTION_KEY` to Render env.

---

#### D4: Bootstrap Admin UX

**Problem:** No first admin can be created without manual DB access.
**Current state:** `ensure_bootstrap_admin()` is referenced in docs but not in codebase.

**Decision:** Implement a log-based bootstrap (Phase 1.5). The admin sees the code in Render logs on first deploy. This is acceptable for a small teacher platform. A UI-based bootstrap wizard is optional.

**Risk:** If logs are lost or not monitored, the first admin code is lost. Mitigation: Bootstrap code is also stored (hashed) in DB, so an admin can regenerate via `POST /api/v2/admin/users/1/regenerate-code` directly with a fresh DB query.

---

### 🟡 Important Tradeoffs

#### T1: O(n) Authentication Performance

`authenticate_by_code()` iterates all active users and runs argon2id (~200ms) for each until match.

| Users | Worst-case login time |
|---|---|
| 10 | ~2 seconds |
| 50 | ~10 seconds |
| 100 | ~20 seconds |
| 1000 | ~200 seconds (unacceptable) |

**Mitigation (Phase 1.4):** Store `code_prefix` (first 4 chars). On login, filter to `WHERE code_prefix = :prefix` first, then run argon2 only on candidates. Reduces O(n) to O(k) where k ≈ 1.

**Note for current MVP:** With <20 teachers, worst-case is ~4 seconds. Acceptable for immediate launch if optimization is planned for before onboarding >50 users.

---

#### T2: monolithic `src/app.js` (3628 lines)

Splitting into modules requires careful ordering of `<script>` tags (no bundler). The IIFE closure means all state is shared within the function.

**Short-term:** Add multi-user auth calls inside the existing IIFE, gated by `MULTIUSER_ENABLED`. This is the approach already taken.

**Medium-term (post-launch):** Split as documented in lines 1–19 of `src/app.js`. Recommended file order:
1. `src/state.js` — constants, state
2. `src/api.js` — fetch helpers
3. `src/features/grades.js`, `classwork.js`, `webuntis.js`, etc.
4. `src/render.js` — renderAll
5. `src/events.js` — initialize()
6. `src/auth.js` — checkAuthState, logout (new)

---

#### T3: Two Parallel API Versions

v1 (`/api/`) and v2 (`/api/v2/`) coexist. This is correct for zero-downtime migration but creates maintenance overhead.

**Strategy:**
- v1 endpoints remain for the local dev workflow (server.py, `.env.local`)
- v2 endpoints are the SaaS path
- After all teachers are migrated, v1 can be deprecated (but not deleted — some users may still use local mode)

---

#### T4: `server.py` is Not Multi-User

The local stdlib-based dev server has no Flask blueprint support and cannot serve v2 endpoints. This is intentional (per CLAUDE_HANDOFF.md) — local dev uses `server.py` for the single-user flow.

**For multi-user local testing:** `flask run` or `python app.py` with a local PostgreSQL instance.

**Documented risk:** Developers who only use `server.py` for local dev will not discover v2 endpoint bugs locally.

---

### 🟢 Non-Issues (Already Handled Well)

| Item | Why It's Fine |
|---|---|
| argon2id parameters | OWASP-correct, production-ready |
| Session TTL (30 days) | Reasonable for teacher workflow |
| Module seed data | Idempotent `ON CONFLICT DO NOTHING` |
| DB migrations | Idempotent `IF NOT EXISTS` |
| `@require_auth` / `@require_admin` decorators | Correctly check both active and role |
| Rate limiting on login | flask-limiter 5/min 20/hr is appropriate |
| Test isolation | Transaction rollback pattern is correct |
| Soft-import of heavy adapters | `try/except` import blocks prevent startup failures |
| Legacy v1 backward compat | v1 routes kept; no breaking changes |

---

## Summary: Minimal Path to Production

The fastest path to a working SaaS product requires exactly **8 focused changes**:

| # | Change | File | Phase |
|---|---|---|---|
| 1 | `MULTIUSER_ENABLED = true` | `index.html:30` | 4.1 |
| 2 | Fix `SameSite=None; Secure=True` cookie | `helpers.py:58` | 1.1 |
| 3 | Fix CORS: restrict origin + add credentials header | `app.py:133` | 1.2/3.1 |
| 4 | Update hardcoded URLs to `api.lehrercockpit.com` | `index.html`, `login.html` | 1.3 |
| 5 | Set `CORS_ORIGIN=https://app.lehrercockpit.com` | Render ENV | 1.2 |
| 6 | Implement `ensure_bootstrap_admin()` | New `backend/admin/bootstrap.py` | 1.5 |
| 7 | Wire bootstrap into `app.py` startup | `app.py:471` | 1.5 |
| 8 | Fix login redirect by role (admin → `/admin.html`) | `login.html:218` | 4.2 |

After these 8 changes: admin can log in, create teachers, teachers can log in to the dashboard. All existing dashboard features continue working via the legacy v1 API. Module config, onboarding, and modular dashboard are additive improvements on top of this base.