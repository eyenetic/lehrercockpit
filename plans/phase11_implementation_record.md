# Phase 11 Implementation Record

**Date:** 2026-03-26
**Phase:** 11 — v1→v2 Dashboard Migration, itslearning.js Extraction, Testing & Documentation

---

## Goals Achieved

- [x] Fixed itslearning + nextcloud v2 endpoint serialization bugs (`dataclasses.asdict()`)
- [x] Fixed nextcloud `NextcloudSettings` constructor mismatch (`nextcloud_data()` now constructs `NextcloudSettings` from config dict before calling `fetch_nextcloud_sync(settings, now)`)
- [x] `orgaplan_data()` returns parsed digest with 60min server-side caching (stores in `system_settings`)
- [x] `klassenarbeitsplan_data()` returns classwork cache content (prefers `classwork-cache.json`, falls back to `build_plan_digest()`)
- [x] `GET /api/v2/dashboard/data` — parallel aggregated module data (`ThreadPoolExecutor`, 5s per-module timeout)
- [x] `overlayV2ModuleData()` in `src/app.js` — v2 module data overlaid on v1 base payload
- [x] `DashboardManager.getActiveModuleIds()` — filters fetches to active/visible modules only
- [x] `src/features/itslearning.js` extracted (~130 lines; exposes `window.LehrerItslearning`)
- [x] v1 endpoints marked deprecated with `X-Deprecated` header (`GET /api/classwork`, `GET /api/grades`, `GET /api/notes`, `POST /api/local-settings/itslearning`, `POST /api/local-settings/nextcloud`)
- [x] Phase 11f: Tests for itslearning/nextcloud/orgaplan/klassenarbeitsplan v2 endpoints (`tests/test_module_routes.py`)
- [x] Phase 11f: Tests for `GET /api/v2/dashboard/data` (`tests/test_dashboard_routes.py`)
- [x] Phase 11f: Tests for `src/features/itslearning.js` existence and load order (`tests/test_frontend_structure.py`)
- [x] Phase 11g: `README.md` updated — new endpoints, deprecated v1 section, dashboard architecture note, frontend structure, next steps
- [x] Phase 11g: `CLAUDE_HANDOFF.md` updated — Phase 11 deliverables, technical debt, API reference, frontend pages, script load order, next steps
- [x] Phase 11g: `plans/phase11_implementation_record.md` created (this file)

---

## Dashboard Composition Architecture (Phase 11)

### Before Phase 11

```
loadDashboard()
  └── GET /api/dashboard (v1, global .env.local settings, not per-user)
        provides: quickLinks, workspace, berlinFocus, documentMonitor,
                  webuntisCenter, messages, planDigest, sources, schedule
  └── GET /api/v2/modules/noten/data overlay (Phase 9)
        replaces: grades, notes
```

### After Phase 11

```
loadDashboard()
  ├── loadDashboardV1Base()
  │     └── GET /api/dashboard (v1) — base payload
  │           provides: quickLinks, workspace, berlinFocus, documentMonitor
  │           (still used because no v2 equivalent for these yet)
  │
  └── overlayV2ModuleData()
        └── GET /api/v2/dashboard/data — parallel module fetch
              replaces per-module data:
              ├── webuntisCenter (from WebUntis iCal per-user)
              ├── messages (from itslearning per-user credentials)
              ├── planDigest.orgaplan (from PDF digest, 60min cache)
              └── planDigest.classwork (from classwork cache)

  Grades/notes: GET /api/v2/modules/noten/data (Phase 9 — unchanged)
  v1 data is always the safety net; v2 overlay fails silently per module
```

### Key Design Decisions

1. **`Promise.allSettled()` / `ThreadPoolExecutor`** — one module failing does not block others
2. **Active modules only** — `DashboardManager.getActiveModuleIds()` skips fetching disabled modules
3. **v1 still the base** — quickLinks, workspace, berlinFocus, documentMonitor have no v2 equivalent yet; v1 `GET /api/dashboard` serves them
4. **5-second per-module timeout** — prevents slow external APIs from blocking the dashboard

---

## Files Changed

| File | Change |
|---|---|
| `backend/api/module_routes.py` | Fixed `itslearning_data()` + `nextcloud_data()` serialization; enhanced `orgaplan_data()` with cached digest; enhanced `klassenarbeitsplan_data()` with cache |
| `backend/api/dashboard_routes.py` | Added `GET /api/v2/dashboard/data` with `ThreadPoolExecutor` parallel fetch; `_fetch_*_data()` helpers |
| `src/api-client.js` | Added `getModuleData(moduleId)` v2 method |
| `src/modules/dashboard-manager.js` | Added `getActiveModuleIds()` public method |
| `src/app.js` | Added `overlayV2ModuleData()`, `applyWebuntisV2Data()`, `applyItslearningV2Data()`, `applyOrgaplanV2Data()`, `applyClassworkV2Data()`; replaced `renderItslearningConnector()` / `saveItslearningCredentials()` / `getRelevantInboxMessages()` with delegates |
| `src/features/itslearning.js` | **NEW** — `window.LehrerItslearning` IIFE module |
| `index.html` | Added `<script src="./src/features/itslearning.js?v=37"></script>` (position 5 in load order) |
| `app.py` | Added `X-Deprecated` headers to 5 v1 endpoints |
| `tests/test_module_routes.py` | Added 12 new test functions for Phase 11 endpoints |
| `tests/test_dashboard_routes.py` | **NEW** — 9 test functions for `GET /api/v2/dashboard/data` |
| `tests/test_frontend_structure.py` | Added 8 new test functions for Phase 11 frontend structure |
| `README.md` | Updated API endpoints, deprecated v1 section, dashboard note, frontend structure, next steps |
| `CLAUDE_HANDOFF.md` | Updated Phase 11 deliverables, technical debt, API reference, frontend pages, next steps |

---

## Remaining Deferred Items

- [ ] Full v1 `GET /api/dashboard` retirement (needs v2 equivalents for quickLinks, workspace, berlinFocus)
- [ ] Extract `src/features/nextcloud.js`
- [ ] Admin UI for orgaplan URL configuration (currently API-only via `PUT /api/v2/admin/settings`)
- [ ] WebUntis full schedule v2 endpoint (current `GET /api/v2/modules/webuntis/data` returns basic sync result, not the full picker/finder/watchlist data)
- [ ] Remove delegate fallbacks in `src/app.js` for itslearning functions (after production verification)
