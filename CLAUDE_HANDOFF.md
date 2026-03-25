# Claude Handoff — Lehrercockpit

> Last updated: 2026-03-25 (Phase 9h — final documentation update)
>
> **Purpose:** This file onboards a new AI assistant to the Lehrercockpit project. Read this first before touching any code. It describes the actual implemented state, not aspirational plans.

---

## 1. Project Identity

**Lehrercockpit** is a production SaaS multi-user teacher cockpit for Berlin schools. It is not an MVP or prototype — all core backend infrastructure, API routes, auth system, and frontend pages are implemented and tested.

Each teacher gets a personal dashboard with individually configured modules (WebUntis timetable, itslearning LMS, Nextcloud files, grades, notes). An admin manages access codes and school-wide resources (Orgaplan PDF, Klassenarbeitsplan).

**GitHub:** `https://github.com/eyenetic/lehrercockpit` (branch: `main`)

---

## 2. Current Architecture State

| Layer | Technology | State |
|---|---|---|
| Frontend | Vanilla HTML/CSS/JS (no build step) | ✅ Production-ready |
| Backend | Python 3.11, Flask, gunicorn | ✅ Production-ready |
| Database | PostgreSQL via psycopg (psycopg3) | ✅ Migrations run at startup |
| Auth | argon2-cffi (argon2id), custom session table | ✅ Implemented |
| Rate limiting | flask-limiter | ✅ On login endpoint |
| Frontend host | Netlify (`https://app.lehrercockpit.com`) | ✅ Auto-deploy on `main` |
| Backend host | Render Docker/gunicorn (`https://api.lehrercockpit.com`) | ✅ |
| CI | GitHub Actions (`.github/workflows/ci.yml`) | ✅ PostgreSQL 15 service container; full syntax check; encryption key generated |

### What IS implemented

- DB schema, idempotent migrations, module seed data
- argon2id access code generation/hashing/verification
- Session management (create/get/refresh/delete/cleanup)
- Full User CRUD (`backend/users/user_store.py`, `user_service.py`)
- Module registry with per-user visibility/order/config (`backend/modules/module_registry.py`)
- Admin service: system settings, module defaults, user overview (`backend/admin/admin_service.py`)
- Bootstrap admin creation on first deploy (`backend/admin/bootstrap.py`) — hardened with PostgreSQL advisory lock, writes `bootstrap_completed_at` and `bootstrap_pending_rotation` to `system_settings`, logs `bootstrap_created` to `audit_log`
- All 4 Flask API blueprints: auth, admin, dashboard, module routes
- Auth decorators: `@require_auth`, `@require_admin`
- Rate-limited login endpoint (5/min, 20/hr per IP)
- Cookie management: `Secure=True`, `SameSite=None` in production, `SameSite=Lax` in dev
- CORS: restricted to configured `CORS_ORIGIN`, with `Access-Control-Allow-Credentials: true`
- Frontend pages: `login.html` (functional), `admin.html` (1044 lines, full tab UI + audit log tab), `onboarding.html`, `index.html` (`MULTIUSER_ENABLED=true`, auth gate active)
- **Phase 8 — Fernet encryption** for `user_module_configs` sensitive fields (`backend/crypto.py`); `enc:` prefix storage format; backward compatible
- **Phase 8 — `audit_log` table** + `log_audit_event()` helper (`backend/migrations.py`); login success/failure events logged in `auth_routes.py`
- **Phase 8 — `mask_config()`** centralized in `backend/api/helpers.py`; applied in both `dashboard_routes.py` and `module_routes.py`
- **Phase 8 — `src/api-client.js`** unified `window.LehrerAPI` API layer; all requests use `credentials: 'include'`
- **Phase 8 — `src/modules/dashboard-manager.js`** `DashboardManager` extracted from monolithic `src/app.js`
- **Phase 8 — `saveItslearningCredentials` / `saveNextcloudCredentials`** always use v2 path (no more if/else)
- **Phase 8 — v1 endpoints** clearly marked with `LEGACY v1 API ENDPOINTS` comment block; responses get `X-API-Version: v1-legacy` header
- **Phase 8 — CI** PostgreSQL 15 service container; full syntax check for all `backend/**/*.py`; Fernet key generated; `DATABASE_URL` set in CI
- **Phase 8 — Tests** 21 new tests (`tests/test_crypto.py`) + 11 tests (`tests/test_frontend_structure.py`) + extensions to `test_bootstrap.py`, `test_auth_api.py`, `test_module_registry.py`
- Full test suite for core modules
- **Phase 9 — Per-user `grades` and `class_notes` DB tables** + v2 CRUD API (`/api/v2/modules/noten/*`): GET data, POST grade, DELETE grade, POST note, DELETE note
- **Phase 9 — `code_prefix` O(1) auth optimization**: `get_code_prefix()` in `access_code.py`; `PREFIX_LENGTH=8`; stored in `user_access_codes.code_prefix`; `authenticate_by_code()` pre-filters by prefix (backward compatible with NULL-prefix legacy codes)
- **Phase 9 — `GET /api/v2/admin/audit-log`** with pagination (`limit`/`offset`) and `event_type` filter; returns `{events, total, limit, offset}`
- **Phase 9 — Audit events** for `teacher_created`, `teacher_deactivated`, `code_rotated` in `admin_routes.py`
- **Phase 9 — `scripts/backfill_encryption.py`** — idempotent, `--dry-run`, `--verbose`, round-trip verified, safe to re-run
- **Phase 9 — `src/features/grades.js`** extracted from `src/app.js`; exposes `window.LehrerGrades`; all grades/notes functions delegate to it
- **Phase 9 — Admin audit log UI tab** in `admin.html` (`data-tab="audit"`, `id="tab-audit"`); table + pagination + event_type filter
- **Phase 9 — `loadDashboard()`** in `src/app.js` overlays v2 grades/notes data on v1 payload

