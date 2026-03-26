# Phase 12 Implementation Record
## Title: Retire Frontend Dependency on GET /api/dashboard (v1)

**Date:** 2026-03-26  
**Status:** ✅ Complete  
**Tests:** 269 passed, 0 failed (4 new backend tests, 3 new frontend tests)

---

## Objective

Retire the last remaining frontend dependency on `GET /api/dashboard` (v1) for the base payload (quickLinks, workspace, berlinFocus). Switch `loadDashboard()` in `src/app.js` to use `GET /api/v2/dashboard/data` as the primary data source when `MULTIUSER_ENABLED=true`. Keep v1 as a fallback for local runtime.

---

## v1 Field Audit

### Fields extracted by `normalizeDashboard()` from v1 response

| v1 field | Render function(s) that consume it | v2 status after Phase 12 |
|---|---|---|
| `workspace` | `renderWorkspace()` | ✅ Now in `base.workspace` |
| `quickLinks` | `renderQuickLinks()` | ✅ Now in `base.quick_links` |
| `berlinFocus` | `renderBerlinFocus()` | ✅ Now in `base.berlin_focus` |
| `meta` | `renderMeta()`, `renderRuntimeBanner()` | ⚠️ Synthesized in `normalizeV2Dashboard()` |
| `priorities` | `renderPriorities()`, `renderBriefing()` | ✅ Overlay via `_applyWebuntisV2Data()` / `_applyItslearningV2Data()` (Phase 11) |
| `messages` | `renderMessages()`, `renderChannelFilters()` | ✅ Overlay via `_applyItslearningV2Data()` (Phase 11) |
| `sources` | `renderSources()` | ✅ Overlay via `_applyItslearningV2Data()` (Phase 11) |
| `documents` | `renderDocuments()` | ⏳ DEFERRED — returns `null` in v2; requires document_monitor pipeline |
| `documentMonitor` | `renderDocumentMonitor()` | ⏳ DEFERRED — defaults to `[]`; requires document_monitor pipeline |
| `webuntisCenter` | `renderWebUntisControls()`, `renderWebUntisSchedule()`, `renderBriefing()` | ✅ Overlay via `_applyWebuntisV2Data()` (Phase 11) |
| `planDigest.orgaplan` | `renderPlanDigest()`, `renderBriefing()` | ✅ Overlay via `_applyOrgaplanV2Data()` (Phase 11) |
| `planDigest.classwork` | `renderPlanDigest()`, `renderBriefing()` | ✅ Overlay via `_applyClassworkV2Data()` (Phase 11) |
| `grades` / `notes` | `renderGrades()`, `renderClassNotes()` | ✅ Overlay via noten module (Phase 9 / Phase 11) |
| `localConnections` | `renderItslearningConnector()`, `renderNextcloudConnector()` | N/A — only used in local-runtime; not relevant in SaaS mode |

---

## normalizeV2Dashboard() Field Mapping

```javascript
function normalizeV2Dashboard(v2) {
  var data = normalizeDashboard({});  // defaults

  // base section
  if (v2.base.workspace)    data.workspace   = v2.base.workspace;
  if (v2.base.quick_links)  data.quickLinks  = v2.base.quick_links;
  if (v2.base.berlin_focus) data.berlinFocus = v2.base.berlin_focus;
  // documents deferred — keeps default []

  // modules section (same helpers as overlayV2ModuleData)
  _applyWebuntisV2Data(data, modules.webuntis.data)
  _applyItslearningV2Data(data, modules.itslearning.data)
  _applyOrgaplanV2Data(data, modules.orgaplan.data)
  _applyClassworkV2Data(data, modules.klassenarbeitsplan.data)
  // noten module
  data.grades = modules.noten.data.grades
  data.notes  = modules.noten.data.notes

  // meta
  data.meta.mode = 'live'
  data.generatedAt = v2.generated_at
}
```

---

## Changes Made

### Step 2: Backend — `backend/api/dashboard_routes.py`

