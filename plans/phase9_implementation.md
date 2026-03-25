# Phase 9 Implementation Plan — Lehrercockpit

> **Produced:** 2026-03-25 | **Scope:** Phase 9 (post Phase 8g) | **Based on full source audit**
>
> This document is the authoritative implementation plan for Phase 9. Every section is grounded in exact line numbers, function names, and file paths from the current codebase.

---

## Section 1: Remaining v1 Dashboard Dependencies

### 1.1 `GET /api/dashboard` (v1) — Main Dashboard Payload

**File:** [`src/app.js`](../src/app.js)

| Function | Line | Dependency | Detail |
|---|---|---|---|
| `loadDashboard()` | 212–236 | `GET /api/dashboard` (v1) | Primary call. Constructs URL list; on IS_LOCAL_RUNTIME fetches `/api/dashboard`, on production fetches `${PRODUCTION_API_BASES}/api/dashboard`. Falls back to `./data/mock-dashboard.json`. |
| `normalizeDashboard()` | 238–298 | Consumes response directly | Receives full v1 payload, normalizes missing keys with defaults for `webuntisCenter`, `planDigest`. |
| `refreshDashboard()` (called via `briefingButton`) | 2741 | Calls `loadDashboard()` | Re-fetches on button click. |

**What `GET /api/dashboard` returns** (from [`backend/dashboard.py`](../backend/dashboard.py), `build_dashboard_payload()` lines 21–103):

```json
{
  "generatedAt": "ISO timestamp",
  "teacher": {"name": "...", "school": "..."},
  "workspace": {"eyebrow": "...", "title": "...", "description": "..."},
  "localConnections": {
    "itslearning": {"configured": bool, "username": "..."},
    "nextcloud": {"configured": bool, "username": "...", "baseUrl": "...", ...},
    "mail": {"configured": bool, "account": "..."}
  },
  "meta": {"mode": "live|mixed|snapshot", "note": "...", "lastUpdatedLabel": "HH:MM"},
  "quickLinks": [...],
  "berlinFocus": [...],
  "documentMonitor": [...],
  "webuntisCenter": {
    "status": "ok|warning",
    "note": "...", "detail": "...",
    "activePlan": "...",
    "todayUrl": "...", "startUrl": "...",
    "currentDate": "YYYY-MM-DD", "currentWeekLabel": "KW N",
    "events": [...],   ← iCal events from fetch_webuntis_sync()
    "planTypes": [...],
    "finder": {"status":..., "entities": [...], "watchlist": [...], ...},
    "shortcutHint": "..."
  },
  "planDigest": {
    "orgaplan": {"status": "ok|warning", "title":..., "detail":..., "monthLabel":..., "updatedAt":..., "highlights": [...], "upcoming": [...], "sourceUrl":...},
    "classwork": {"status": "ok|warning", "title":..., "detail":..., "updatedAt":..., "previewRows": [...], "classes": [...], "entries": [...], "defaultClass":..., "sourceUrl":...}
  },
  "messages": [...],   ← from itslearning + mail adapters
  "priorities": [...], ← from webuntis/mail/orgaplan/monitor
  "documents": [...],  ← static + plan_digest enriched
  "sources": [...],    ← status of each integration
  "schedule": [...]    ← from webuntis_sync.schedule
}
```

**What `src/app.js` consumes from this payload** (across `renderAll`, `renderBriefing`, `renderWorkspace`, `renderStats`, etc.):

- `data.workspace.*` → `renderWorkspace()` (line 376)
- `data.meta.*` → `renderMeta()`, `renderRuntimeBanner()` (lines 408, 413)
- `data.messages[]` → `renderMessages()`, `renderSources()`, inbox section
- `data.priorities[]` → `renderPriorities()`
- `data.documents[]` → `renderDocuments()`
- `data.sources[]` → `renderSources()`
- `data.quickLinks[]` → `renderQuickLinks()` (line 736)
- `data.berlinFocus[]` → `renderBerlinFocus()`
- `data.webuntisCenter.*` → all WebUntis rendering functions
- `data.planDigest.orgaplan.*` → orgaplan digest section
- `data.planDigest.classwork.*` → classwork section
- `data.documentMonitor[]` → monitor list
- `data.localConnections.*` → `renderItslearningConnector()` (line 780), nextcloud connector
- `data.generatedAt` → timing calculations in briefing

**v2 replacement strategy:** See Section 2.

---

### 1.2 `GET /api/grades` (v1) — Grades Fetch

**File:** [`src/app.js`](../src/app.js)

| Function | Line | Dependency | Detail |
|---|---|---|---|
| `loadGradebook()` | 2537–2548 | `window.LehrerAPI.legacy.getGrades()` → `GET /api/grades` | Fetches all grades for user; sets `state.gradesData`; calls `renderGrades()` |
| `saveGradeEntry()` | 2564–2621 | `POST /api/local-settings/grades` (direct `fetch`, line 2594) | Gated by `IS_LOCAL_RUNTIME` check. Saves a grade entry. |
| `deleteGradeEntry()` | 2623–2647 | `POST /api/local-settings/grades` (mode: "delete", line 2628) | Gated by `IS_LOCAL_RUNTIME` check. |

**Consumed response shape** (`grades_store.py` load_gradebook): `{status, detail, updatedAt, entries: [{id, classLabel, studentName, title, type, gradeValue, points, date, comment, createdAt}], classes: [...]}`

**Current backend:** [`app.py`](../app.py) line 221–226: `GET /api/grades` calls `load_gradebook(GRADES_LOCAL_PATH)`. Uses `persistence.store` — PostgreSQL-backed via `app_state` table when `DATABASE_URL` is set, otherwise a JSON file. **No per-user isolation** — all users share the same `grades-local` key in `app_state`.

**v2 replacement strategy:** Add `GET /api/v2/modules/noten/data` and `POST /api/v2/modules/noten/data` endpoints. Requires a new `grades` table with `user_id` FK. See Section 3.

---

### 1.3 `GET /api/notes` (v1) — Notes Fetch

**File:** [`src/app.js`](../src/app.js)

| Function | Line | Dependency | Detail |
|---|---|---|---|
| `loadNotes()` | 2550–2562 | `window.LehrerAPI.legacy.getNotes()` → `GET /api/notes` | Fetches all class notes; sets `state.notesData`; calls `renderClassNotes()` |
| `saveClassNote()` | 2649–2693 | `POST /api/local-settings/notes` (line 2672) | Gated by `IS_LOCAL_RUNTIME` check. |
| `clearClassNote()` | 2695+ | `POST /api/local-settings/notes` (mode: "delete") | Gated by `IS_LOCAL_RUNTIME` check. |

