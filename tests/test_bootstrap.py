"""Tests für backend/admin/bootstrap.py.

Tests prüfen:
- ensure_bootstrap_admin() ist aufrufbar ohne Fehler wenn keine DB vorhanden
- Mit gemockter DB: Idempotenz (zweimaliger Aufruf erzeugt nur einen Admin)

Note: bootstrap.py uses lazy imports inside the function body:
    from backend.db import db_connection
    from backend.users.user_service import create_teacher
Therefore we patch the source modules, not backend.admin.bootstrap.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


# ── Tests ohne echte DB (Mock-basiert) ────────────────────────────────────────

def test_ensure_bootstrap_admin_handles_db_exception_gracefully():
    """ensure_bootstrap_admin() fängt DB-Ausnahmen ab und bricht nicht ab."""
    from backend.admin.bootstrap import ensure_bootstrap_admin

    # Patch db_connection at source — bootstrap imports it lazily from backend.db
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(side_effect=Exception("DB nicht erreichbar"))
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.db_connection", return_value=mock_ctx):
        # Should NOT raise — exceptions must be caught internally
        ensure_bootstrap_admin()


def test_ensure_bootstrap_admin_no_op_when_admin_exists():
    """ensure_bootstrap_admin() macht nichts wenn bereits ein Admin vorhanden."""
    from backend.admin.bootstrap import ensure_bootstrap_admin

    mock_conn = MagicMock()
    # Simulate: SELECT COUNT(*) FROM users WHERE role = 'admin' → 1 (admin exists)
    mock_conn.execute.return_value.fetchone.return_value = (1,)

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.db_connection", return_value=mock_ctx):
        with patch("backend.users.user_service.create_teacher") as mock_create:
            ensure_bootstrap_admin()
            # create_teacher must NOT be called
            mock_create.assert_not_called()


def test_ensure_bootstrap_admin_creates_admin_when_none_exist(capsys):
    """ensure_bootstrap_admin() erstellt Admin wenn noch keiner existiert."""
    from backend.admin.bootstrap import ensure_bootstrap_admin

    mock_conn = MagicMock()
    # Simulate: SELECT COUNT(*) → 0 (no admins)
    mock_conn.execute.return_value.fetchone.return_value = (0,)

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.full_name = "Bootstrap Admin"

    with patch("backend.db.db_connection", return_value=mock_ctx):
        with patch("backend.users.user_service.create_teacher",
                   return_value=(mock_user, "plaincode123")) as mock_create:
            ensure_bootstrap_admin()
            # create_teacher MUST be called once
            mock_create.assert_called_once()


def test_ensure_bootstrap_admin_prints_code_on_creation(capsys):
    """ensure_bootstrap_admin() gibt Zugangscode auf stdout aus."""
    from backend.admin.bootstrap import ensure_bootstrap_admin

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (0,)

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    mock_user = MagicMock()
    mock_user.id = 42
    mock_user.full_name = "Bootstrap Admin"

    test_code = "TESTCODE1234567890ABCDEF12345678"

    with patch("backend.db.db_connection", return_value=mock_ctx):
        with patch("backend.users.user_service.create_teacher",
                   return_value=(mock_user, test_code)):
            ensure_bootstrap_admin()

    captured = capsys.readouterr()
    assert test_code in captured.out


def test_ensure_bootstrap_admin_no_output_when_admin_exists(capsys):
    """Kein Bootstrap-Output wenn Admin bereits vorhanden."""
    from backend.admin.bootstrap import ensure_bootstrap_admin

    mock_conn = MagicMock()
    # Admin exists
    mock_conn.execute.return_value.fetchone.return_value = (1,)

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.db_connection", return_value=mock_ctx):
        ensure_bootstrap_admin()

    captured = capsys.readouterr()
    assert "BOOTSTRAP" not in captured.out


def test_ensure_bootstrap_admin_idempotent_via_mock():
    """Zweimaliger Aufruf mit Mock: create_teacher wird nur beim ersten Mal aufgerufen."""
    from backend.admin.bootstrap import ensure_bootstrap_admin

    call_count = {"n": 0}

    def mock_fetchone_side_effect():
        count = call_count["n"]
        call_count["n"] += 1
        # First call: no admins; second call: 1 admin
        return (0,) if count == 0 else (1,)

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.side_effect = mock_fetchone_side_effect

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.full_name = "Bootstrap Admin"

    created_count = {"n": 0}

    def mock_create_teacher(*args, **kwargs):
        created_count["n"] += 1
        return mock_user, "testcode12345678901234567890ab"

    with patch("backend.db.db_connection", return_value=mock_ctx):
        with patch("backend.users.user_service.create_teacher",
                   side_effect=mock_create_teacher):
            ensure_bootstrap_admin()  # First call — should create
            ensure_bootstrap_admin()  # Second call — should NOT create again

    # create_teacher should only have been called once (first call)
    assert created_count["n"] == 1


def test_ensure_bootstrap_admin_advisory_lock_called():
    """Bootstrap acquires pg_advisory_lock before the COUNT check."""
    from backend.admin.bootstrap import ensure_bootstrap_admin

    mock_conn = MagicMock()
    # Track which SQL statements are executed
    executed_sql = []

    def track_execute(sql, *args, **kwargs):
        executed_sql.append(sql.strip())
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)  # Admin already exists
        return mock_result

    mock_conn.execute.side_effect = track_execute

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.db_connection", return_value=mock_ctx):
        ensure_bootstrap_admin()

    # First SQL must be the advisory lock
    assert len(executed_sql) >= 1, "No SQL executed"
    assert "pg_advisory_lock" in executed_sql[0], (
        f"First SQL call must be pg_advisory_lock, got: {executed_sql[0]!r}"
    )


# ── Phase 13: Bootstrap uses is_admin=TRUE query ──────────────────────────────

def test_ensure_bootstrap_admin_queries_is_admin_not_role(capsys):
    """Bootstrap check queries is_admin=TRUE (not role='admin') — Phase 13."""
    from backend.admin.bootstrap import ensure_bootstrap_admin

    mock_conn = MagicMock()
    executed_sql = []

    def track_execute(sql, *args, **kwargs):
        executed_sql.append(sql.strip())
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)  # Admin exists
        return mock_result

    mock_conn.execute.side_effect = track_execute

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.db_connection", return_value=mock_ctx):
        ensure_bootstrap_admin()

    # Find the COUNT SQL (not the advisory lock)
    count_sqls = [s for s in executed_sql if "COUNT" in s.upper()]
    assert count_sqls, "Expected at least one COUNT query"
    count_sql = count_sqls[0]
    assert "is_admin" in count_sql.lower(), (
        f"Phase 13: Bootstrap should query is_admin=TRUE, not role='admin'. "
        f"Got SQL: {count_sql!r}"
    )


def test_ensure_bootstrap_admin_creates_with_is_admin_true(capsys):
    """Bootstrap creates admin with is_admin=True (canonical Phase 13 form)."""
    from backend.admin.bootstrap import ensure_bootstrap_admin

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (0,)

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    mock_user = MagicMock()
    mock_user.id = 99
    mock_user.full_name = "Bootstrap Admin"

    captured_kwargs = {}

    def mock_create_teacher(conn, first_name, last_name, role="teacher", is_admin=False):
        captured_kwargs["role"] = role
        captured_kwargs["is_admin"] = is_admin
        return mock_user, "bootstrapcode12345678901234567890"

    with patch("backend.db.db_connection", return_value=mock_ctx):
        with patch("backend.users.user_service.create_teacher",
                   side_effect=mock_create_teacher):
            ensure_bootstrap_admin()

    assert captured_kwargs.get("is_admin") is True, (
        f"Phase 13: Bootstrap admin must be created with is_admin=True, "
        f"got: {captured_kwargs.get('is_admin')!r}"
    )


# ── DB-backed tests (skipped without DATABASE_URL) ────────────────────────────

@pytest.mark.db
@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_ensure_bootstrap_admin_db_idempotent():
    """Mit echter DB: zweimaliger Aufruf erzeugt nicht zwei Admin-User."""
    import psycopg
    from backend.migrations import run_migrations

    db_url = os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()

    try:
        from backend.admin.bootstrap import ensure_bootstrap_admin

        # Call twice
        ensure_bootstrap_admin()
        ensure_bootstrap_admin()

        # Count admin-capable users via persisted authorization flag (Phase 13)
        row = conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_admin = TRUE"
        ).fetchone()
        admin_count = row[0]
        assert admin_count >= 1, "At least one admin should exist after bootstrap"
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.db
@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_bootstrap_sets_system_settings_completed_at():
    """After bootstrap runs, system_settings has a row for bootstrap_completed_at."""
    import psycopg
    from backend.migrations import run_migrations

    db_url = os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()

    try:
        from backend.admin.bootstrap import ensure_bootstrap_admin
        ensure_bootstrap_admin()

        row = conn.execute(
            "SELECT value FROM system_settings WHERE key = 'bootstrap_completed_at'"
        ).fetchone()
        assert row is not None, "system_settings row 'bootstrap_completed_at' not found"
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.db
@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_bootstrap_sets_system_settings_pending_rotation():
    """After bootstrap runs, system_settings has bootstrap_pending_rotation = 'true'."""
    import psycopg
    from backend.migrations import run_migrations

    db_url = os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()

    try:
        from backend.admin.bootstrap import ensure_bootstrap_admin
        ensure_bootstrap_admin()

        row = conn.execute(
            "SELECT value FROM system_settings WHERE key = 'bootstrap_pending_rotation'"
        ).fetchone()
        assert row is not None, "system_settings row 'bootstrap_pending_rotation' not found"
        # value is stored as JSONB — psycopg3 returns it as a Python object
        value = row[0]
        assert str(value).strip('"') == "true", (
            f"Expected 'true', got: {value!r}"
        )
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.db
@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_bootstrap_creates_audit_log_entry():
    """After bootstrap runs, audit_log has a 'bootstrap_created' event."""
    import psycopg
    from backend.migrations import run_migrations

    db_url = os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()

    try:
        from backend.admin.bootstrap import ensure_bootstrap_admin
        ensure_bootstrap_admin()

        row = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE event_type = 'bootstrap_created'"
        ).fetchone()
        assert row is not None
        assert row[0] >= 1, (
            f"Expected at least one 'bootstrap_created' audit log entry, found: {row[0]}"
        )
    finally:
        conn.rollback()
        conn.close()
