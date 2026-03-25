# Phase 10 Implementation Plan — Lehrercockpit SaaS

**Date:** 2026-03-25  
**HEAD commit:** `2472eb7` — feat: Phase 9 - per-user grades/notes v2 API, audit log viewer, code_prefix auth optimization, backfill encryption script, grades.js extraction, frontend v2 migration  
**Branch:** main (up to date with origin/main)  
**Files committed in Phase 9:** 56 files, 16 181 insertions

---

## Git Push Result

| Field | Value |
|---|---|
| Files changed | 56 |
| Push status | ✅ Succeeded (`2472eb7 → origin/main`) |
| HEAD commit | `2472eb7` |

---

## Audit Summary (pre-10 state)

### Backend — Login / Rate Limiting

**Current state:** Rate limiting is **already partially implemented**.

- [`flask-limiter>=3.5`](requirements.txt) is already in `requirements.txt`
- [`backend/api/auth_routes.py`](backend/api/auth_routes.py:24) creates `limiter = Limiter(key_func=get_remote_address, default_limits=[])` and decorates the login route with `@limiter.limit("5 per minute;20 per hour")`
- [`app.py`](app.py:499) calls `limiter.init_app(app)` on startup

**Gaps:**
- Thresholds are **hardcoded strings**, not ENV-var driven
- The `429` response uses Flask-Limiter's default body, not the required `{"error": "Too many login attempts. Try again in X minutes."}`
- No `LOGIN_RATE_LIMIT_MAX` / `LOGIN_RATE_LIMIT_WINDOW_SECONDS` ENV vars
- No in-process dict-based fallback for environments where Redis is unavailable

---

### Frontend — WebUntis

**WebUntis functions in `src/app.js`** (3 501 total lines):

| Function | Approx. Line | Role |
|---|---|---|
| `renderWebUntisControls()` | 1667 | View-switch buttons, "Heute" link |
| `renderWebUntisPicker()` | 1704 | Full picker overlay (search, categories, favorites) |
| `renderWebUntisWatchlist()` | 1804 | Watchlist panel |
| `renderWebUntisPlanStrip()` | 1823 | Pinned plan chips |
| `renderWebUntisSchedule()` | 1848 | Schedule router (day/week/next-week) |
| `renderWeekSchedule()` | 1870 | Week board with columns |
| `renderAgendaGroups()` | 1911 | Day agenda groups wrapper |
| `renderAgendaGroup()` | 1923 | Single agenda group |
| `renderDayGroup()` | 1941 | Day group (day view) |
| `renderDayEvent()` | 1953 | Individual day-view event card |
| `renderWeekEvent()` | 1974 | Individual week-view event chip |
| `getWebUntisEvents()` | 1991 | Filter events by current view window |
| `groupEventsByDay()` | 2015 | Group events by ISO date |
| `buildWeekColumns()` | 2031 | Build Mon–Fri column structs |
| `getWeekAnchorDate()` | 2058 | Resolve week anchor from currentDate + view |
| `nextWeekLabel()` | 2069 | Format "Nächste KW N" label |
| `getWebUntisRangeLabel()` | 2075 | Range label for header |
| Picker helpers (8+ fns) | ~2100–2400 | `bindPickerActions`, `getGlobalPickerResults`, `getPickerEntities`, `getFavoriteEntities`, `isEntityActive`, `getActivePlan`, `getPinnedPlans`, `selectPlanById`, `closePicker`, `shortcutTypeLabel`, `renderPickerItem`, `isPlanChipActive`, etc. |
| Shortcut/favorites state | ~24–26 | `WEBUNTIS_SHORTCUTS_KEY`, `WEBUNTIS_FAVORITES_KEY`, `ACTIVE_WEBUNTIS_PLAN_KEY` constants + `loadSavedShortcuts()`, `loadWebUntisFavorites()` |
| `extractClassLabels()` | ~2400+ | Extracts class labels from events |
| `renderEmptyWeekColumn()` | ~2400+ | Empty column placeholder |
| `findNextEventAfter()` | ~2400+ | Finds next future event |

**Total WebUntis block:** ~470 lines (lines 1665–2083 core render + ~200 lines picker helpers)