- Added `_build_base_quick_links()` helper — builds the quick_links list from system_settings / local config
- Added `_fetch_base_data()` function — fetches `quick_links`, `workspace`, `berlin_focus` independently; `documents` deferred (returns `None`); uses `_safe_str()` guard to prevent MagicMock/non-string values from leaking into JSON serialization
- Extended `get_dashboard_data()` to include `_fetch_base_data` in the parallel `ThreadPoolExecutor` run (as `__base__` key)
- Response now includes `base: {quick_links, workspace, berlin_focus, documents}` alongside `modules`

**Updated response shape:**
```json
{
  "ok": true,
  "base": {
    "quick_links":  [{id, title, url, kind, note}],
    "workspace":    {"eyebrow": "...", "title": "...", "description": "..."},
    "berlin_focus": [{"title": "...", "detail": "..."}],
    "documents":    null
  },
  "modules": { ... },
  "user": {"id": 1, "display_name": "..."},
  "generated_at": "ISO"
}
```

### Step 3: Frontend — `src/app.js`

- **`loadDashboard()`** — added v2 PRIMARY path at the top:
  - When `MULTIUSER_ENABLED && window.LehrerAPI`: call `getDashboardData()` first
  - On `v2Json.ok`: call `normalizeV2Dashboard(v2Json)` and return immediately
  - On any failure: fall through to v1 path (with `console.warn`)
  - Removed the Phase-11 `overlayV2ModuleData()` call from the v1 path (redundant when v2 is primary)
  - Fixed `let data` (was `const`) to allow reassignment in the v1 path

- **`normalizeV2Dashboard(v2)`** — new function inserted before `getData()`:
  - Starts from `normalizeDashboard({})` for safe defaults
  - Maps `v2.base.workspace` → `data.workspace`
  - Maps `v2.base.quick_links` → `data.quickLinks`
  - Maps `v2.base.berlin_focus` → `data.berlinFocus`
  - Calls all existing `_apply*V2Data()` helpers for per-module fields
  - Maps `v2.modules.noten.data` → `data.grades` / `data.notes`
  - Sets `data.meta.mode = 'live'` and `data.generatedAt = v2.generated_at`

### Step 4: `app.py`

- Added `X-Deprecated: Use GET /api/v2/dashboard/data` response header to `GET /api/dashboard`
- Added deprecation comment above the route

### Step 5: `src/api-client.js`

- No changes needed — `getDashboardData()` already existed and pointed to the correct URL

---

## Tests Added

### `tests/test_dashboard_routes.py` (4 new tests)

| Test | Description |
|---|---|
| `test_dashboard_data_response_has_base_key` | Response contains `base` dict |
| `test_dashboard_data_base_has_quick_links` | `base.quick_links` is a list with ≥1 entry |
| `test_dashboard_data_base_has_workspace` | `base.workspace` is a dict |
| `test_dashboard_data_base_sections_independent_on_base_failure` | If `_fetch_base_data` raises, endpoint still returns 200 with `ok=true` and safe default `base` values |

### `tests/test_frontend_structure.py` (3 new tests)

| Test | Description |
|---|---|
| `test_app_js_contains_normalizeV2Dashboard` | `src/app.js` defines `normalizeV2Dashboard` |
| `test_app_js_calls_getDashboardData_as_primary` | `src/app.js` calls `getDashboardData` |
| `test_app_py_api_dashboard_has_x_deprecated` | `app.py` contains `Use GET /api/v2/dashboard/data` |

---

## Deferred Items (Known Technical Debt)

| Item | Reason | Impact |
|---|---|---|
| `base.documents` returns `null` | Requires `build_document_monitor()` + mock enrichment pipeline — heavy, local-only | Documents panel shows empty state in SaaS mode (same as before Phase 12) |
| `base.documentMonitor` not included | Same reason as documents | Document monitor panel shows empty state |
| `localConnections` not in v2 | Only used by local-runtime connectors (itslearning, nextcloud credentials) — not needed in SaaS mode | No impact in SaaS mode; v1 fallback still serves local runtime |

---

## Verification

```
find backend/ -name "*.py" | xargs python3 -m py_compile → ALL OK
python3 -m pytest tests/ → 269 passed, 104 skipped, 0 failed
```

Test files target: `tests/test_dashboard_routes.py` (13 tests), `tests/test_frontend_structure.py` (35 tests)
