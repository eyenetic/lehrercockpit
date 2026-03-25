# Phase 9 Implementation Record

> **Produced:** 2026-03-25 | **Scope:** Phase 9 (post Phase 8g)

---

## Goals Achieved

- [x] Per-user grades DB table + v2 CRUD API
- [x] Per-user class_notes DB table + v2 CRUD API
- [x] `GET /api/v2/admin/audit-log` with pagination and filtering
- [x] Audit events for teacher_created, teacher_deactivated, code_rotated
- [x] `code_prefix` O(1) auth lookup optimization (backward compatible)
- [x] `scripts/backfill_encryption.py` — idempotent, dry-run, safe
- [x] `src/features/grades.js` extracted from app.js monolith
- [x] Admin audit log UI tab in admin.html
- [x] `loadDashboard()` overlays v2 grades/notes data on v1 payload

---

## Key Architecture: Grades/Notes v2

### DB Tables

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

### Ownership Enforcement

- Each grade row has `user_id FK` → teachers only see their own grades
- All write endpoints include `AND user_id = %s` ownership check
- `delete_grade(conn, user_id, grade_id)` returns `False` if wrong owner (no 403 leakage)
- `upsert_note()` uses `ON CONFLICT (user_id, class_name) DO UPDATE` — idempotent

### API Endpoints (Phase 9)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/v2/modules/noten/data` | cookie | `{grades: [...], notes: [...]}` |
| POST | `/api/v2/modules/noten/grades` | cookie | Create/update grade; body: `{class_name, subject, grade_value, grade_date?, note?, id?}` |
| DELETE | `/api/v2/modules/noten/grades/<id>` | cookie | Ownership enforced; 404 if wrong user |
| POST | `/api/v2/modules/noten/notes` | cookie | Upsert note; body: `{class_name, note_text}` |
| DELETE | `/api/v2/modules/noten/notes/<class_name>` | cookie | 404 if not found |
| GET | `/api/v2/admin/audit-log` | admin | `{events, total, limit, offset}`; query: `limit`, `offset`, `event_type` |

### Frontend Integration

`src/features/grades.js` exposes `window.LehrerGrades`:
- `init(state, elements, callbacks)` — receives shared state refs
- `loadGradebook()` — calls `GET /api/v2/modules/noten/data`
- `loadNotes()` — uses noten data response
- `saveGradeEntry()` — calls `POST /api/v2/modules/noten/grades`
- `deleteGradeEntry(id)` — calls `DELETE /api/v2/modules/noten/grades/<id>`
- `saveClassNote()` — calls `POST /api/v2/modules/noten/notes`
- `clearClassNote()` — calls `DELETE /api/v2/modules/noten/notes/<class>`

`src/app.js` delegates all grade/note calls to `window.LehrerGrades` via thin wrappers.
`loadDashboard()` overlays v2 noten data on v1 payload after load.

---

## code_prefix Optimization

- `PREFIX_LENGTH = 8`: first 8 chars of plaintext code (uppercased)
- Stored in `user_access_codes.code_prefix` alongside argon2id hash
- Existing NULL-prefix rows still work (fallback `OR code_prefix IS NULL` in WHERE clause)
- New registrations / code rotations automatically store prefix
- `authenticate_by_code()` pre-filters by prefix → typically 0–1 rows for argon2id verify
- **Backfill not possible**: argon2id is one-way — old codes must be rotated to get prefix

---

## backfill_encryption.py

File: `scripts/backfill_encryption.py`

- Iterates all rows in `user_module_configs`
- For each row: `decrypt_config()` → `encrypt_config()` → compare
- Only updates rows where result differs (plaintext sensitive fields)
- Round-trip verification before each write: `encrypt → decrypt → assert equals original`
- `--dry-run` flag: shows what would change without writing
- `--verbose` flag: prints details for every row
- Exit codes: `0` success, `1` missing env vars, `2` DB error, `3` round-trip failure
- Idempotent: safe to re-run (already-encrypted rows are skipped)

---

## Admin Audit Log UI

Tab added to `admin.html`:
- `data-tab="audit"` button in nav
- `id="tab-audit"` section
- `id="audit-table-container"` for the table
- Event type filter: `id="audit-event-filter"` select
- Pagination: `id="audit-prev"`, `id="audit-next"`, `id="audit-page-info"`
- Default 50 events/page; newest first; no auto-refresh

---

## Deferred / Remaining

- [ ] Run `scripts/backfill_encryption.py` on Render to encrypt existing plaintext configs
- [ ] Migrate v1 `/api/dashboard` payload to per-module v2 endpoints (webuntis, itslearning, orgaplan, classwork)
- [ ] Extract `src/features/webuntis.js` (~470 lines)
- [ ] `code_prefix` backfill for existing access codes (rotate to get prefix)
- [ ] Rate limiting on `/api/v2/auth/login` endpoint — already implemented (5/min, 20/hr)
- [ ] Session cleanup automation (currently manual trigger only)

---

## Test Coverage Added (Phase 9)

| File | New tests | Notes |
|---|---|---|
| `tests/test_module_routes.py` | +12 | noten v2 auth + mock tests |
| `tests/test_admin_routes.py` | +6 | audit-log endpoint tests |
| `tests/test_access_code.py` | +8 | get_code_prefix() tests |
| `tests/test_frontend_structure.py` | +7 | grades.js, backfill, audit-log UI |
| `tests/test_grades_notes_v2.py` | 18 (new) | Service layer unit + DB integration |
| `tests/test_backfill.py` | 9 (new) | Compile, dry-run, skip, live, env checks |