**Shared state depended on:**
- `state.webuntisView` — "day" | "week" | "next-week"
- `state.webuntisPickerOpen` / `state.webuntisPickerCategory` / `state.webuntisPickerSearch`
- `state.activeShortcutId` / `state.activeFinderEntityId`
- `state.shortcuts` / `state.favorites`
- `elements.scheduleList`, `elements.webuntisViewSwitch`, etc. (all `elements.*` DOM refs)
- `getData().webuntisCenter` — dashboard data
- `WEBUNTIS_SHORTCUTS_KEY`, `WEBUNTIS_FAVORITES_KEY`, `ACTIVE_WEBUNTIS_PLAN_KEY` constants

**Extraction pattern to follow:** [`src/features/grades.js`](src/features/grades.js) — IIFE wrapping, `init(state, elements, callbacks)` pattern, `window.LehrerWebUntis` global.

---

### Backend — WebUntis v2

| File | What it does |
|---|---|
| [`backend/webuntis_adapter.py`](backend/webuntis_adapter.py) | Downloads iCal URL (urllib, no deps), parses VEVENT blocks, returns `WebUntisSyncResult` **dataclass** with `source`, `schedule`, `events`, `priorities` |
| [`backend/webuntis_cache.py`](backend/webuntis_cache.py) | JSON file cache for events/schedule/priorities with `cache_is_recent()` (max 24h) |
| [`backend/dashboard.py`](backend/dashboard.py:34) | v1 endpoint: calls `fetch_webuntis_sync(settings.webuntis_base_url, settings.webuntis_ical_url, now)` from global `.env.local` settings |
| [`backend/api/module_routes.py`](backend/api/module_routes.py:175) | **`GET /api/v2/modules/webuntis/data`** already exists — reads `ical_url` from per-user module config, calls `fetch_webuntis_sync()` |

**Critical bug found in `GET /api/v2/modules/webuntis/data`:**
```python
data = fetch_webuntis_sync(base_url, ical_url, now)
return success({"data": data})   # ← data is a WebUntisSyncResult *dataclass*, not a dict → JSON serialization will fail
```
`WebUntisSyncResult` is a `@dataclass` — Flask's `jsonify` cannot serialize it. The endpoint needs `dataclasses.asdict(data)` or converting to dict manually.

**`ical_url` config field:** already present — onboarding stores `ical_url` in the `webuntis` module config via `PUT /api/v2/modules/webuntis/config`.

---

### Admin — Audit Log

**Backend** ([`backend/api/admin_routes.py`](backend/api/admin_routes.py:447)):
- `GET /api/v2/admin/audit-log` — pagination (`limit`/`offset`), single `event_type` filter
- No `date_from` / `date_to` support
- No CSV export endpoint

**Frontend** (`admin.html`):
- Has event_type dropdown filter and pagination buttons
- Missing: date range pickers, CSV export button, user_name filter, event count badges

---

### Operational

**[`scripts/backfill_encryption.py`](scripts/backfill_encryption.py):** Good pattern — idempotent, dry-run mode, round-trip verification, env-check on startup.

**[`backend/users/user_store.py`](backend/users/user_store.py:193):** `set_access_code()` stores `code_prefix` (first 8 chars of plaintext). Existing NULL rows **cannot be backfilled** — the hash is one-way. Code rotation is required.

**[`backend/api/admin_routes.py`](backend/api/admin_routes.py:529):** `POST /api/v2/admin/maintenance/cleanup-sessions` already exists.

---

## Phase 10 Implementation Plan

### Priority Order

| Priority | Item | Effort | Value |
|---|---|---|---|
| 🔴 P1 | **10d: Fix WebUntis v2 endpoint** | Low (1-line fix + test) | Critical — endpoint is broken |
| 🔴 P1 | **10b: Login rate limit ENV-config** | Low (refactor existing code) | Security hardening |
| 🟡 P2 | **10e: Audit log date range filter** | Medium | Operational visibility |
| 🟡 P2 | **10c: WebUntis frontend extraction** | High | Code quality / maintainability |
| 🟢 P3 | **10e: Audit log CSV export** | Medium | Compliance / ops |
| 🟢 P3 | **10f: Operational runbook** | Low | Documentation |
| 🟢 P3 | **10f: code_prefix rotation guidance** | Low | Ops clarity |

---