### What is NOT yet done (known technical debt)

- `src/app.js` still calls legacy `GET /api/dashboard` (v1) for the main dashboard payload (webuntis, itslearning, orgaplan, classwork) — v2 per-module migration pending
- `user_module_configs.config_data` stores credentials as **plaintext JSONB** if `ENCRYPTION_KEY` is not set; run `scripts/backfill_encryption.py` on Render after setting the key
- `backfill_encryption.py` must be run manually on Render after `ENCRYPTION_KEY` is first set
- `code_prefix` backfill for existing access codes is impossible (argon2id one-way) — must rotate codes to get prefix-accelerated login
- No drag-and-drop module reorder (uses number inputs)
- No email-based password reset (by design — access codes are the auth mechanism)

---

## 3. Authentication System

### Access Code Generation

File: [`backend/auth/access_code.py`](backend/auth/access_code.py)

- `generate_code()` → 32-char alphanumeric (`string.ascii_letters + string.digits`)
- `hash_code(code)` → argon2id hash string
- `verify_code(code, hash)` → bool (timing-safe)
- `needs_rehash(hash)` → bool

argon2id parameters:
```python
PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, hash_len=32, salt_len=16)
```

### Session Management

File: [`backend/auth/session.py`](backend/auth/session.py)

```python
@dataclass
class Session:
    id: str          # UUID string (PK in sessions table)
    user_id: int     # INTEGER FK to users.id
    created_at: datetime
    expires_at: datetime   # NOW() + 30 days
    last_seen: datetime
```

- `create_session(conn, user_id)` → `Session`
- `get_session(conn, session_id)` → `Session | None` — validates expiry, does NOT refresh
- `refresh_session(conn, session_id)` → `bool` — updates `last_seen`
- `delete_session(conn, session_id)` — logout
- `cleanup_expired_sessions(conn)` → `int` — count deleted

### Cookie Settings

File: [`backend/api/helpers.py`](backend/api/helpers.py)

```python
_IS_PROD = bool(os.environ.get("DATABASE_URL", "").strip())

response.set_cookie(
    "lc_session",
    session_id,
    max_age=30 * 24 * 3600,
    httponly=True,
    secure=_IS_PROD,              # True on Render
    samesite="None" if _IS_PROD else "Lax",  # None required for cross-origin
    path="/",
)
```

`SameSite=None; Secure=True` is required because Netlify (`app.lehrercockpit.com`) makes `fetch(..., {credentials: 'include'})` calls to Render (`api.lehrercockpit.com`) — a cross-origin request.

### Auth Decorators

```python
# In backend/api/helpers.py
def require_auth(f):   # sets g.current_user, returns 401 if no valid session
def require_admin(f):  # calls require_auth + checks g.current_user.is_admin, returns 403
```

`get_current_user()` reads the `lc_session` cookie, calls `get_session()` + `refresh_session()` + `get_user_by_id()`.

