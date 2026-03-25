# Lehrercockpit Operations Runbook

> **Audience:** System administrators and operators deploying Lehrercockpit on Render.  
> **Last updated:** Phase 10 (2026-03)  
> **Stack:** Python/Flask backend on Render · PostgreSQL (Render Managed) · Netlify frontend

---

## Post-Deploy Tasks

### 1. Run Database Migrations

Migrations run automatically on app startup when `DATABASE_URL` is set. Check the Render deploy logs for:

```
[migrations] Alle Migrationen erfolgreich ausgeführt.
```

If migrations fail, check for:
- Missing `DATABASE_URL` environment variable
- Network connectivity to the PostgreSQL instance
- Schema conflicts (run `python3 -c "from app import app; app.run()"` locally with `DATABASE_URL` to reproduce)

Manual migration run (SSH or Render Shell):
```bash
python3 -c "
from backend.migrations import run_all_migrations
run_all_migrations()
print('Done')
"
```

---

### 2. Set `ENCRYPTION_KEY` and Encrypt Existing Module Configs

**Required ENV var:**
```
ENCRYPTION_KEY=<base64-encoded 32-byte key>
```

Generate a new key:
```bash
python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

Set in Render → Environment → `ENCRYPTION_KEY`.

**Backfill existing plaintext module configs (one-time, after Phase 9 upgrade):**
```bash
# Dry run first (no changes made):
python3 scripts/backfill_encryption.py --dry-run

# Apply:
python3 scripts/backfill_encryption.py
```

The script is idempotent — fields already encrypted (prefixed `enc:`) are skipped.

---

### 3. Bootstrap Admin — First Login

On a fresh deployment, no admin user exists. Create the bootstrap admin:

```bash
# Set the bootstrap secret in ENV:
BOOTSTRAP_SECRET=<your-secure-secret>

# POST to the bootstrap endpoint:
curl -X POST https://api.lehrercockpit.com/api/v2/admin/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"secret": "<your-secure-secret>", "first_name": "Admin", "last_name": "Schule"}'
```

Response includes `access_code` — **save it immediately, it is shown only once**.  
This event is logged as `bootstrap_created` in the audit log.

**If admin is locked out:** repeat the bootstrap call — it is idempotent (only creates if no admin exists).

---

### 4. Activating `code_prefix` Optimization for Existing Users

Users created before Phase 9c have `code_prefix IS NULL` in `user_access_codes`. These users use a slower authentication path (full table scan + argon2 verify for all users).

**Identify affected users:**
```
GET /api/v2/admin/maintenance/null-prefix-users
```
In admin UI: Audit-Log tab → (currently not shown in UI — use API directly)

**Fix:** Rotate the code for each affected user via the admin UI (Lehrkräfte → Code neu) or API:
```bash
curl -X POST https://api.lehrercockpit.com/api/v2/admin/users/<id>/rotate-code \
  -H "Cookie: lc_session=<your-session>"
```

**Priority:** This only affects authentication performance. With <50 users and argon2 at ~300ms/verify, the worst case is ~15 seconds for a full scan. Rotate in the first maintenance window after Phase 9 deploy.

---

## Maintenance Commands

### Session Cleanup

Expired sessions accumulate in the `sessions` table. Clean them up:

**Via admin UI:** System tab → (if implemented) or via API:
```
POST /api/v2/admin/maintenance/cleanup-sessions
```

**Expected response:**
```json
{"ok": true, "deleted": 42}
```

Recommended: run weekly. Sessions expire after 30 days automatically, cleanup is for disk space.

---

### Code Rotation (Security / NULL prefix fix)

When to rotate:
- Suspected code compromise
- User reports they can no longer log in with a valid code
- `code_prefix IS NULL` (optimization fix)

**Per-user rotation:**
```
POST /api/v2/admin/users/<id>/rotate-code
```
Returns `{"ok": true, "access_code": "..."}` — new code shown once only.

**In admin UI:** Lehrkräfte → Code neu button.

---

### Encrypt Existing Plaintext Module Configs

```bash
python3 scripts/backfill_encryption.py --dry-run  # preview
python3 scripts/backfill_encryption.py             # apply
```

Requires `ENCRYPTION_KEY` ENV var. Script logs each field encrypted.

---

### Audit Log Review

**Via admin UI:** Audit-Log tab supports:
- Date range filter (Von/Bis)
- Event type filter
- CSV export (session-authenticated)

**Via API:**
```bash
# Last 200 login failures:
curl "https://api.lehrercockpit.com/api/v2/admin/audit-log?event_type=login_failure&limit=200" \
  -H "Cookie: lc_session=<session>"