### 10b: Login Rate Limiting (ENV-configurable)

**Current state:** Already implemented via `flask-limiter` with hardcoded `"5 per minute;20 per hour"`. Needs ENV-configurability and better error responses.

#### What to change

**File:** [`backend/api/auth_routes.py`](backend/api/auth_routes.py)

```python
# Add at top of file:
import os as _os

_LOGIN_RATE_MAX = int(_os.environ.get("LOGIN_RATE_LIMIT_MAX", "10"))
_LOGIN_RATE_WINDOW = int(_os.environ.get("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "900"))

# Replace existing decorator:
@auth_bp.route("/login", methods=["POST"])
@limiter.limit(f"{_LOGIN_RATE_MAX} per {_LOGIN_RATE_WINDOW} seconds")
def login():
    ...
```

**Custom 429 handler** — add to `app.py` or `auth_routes.py`:
```python
from flask_limiter.errors import RateLimitExceeded

@app.errorhandler(RateLimitExceeded)
def handle_rate_limit(e):
    # Parse window from limiter context to compute minutes remaining
    retry_after = getattr(e, "retry_after", _LOGIN_RATE_WINDOW)
    minutes = max(1, round(retry_after / 60))
    return jsonify({"error": f"Too many login attempts. Try again in {minutes} minutes."}), 429
```

#### ENV vars

| Variable | Default | Meaning |
|---|---|---|
| `LOGIN_RATE_LIMIT_MAX` | `10` | Max attempts per window |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | `900` | Window duration in seconds (900 = 15 min) |

#### Behaviour specification
- IP-based (via `get_remote_address`, X-Forwarded-For aware)
- Window-based only — **no reset on successful login**
- Applies to `POST /api/v2/auth/login` only (not logout/me)
- Single-process in-memory storage (acceptable for Render single-worker deployment; documented caveat)
- **Caveat:** `flask-limiter` defaults to in-process memory store when no `storage_uri` is set. In a multi-worker deployment (e.g. `gunicorn -w 4`) this is per-worker, not global. Document this clearly. For Render's single-worker free tier this is fine.

#### Tests to write
- `tests/test_auth_api.py` — add test for `429` after `LOGIN_RATE_LIMIT_MAX` attempts
- Mock `get_remote_address` to control IP

---

### 10c: WebUntis Frontend Extraction

#### Goal
Extract the WebUntis block (~470 core lines + ~200 picker lines = ~670 lines total) from `src/app.js` into `src/features/webuntis.js`, following the same pattern as [`src/features/grades.js`](src/features/grades.js).

#### Functions to extract

**Core rendering (move verbatim):**
- `renderWebUntisControls()`
- `renderWebUntisPicker()`
- `renderWebUntisWatchlist()`
- `renderWebUntisPlanStrip()`
- `renderWebUntisSchedule()`
- `renderWeekSchedule()`
- `renderAgendaGroups()`
- `renderAgendaGroup()`
- `renderDayGroup()`
- `renderDayEvent()`
- `renderWeekEvent()`

**Data helpers (move verbatim):**
- `getWebUntisEvents()`
- `groupEventsByDay()`
- `buildWeekColumns()`
- `getWeekAnchorDate()`
- `nextWeekLabel()`
- `getWebUntisRangeLabel()`
- `renderEmptyWeekColumn()`
- `findNextEventAfter()`
- `extractClassLabels()`

**Picker helpers (move verbatim):**
- `bindPickerActions()`
- `getGlobalPickerResults()`
- `getPickerEntities()`
- `getFavoriteEntities()`
- `isEntityActive()`
- `getActivePlan()`
- `getPinnedPlans()`
- `selectPlanById()`
- `closePicker()`
- `renderPickerItem()`
- `isPlanChipActive()`
- `shortcutTypeLabel()`
- `watchStatusClass()`
- `watchStatusLabel()`
- `eventStateLabel()`
- `eventStateTagClass()`
- `getEventTimingClass()`
- `isEventCurrent()`
- `isCancelledEvent()`
- `compactEventDetail()`

**State/localStorage (either move or expose via `init`):**
- `loadSavedShortcuts()`
- `loadWebUntisFavorites()`
- `saveShortcut()`
- `saveWebUntisFavorites()`
- Constants: `WEBUNTIS_SHORTCUTS_KEY`, `WEBUNTIS_FAVORITES_KEY`, `ACTIVE_WEBUNTIS_PLAN_KEY`

