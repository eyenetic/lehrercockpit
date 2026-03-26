# Phase 10 Implementation Record

**Date:** 2026-03-25  
**Branch:** main  
**Phases completed:** 10b, 10c, 10d, 10e, 10f, 10g, 10h

---

## Goals Achieved

- [x] ENV-driven login rate limiting with custom 429 handler
- [x] WebUntis v2 endpoint JSON serialization fix + missing config handling
- [x] `src/features/webuntis.js` extracted from `src/app.js` (~935 lines)
- [x] Audit log date range filter (`date_from`, `date_to` query params)
- [x] Audit log CSV export (`GET /api/v2/admin/audit-log/export.csv`)
- [x] Human-readable German event labels in audit log UI
- [x] `GET /api/v2/admin/maintenance/null-prefix-users` operational endpoint
- [x] `docs/operations_runbook.md` — comprehensive post-deploy and maintenance guide
- [x] Phase 10g: Tests extended (rate limit, audit log improvements, WebUntis v2, frontend structure)
- [x] Phase 10h: Documentation updated (README, CLAUDE_HANDOFF, implementation record)

---

## Rate Limiting Design (Phase 10b)

- **Library:** `flask-limiter` with in-process memory storage (acceptable for single Render worker)
- **Defaults:** `5/min + 10/900sec` per IP — all configurable via ENV vars
- **ENV vars** (in `backend/config.py`):
  - `LOGIN_RATE_LIMIT_MAX_PER_MINUTE` — default `5`
  - `LOGIN_RATE_LIMIT_MAX` — default `10`
  - `LOGIN_RATE_LIMIT_WINDOW_SECONDS` — default `900`
  - `RATELIMIT_STORAGE_URI` — optional Redis URL for multi-worker
- **Custom 429 response:** German error message ("Zu viele Anmeldeversuche") + `retry_after_seconds` key + `Retry-After` header
- **Limit string:** built dynamically via `_login_limit_string()` callable — evaluated at request time, reflects ENV changes on restart
- **Multi-worker upgrade path:** set `RATELIMIT_STORAGE_URI=redis://...` in ENV

---

## WebUntis v2 Fix (Phase 10d)

- **Bug:** `WebUntisSyncResult` is a `@dataclass` — Flask's `jsonify` cannot serialize it directly
- **Fix:** `dataclasses.asdict(result)` applied before `return success({"data": data_dict})`
- **Missing config handling:** empty `ical_url` returns `{"configured": false}` with HTTP 200 (not 500)
- **File:** `backend/api/module_routes.py` — [`webuntis_data()`](backend/api/module_routes.py:176)

---

## Frontend Modularization Progress (Phase 10c)

| File | Status | Lines |
|---|---|---|
| `src/app.js` | Modified — delegates to `window.LehrerWebUntis` | ~3211 (reduced from ~3500+) |
| `src/features/webuntis.js` | NEW — extracted WebUntis module | ~935 |
| `src/features/grades.js` | Phase 9 — grades/notes module | ~200 |
| `src/modules/dashboard-manager.js` | Phase 8 — DashboardManager | ~270 |

**Extraction history:**
- Phase 8: `DashboardManager` → `src/modules/dashboard-manager.js`
- Phase 9: Grades/notes → `src/features/grades.js`
- Phase 10: WebUntis timetable → `src/features/webuntis.js`

**`index.html` script load order:**
```html
<script src="src/api-client.js"></script>
<script src="src/modules/dashboard-manager.js"></script>
<script src="src/features/grades.js"></script>
<script src="src/features/webuntis.js"></script>   <!-- Phase 10 addition -->
<script src="src/app.js"></script>
```

---

## Audit Log Improvements (Phase 10e)

### Date range filter
- Added `date_from` and `date_to` ISO date query params to `GET /api/v2/admin/audit-log`
- Shared `_build_audit_query(event_type, date_from, date_to)` helper returns `(where_clause, params)`
- Uses PostgreSQL `::date` cast and `INTERVAL '1 day'` for inclusive `date_to`
- **File:** `backend/api/admin_routes.py` — [`_build_audit_query()`](backend/api/admin_routes.py:450)