### Bootstrap Flow

File: [`backend/admin/bootstrap.py`](backend/admin/bootstrap.py)

`ensure_bootstrap_admin()` — called from `app.py` at startup when `DATABASE_URL` is set:
1. Acquires a **PostgreSQL advisory lock** (`pg_advisory_lock(12345678)`) — prevents TOCTOU race with multiple gunicorn workers
2. Counts users with `role='admin'` (inside the lock)
3. If zero: calls `create_teacher(conn, "Bootstrap", "Admin", role="admin")`
4. Logs `bootstrap_created` event to `audit_log`
5. Writes `bootstrap_completed_at` and `bootstrap_pending_rotation = "true"` to `system_settings`
6. Prints the plaintext code to stdout (Render logs) — **only time it's visible**
7. Releases the advisory lock
8. Idempotent: does nothing if any admin exists

Login request body: `{"code": "..."}` (field is `code`, not `access_code`).

---

## 4. Database Schema

**All implemented in [`backend/migrations.py`](backend/migrations.py)**. Migrations run idempotently at startup.

```sql
-- Existing (from persistence.py)
CREATE TABLE IF NOT EXISTS app_state (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Multi-user tables (INTEGER PKs, not UUID — deliberate decision)
CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name  TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'teacher' CHECK (role IN ('admin', 'teacher')),
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_access_codes (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash   TEXT NOT NULL,            -- argon2id hash
    code_prefix TEXT NOT NULL DEFAULT '', -- first 8 chars of plaintext, uppercased (Phase 9)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)                       -- max 1 active code per user
);
-- idx_access_codes_prefix ON user_access_codes(code_prefix) (Phase 9)

CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,   -- UUID string
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS modules (
    id              TEXT PRIMARY KEY,    -- e.g. 'itslearning'
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
    config_data JSONB NOT NULL DEFAULT '{}',  -- encrypted with enc: prefix when ENCRYPTION_KEY is set
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, module_id)
);

CREATE TABLE IF NOT EXISTS system_settings (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### audit_log table (Phase 8)

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id          SERIAL PRIMARY KEY,
    event_type  VARCHAR(64) NOT NULL,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ip_address  VARCHAR(64),
    details     JSONB DEFAULT '{}',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
-- Indexes: idx_audit_log_user_id, idx_audit_log_event_type, idx_audit_log_created_at
```

Currently logged events: `login_success`, `login_failure`, `bootstrap_created`, `teacher_created`, `teacher_deactivated`, `code_rotated`.

### grades table (Phase 9)

```sql
CREATE TABLE IF NOT EXISTS grades (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_name  TEXT NOT NULL,
    subject     TEXT NOT NULL DEFAULT '',
    grade_value TEXT NOT NULL DEFAULT '',
    grade_date  DATE,
    note        TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- idx_grades_user_id ON grades(user_id)
```

### class_notes table (Phase 9)

```sql
CREATE TABLE IF NOT EXISTS class_notes (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_name TEXT NOT NULL,
    note_text  TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, class_name)
);
-- idx_class_notes_user_id ON class_notes(user_id)
```

**Important:** `users.id` is `SERIAL INTEGER`, not UUID. This diverges from the design docs but is the implemented reality. All FKs are INTEGER.

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

---

## 5. API Reference

All v2 endpoints are under `/api/v2/`. Response format: `{"ok": true, ...}` on success, `{"error": "..."}` on failure.

### Auth

| Method | Path | Auth | Response shape |
|---|---|---|---|
| POST | `/api/v2/auth/login` | None | `{"ok": true, "user": {id, first_name, last_name, full_name, role, is_active, is_admin}}` + sets `lc_session` cookie |
| POST | `/api/v2/auth/logout` | cookie | `{"ok": true}` + clears cookie |
| GET | `/api/v2/auth/me` | cookie | `{"ok": true, "user": {...}}` |

Login body: `{"code": "..."}` — field is `code`, not `access_code`. Min length 8 chars.

Rate limit: 5/minute, 20/hour per IP (flask-limiter). Returns HTTP 429 on excess.