#### Proposed `src/features/webuntis.js` structure

```javascript
(function () {
  'use strict';

  // ── Constants ────────────────────────────────────────────────────────────────
  var WEBUNTIS_SHORTCUTS_KEY = "lehrerCockpit.webuntis.shortcuts";
  var WEBUNTIS_FAVORITES_KEY = "lehrerCockpit.webuntis.favorites";
  var ACTIVE_WEBUNTIS_PLAN_KEY = "lehrerCockpit.webuntis.activePlan";

  // ── Internal references (set via init) ──────────────────────────────────────
  var _state = null;
  var _elements = null;
  var _callbacks = {};  // { getData, formatDate, weekdayLabel, isSameDay, ... }

  // ── All WebUntis functions ───────────────────────────────────────────────────
  // ... (all functions moved here) ...

  // ── Public API ───────────────────────────────────────────────────────────────
  function init(state, elements, callbacks) {
    _state = state;
    _elements = elements;
    _callbacks = callbacks || {};
  }

  window.LehrerWebUntis = {
    init: init,
    renderWebUntisControls: renderWebUntisControls,
    renderWebUntisPicker: renderWebUntisPicker,
    renderWebUntisWatchlist: renderWebUntisWatchlist,
    renderWebUntisPlanStrip: renderWebUntisPlanStrip,
    renderWebUntisSchedule: renderWebUntisSchedule,
    getWebUntisEvents: getWebUntisEvents,
    loadSavedShortcuts: loadSavedShortcuts,
    loadWebUntisFavorites: loadWebUntisFavorites,
  };
})();
```

#### What stays in `src/app.js` as delegates

```javascript
// Delegate calls after window.LehrerWebUntis.init(state, elements, callbacks)
function renderWebUntisControls() {
  if (window.LehrerWebUntis) window.LehrerWebUntis.renderWebUntisControls();
}
// ... (same pattern for each function)
```

#### `index.html` load order
```html
<script src="src/features/grades.js"></script>
<script src="src/features/webuntis.js"></script>   <!-- NEW -->
<script src="src/app.js"></script>
```

#### Risks
- `webuntis.js` functions call many utility helpers (`formatDate`, `weekdayLabel`, `isSameDay`, `startOfWeek`, `isoWeekNumber`, `formatTime`, `getVisiblePanelItems`, `setExpandableMeta`, `bindExternalLink`) that remain in `app.js`
- These need to be passed through `callbacks` or kept in a shared `src/utils.js`
- **Recommendation:** Pass utility functions via the `callbacks` object in `init()` — no new files needed for Phase 10
- Risk of subtle closure bugs if state references are not correctly threaded through `_state`
- Event handlers in `registerEvents()` that call WebUntis functions must remain delegating to the module after init

---

### 10d: WebUntis v2 Data Endpoint Fix

**File:** [`backend/api/module_routes.py`](backend/api/module_routes.py:175)

#### The bug

```python
# Current (broken):
data = fetch_webuntis_sync(base_url, ical_url, now)
return success({"data": data})  # WebUntisSyncResult dataclass → TypeError

# Fix:
from dataclasses import asdict
data = fetch_webuntis_sync(base_url, ical_url, now)
return success({"data": asdict(data)})
```

#### What the endpoint should return

```json
{
  "ok": true,
  "data": {
    "source": { "id": "webuntis", "name": "WebUntis", "status": "ok", ... },
    "schedule": [...],
    "priorities": [...],
    "events": [...],
    "mode": "live-webuntis",
    "note": "WebUntis läuft live über deinen persönlichen iCal-Export."
  }
}
```

#### Frontend consumption (future Phase 10d work)

Once the endpoint works correctly, `src/features/webuntis.js` can be extended to:
1. Call `GET /api/v2/modules/webuntis/data` when `MULTIUSER_ENABLED` is true
2. Use the returned `data.events` and `data.source` to populate `state.data.webuntisCenter`
3. Fall back to `state.data.webuntisCenter` from the v1 dashboard payload if the v2 call fails