### CSV export
- New endpoint: `GET /api/v2/admin/audit-log/export.csv`
- Same filters as GET audit-log (up to 5000 rows)
- Response: `text/csv` with `Content-Disposition: attachment; filename="audit-log-YYYY-MM-DD.csv"`
- Columns: Zeitpunkt, Ereignis, Benutzer, IP, Details
- **File:** `backend/api/admin_routes.py` — [`export_audit_log_csv()`](backend/api/admin_routes.py:536)

---

## Operational Endpoint (Phase 10f)

### `GET /api/v2/admin/maintenance/null-prefix-users`
- Returns active users with `code_prefix IS NULL` in `user_access_codes`
- These users require code rotation for O(1) prefix-lookup auth
- Response: `{"ok": true, "users": [...], "count": int}`
- **File:** `backend/api/admin_routes.py` — [`get_null_prefix_users()`](backend/api/admin_routes.py:599)

---

## Testing (Phase 10g)

### New test functions added

**`tests/test_auth_api.py`** (+6 tests):
- `test_login_limit_string_contains_per_minute`
- `test_login_limit_string_contains_env_derived_values`
- `test_rate_limit_env_vars_exist_in_config`
- `test_rate_limit_env_vars_have_sane_defaults`
- `test_429_handler_json_contract`

**`tests/test_admin_routes.py`** (+6 tests):
- `test_get_audit_log_with_date_filter_returns_200`
- `test_export_audit_log_csv_without_auth_returns_401`
- `test_export_audit_log_csv_with_teacher_returns_403`
- `test_export_audit_log_csv_with_admin_returns_200_with_csv_content_type`
- `test_get_null_prefix_users_without_auth_returns_401`
- `test_get_null_prefix_users_with_admin_returns_200_with_users_list`

**`tests/test_module_routes.py`** (+3 tests):
- `test_webuntis_data_without_auth_returns_401`
- `test_webuntis_data_no_ical_url_returns_200_configured_false`
- `test_webuntis_data_with_ical_url_returns_serializable_json`

**`tests/test_frontend_structure.py`** (+8 tests):
- `test_webuntis_js_exists`
- `test_index_html_contains_webuntis_js_script`
- `test_index_html_webuntis_js_before_app_js`
- `test_webuntis_js_exports_window_lehrerwebuntis`
- `test_app_js_references_window_lehrerWebUntis`
- `test_operations_runbook_exists`
- `test_operations_runbook_contains_encryption_key_reference`

---

## Documentation (Phase 10h)

### `README.md` updates
- Rate limiting ENV vars added to environment variables table (Security section)
- Security section: rate limiting mechanism documented
- API endpoints: webuntis/data, audit-log/export.csv, null-prefix-users added
- Known Limitations: "rate limiting is in-process only" caveat added
- Next Steps: rate limit tuning and Redis backend steps added
- Frontend Structure: `src/features/webuntis.js` added
- Operations section added with reference to `docs/operations_runbook.md`

### `CLAUDE_HANDOFF.md` updates
- Phase 10 deliverables added to "What IS implemented"
- Known Technical Debt: rate limit in-process caveat added
- Frontend pages table: `src/features/webuntis.js` row added
- Script load order: `webuntis.js` added as step 4
- API Reference: webuntis/data description updated; Phase 10 admin endpoints added
- Recommended Next Steps: updated to reflect Phase 10 completions

---

## Deferred / Remaining

- [ ] Migrate v1 `/api/dashboard` main payload to v2 per-module endpoints
- [ ] Extract `src/features/itslearning.js`
- [ ] itslearning/nextcloud v2 data endpoints wired into `loadDashboard()`
- [ ] Rate limit Redis backend for multi-worker scaling (`RATELIMIT_STORAGE_URI`)
- [ ] `code_prefix` backfill — rotate existing codes via admin panel
- [ ] Session cleanup automation (probabilistic in `get_current_user()`)