**Consumed response shape** (`notes_store.py` load_notes): `{status, detail, updatedAt, notes: [{classLabel, text, updatedAt}], classes: [...]}`

**Current backend:** [`app.py`](../app.py) line 228–233: `GET /api/notes` calls `load_notes(NOTES_LOCAL_PATH)`. Same `persistence.store` pattern. **No per-user isolation.**

**v2 replacement strategy:** Same as grades — see Section 3.

---

### 1.4 `GET /api/classwork` (v1) — Classwork Cache

**File:** [`src/app.js`](../src/app.js)

| Function | Line | Dependency | Detail |
|---|---|---|---|
| `loadClassworkCache()` | 2806–2822 | `window.LehrerAPI.legacy.getClasswork()` → `GET /api/classwork` | Supplements `planDigest.classwork` from dashboard with cached Playwright scrape results |

**Note:** This is a low-priority replacement — the classwork data primarily flows through `GET /api/dashboard`. The `loadClassworkCache()` function is supplementary and fails silently.

---

### 1.5 `POST /api/local-settings/*` (v1) — Write Endpoints

These are still called directly with `fetch()` in `src/app.js`:

| URL | Line in app.js | Function |
|---|---|---|
| `POST /api/local-settings/grades` | 2594, 2628 | `saveGradeEntry()`, `deleteGradeEntry()` |
| `POST /api/local-settings/notes` | 2672, 2716 | `saveClassNote()`, `clearClassNote()` |
| `POST /api/classwork/upload` | 2897 | `uploadClassworkFile()` |
| `POST /api/classwork/browser-fetch` | 2497 | `handleBrowserFetch()` |

All write paths for grades/notes are gated by `IS_LOCAL_RUNTIME` — they currently **only work when running locally** (not in the SaaS deployment). This is the core gap: the multi-user SaaS has no working grades/notes persistence for individual teachers.

---

### 1.6 Already Migrated to v2

For reference — these calls were migrated in Phase 8 and no longer use v1:

- `saveItslearningCredentials()` → `PUT /api/v2/modules/itslearning/config`
- `saveNextcloudCredentials()` → `PUT /api/v2/modules/nextcloud/config`
- All auth flows (`/api/v2/auth/*`)
- DashboardManager → `GET /api/v2/dashboard`

---

## Section 2: v2 Dashboard Data Model Gap Analysis

### 2.1 What `GET /api/v2/dashboard` Currently Returns

From [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py), `get_dashboard()` (line 22–66):

```json
{
  "ok": true,
  "user": {id, first_name, last_name, full_name, role, is_active, is_admin},
  "modules": [
    {
      "module_id": "webuntis",
      "name": "WebUntis Stundenplan",
      "display_name": "WebUntis Stundenplan",
      "module_type": "individual",
      "enabled": true,
      "is_visible": true,
      "order": 30,
      "sort_order": 30,
      "configured": false,
      "is_configured": false,
      "requires_config": true
    }
  ],
  "onboarding_complete": false
}
```

**This is module layout metadata only — it contains zero teacher content data.** The actual schedule, inbox, orgaplan, grades, notes, documents — none of this is in the v2 dashboard response.

### 2.2 The Gap

The entire teacher content payload (webuntis events, itslearning messages, orgaplan digest, classwork plan, mail messages, priorities, documents) still comes from `GET /api/dashboard` (v1), assembled by [`backend/dashboard.py:build_dashboard_payload()`](../backend/dashboard.py:21).

### 2.3 Strategy Options and Recommendation

**Option A: Extend `GET /api/v2/dashboard` to include full data payload**

Pros: Single request for all data. Backward compatible.
Cons: Extremely heavy endpoint — v2 dashboard would need to call all 6 adapters (webuntis, itslearning, nextcloud, mail, orgaplan, classwork) synchronously. Mixes layout management with data fetching. Makes the endpoint ~10s latency. Breaks the clean separation of concerns.

**Option B: Per-module data endpoints — `GET /api/v2/modules/{id}/data`** ← **RECOMMENDED**

These **already exist** in [`backend/api/module_routes.py`](../backend/api/module_routes.py):
- `GET /api/v2/modules/itslearning/data` (line 137) — calls `fetch_itslearning_sync()`
- `GET /api/v2/modules/webuntis/data` (line 167) — calls `fetch_webuntis_sync()`
- `GET /api/v2/modules/nextcloud/data` (line 192) — calls `fetch_nextcloud_sync()`
- `GET /api/v2/modules/orgaplan/data` (line 213) — returns system_settings URLs
- `GET /api/v2/modules/klassenarbeitsplan/data` (line 233) — returns XLSX data

**Missing module data endpoints that need to be built:**
- `GET /api/v2/modules/noten/data` — grades for current user
- `POST /api/v2/modules/noten/data` — save grade entry
- `DELETE /api/v2/modules/noten/data/{id}` — delete grade entry
- `GET /api/v2/modules/noten/notes` — class notes for current user
- `POST /api/v2/modules/noten/notes` — save/update note
- `DELETE /api/v2/modules/noten/notes/{class_label}` — delete note

**Why Option B is best:**
1. Per-module data endpoints are already half-implemented (5/7 modules done)
2. `src/app.js` can load data in parallel via `Promise.all()`
3. Each module fetches only when visible/needed
4. Aligns with the existing `DashboardManager` module-centric architecture
5. The v1 `GET /api/dashboard` can then be kept as a compatibility shim that aggregates from v2 endpoints, or simply deprecated after `src/app.js` is updated

**Option C: `GET /api/v2/dashboard/data`**

Pros: Clean URL, single call.
Cons: Still aggregates everything server-side — same latency problem as Option A. Less flexible than per-module. Doesn't reuse existing per-module endpoints.

### 2.4 Migration Path for `src/app.js` `loadDashboard()`

Replace the single `loadDashboard()` call with a parallel fetch strategy:

```javascript
// New function — replaces loadDashboard()
async function loadDashboardV2() {
  const [
    webuntisResp,
    itslearningResp,
    orgaplanResp,
    classworkResp
  ] = await Promise.allSettled([
    window.LehrerAPI.getModuleData('webuntis'),
    window.LehrerAPI.getModuleData('itslearning'),
    window.LehrerAPI.getModuleData('orgaplan'),
    window.LehrerAPI.getModuleData('klassenarbeitsplan'),
  ]);
  // Merge results into state.data structure + fall back to mock-dashboard.json shape
}
```

The `normalizeDashboard()` function (line 238) can be adapted to normalize per-module payloads into the same `state.data` shape that all existing render functions consume — meaning all rendering code stays untouched.

---

## Section 3: Grades and Notes v2 Gap

### 3.1 Current Storage Mechanism

**Grades:** [`backend/grades_store.py`](../backend/grades_store.py) uses `persistence.store` (line 20). When `DATABASE_URL` is set, `store` is a `DbStore` that reads/writes the `app_state` JSONB table with key `"grades-local"`. **All teachers share one key.** No per-user isolation.

**Notes:** [`backend/notes_store.py`](../backend/notes_store.py) same pattern, key `"class-notes-local"`. **Also shared across all users.**

### 3.2 Current Storage Shape

**Grades** (`grades-local` key in `app_state`):
```json
{
  "updatedAt": "HH:MM",
  "savedAt": "ISO timestamp",
  "entries": [
    {
      "id": "uuid-hex",
      "classLabel": "10A",
      "studentName": "Max Mustermann",
      "title": "3. KA Mathe",
      "type": "Klassenarbeit",
      "gradeValue": "2-",
      "points": "",
      "date": "YYYY-MM-DD",
      "comment": "",
      "createdAt": "ISO timestamp"
    }
  ]
}
```

**Notes** (`class-notes-local` key in `app_state`):
```json
{
  "updatedAt": "HH:MM",
  "savedAt": "ISO timestamp",
  "notes": [
    {
      "classLabel": "10A",
      "text": "Max fehlt oft freitags.",
      "updatedAt": "ISO timestamp"
    }
  ]
}
```

### 3.3 Is it PostgreSQL-backed?

Yes, when `DATABASE_URL` is set — via `DbStore` in `persistence.py` which uses the `app_state` JSONB table. But this is a flat key-value store, not relational. **There is no per-user isolation, no indexing, and no row-level data model.**

### 3.4 Minimal v2 DB-Backed Grades/Notes API

**New DB tables required:**

```sql
-- Grades: per-user entries
CREATE TABLE IF NOT EXISTS grades (
    id          TEXT PRIMARY KEY,           -- uuid hex
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_label TEXT NOT NULL,
    student_name TEXT NOT NULL,
    title       TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'Sonstiges',
    grade_value TEXT NOT NULL DEFAULT '',
    points      TEXT NOT NULL DEFAULT '',
    date        DATE,
    comment     TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_grades_user_id ON grades(user_id);
CREATE INDEX IF NOT EXISTS idx_grades_class_label ON grades(user_id, class_label);

-- Class notes: one note per class per user
CREATE TABLE IF NOT EXISTS class_notes (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_label TEXT NOT NULL,
    note_text   TEXT NOT NULL DEFAULT '',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, class_label)
);
CREATE INDEX IF NOT EXISTS idx_class_notes_user_id ON class_notes(user_id);
```

**New v2 endpoints in `module_routes.py`:**

```python
GET  /api/v2/modules/noten/data          → {ok, grades: [...], notes: [...], classes: [...]}
POST /api/v2/modules/noten/grades        → save grade entry, returns updated list
DELETE /api/v2/modules/noten/grades/<id> → delete grade by id
POST /api/v2/modules/noten/notes         → upsert class note
DELETE /api/v2/modules/noten/notes/<class_label> → delete note
```

**Frontend changes in `src/app.js`:**
- `loadGradebook()` (line 2537): replace `window.LehrerAPI.legacy.getGrades()` with `window.LehrerAPI.getModuleData('noten')`
- `loadNotes()` (line 2550): same, consume from unified noten response
- `saveGradeEntry()` (line 2564): remove `IS_LOCAL_RUNTIME` gate, use v2 endpoint
- `deleteGradeEntry()` (line 2623): same
- `saveClassNote()` (line 2649): same
- `clearClassNote()` (line 2695): same

**Update `src/api-client.js`** to add:
```javascript
noten: {
  getData: function() { return apiFetch('/api/v2/modules/noten/data'); },
  saveGrade: function(data) { return apiFetch('/api/v2/modules/noten/grades', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }); },
  deleteGrade: function(id) { return apiFetch('/api/v2/modules/noten/grades/' + id, { method: 'DELETE' }); },
  saveNote: function(data) { return apiFetch('/api/v2/modules/noten/notes', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }); },
  deleteNote: function(classLabel) { return apiFetch('/api/v2/modules/noten/notes/' + encodeURIComponent(classLabel), { method: 'DELETE' }); },
}
```

### 3.5 Worth Building in Phase 9?

**YES — critical.** Without this, the `noten` module is completely broken in the SaaS deployment because:
1. `GET /api/grades` and `GET /api/notes` succeed but return shared data
2. `POST /api/local-settings/grades` and `POST /api/local-settings/notes` return HTTP 403 because `_is_local_request()` rejects all non-localhost requests

This means every teacher in production sees an empty grade book that they cannot write to. This is a data integrity and product completeness failure.

---

## Section 4: Audit Log Read Endpoint

### 4.1 `audit_log` Table Schema

From [`backend/migrations.py`](../backend/migrations.py) lines 146–170:

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id          SERIAL PRIMARY KEY,
    event_type  VARCHAR(64) NOT NULL,          -- 'login_success', 'login_failure', 'bootstrap_created'
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ip_address  VARCHAR(64),
    details     JSONB DEFAULT '{}',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
-- Indexes: idx_audit_log_user_id, idx_audit_log_event_type, idx_audit_log_created_at
```

Currently logged events (from [`backend/api/auth_routes.py`](../backend/api/auth_routes.py) and [`backend/admin/bootstrap.py`](../backend/admin/bootstrap.py)):
- `login_success` — `{user_id, ip_address, details: {}}`
- `login_failure` — `{user_id: null, ip_address, details: {"reason": "invalid_code"}}`
- `bootstrap_created` — `{user_id: 1, ip_address: null, details: {}}`

### 4.2 Required Query for Admin UI

The admin UI needs: recent events with user names, paginated, filterable by event type.

```sql
SELECT
    al.id,
    al.event_type,
    al.user_id,
    u.first_name || ' ' || u.last_name AS user_name,
    al.ip_address,
    al.details,
    al.created_at