### Admin

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/v2/admin/users` | admin | `{"ok": true, "users": [...]}` — includes `module_count`, `has_access_code` |
| POST | `/api/v2/admin/users` | admin | Body: `{first_name, last_name, role}` or `{display_name, role}`. Returns `{"ok": true, "user": {...}, "access_code": "..."}` (201) |
| GET | `/api/v2/admin/users/<id>` | admin | `{"ok": true, "user": {...}}` |
| PUT/PATCH | `/api/v2/admin/users/<id>` | admin | Partial update: any of `{first_name, last_name, role, is_active}` |
| POST | `/api/v2/admin/users/<id>/deactivate` | admin | Soft-delete: sets `is_active=False`, deletes all user sessions |
| DELETE | `/api/v2/admin/users/<id>` | admin | Hard-delete. Cannot delete own account. |
| POST | `/api/v2/admin/users/<id>/rotate-code` | admin | Returns `{"ok": true, "access_code": "..."}` (one-time) |
| POST | `/api/v2/admin/users/<id>/regenerate-code` | admin | Alias for rotate-code |
| GET | `/api/v2/admin/users/<id>/modules` | admin | Module status for one user |
| GET | `/api/v2/admin/modules` | admin | All modules with global config |
| PUT | `/api/v2/admin/modules/<id>` | admin | Update `{is_enabled, default_visible, default_order}` |
| GET/PUT | `/api/v2/admin/modules/defaults` | admin | Default module order and enabled list |
| GET | `/api/v2/admin/settings` | admin | `{"ok": true, "settings": {key: value, ...}}` |
| PUT | `/api/v2/admin/settings` | admin | Body: `{"key": "...", "value": ...}` |
| PUT | `/api/v2/admin/settings/<key>` | admin | Body: `{"value": ...}` |
| POST | `/api/v2/admin/maintenance/cleanup-sessions` | admin | `{"ok": true, "deleted": int}` |

### Dashboard

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/v2/dashboard` | cookie | `{"ok": true, "user": {...}, "modules": [...], "onboarding_complete": bool}` |
| GET | `/api/v2/dashboard/layout` | cookie | `{"ok": true, "modules": [{module_id, is_visible, sort_order, is_configured, display_name, module_type, requires_config}]}` |
| PUT | `/api/v2/dashboard/layout` | cookie | Body: `{"modules": [{module_id, sort_order, enabled}]}` |
| PUT | `/api/v2/dashboard/layout/<id>/visibility` | cookie | Body: `{"is_visible": bool}` |
| GET | `/api/v2/dashboard/module-config/<id>` | cookie | Returns config with sensitive fields masked as `***` (Phase 8: masking now applied here too) |
| PUT | `/api/v2/dashboard/module-config/<id>` | cookie | Body: any JSON object |
| GET | `/api/v2/dashboard/onboarding-status` | cookie | `{"ok": true, "needs_onboarding": bool, "unconfigured_modules": [...], "onboarding_complete": bool}` |
| POST | `/api/v2/dashboard/onboarding/complete` | cookie | Stores `system_settings[f"onboarding_done_{user_id}"] = {"done": true}` |

### Modules

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/v2/modules` | None | Public — all modules |
| GET | `/api/v2/modules/defaults` | None | Public — default-enabled modules |
| GET | `/api/v2/modules/<id>/config` | cookie | **Passwords masked as `***`** |
| PUT | `/api/v2/modules/<id>/config` | cookie | Rejects `central`/`local` modules (403) |
| DELETE | `/api/v2/modules/<id>/config` | cookie | Resets to `{}`, sets `is_configured=False` |
| GET | `/api/v2/modules/itslearning/data` | cookie | Calls `fetch_itslearning_sync()` using stored config |
| GET | `/api/v2/modules/webuntis/data` | cookie | Calls `fetch_webuntis_sync()` |
| GET | `/api/v2/modules/nextcloud/data` | cookie | Calls `fetch_nextcloud_sync()` |
| GET | `/api/v2/modules/orgaplan/data` | cookie | Reads `system_settings.orgaplan_url` + `orgaplan_pdf_url` |
| GET | `/api/v2/modules/klassenarbeitsplan/data` | cookie | Reads `system_settings.klassenarbeitsplan_url` + local XLSX |
| GET | `/api/v2/modules/noten/data` | cookie | Returns `{grades: [...], notes: [...]}` for current user (Phase 9) |
| POST | `/api/v2/modules/noten/grades` | cookie | Body: `{class_name, subject, grade_value, grade_date?, note?, id?}` → `{grade: {...}}` (Phase 9) |
| DELETE | `/api/v2/modules/noten/grades/<id>` | cookie | Ownership enforced (`AND user_id = %s`) — 404 if wrong user (Phase 9) |
| POST | `/api/v2/modules/noten/notes` | cookie | Body: `{class_name, note_text}` — upsert by user_id+class_name → `{note: {...}}` (Phase 9) |
| DELETE | `/api/v2/modules/noten/notes/<class_name>` | cookie | 404 if not found (Phase 9) |

### Admin (additional Phase 9)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/v2/admin/audit-log` | admin | `{events, total, limit, offset}` — query params: `limit` (max 200), `offset`, `event_type` |

