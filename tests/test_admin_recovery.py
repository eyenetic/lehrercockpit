"""Tests für scripts/admin_recovery.py

Tests use py_compile for syntax check and unittest.mock.patch for DB mocking.
No real DATABASE_URL needed — all DB operations are mocked.

Test patterns follow tests/test_backfill.py.
"""
import os
import sys
import py_compile
import subprocess
import pytest
from unittest.mock import MagicMock, patch

# ── Script path ───────────────────────────────────────────────────────────────

SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "scripts", "admin_recovery.py"
)


# ── Helper: load the module via importlib ─────────────────────────────────────

def _load_recovery_module(module_name: str = "admin_recovery_mod"):
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(module_name, SCRIPT_PATH)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Helper: make a mock db_connection context manager ─────────────────────────

def _make_mock_db_context(conn=None):
    if conn is None:
        conn = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx, conn


# ── Compile check ─────────────────────────────────────────────────────────────

def test_admin_recovery_script_compiles():
    """scripts/admin_recovery.py kompiliert ohne Fehler."""
    assert os.path.isfile(SCRIPT_PATH), f"Script not found: {SCRIPT_PATH}"
    try:
        py_compile.compile(SCRIPT_PATH, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"Compile error in admin_recovery.py: {e}")


def test_admin_recovery_has_main_entrypoint():
    """Script has __main__ entrypoint."""
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert 'if __name__ == "__main__"' in content


def test_admin_recovery_has_all_commands():
    """Script contains --list, --rotate-admin, and --ensure-bootstrap-admin."""
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "--list" in content
    assert "--rotate-admin" in content
    assert "--ensure-bootstrap-admin" in content


# ── Exit with error if DATABASE_URL not set ───────────────────────────────────