FROM audit_log al
LEFT JOIN users u ON u.id = al.user_id
ORDER BY al.created_at DESC
LIMIT %s OFFSET %s
```

### 4.3 Proposed Endpoint

**`GET /api/v2/admin/audit-log`**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 50 | Max rows returned (max 200) |
| `offset` | int | 0 | Pagination offset |
| `event_type` | string | (all) | Filter by event type |
| `user_id` | int | (all) | Filter by user |

**Response shape:**
```json
{
  "ok": true,
  "total": 247,
  "limit": 50,
  "offset": 0,
  "events": [
    {
      "id": 42,
      "event_type": "login_success",
      "user_id": 3,
      "user_name": "Anna Müller",
      "ip_address": "82.113.42.1",
      "details": {},
      "created_at": "2026-03-25T10:14:22+00:00"
    }
  ]
}
```

**Implementation:** Add to [`backend/api/admin_routes.py`](../backend/api/admin_routes.py) under the `admin_bp` blueprint:

```python
@admin_bp.route("/audit-log", methods=["GET"])
@require_admin
def get_audit_log():
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    event_type = request.args.get("event_type", "").strip() or None
    user_id_filter = request.args.get("user_id", "").strip() or None
    # Build query with optional WHERE clauses
    # COUNT(*) for total, then SELECT with LIMIT/OFFSET
```

**Auth:** `@require_admin` — admin role only. `g.current_user.is_admin` checked by the decorator.

**Pagination strategy:** Offset-based (simple, no cursor needed at <50 users and <10,000 events). Add `total` to the response for the UI to show "Showing 1–50 of 247 events."

---

## Section 5: `code_prefix` Auth Optimization

### 5.1 Current Auth Flow

From [`backend/users/user_service.py`](../backend/users/user_service.py), `authenticate_by_code()` (lines 58–104):

```python
rows = conn.execute("""
    SELECT u.id, u.first_name, u.last_name, u.role, u.is_active,
           u.created_at, u.updated_at, uac.code_hash
    FROM users u
    INNER JOIN user_access_codes uac ON uac.user_id = u.id
    WHERE u.is_active = TRUE
""").fetchall()

for row in rows:
    stored_hash = row[7]
    if verify_code(plain_code, stored_hash):  # argon2id verify — ~200ms each
        return User(...)
```

**This is O(n) over all active users.** Every login attempt verifies argon2id against every user's hash until a match is found (or all fail).

### 5.2 Actual Performance at Scale

argon2id with `time_cost=3, memory_cost=65536 (64MB)` takes ~150–250ms per verify on typical VPS hardware.

- 10 users: ~1.5s worst case
- 50 users: ~12.5s worst case (catastrophic for UX)
- 1 user (bootstrap): ~0.25s (negligible)

Currently at ~50 users this is a real UX problem — a user at position 50 in the table could wait over 10 seconds for login. Even at 10 users it's noticeable.

### 5.3 The `code_prefix` Optimization

Store the first 8 characters of the plain code as a plaintext prefix column. On login, pre-filter candidates to users whose `code_prefix` matches the first 8 chars of the submitted code. Since codes are 32 chars from 62-character alphabet, collision probability is ~(1/62^8) ≈ 1 in 218 trillion per character position — functionally zero collision rate at <50 users.

**DB change** (add to `backend/migrations.py` as a new `ALTER TABLE` migration):

```sql
ALTER TABLE user_access_codes
    ADD COLUMN IF NOT EXISTS code_prefix TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_access_codes_prefix
    ON user_access_codes (code_prefix);
```

**Code change** in [`backend/users/user_store.py`](../backend/users/user_store.py), `set_access_code()` (line 193):

```python
def set_access_code(conn, user_id: int, code_hash: str, code_prefix: str = '') -> None:
    conn.execute(
        """
        INSERT INTO user_access_codes (user_id, code_hash, code_prefix)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
            SET code_hash = EXCLUDED.code_hash,
                code_prefix = EXCLUDED.code_prefix,
                created_at = NOW()
        """,
        (user_id, code_hash, code_prefix),
    )
```

**Code change** in [`backend/auth/access_code.py`](../backend/auth/access_code.py) — add helper:

```python
PREFIX_LENGTH = 8

def extract_prefix(code: str) -> str:
    """Extracts the first PREFIX_LENGTH characters as the lookup prefix."""
    return code[:PREFIX_LENGTH]
```

**Code change** in [`backend/users/user_service.py`](../backend/users/user_service.py), `authenticate_by_code()`:

```python
def authenticate_by_code(conn, plain_code: str) -> Optional[User]:
    from ..auth.access_code import extract_prefix
    prefix = extract_prefix(plain_code)

    rows = conn.execute("""
        SELECT u.id, u.first_name, u.last_name, u.role, u.is_active,
               u.created_at, u.updated_at, uac.code_hash
        FROM users u
        INNER JOIN user_access_codes uac ON uac.user_id = u.id
        WHERE u.is_active = TRUE
          AND uac.code_prefix = %s     ← O(1) index lookup
    """, (prefix,)).fetchall()

    for row in rows:  # typically 0–1 rows
        if verify_code(plain_code, row[7]):
            return User(id=row[0], ...)
    return None