**Credential masking** — centralized in `backend/api/helpers.py:mask_config()` (Phase 8):
```python
_SENSITIVE_PATTERNS = {"password", "secret", "token", "credential"}
# Any config key whose lowercase name contains one of these patterns → value replaced with "***"
# Applied in both dashboard_routes.py and module_routes.py
```

---

## 6. Module Registry

All module logic lives in [`backend/modules/module_registry.py`](backend/modules/module_registry.py).

Key dataclasses:

```python
@dataclass
class Module:
    id: str; display_name: str; description: str
    module_type: str  # 'individual' | 'central' | 'local'
    is_enabled: bool; default_visible: bool; default_order: int; requires_config: bool

@dataclass
class UserModule:
    id: int; user_id: int; module_id: str
    is_visible: bool; sort_order: int; is_configured: bool
```

Key functions:
- `get_all_modules(conn)` — all enabled modules, sorted by `default_order`
- `get_module_by_id(conn, module_id)` — single module lookup
- `get_user_modules(conn, user_id)` — joins `user_modules` with `modules`, filtered to enabled
- `initialize_user_modules(conn, user_id)` — creates `user_modules` rows for all enabled modules (idempotent via `ON CONFLICT DO NOTHING`)
- `save_user_module_config(conn, user_id, module_id, config_data)` — upserts `user_module_configs`, sets `is_configured=True`
- `get_user_module_config(conn, user_id, module_id)` — returns config dict or `{}`
- `update_user_module_visibility(conn, user_id, module_id, is_visible)` — toggles visibility
- `update_user_module_order(conn, user_id, module_orders)` — batch sort_order update
- `update_user_module(conn, user_id, module_id, **fields)` — generic update (enabled/is_visible/sort_order)

---

## 7. Admin Workflow (Step by Step)

### Bootstrap

1. First deploy with `DATABASE_URL` set
2. `app.py` calls `run_all_migrations()` then `ensure_bootstrap_admin()`
3. Render logs show the bootstrap access code
4. Admin navigates to `https://app.lehrercockpit.com/login.html`
5. Enters the bootstrap code
6. Redirected to `admin.html` (admin role detected in `login.html` JS)
7. Updates their name via the admin panel user edit form

### Create Teacher

1. Admin logs in → `admin.html` loads via `GET /api/v2/auth/me` check
2. Admin panel → Users tab → "Neue Lehrkraft anlegen"
3. `POST /api/v2/admin/users` with `{first_name, last_name, role: "teacher"}`
4. Backend calls `create_teacher(conn, first_name, last_name, role)` then `initialize_user_modules(conn, user.id)`
5. Response: `{ok: true, user: {...}, access_code: "..."}`
6. Admin copies the code and delivers it securely to the teacher

### Teacher First Login

1. Teacher visits `/login.html`
2. `POST /api/v2/auth/login` with `{"code": "..."}` → session cookie set
3. `login.html` checks `data.user.role` — if admin: redirect to `admin.html`, else to `index.html`
4. `index.html` (if `MULTIUSER_ENABLED=true`) calls `GET /api/v2/auth/me` to verify auth
5. `GET /api/v2/dashboard/onboarding-status` → if `needs_onboarding: true` → redirect to `onboarding.html`
6. After onboarding: `POST /api/v2/dashboard/onboarding/complete`
7. Dashboard at `/`

---

## 8. Frontend Pages