# Export to CSV (date range):
curl "https://api.lehrercockpit.com/api/v2/admin/audit-log/export.csv?date_from=2026-01-01&date_to=2026-03-31&limit=5000" \
  -H "Cookie: lc_session=<session>" \
  -o audit-log.csv
```

**Events logged:**
| event_type | Meaning |
|---|---|
| `login_success` | Successful access code authentication |
| `login_failure` | Failed authentication attempt |
| `teacher_created` | New teacher account created |
| `teacher_deactivated` | Teacher account deactivated |
| `code_rotated` | Access code regenerated |
| `bootstrap_created` | Bootstrap admin created |

---

### Rate Limit Monitoring

Check the audit log for `login_failure` bursts:
```
GET /api/v2/admin/audit-log?event_type=login_failure&date_from=<today>
```

If many failures from a single IP appear in the audit log, the IP may be actively attacking.

**Threshold:** configured via ENV:
| Variable | Default | Meaning |
|---|---|---|
| `LOGIN_RATE_LIMIT_MAX` | `10` | Max attempts per window |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | `900` | Window in seconds (15 min) |

**Caveat:** Rate limiting uses in-process memory (flask-limiter default). On Render free tier (1 worker), this is sufficient. If multiple workers are deployed, set `RATELIMIT_STORAGE_URI=redis://...` for cross-worker enforcement.

---

### Database Backup

Render Managed PostgreSQL provides automatic daily backups. For manual backup:

```bash
pg_dump $DATABASE_URL > backup-$(date +%Y%m%d).sql
```

Or use Render dashboard: Database → Backups → Create Backup.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | **Yes** (production) | — | PostgreSQL connection URL (set by Render) |
| `SECRET_KEY` | **Yes** | — | Flask secret key for session signing |
| `ENCRYPTION_KEY` | Recommended | — | Base64 32-byte key for module config encryption |
| `BOOTSTRAP_SECRET` | **Yes** (first deploy) | — | One-time admin bootstrap secret |
| `LOGIN_RATE_LIMIT_MAX` | No | `10` | Max login attempts per window |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | No | `900` | Rate limit window in seconds |
| `RATELIMIT_STORAGE_URI` | No | in-memory | Redis URI for multi-worker rate limiting |
| `PORT` | No | `5000` | Flask port (Render sets this automatically) |
| `MULTIUSER_ENABLED` | Frontend | `true` | Injected in `index.html` |
| `BACKEND_API_URL` | Frontend | — | Injected in `index.html` and `admin.html` |

---

## Render-Specific Notes

### Deploy Hook / Auto-Deploy

Render auto-deploys on push to `main`. To disable: Render → Service → Settings → Auto-Deploy → Off.

### Logs

```bash
# Render CLI:
render logs --service <service-id> --tail
```

Or: Render dashboard → Service → Logs.

### Health Check

Render pings `GET /` by default. The Flask app returns `{"ok": true, "mode": "saas"}` on `/` when `DATABASE_URL` is set.

### Single-Worker Constraint

Render free tier runs 1 gunicorn worker. Rate limiting (in-memory) and session management work correctly at this scale. If upgrading to multi-worker:
1. Set `RATELIMIT_STORAGE_URI` (Redis)
2. Ensure sessions use DB-backed storage (already implemented)

### Cold Starts

Render free tier sleeps after inactivity. First request after sleep may take 10–30 seconds. Consider upgrading to a paid plan or using a ping service (e.g., cron-job.org pinging `/api/v2/health` every 10 minutes).

---

## Troubleshooting

### "Nicht angemeldet" after deploy

Session cookies use `Secure=True; SameSite=None` in production (cross-origin Netlify → Render). Ensure:
1. The backend is running HTTPS (Render provides this automatically)
2. `BACKEND_API_URL` in `index.html` matches the Render service URL exactly
3. Browser is not blocking third-party cookies for the API domain

### Module config not saving

1. Check `ENCRYPTION_KEY` is set — without it, the crypto module may fail
2. Check Render logs for `[crypto]` errors
3. Try `python3 -c "from backend.crypto import encrypt, decrypt; print(decrypt(encrypt('test')))"` in Render Shell

### WebUntis shows no data

1. Verify the user has configured their iCal URL: admin UI → Lehrkräfte → (check module configured status)
2. Test the iCal URL directly in a browser
3. Check Render logs for `[webuntis]` fetch errors
4. Note: WebUntis iCal data is cached for 24 hours (`backend/webuntis_cache.py`)

### Audit log is empty

The audit log requires the `audit_log` table to exist. Check migrations ran successfully. If the table is missing:
```bash
python3 -c "
from backend.db import db_connection
from backend.migrations import run_migrations
with db_connection() as conn:
    run_migrations(conn)
"
```