#### Module config fields needed
- `ical_url` — personal WebUntis iCal URL (already collected during onboarding via `PUT /api/v2/modules/webuntis/config`)
- `base_url` — WebUntis school base URL (optional, for "open today" link)

#### Tests to write
- `tests/test_module_routes.py` — add test for `GET /api/v2/modules/webuntis/data` with mocked `fetch_webuntis_sync`
- Verify JSON response is serializable (no dataclass)
- Test with empty `ical_url` (should return `mode: "missing"`)

---

### 10e: Audit Log Improvements

#### Current state
- Backend: filters by `event_type` + pagination only
- Frontend: event_type dropdown + prev/next pagination
- Missing: **date range filter**, **CSV export**, **user_name filter**

#### Priority improvements

##### 1. Date range filter (backend + frontend)

**Backend change** ([`backend/api/admin_routes.py`](backend/api/admin_routes.py:447)):

```python
# Add date_from and date_to query params:
date_from = request.args.get("date_from", "").strip() or None  # ISO date "2026-01-01"
date_to = request.args.get("date_to", "").strip() or None      # ISO date "2026-03-31"

# Build WHERE clause dynamically:
conditions = []
params = []
if event_type:
    conditions.append("al.event_type = %s")
    params.append(event_type)
if date_from:
    conditions.append("al.created_at >= %s::date")
    params.append(date_from)
if date_to:
    conditions.append("al.created_at < (%s::date + INTERVAL '1 day')")
    params.append(date_to)

where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
```

**Frontend change** (`admin.html`): Add `<input type="date">` for date_from/date_to above the event_type filter.

##### 2. CSV export endpoint

```python
@admin_bp.route("/audit-log/export", methods=["GET"])
@require_admin
def export_audit_log():
    """Export audit log as CSV. Supports same filters as GET /audit-log."""
    import csv
    import io
    # ... (fetch rows, write csv, return Response with Content-Disposition: attachment)
```

##### 3. Better event type labels in frontend

Map raw `event_type` strings to human-readable labels:

```javascript
var EVENT_LABELS = {
  'login_success': 'Login OK',
  'login_failure': 'Login Fehler',
  'teacher_created': 'Lehrkraft angelegt',
  'teacher_deactivated': 'Lehrkraft deaktiviert',
  'code_rotated': 'Code rotiert',
};
```

#### Event types currently logged
- `login_success`, `login_failure`
- `teacher_created`, `teacher_deactivated`
- `code_rotated`

#### What has highest value
1. **Date range filter** — needed for real operational use (investigating incidents)
2. **CSV export** — needed for compliance reporting
3. **Better labels** — cosmetic but improves usability

---

### 10f: Operational Helpers

#### code_prefix backfill — Status: NOT POSSIBLE

Existing `NULL` `code_prefix` rows in `user_access_codes` **cannot be backfilled** without knowing the original plaintext codes. The `code_prefix` is the first 8 characters of the plaintext access code, stored only to enable O(1) prefix-lookup during authentication. Since the plaintext is never stored after code generation, backfilling requires code rotation.

**Recommended approach:**
- Admin UI: warn when `code_prefix IS NULL` rows exist
- Provide a "bulk rotate codes" option that regenerates all codes with NULL prefix
- Route already exists: `POST /api/v2/admin/users/<id>/rotate-code`
- Missing: batch route `POST /api/v2/admin/maintenance/rotate-null-prefix-codes`

#### Session cleanup — Already implemented

`POST /api/v2/admin/maintenance/cleanup-sessions` exists in [`backend/api/admin_routes.py:529`](backend/api/admin_routes.py:529) and is already accessible from `admin.html`.

#### Maintenance runbook

**New file:** `docs/maintenance_runbook.md`

Should document:
1. **Session cleanup** — when to run, expected output
2. **Code rotation** — when required (NULL code_prefix, suspected compromise)
3. **Encryption backfill** — when/how to run `scripts/backfill_encryption.py`
4. **Database backup** — instructions for Render PostgreSQL
5. **ENV vars reference** — all required/optional ENV vars with defaults
6. **Rate limit monitoring** — how to identify abuse from audit log
7. **Bootstrap admin** — how to recover if admin locked out

---

## Risks and Caveats