| File | Purpose | Key API calls |
|---|---|---|
| [`login.html`](login.html) | Access code entry, session check, role-based redirect | `POST /api/v2/auth/login`, `GET /api/v2/auth/me` |
| [`onboarding.html`](onboarding.html) | Multi-step first-time setup: select modules, enter credentials | `GET /api/v2/dashboard/layout`, `PUT /api/v2/dashboard/module-config/<id>`, `POST /api/v2/dashboard/onboarding/complete` |
| [`admin.html`](admin.html) | Admin panel: user table, code generation, settings, module defaults | All `/api/v2/admin/*` endpoints |
| [`index.html`](index.html) | Main cockpit dashboard | `GET /api/v2/auth/me`, legacy `GET /api/dashboard` |
| [`src/api-client.js`](src/api-client.js) | Unified API layer (`window.LehrerAPI`); all requests use `credentials:'include'`; v2 and v1 legacy paths separated | Loaded first before other scripts |
| [`src/modules/dashboard-manager.js`](src/modules/dashboard-manager.js) | `DashboardManager` — module layout management, extracted from `src/app.js` (Phase 8d) | Depends on `window.LehrerAPI` |
| [`src/features/grades.js`](src/features/grades.js) | Grades/notes module (Phase 9e). Exposes `window.LehrerGrades`. All grade/note functions extracted from `src/app.js`. | Depends on `window.LehrerAPI` |
| [`src/app.js`](src/app.js) | IIFE: dashboard logic, auth check, module rendering. Delegates grades/notes to `window.LehrerGrades`. | `GET /api/dashboard` (legacy v1), noten v2, `PUT /api/v2/modules/*/config` |

### Script load order in `index.html` (must not change):

```html
<script src="src/api-client.js"></script>              <!-- 1: window.LehrerAPI -->
<script src="src/modules/dashboard-manager.js"></script>  <!-- 2: window.DashboardManager -->
<script src="src/features/grades.js"></script>         <!-- 3: window.LehrerGrades (Phase 9) -->
<script src="src/app.js"></script>                     <!-- 4: main IIFE -->
```

### `index.html` flag (Phase 8):

```javascript
window.MULTIUSER_ENABLED = true; // ← set in Phase 8f; auth gate is now active
```

### `src/app.js` architecture notes:

- Single IIFE pattern — all state, rendering, and events in one closure
- Auth check, user context, and logout button gated by `MULTIUSER_ENABLED` (now `true`)
- Grades/notes functions delegate to `window.LehrerGrades` (Phase 9): `loadGradebook()`, `loadNotes()`, `saveGradeEntry()`, `deleteGradeEntry()`, `saveClassNote()`, `clearClassNote()`
- `saveItslearningCredentials()` / `saveNextcloudCredentials()` always use v2 path (`PUT /api/v2/modules/*/config`)
- `loadDashboard()` overlays v2 noten data on v1 payload after loading
- Further extraction (`src/features/webuntis.js`) is a documented next step

---

## 9. Test Suite

### Running Tests

```bash
# All tests (DB tests skip without TEST_DATABASE_URL):
python -m pytest tests/ -v --tb=short

# Non-DB only:
python -m pytest tests/ -v -k "not db" --tb=short

# With database:
TEST_DATABASE_URL="postgresql://..." python -m pytest tests/ -v --tb=short
```

### Test Files

| File | Count | DB | Notes |
|---|---|---|---|
| `tests/test_access_code.py` | 19 | No | generate, hash, verify, needs_rehash + get_code_prefix (Phase 9) |
| `tests/test_user_store.py` | 13 | Yes | Full user CRUD, access code ops |
| `tests/test_user_service.py` | 18 | Yes | create_teacher, authenticate_by_code |
| `tests/test_session.py` | 7 | Yes | create, get, refresh, delete, cleanup |
| `tests/test_module_registry.py` | 11 | Yes | Module CRUD, user_modules, config |
| `tests/test_crypto.py` | 21 | No | encrypt/decrypt/round-trip/backward-compat |
| `tests/test_frontend_structure.py` | 18 | No | Script extraction, load order + Phase 9 grades.js/audit-log (Phase 9) |
| `tests/test_auth_api.py` | 8 | No | Mocked DB — login/logout/me + audit log events |
| `tests/test_admin_routes.py` | varies | No/Yes | Admin endpoint integration + audit-log tests (Phase 9) |
| `tests/test_admin_service.py` | varies | Yes | System settings, user overview |
| `tests/test_bootstrap.py` | varies | Yes | Bootstrap + advisory lock + system_settings flags |
| `tests/test_module_routes.py` | varies | No/Yes | Module config CRUD, encryption, noten v2 endpoints (Phase 9) |
| `tests/test_grades_notes_v2.py` | varies | Mixed | Service layer unit tests + DB integration (Phase 9) |
| `tests/test_backfill.py` | varies | No | backfill_encryption.py: compile, dry-run, skip-encrypted, live-update (Phase 9) |
| `tests/test_api_endpoints.py` | — | No | Legacy v1 endpoint smoke tests |
| `tests/test_grades_store.py` | — | Partial | Local file store |
| `tests/test_notes_store.py` | — | Partial | Local file store |
| `tests/test_classwork_cache.py` | — | No | Classwork upload/parse |
| `tests/test_persistence.py` | — | No | JsonFileStore/DbStore abstraction |