```

**Update `create_teacher()` and `regenerate_access_code()`** in `user_service.py` to pass `code_prefix=plain_code[:8]` to `set_access_code()`.

**Backfill existing rows** (one-time migration script or startup hook):

```python
# In run_migrations() or as a standalone script
rows = conn.execute("SELECT user_id, code_hash FROM user_access_codes WHERE code_prefix = ''").fetchall()
# Cannot recover prefix from hash — set to '' permanently for old codes
# Existing teachers must rotate their code to get prefix-accelerated login
```

**Alternative backfill for existing plaintext-phase installs** — not possible. argon2id is one-way. Old hashes cannot have their prefix recovered. However, since we have <50 users and they will rotate codes naturally over time, this is acceptable. The system degrades gracefully: `code_prefix = ''` rows fall through to full table scan (old behavior).

### 5.4 Worth Implementing?

**YES — at 50 users it's urgent for production UX.** Login latency of 10+ seconds is unacceptable. The fix is minimal (1 column, 1 index, 3 code changes) and completely backward compatible.

---

## Section 6: Plaintext Config Migration

### 6.1 How Configs Are Currently Stored

From [`backend/modules/module_registry.py`](../backend/modules/module_registry.py), `save_user_module_config()` (lines 335–373):

```python
from backend.crypto import encrypt_config
config_data = encrypt_config(config_data)
# JSONB upsert into user_module_configs.config_data
```

From [`backend/crypto.py`](../backend/crypto.py), `encrypt_config()` (lines 86–118):

- If `ENCRYPTION_KEY` is NOT set: logs a one-time warning, returns `config` unchanged → **plaintext stored in JSONB**
- If `ENCRYPTION_KEY` IS set: encrypts sensitive fields (password, secret, token, credential) and prefixes them with `enc:`, e.g., `"enc:gAAAAAB..."`

### 6.2 How `enc:` Prefix Detection Works

From [`backend/crypto.py`](../backend/crypto.py) line 19:
```python
_ENC_PREFIX = "enc:"
```

`decrypt_config()` (lines 121–148): iterates all config keys, checks `value.startswith("enc:")`, decrypts if true, returns raw value otherwise (backward compatible with plaintext).

`encrypt_config()` (line 111): checks `if value.startswith(_ENC_PREFIX): result[key] = value` — prevents double-encryption.

### 6.3 The Backfill Problem

When `ENCRYPTION_KEY` is first set on Render:
1. **New saves** → encrypted immediately
2. **Existing records** → remain plaintext in `user_module_configs.config_data`
3. `decrypt_config()` returns plaintext values unchanged (backward compatible)
4. When teacher re-saves → now encrypted

So existing plaintext records are only encrypted when teachers actively re-save their module configs. This is documented in `CLAUDE_HANDOFF.md` section 11.

### 6.4 How to Detect Plaintext vs Encrypted Values

```python
def is_plaintext_sensitive(config: dict) -> bool:
    """Returns True if any sensitive field is stored in plaintext."""
    for key, value in config.items():
        if _is_sensitive(key) and isinstance(value, str) and value:
            if not value.startswith(_ENC_PREFIX):
                return True
    return False
```

### 6.5 Backfill Strategy Options

**Option A: Standalone script** (safest)

```python
# scripts/backfill_encryption.py
"""
Run once after setting ENCRYPTION_KEY on Render:
  python -m scripts.backfill_encryption
"""
import os
from backend.db import db_connection
from backend.crypto import encrypt_config, is_encryption_enabled
import psycopg.types.json as pjson

def backfill():
    assert is_encryption_enabled(), "ENCRYPTION_KEY must be set"
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT id, config_data FROM user_module_configs"
        ).fetchall()
        for row_id, config_data in rows:
            encrypted = encrypt_config(config_data)
            if encrypted != config_data:  # only update if changed
                conn.execute(
                    "UPDATE user_module_configs SET config_data = %s WHERE id = %s",
                    (pjson.Jsonb(encrypted), row_id)
                )
                print(f"[backfill] Encrypted config for row {row_id}")
    print("[backfill] Done.")
```

**Option B: Migration hook** — Add to [`backend/migrations.py`](../backend/migrations.py) `run_migrations()`. Risk: runs at every startup, but `encrypt_config()` on already-encrypted values is idempotent.

**Option C: Startup hook** in `app.py` — Same as B but outside migrations.

### 6.6 Recommendation

**Option A (standalone script)** for Phase 9. Reasons:
1. Zero risk — runs manually, admin can inspect output
2. Does not pollute migration history
3. Atomic: if it fails midway, no data is corrupted (existing plaintext still decrypts)
4. `encrypt_config()` is idempotent on already-encrypted values — safe to re-run

**Risks of backfill:**
- If `ENCRYPTION_KEY` is rotated or lost after backfill, all encrypted records become unreadable
- Mitigated by: back up DB before running, use `decrypt_config()` to verify round-trip before committing
- Never loses data: `decrypt_config()` falls through to raw value on decryption failure

### 6.7 Exact SQL/Python Logic for Safe Backfill

```python
# Safe round-trip check before commit
def safe_backfill_row(conn, row_id, config_data, fernet):
    encrypted = encrypt_config(config_data)
    # Verify round-trip
    from backend.crypto import decrypt_config
    decrypted = decrypt_config(encrypted)
    assert decrypted == config_data, f"Round-trip failed for row {row_id}"
    conn.execute(
        "UPDATE user_module_configs SET config_data = %s, updated_at = NOW() WHERE id = %s",
        (pjson.Jsonb(encrypted), row_id)
    )