def test_admin_recovery_exits_error_if_database_url_not_set():
    """Script gibt exit code 1 zurück wenn DATABASE_URL nicht gesetzt ist."""
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)

    result = subprocess.run(
        [sys.executable, SCRIPT_PATH, "--list"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "DATABASE_URL" in result.stderr


def test_check_env_raises_systemexit_without_database_url(monkeypatch):
    """_check_env() gibt SystemExit(1) aus wenn DATABASE_URL fehlt."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    mod = _load_recovery_module("recovery_env_check")

    with pytest.raises(SystemExit) as exc_info:
        mod._check_env()
    assert exc_info.value.code == 1


def test_check_env_passes_with_database_url(monkeypatch):
    """_check_env() läuft ohne Fehler wenn DATABASE_URL gesetzt ist."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")

    mod = _load_recovery_module("recovery_env_check_ok")
    # Should not raise
    mod._check_env()


# ── --list with no admins ─────────────────────────────────────────────────────

def test_list_no_admins_exits_1(capsys):
    """--list mit leerer DB: gibt 'Keine Admin-User gefunden' aus und exit 1."""
    mock_conn = MagicMock()
    # SELECT ... WHERE role = 'admin' → no rows
    mock_conn.execute.return_value.fetchall.return_value = []
    mock_ctx, _ = _make_mock_db_context(conn=mock_conn)

    mod = _load_recovery_module("recovery_list_empty")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with patch("backend.db.db_connection", return_value=mock_ctx):
            with pytest.raises(SystemExit) as exc_info:
                mod.cmd_list()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "keine" in captured.out.lower() or "Keine" in captured.out


def test_list_with_admins_exits_0_and_prints_table(capsys):
    """--list mit Admin in DB: gibt Tabelle aus und exit 0.

    Phase 13: row now has columns:
        id, first_name, last_name, role, is_active, created_at, is_admin
    (display_name column removed; is_admin column added)
    """
    from datetime import datetime

    mock_conn = MagicMock()

    # Phase 13 column order: id, first_name, last_name, role, is_active, created_at, is_admin
    fake_created = datetime(2026, 1, 15, 10, 0, 0)
    admin_rows = [
        (1, "Bootstrap", "Admin", "teacher", True, fake_created, True)
        # id  first_name  last_name  role      is_active  created_at      is_admin
    ]

    call_count = {"n": 0}

    def mock_execute(sql, *args, **kwargs):
        call_count["n"] += 1
        mock_result = MagicMock()
        if "is_admin" in sql and "ORDER BY id" in sql:
            # Main admin list query (Phase 13: WHERE is_admin = TRUE)
            mock_result.fetchall.return_value = admin_rows
        else:
            # Access code count query
            mock_result.fetchone.return_value = (1,)
        mock_result.fetchone.return_value = (1,)
        return mock_result

    mock_conn.execute.side_effect = mock_execute
    mock_ctx, _ = _make_mock_db_context(conn=mock_conn)

    mod = _load_recovery_module("recovery_list_with_admins")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with patch("backend.db.db_connection", return_value=mock_ctx):
            mod.cmd_list()  # Should not raise / exit 1

    captured = capsys.readouterr()
    assert "Admin" in captured.out or "admin" in captured.out
    assert "Bootstrap" in captured.out


# ── --rotate-admin with invalid user_id ───────────────────────────────────────

def test_rotate_admin_invalid_user_id_exits_1(capsys):
    """--rotate-admin mit ungültiger ID (nicht Integer): exit 1."""
    mod = _load_recovery_module("recovery_rotate_invalid_id")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with pytest.raises(SystemExit) as exc_info:
            mod.cmd_rotate_admin("not-an-int")

    assert exc_info.value.code == 1


def test_rotate_admin_nonexistent_user_exits_1(capsys):
    """--rotate-admin mit nicht existierender User-ID: exit 1."""
    mock_conn = MagicMock()
    # SELECT ... WHERE id = %s → no row
    mock_conn.execute.return_value.fetchone.return_value = None
    mock_ctx, _ = _make_mock_db_context(conn=mock_conn)

    mod = _load_recovery_module("recovery_rotate_nonexistent")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with patch("backend.db.db_connection", return_value=mock_ctx):
            with pytest.raises(SystemExit) as exc_info:
                mod.cmd_rotate_admin("999")

    assert exc_info.value.code == 1


def test_rotate_admin_non_admin_user_exits_1(capsys):
    """--rotate-admin mit User der nicht Admin ist: exit 1."""
    from datetime import datetime

    mock_conn = MagicMock()
    # SELECT ... WHERE id = %s → returns a teacher, not admin
    # row: id, first_name, last_name, role, is_active
    mock_conn.execute.return_value.fetchone.return_value = (
        42, "Max", "Mustermann", "teacher", True
    )
    mock_ctx, _ = _make_mock_db_context(conn=mock_conn)

    mod = _load_recovery_module("recovery_rotate_non_admin")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with patch("backend.db.db_connection", return_value=mock_ctx):
            with pytest.raises(SystemExit) as exc_info:
                mod.cmd_rotate_admin("42")

    assert exc_info.value.code == 1


def test_rotate_admin_valid_admin_exits_0_and_prints_banner(capsys):
    """--rotate-admin mit gültigem Admin: exit 0, druckt Zugangscode-Banner."""
    mock_conn = MagicMock()
    # SELECT ... WHERE id = %s → returns an admin row
    # row: id, first_name, last_name, role, is_active
    mock_conn.execute.return_value.fetchone.return_value = (
        1, "Bootstrap", "Admin", "admin", True
    )
    mock_ctx, _ = _make_mock_db_context(conn=mock_conn)

    fake_code = "ABCDEFGH12345678ABCDEFGH12345678"

    mod = _load_recovery_module("recovery_rotate_valid_admin")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with patch("backend.db.db_connection", return_value=mock_ctx):
            with patch("backend.auth.access_code.generate_code", return_value=fake_code):
                with patch("backend.auth.access_code.hash_code", return_value="$argon2id$fake"):
                    with patch("backend.auth.access_code.get_code_prefix", return_value="ABCDEFGH"):
                        with patch("backend.users.user_store.set_access_code"):
                            with patch("backend.migrations.log_audit_event"):
                                mod.cmd_rotate_admin("1")

    captured = capsys.readouterr()
    assert fake_code in captured.out
    assert "RECOVERY" in captured.out
    assert "=" * 10 in captured.out  # Banner separator


# ── --ensure-bootstrap-admin when admin exists ────────────────────────────────

def test_ensure_bootstrap_admin_when_admin_exists_exits_0(capsys):
    """--ensure-bootstrap-admin wenn Admin existiert: gibt Hinweis aus, exit 0."""
    mock_conn = MagicMock()
    # SELECT COUNT(*) FROM users WHERE role = 'admin' → 2
    mock_conn.execute.return_value.fetchone.return_value = (2,)
    mock_ctx, _ = _make_mock_db_context(conn=mock_conn)

    mod = _load_recovery_module("recovery_ensure_exists")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with patch("backend.db.db_connection", return_value=mock_ctx):
            mod.cmd_ensure_bootstrap_admin()  # Should not raise

    captured = capsys.readouterr()
    assert "2" in captured.out
    assert "existieren" in captured.out or "Admin" in captured.out


def test_ensure_bootstrap_admin_when_no_admin_creates_and_exits_0(capsys):
    """--ensure-bootstrap-admin wenn kein Admin: erstellt einen, druckt Code, exit 0."""
    mock_conn = MagicMock()
    # SELECT COUNT(*) → 0 (no admins)
    mock_conn.execute.return_value.fetchone.return_value = (0,)
    mock_ctx, _ = _make_mock_db_context(conn=mock_conn)

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.full_name = "Recovery Admin"

    fake_code = "RECOVERY1234567890ABCDEF12345678"

    mod = _load_recovery_module("recovery_ensure_creates")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with patch("backend.db.db_connection", return_value=mock_ctx):
            with patch(
                "backend.users.user_service.create_teacher",
                return_value=(mock_user, fake_code),
            ):
                with patch("backend.migrations.log_audit_event"):
                    mod.cmd_ensure_bootstrap_admin()

    captured = capsys.readouterr()
    assert fake_code in captured.out
    assert "RECOVERY" in captured.out
    assert "=" * 10 in captured.out  # Banner separator


# ── Audit log event is written ────────────────────────────────────────────────

def test_rotate_admin_writes_audit_event():
    """cmd_rotate_admin schreibt 'admin_code_rotated_by_operator' in den Audit-Log."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (
        1, "Bootstrap", "Admin", "admin", True
    )
    mock_ctx, _ = _make_mock_db_context(conn=mock_conn)

    fake_code = "TESTCODE1234567890ABCDEF12345678"
    audit_calls = []

    def capture_audit(conn, event_type, **kwargs):
        audit_calls.append({"event_type": event_type, **kwargs})

    mod = _load_recovery_module("recovery_audit_check")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with patch("backend.db.db_connection", return_value=mock_ctx):
            with patch("backend.auth.access_code.generate_code", return_value=fake_code):
                with patch("backend.auth.access_code.hash_code", return_value="$argon2id$fake"):
                    with patch("backend.auth.access_code.get_code_prefix", return_value="TESTCODE"):
                        with patch("backend.users.user_store.set_access_code"):
                            with patch(
                                "backend.migrations.log_audit_event",
                                side_effect=capture_audit,
                            ):
                                mod.cmd_rotate_admin("1")

    assert len(audit_calls) == 1
    assert audit_calls[0]["event_type"] == "admin_code_rotated_by_operator"
    assert audit_calls[0].get("user_id") == 1
    assert audit_calls[0].get("details", {}).get("method") == "cli_recovery"


def test_ensure_bootstrap_admin_writes_audit_event():
    """cmd_ensure_bootstrap_admin schreibt 'bootstrap_admin_created_by_operator' in den Audit-Log."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (0,)
    mock_ctx, _ = _make_mock_db_context(conn=mock_conn)

    mock_user = MagicMock()
    mock_user.id = 99
    mock_user.full_name = "Recovery Admin"

    audit_calls = []

    def capture_audit(conn, event_type, **kwargs):
        audit_calls.append({"event_type": event_type, **kwargs})

    mod = _load_recovery_module("recovery_audit_bootstrap")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with patch("backend.db.db_connection", return_value=mock_ctx):
            with patch(
                "backend.users.user_service.create_teacher",
                return_value=(mock_user, "FAKECODE12345678901234567890AB"),
            ):
                with patch(
                    "backend.migrations.log_audit_event",
                    side_effect=capture_audit,
                ):
                    mod.cmd_ensure_bootstrap_admin()

    assert len(audit_calls) == 1
    assert audit_calls[0]["event_type"] == "bootstrap_admin_created_by_operator"
    assert audit_calls[0].get("user_id") == 99


# ── Access code never logged / only printed once ──────────────────────────────

def test_rotate_admin_code_printed_exactly_once(capsys):
    """Der neue Zugangscode wird genau einmal auf stdout ausgegeben."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (
        1, "Bootstrap", "Admin", "admin", True
    )
    mock_ctx, _ = _make_mock_db_context(conn=mock_conn)

    unique_code = "UNIQUECODE12345678901234567890"

    mod = _load_recovery_module("recovery_code_once")

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
        with patch("backend.db.db_connection", return_value=mock_ctx):
            with patch("backend.auth.access_code.generate_code", return_value=unique_code):
                with patch("backend.auth.access_code.hash_code", return_value="$argon2id$fake"):
                    with patch("backend.auth.access_code.get_code_prefix", return_value="UNIQUECO"):
                        with patch("backend.users.user_store.set_access_code"):
                            with patch("backend.migrations.log_audit_event"):
                                mod.cmd_rotate_admin("1")

    captured = capsys.readouterr()
    assert captured.out.count(unique_code) == 1, (
        f"Expected access code to appear exactly once in stdout, "
        f"got {captured.out.count(unique_code)} times"
    )