### DB test skip pattern

```ini
# pytest.ini
[pytest]
markers =
    db: marks tests requiring a database connection
```

DB fixtures auto-skip if `TEST_DATABASE_URL` is not set.

### CI (GitHub Actions)

`.github/workflows/ci.yml` runs two jobs:
1. **Test (no DB):** `py_compile` syntax check for all `backend/**/*.py` + `pytest -k "not db"`; generates a Fernet key for crypto tests
2. **Test (with DB — `test-db` job):** Full `pytest` with a PostgreSQL 15 service container — no external secrets needed; `DATABASE_URL` is set automatically from the ephemeral CI database

---

## 10. Environment & Deployment

### Required Environment Variables (Render)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string |
| `SECRET_KEY` | ✅ Yes | Flask session key (32+ bytes) |
| `CORS_ORIGIN` | ✅ Yes | `https://app.lehrercockpit.com` |
| `ENCRYPTION_KEY` | ✅ **Strongly recommended** | Fernet key for credential encryption at rest. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Without it, passwords are stored as plaintext. |
| `LEHRERCOCKPIT_ENV` | Recommended | Set to `production` |
| `FRONTEND_URL` | Recommended | `https://app.lehrercockpit.com` |
| `API_URL` | Recommended | `https://api.lehrercockpit.com` |

`_IS_PROD` is derived from `bool(DATABASE_URL)` in `helpers.py` — not a separate flag.

### Cookie and CORS in Production

`app.py` `after_request` sets CORS headers:
- `Access-Control-Allow-Origin`: exact matching origin (never `*`) if in `CORS_ORIGIN` list
- `Access-Control-Allow-Credentials: true` (required for `credentials: 'include'`)
- `Vary: Origin`

`helpers.py` `set_session_cookie()`:
- `secure=True`, `samesite="None"` when `DATABASE_URL` is set
- This is the correct configuration for cross-origin Netlify → Render requests

### Netlify Config

[`netlify.toml`](netlify.toml) — no build command (static files only). The backend (`api.lehrercockpit.com`) is a separate Render service.

### Render Config

- `Dockerfile` — Docker build, no Playwright, no system deps beyond Python
- `Procfile` — `web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`
- Migrations and bootstrap run automatically when `DATABASE_URL` is set

---

## 11. Known Technical Debt

### HIGH priority

1. **Set `ENCRYPTION_KEY` on Render** — Credentials are encrypted at rest for new saves once this is set. Existing records remain plaintext until teachers re-save their module configs.
2. **`src/app.js` uses v1 API** — Grades (`/api/grades`), notes (`/api/notes`) still use legacy IP-guarded v1 endpoints. These need migration to `/api/v2/modules/*` with `credentials: 'include'`. itslearning/Nextcloud configs now correctly use v2 (fixed in Phase 8).
3. **Migrate `GET /api/dashboard`** — Main dashboard payload still served from legacy v1 endpoint.

### MEDIUM priority

4. ~~**O(n) auth scan**~~ — **RESOLVED in Phase 9**: `code_prefix` column added to `user_access_codes`; `authenticate_by_code()` pre-filters by prefix; O(1) index lookup for new codes. Existing NULL-prefix codes still work.
5. ~~**`audit_log` display not in admin panel**~~ — **RESOLVED in Phase 9**: `GET /api/v2/admin/audit-log` + admin tab in `admin.html`.
6. **Monolithic `src/app.js`** — 3600+ lines. `grades.js` extracted (Phase 9). Next: `src/features/webuntis.js` (~470 lines, `src/api.js`).

### LOW priority

8. **`server.py` is not multi-user** — Stdlib `ThreadingHTTPServer` has no Flask blueprint support. For local multi-user dev, use `flask run` or `gunicorn`.
9. **Session cleanup not automated** — Must be triggered manually via `POST /api/v2/admin/maintenance/cleanup-sessions` or via probabilistic trigger (not yet implemented).
10. **No drag-and-drop** — Module reorder uses number inputs, not HTML5 drag events.