```

---

## Section 7: Frontend Modularization Target

### 7.1 Current State of `src/app.js`

**Lines:** 3,604 total (per file read — truncated at line 3604, file header states ~3700 after DashboardManager extraction).

The `DashboardManager` was extracted in Phase 8d to [`src/modules/dashboard-manager.js`](../src/modules/dashboard-manager.js) (313 lines). That leaves the monolithic IIFE at 3,604 lines containing:

| Section | Approx Lines | Notes |
|---|---|---|
| State & constants | 1–200 | `state`, `elements`, `channelLabels`, constants |
| DashboardManager reference | 201–209 | Already extracted |
| API / data loading | 210–375 | `loadDashboard`, `normalizeDashboard`, `getData` |
| Core render helpers | 374–780 | `renderWorkspace`, `renderMeta`, `renderStats`, `renderBriefing`, helpers |
| Inbox | ~895–1083 | `renderPriorities`, `renderSources`, `renderMessages` |
| Classwork | ~1085–1241 | `renderClasswork*` |
| Grades | ~1243–1553 | `renderGrades`, grade form logic |
| Documents | ~1555–1601 | `renderDocuments` |
| WebUntis | ~1603–2075 | `renderWebUntis*`, picker, shortcuts |
| Render/workspace | ~2283+ | `renderAll`, `renderBriefing`, `renderWorkspace` |
| Grades/Notes API calls | 2537–2720 | `loadGradebook`, `loadNotes`, `saveGradeEntry`, `saveClassNote`, etc. |
| Events/initialize | ~2715–3604 | `registerEvents`, `initialize` |

### 7.2 Top 3 Extraction Candidates

**Candidate 1: `src/features/grades.js`** (highest Phase 9 impact)
- Contains: `loadGradebook()`, `loadNotes()`, `saveGradeEntry()`, `deleteGradeEntry()`, `saveClassNote()`, `clearClassNote()`, `renderGrades()`, `renderClassNotes()`, all grade/note rendering logic
- Lines: ~1243–1553 + ~2537–2720 = ~470 lines
- **Phase 9 impact:** The grades/notes v2 migration (Section 3) requires touching all these functions. Extracting first makes the migration diff smaller and isolated.
- **Extraction complexity:** Medium — reads from `state.gradesData`, `state.notesData`; writes to `state.*`; calls `elements.*`. Requires exposing state accessors or passing by reference.

**Candidate 2: `src/features/webuntis.js`** (largest single block)
- Contains: all WebUntis rendering, picker logic, shortcuts, favorites
- Lines: ~1603–2075 = ~470 lines
- **Phase 9 impact:** Low direct impact, but WebUntis is the most complex module with its own rich internal state (shortcuts, favorites, active plan, picker). Isolating it prevents side-effect bugs during other migrations.

**Candidate 3: `src/api.js`** (highest architectural impact)
- Contains: `loadDashboard()`, `normalizeDashboard()`, `getData()`, `refreshDashboard()`
- Lines: ~210–375 = ~165 lines
- **Phase 9 impact:** HIGHEST — this is exactly what needs to change for the v2 dashboard migration (Section 2). Extracting it first means the migration only touches one file.

### 7.3 Recommendation

**Extract in this order for Phase 9:**

1. **`src/api.js`** first — because the v2 dashboard migration (Section 2) and grades/notes v2 migration (Section 3) both require changing API loading functions. Having them isolated reduces risk.

2. **`src/features/grades.js`** second — because the grades/notes v2 migration touches 7+ functions all in the same logical unit. Extracting before migrating keeps the v2 PR clean.

3. **`src/features/webuntis.js`** third — no Phase 9 dependency, but it's the single largest block and most prone to regression.

**Pattern for extraction** (no build tool required):

```html
<!-- index.html — add before app.js -->
<script src="./src/api.js?v=35"></script>
<script src="./src/features/grades.js?v=35"></script>
```

Each extracted file must use `(function() { 'use strict'; ... })();` wrapper. State and elements are exposed via closure or passed as arguments to exported functions (prefer closure via `window.LehrerState = state` pattern if needed).

---

## Section 8: Admin UI Audit Log Requirements

### 8.1 Current `admin.html` Tab Structure

From [`admin.html`](../admin.html) lines 471–481:

```html
<nav class="admin-tabs" role="tablist">
  <button ... data-tab="users">👥 Lehrkräfte</button>
  <button ... data-tab="settings">⚙️ System</button>
  <button ... data-tab="modules">📦 Module</button>
</nav>
```

Three tabs: `users`, `settings`, `modules`. Each has a corresponding `<section id="tab-{name}">` in the body.

### 8.2 Where the Audit Log Should Appear

Add a **4th tab** `data-tab="audit"` labeled `🔍 Audit-Log`. Rationale:
- It's an admin-only operational view
- Doesn't fit in existing tabs (not users, not settings, not modules)
- Follows the existing pattern exactly

### 8.3 HTML Structure

Add to `admin.html`:

**Tab button** (after the modules tab):
```html
<button class="admin-tab" type="button" data-tab="audit" role="tab" aria-selected="false">
  🔍 Audit-Log
</button>
```

**Tab section** (after `#tab-modules`):
```html
<section class="admin-section" id="tab-audit" role="tabpanel">
  <div class="admin-card">
    <div class="admin-card-header">
      <h2 class="admin-section-title">Audit-Log</h2>
      <div style="display:flex;gap:0.5rem;align-items:center;">
        <select id="audit-event-filter" class="form-field" style="min-width:160px;">
          <option value="">Alle Ereignisse</option>
          <option value="login_success">Login erfolgreich</option>
          <option value="login_failure">Login fehlgeschlagen</option>
          <option value="bootstrap_created">Bootstrap</option>
        </select>
        <button class="btn btn-sm" id="btn-audit-refresh">Aktualisieren</button>
      </div>
    </div>
    <div id="audit-feedback"></div>
    <div id="audit-table-container">
      <p class="loading-row">Lade Audit-Log…</p>
    </div>
    <div id="audit-pagination" style="display:flex;gap:0.5rem;align-items:center;margin-top:1rem;font-size:0.82rem;color:var(--muted);">
      <button class="btn btn-sm" id="audit-prev" disabled>← Zurück</button>
      <span id="audit-page-info">–</span>
      <button class="btn btn-sm" id="audit-next" disabled>Weiter →</button>
    </div>
  </div>
</section>
```

### 8.4 JavaScript Code

Add to the admin IIFE in `admin.html`:

```javascript
// ── Audit Log Tab ─────────────────────────────────────────────────────────

var _auditOffset = 0;
var _auditLimit = 50;
var _auditTotal = 0;

async function loadAuditLog() {
  var container = document.getElementById('audit-table-container');
  var eventType = document.getElementById('audit-event-filter').value;
  var params = 'limit=' + _auditLimit + '&offset=' + _auditOffset;
  if (eventType) params += '&event_type=' + encodeURIComponent(eventType);
  try {
    var resp = await apiFetch('/api/v2/admin/audit-log?' + params);
    if (!resp.ok) throw new Error('Fehler beim Laden');
    var data = await resp.json();
    _auditTotal = data.total || 0;
    renderAuditTable(data.events || [], container);
    renderAuditPagination();
  } catch(e) {
    container.innerHTML = '<p class="feedback-msg error">Fehler beim Laden des Audit-Logs.</p>';
  }
}

function renderAuditTable(events, container) {
  if (!events.length) {
    container.innerHTML = '<p style="color:var(--muted);font-size:0.85rem;padding:1rem 0;">Keine Einträge gefunden.</p>';
    return;
  }
  var html = '<table class="user-table"><thead><tr>'
    + '<th>Zeit</th><th>Ereignis</th><th>Lehrkraft</th><th>IP</th><th>Details</th>'
    + '</tr></thead><tbody>';
  events.forEach(function(ev) {
    var time = ev.created_at ? new Date(ev.created_at).toLocaleString('de-DE') : '–';
    var detailStr = ev.details && Object.keys(ev.details).length
      ? JSON.stringify(ev.details)
      : '–';
    html += '<tr>'
      + '<td style="white-space:nowrap;font-size:0.78rem;color:var(--muted);">' + esc(time) + '</td>'
      + '<td><code style="font-size:0.78rem;">' + esc(ev.event_type) + '</code></td>'
      + '<td>' + esc(ev.user_name || '–') + '</td>'
      + '<td style="font-size:0.78rem;color:var(--muted);">' + esc(ev.ip_address || '–') + '</td>'
      + '<td style="font-size:0.75rem;color:var(--muted);">' + esc(detailStr) + '</td>'
      + '</tr>';
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

function renderAuditPagination() {
  var info = document.getElementById('audit-page-info');
  var prev = document.getElementById('audit-prev');
  var next = document.getElementById('audit-next');
  var from = _auditTotal ? _auditOffset + 1 : 0;
  var to = Math.min(_auditOffset + _auditLimit, _auditTotal);
  if (info) info.textContent = _auditTotal ? (from + '–' + to + ' von ' + _auditTotal) : '0 Einträge';
  if (prev) prev.disabled = _auditOffset <= 0;
  if (next) next.disabled = (_auditOffset + _auditLimit) >= _auditTotal;
}
```

