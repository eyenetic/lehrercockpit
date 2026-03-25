# Contributing to Lehrer-Cockpit

Short practical guide for the two-developer workflow.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 server.py        # starts dev server at http://localhost:8080
```

No database is needed for local development.  `DATABASE_URL` is only required
in production (Render) or for the optional DB integration tests.

## Branch workflow

1. Pull latest `main`:
   ```bash
   git pull origin main
   ```
2. Create a feature branch:
   ```bash
   git checkout -b your-name/short-description
   ```
3. Make changes, commit with a clear message.
4. Push and open a Pull Request against `main`.
5. Wait for the **CI / Test (no DB)** check to go green.
6. The other developer reviews and merges.

## Reproducing CI locally

**Fast path (always required, no DB needed):**
```bash
python3 -m py_compile app.py server.py dev_runner.py backend/*.py
pytest tests/ -v -m "not db"
```

**DB integration tests (optional, requires a live Postgres):**
```bash
TEST_DATABASE_URL="postgresql://user:pass@host/db" pytest tests/ -v -m "db"
```

## CI overview

GitHub Actions runs two jobs on every push and pull request:

| Job | When | What |
|-----|------|------|
| `Test (no DB)` | always | compile check + `pytest -m "not db"` |
| `Test (with DB)` | only if `TEST_DATABASE_URL` secret is set | `pytest -m "db"` |

The **Test (no DB)** job is the required check before merging.
The DB job is optional — set the `TEST_DATABASE_URL` repository secret in
GitHub Settings → Secrets and variables → Actions to enable it.

## Before opening a PR

- Run `pytest tests/ -v -m "not db"` locally and confirm all tests pass.
- Keep the diff small and focused — one logical change per PR where possible.
- Do not commit `.env.local` or any credentials.