---

## 12. What Must NOT Be Changed

### Load-bearing — do not modify without careful review

| Component | Why it's fragile |
|---|---|
| `backend/migrations.py` | Idempotent via `IF NOT EXISTS`. Adding a new column requires `ALTER TABLE IF NOT EXISTS ... ADD COLUMN IF NOT EXISTS ...` separately — not in the `CREATE TABLE`. |
| `backend/api/helpers.py:set_session_cookie()` | `SameSite=None` + `Secure=True` in production is required for cross-origin cookies. Changing to `Lax` breaks login on the SaaS deployment. |
| `app.py:_cors()` and `after_request` | `Access-Control-Allow-Credentials: true` must coexist with explicit (non-wildcard) origin. The current implementation handles multi-origin via the `CORS_ORIGIN` comma-separated list. |
| `backend/auth/access_code.py:_ph` | argon2id parameters must not change after any codes are in production. Changing them invalidates all existing hashes unless `needs_rehash()` + rotation is implemented. |
| `app.py` legacy v1 routes | `GET /api/dashboard`, `GET /api/grades`, `GET /api/notes` are still called by `src/app.js`. Removing them breaks the dashboard. |
| `backend/migrations.py` module seed | `ON CONFLICT (id) DO NOTHING` means the initial seed only runs once. Changing a display name or type requires an explicit `UPDATE` statement, not modifying the seed. |
| `backend/crypto.py` | The `enc:` prefix is a storage contract. Changing or removing it corrupts all existing encrypted records in `user_module_configs.config_data`. |
| `src/api-client.js` | All frontend pages depend on `window.LehrerAPI`. Changing the public API surface (method names, signatures) breaks the app. |
| Script load order in `index.html` | `api-client.js` → `dashboard-manager.js` → `grades.js` → `app.js`. Changing this order causes `window.LehrerAPI` or `window.LehrerGrades` to be undefined when later scripts execute. |

### Fragile patterns

- `g.current_user` is set by `@require_auth` / `@require_admin` decorators and consumed in route handlers. Do not read from `g.current_user` outside a decorated route.
- `db_connection()` is a psycopg3 context manager with autocommit. It does NOT share transactions with `persistence.py` DbStore connections — they are independent.
- The `app_state` table is used by both the legacy persistence layer and by `dashboard_routes.py` for onboarding flags (`onboarding_done_{user_id}` keys). Do not drop this table.

---

## 13. Recommended Next Steps

In priority order (Phase 9 completed items are crossed out):

1. **Run `scripts/backfill_encryption.py` on Render** — After setting `ENCRYPTION_KEY`, existing plaintext configs must be backfilled. Use `--dry-run` first, then without it.

2. **Migrate remaining v1 `GET /api/dashboard`** payload to v2 per-module data endpoints — webuntis, itslearning, orgaplan, classwork are still served from legacy v1. Build `loadDashboardV2()` with `Promise.allSettled()`.

3. **Add WebUntis and itslearning v2 data endpoints** callable from `src/app.js` directly — `GET /api/v2/modules/webuntis/data` and `GET /api/v2/modules/itslearning/data` already exist; wire them into `loadDashboard()`.

4. ~~**Migrate grades/notes to v2**~~ — **DONE in Phase 9** via `src/features/grades.js` + `/api/v2/modules/noten/*`.

5. **Rotate existing access codes** to backfill `code_prefix` — Cannot backfill from existing hashes (one-way). Teachers must rotate to benefit from O(1) login.

6. **Extract `src/features/webuntis.js`** — ~470 lines, highest regression risk. Extract after Phase 9 is stable.

5. **Add `code_prefix` to auth** — O(1) auth lookup at scale:
   ```sql
   ALTER TABLE user_access_codes ADD COLUMN IF NOT EXISTS code_prefix TEXT NOT NULL DEFAULT '';
   CREATE INDEX IF NOT EXISTS idx_access_codes_prefix ON user_access_codes (code_prefix);
   ```

6. **Split `src/app.js`** — Create `src/state.js`, `src/api.js`, `src/features/` directory. No bundler needed — add `<script>` tags in order.

7. **Session cleanup automation** — Add 1% probabilistic cleanup in `get_current_user()`.

8. **Admin display name update** — Add a profile endpoint so admin can change their own name after bootstrap.

9. **Teacher self-service code rotation** — Add `POST /api/v2/auth/rotate-code`.