### Rate Limiting (10b)
- **Multi-worker caveat:** `flask-limiter` in-process memory store is per-worker. On Render free tier (1 worker) this is fine. If Render adds multi-worker, rate limits become ineffective. Document this explicitly. For true multi-worker enforcement, set `RATELIMIT_STORAGE_URI=redis://...` in ENV.
- **IP spoofing:** `get_remote_address` uses `X-Forwarded-For` on Render. Ensure only Render's trusted proxy is in the chain.

### WebUntis Extraction (10c)
- `src/app.js` is 3 501 lines. The WebUntis block is deeply embedded in a single IIFE closure. During extraction, every reference to `state`, `elements`, `getData()`, and utility functions must be threaded via the `_callbacks` pattern.
- **Regression risk is HIGH.** The picker has complex stateful interaction (categories, favorites, search). Thorough manual testing required after extraction.
- **Mitigation:** Extract to a parallel file first, keep all original functions in `app.js` with `TODO: remove after webuntis.js verified` comment. Only delete originals after 1 sprint of testing.

### WebUntis v2 Endpoint (10d)
- `WebUntisSyncResult.events` contains `dict[str, str]` items — already serializable to JSON
- The **dataclass wrapper** is the only issue — `dataclasses.asdict()` fixes it completely
- After fix, the `data.events` shape matches what `_to_event_item()` produces — compatible with `normalizeDashboard()` in `app.js`

### Audit Log Date Filter (10e)
- The `audit_log.created_at` column is a `TIMESTAMPTZ` (PostgreSQL). Date comparison using `::date` is timezone-sensitive. Use `AT TIME ZONE 'Europe/Berlin'` if the admin expects Berlin-local dates.

### code_prefix NULL backfill (10f)
- **Affects authentication performance only.** NULL `code_prefix` rows fall back to full table scan + argon2 verify for all users. With <50 users this is ~50 hashes × ~300ms = ~15s. Practically only relevant for first-login after phase 8/9 migration.
- Priority: rotate all codes in the first admin maintenance window.

---

## Implementation Order (Recommended Sprints)

### Sprint 10.1 — Quick wins (estimate: 2–3 hours)
1. **10d:** Fix `WebUntisSyncResult` JSON serialization (`dataclasses.asdict`) + test
2. **10b:** Make rate limit ENV-configurable + custom 429 message + test

### Sprint 10.2 — Audit log (estimate: 3–4 hours)
3. **10e.1:** Add `date_from`/`date_to` to backend audit-log endpoint + frontend date pickers
4. **10e.2:** Add CSV export endpoint + button in admin UI
5. **10e.3:** Better event type labels in admin.html

### Sprint 10.3 — Frontend extraction (estimate: 4–6 hours)
6. **10c:** Extract `src/features/webuntis.js` from `src/app.js`
   - Create file with `window.LehrerWebUntis` API
   - Add `<script>` tag in `index.html`
   - Wire delegates in `app.js`
   - Manual regression test: all 3 views (day/week/next-week), picker, favorites, plan strip

### Sprint 10.4 — Operational (estimate: 2 hours)
7. **10f.1:** Add `POST /api/v2/admin/maintenance/rotate-null-prefix-codes` endpoint
8. **10f.2:** Write `docs/maintenance_runbook.md`

---

## File Change Summary

| File | Phase 10 Change |
|---|---|
| `backend/api/auth_routes.py` | ENV-driven rate limit + custom 429 handler |
| `backend/api/module_routes.py` | Fix `WebUntisSyncResult` → `asdict()` |
| `backend/api/admin_routes.py` | Add date_from/date_to to audit-log, CSV export, bulk code rotate |
| `admin.html` | Date pickers, CSV export button, event labels |
| `src/features/webuntis.js` | NEW — extracted WebUntis module |
| `index.html` | Add `<script src="src/features/webuntis.js">` |
| `src/app.js` | Replace WebUntis functions with delegates; keep originals until verified |
| `docs/maintenance_runbook.md` | NEW — operational runbook |
| `tests/test_auth_api.py` | Rate limit 429 test |
| `tests/test_module_routes.py` | WebUntis v2 endpoint serialization test |
| `tests/test_admin_routes.py` | Audit log date filter + CSV export tests |

---

*Document prepared as part of Phase 10 planning. Audit performed against HEAD commit `2472eb7`.*