Wire in `init()` (just before the closing `init();` call):

```javascript
// Audit log tab
document.getElementById('btn-audit-refresh').addEventListener('click', function() {
  _auditOffset = 0;
  loadAuditLog();
});
document.getElementById('audit-event-filter').addEventListener('change', function() {
  _auditOffset = 0;
  loadAuditLog();
});
document.getElementById('audit-prev').addEventListener('click', function() {
  _auditOffset = Math.max(0, _auditOffset - _auditLimit);
  loadAuditLog();
});
document.getElementById('audit-next').addEventListener('click', function() {
  _auditOffset += _auditLimit;
  loadAuditLog();
});
```

Load on tab click (add to `setupTabs()` change handler):
```javascript
if (tab === 'audit') loadAuditLog();
```

### 8.5 Default Display

- **50 events** per page (default)
- **Columns:** Zeit (formatted DE locale), Ereignis (code tag), Lehrkraft (full_name or "–"), IP, Details (JSON inline)
- Sorted: newest first
- No auto-refresh (manual only)

---

## Section 9: Prioritized Phase 9 Action List

### Priority 1 — Critical for v2 Migration

**P1.1: Grades/Notes per-user DB tables + v2 endpoints**

This is blocking. Without it, `noten` module is functionally broken in production.

| File | Change |
|---|---|
| [`backend/migrations.py`](../backend/migrations.py) | Add `grades` and `class_notes` tables after existing migrations (with `ALTER TABLE ... ADD IF NOT EXISTS` pattern) |
| [`backend/api/module_routes.py`](../backend/api/module_routes.py) | Add `GET /api/v2/modules/noten/data`, `POST /api/v2/modules/noten/grades`, `DELETE /api/v2/modules/noten/grades/<id>`, `POST /api/v2/modules/noten/notes`, `DELETE /api/v2/modules/noten/notes/<class>` |
| [`src/api-client.js`](../src/api-client.js) | Add `window.LehrerAPI.noten.*` methods (getData, saveGrade, deleteGrade, saveNote, deleteNote) |
| [`src/app.js`](../src/app.js) | Replace `loadGradebook()` (line 2537), `loadNotes()` (line 2550), `saveGradeEntry()` (line 2564), `deleteGradeEntry()` (line 2623), `saveClassNote()` (line 2649), `clearClassNote()` (line 2695) to use v2 endpoints; remove all `IS_LOCAL_RUNTIME` guards from these functions |

**P1.2: `code_prefix` column + O(1) auth lookup**

At 50 users this is a real latency problem. Fix is minimal.

| File | Change |
|---|---|
| [`backend/migrations.py`](../backend/migrations.py) | Add `ALTER TABLE user_access_codes ADD COLUMN IF NOT EXISTS code_prefix TEXT NOT NULL DEFAULT ''` + index |
| [`backend/auth/access_code.py`](../backend/auth/access_code.py) | Add `PREFIX_LENGTH = 8` and `extract_prefix(code)` function |
| [`backend/users/user_store.py`](../backend/users/user_store.py) | Update `set_access_code()` (line 193) signature to accept `code_prefix` parameter |
| [`backend/users/user_service.py`](../backend/users/user_service.py) | Update `create_teacher()` (line 11) and `regenerate_access_code()` (line 35) to pass prefix; update `authenticate_by_code()` (line 58) to use prefix pre-filter |

---

### Priority 2 — Product Completeness

**P2.1: Audit Log Read Endpoint**

Events are being written, admin has no way to read them.

| File | Change |
|---|---|
| [`backend/api/admin_routes.py`](../backend/api/admin_routes.py) | Add `GET /api/v2/admin/audit-log` endpoint with `limit`, `offset`, `event_type`, `user_id` query params; LEFT JOIN with users table for `user_name` |
| [`src/api-client.js`](../src/api-client.js) | Add `window.LehrerAPI.admin.getAuditLog(params)` method |
| [`admin.html`](../admin.html) | Add 4th tab `🔍 Audit-Log` with table UI, pagination, event type filter |

**P2.2: More audit log events**

Currently only login and bootstrap events are logged. Should also log:

| File | Change |
|---|---|
| [`backend/api/admin_routes.py`](../backend/api/admin_routes.py) | Add `log_audit_event(conn, "user_created", user_id=user.id, ip_address=request.remote_addr)` in `create_user()` |
| [`backend/api/admin_routes.py`](../backend/api/admin_routes.py) | Add `log_audit_event(..., "code_rotated", user_id=user_id)` in `regenerate_code()` |
| [`backend/api/admin_routes.py`](../backend/api/admin_routes.py) | Add `log_audit_event(..., "user_deactivated", user_id=user_id)` in `deactivate_user_route()` |
| [`backend/api/module_routes.py`](../backend/api/module_routes.py) | Add `log_audit_event(..., "module_configured", details={"module_id": module_id})` in `put_module_config_route()` |

---

### Priority 3 — Operational / Admin Visibility

**P3.1: Plaintext config backfill script**

Urgent once `ENCRYPTION_KEY` is set on Render.

| File | Change |
|---|---|
| `scripts/backfill_encryption.py` (new file) | Standalone script: iterates `user_module_configs`, calls `encrypt_config()`, updates row if changed, verifies round-trip before committing |

**P3.2: Session cleanup automation**

Expired sessions accumulate and require manual cleanup call.

| File | Change |
|---|---|
| [`backend/api/helpers.py`](../backend/api/helpers.py) | In `get_current_user()`, add probabilistic cleanup: `if random.random() < 0.01: cleanup_expired_sessions(conn)` — triggers ~1% of requests |

---

### Priority 4 — Optimization

**P4.1: Migrate `GET /api/dashboard` → v2 parallel module data fetches**

The largest single architectural change. Pre-req: P1.1 must be done (so noten data is on v2).

| File | Change |
|---|---|
| [`src/app.js`](../src/app.js) | Replace `loadDashboard()` (line 212) with `loadDashboardV2()` that uses `Promise.allSettled()` over individual module data endpoints; adapter shim converts per-module responses into the `state.data` shape that all existing render functions expect |
| [`src/api-client.js`](../src/api-client.js) | Add `window.LehrerAPI.getModuleData(moduleId)` convenience method |
| [`app.py`](../app.py) | Once `src/app.js` no longer calls `GET /api/dashboard`, add deprecation header (`X-Deprecated: use /api/v2/modules/*/data`); do NOT remove yet — other clients may depend on it |

**P4.2: Migrate `GET /api/grades`, `GET /api/notes` v1 routes**

After P1.1 (v2 noten endpoints) and P4.1 (frontend migrated) are done:

| File | Change |
|---|---|
| [`app.py`](../app.py) | Add deprecation comments to `api_grades()` (line 221) and `api_notes()` (line 228); do not remove yet |
| [`src/api-client.js`](../src/api-client.js) | Remove `window.LehrerAPI.legacy.getGrades()` and `window.LehrerAPI.legacy.getNotes()` from the `legacy` object |

---

### Priority 5 — Modularization

**P5.1: Extract `src/api.js`**

| File | Change |
|---|---|
| New file: [`src/api.js`](../src/api.js) | Extract `loadDashboard()` (line 212), `normalizeDashboard()` (line 238), `getData()` (line 300), `refreshDashboard()`, `buildProductionApiBases()`, `getBackendApiBase()` from `src/app.js`; expose as IIFE with `window.LehrerDataLayer = {...}` |
| [`index.html`](../index.html) | Add `<script src="./src/api.js?v=35"></script>` between `dashboard-manager.js` and `app.js` |
| [`src/app.js`](../src/app.js) | Remove extracted functions; replace references with `window.LehrerDataLayer.*` |

**P5.2: Extract `src/features/grades.js`**

| File | Change |
|---|---|
| New file: `src/features/grades.js` | Extract `loadGradebook()`, `loadNotes()`, `saveGradeEntry()`, `deleteGradeEntry()`, `saveClassNote()`, `clearClassNote()`, `renderGrades()`, `renderClassNotes()`, all grade/note helpers (~470 lines) |
| [`index.html`](../index.html) | Add `<script src="./src/features/grades.js?v=35"></script>` |
| [`src/app.js`](../src/app.js) | Remove extracted functions |

**P5.3: Extract `src/features/webuntis.js`**

| File | Change |
|---|---|
| New file: `src/features/webuntis.js` | Extract all WebUntis rendering (~470 lines, ~1603–2075) |
| [`index.html`](../index.html) | Add `<script src="./src/features/webuntis.js?v=35"></script>` |
| [`src/app.js`](../src/app.js) | Remove extracted functions |

---

### Priority 6 — Docs and Tests

**P6.1: Tests for `GET /api/v2/modules/noten/data`**

| File | Change |
|---|---|
| [`tests/test_module_routes.py`](../tests/test_module_routes.py) | Add tests: `GET noten/data` returns empty for new user, `POST noten/grades` creates entry, `DELETE noten/grades/<id>` removes entry, per-user isolation (two users cannot see each other's grades) |

**P6.2: Tests for `GET /api/v2/admin/audit-log`**

| File | Change |
|---|---|
| [`tests/test_admin_routes.py`](../tests/test_admin_routes.py) | Add tests: endpoint requires admin, returns events with pagination, `total` field correct, `event_type` filter works |

**P6.3: Tests for `code_prefix` auth**

| File | Change |
|---|---|
| [`tests/test_user_service.py`](../tests/test_user_service.py) | Add test: `authenticate_by_code()` uses prefix pre-filter; `code_prefix` stored on `create_teacher()`; prefix mismatch skips argon2 verify |

**P6.4: Update `CLAUDE_HANDOFF.md`**

| File | Change |
|---|---|
| [`CLAUDE_HANDOFF.md`](../CLAUDE_HANDOFF.md) | Update "What IS implemented", "API Reference", "Known Technical Debt" sections; cross out resolved items; add Phase 9 to version header |

---

## Appendix: Quick Reference — Phase 9 File-Change Matrix

| File | P1.1 | P1.2 | P2.1 | P2.2 | P3.1 | P3.2 | P4.1 | P4.2 | P5.1 | P5.2 | P5.3 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `backend/migrations.py` | ✅ | ✅ | | | | | | | | | |
| `backend/api/module_routes.py` | ✅ | | | ✅ | | | | | | | |
| `backend/api/admin_routes.py` | | | ✅ | ✅ | | | | | | | |
| `backend/api/helpers.py` | | | | | | ✅ | | | | | |
| `backend/auth/access_code.py` | | ✅ | | | | | | | | | |
| `backend/users/user_store.py` | | ✅ | | | | | | | | | |
| `backend/users/user_service.py` | | ✅ | | | | | | | | | |
| `scripts/backfill_encryption.py` | | | | | ✅ | | | | | | |
| `src/api-client.js` | ✅ | | ✅ | | | | ✅ | ✅ | | | |
| `src/app.js` | ✅ | | | | | | ✅ | | ✅ | ✅ | ✅ |
| `src/api.js` (new) | | | | | | | ✅ | | ✅ | | |
| `src/features/grades.js` (new) | | | | | | | | | | ✅ | |
| `src/features/webuntis.js` (new) | | | | | | | | | | | ✅ |
| `admin.html` | | | ✅ | | | | | | | | |
| `app.py` | | | | | | | ✅ | ✅ | | | |
| `tests/test_module_routes.py` | | | | | | | | | | | |
| `tests/test_admin_routes.py` | | | | | | | | | | | |
| `tests/test_user_service.py` | | | | | | | | | | | |
| `CLAUDE_HANDOFF.md` | | | | | | | | | | | |
