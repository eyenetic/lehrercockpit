"""Tests für scripts/backfill_encryption.py — Phase 9g.

Tests use py_compile for syntax check and unittest.mock.patch for DB mocking.
No real DB connection needed for most tests.
"""
import os
import sys
import py_compile
import subprocess
import pytest
from unittest.mock import MagicMock, patch, call

# Generate a valid Fernet key once for tests that need it
try:
    from cryptography.fernet import Fernet as _Fernet
    _VALID_FERNET_KEY = _Fernet.generate_key().decode()
except Exception:
    _VALID_FERNET_KEY = ""


# ── Script path ───────────────────────────────────────────────────────────────

SCRIPT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "backfill_encryption.py")


# ── Compile check ─────────────────────────────────────────────────────────────

def test_backfill_script_compiles_without_errors():
    """scripts/backfill_encryption.py kompiliert ohne Fehler."""
    assert os.path.isfile(SCRIPT_PATH), f"Script not found: {SCRIPT_PATH}"
    try:
        py_compile.compile(SCRIPT_PATH, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"Compile error in backfill_encryption.py: {e}")


def test_backfill_script_has_dry_run_argument():
    """Script enthält --dry-run Argumentdefinition."""
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "--dry-run" in content, "backfill_encryption.py does not contain --dry-run"


def test_backfill_script_has_main_entrypoint():
    """Script hat __main__ entrypoint."""
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert 'if __name__ == "__main__"' in content, "No __main__ entrypoint found"


# ── Exit with error if DATABASE_URL not set ──────────────────────────────────

def test_backfill_exits_error_if_database_url_not_set():
    """Script gibt exit code 1 zurück wenn DATABASE_URL nicht gesetzt ist."""
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env.pop("ENCRYPTION_KEY", None)

    result = subprocess.run(
        [sys.executable, SCRIPT_PATH],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "DATABASE_URL" in result.stderr


def test_backfill_exits_error_if_encryption_key_not_set():
    """Script gibt exit code 1 zurück wenn ENCRYPTION_KEY nicht gesetzt ist."""
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql://fake:fake@localhost/fake"
    env.pop("ENCRYPTION_KEY", None)

    result = subprocess.run(
        [sys.executable, SCRIPT_PATH],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "ENCRYPTION_KEY" in result.stderr


# ── Mock-based tests for backfill() function ─────────────────────────────────

def _make_mock_db_context(rows=None):
    """Erstellt einen Mock für db_connection() als Context Manager."""
    mock_conn = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    if rows is not None:
        mock_conn.execute.return_value.fetchall.return_value = rows
    return mock_ctx, mock_conn


def test_dry_run_mode_does_not_execute_update():
    """Dry-run mode: plaintext-Zeile → kein UPDATE ausgeführt."""
    if not _VALID_FERNET_KEY:
        pytest.skip("cryptography not available")

    plaintext_config = {"password": "hunter2", "username": "alice"}
    rows = [(1, 10, "itslearning", plaintext_config)]
    mock_ctx, mock_conn = _make_mock_db_context(rows=rows)

    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("backfill_enc_mod", SCRIPT_PATH)
    backfill_mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(backfill_mod)

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test", "ENCRYPTION_KEY": _VALID_FERNET_KEY}):
        with patch.object(backfill_mod, "_check_env"):
            with patch("backend.db.db_connection", return_value=mock_ctx):
                with patch("backend.crypto.encrypt_config", return_value={"password": "enc:encrypted"}):
                    with patch("backend.crypto.decrypt_config", return_value=plaintext_config):
                        with patch("backend.crypto.is_encryption_enabled", return_value=True):
                            backfill_mod.backfill(dry_run=True)

    update_calls = [
        c for c in mock_conn.execute.call_args_list
        if "UPDATE" in str(c).upper()
    ]
    assert len(update_calls) == 0, f"UPDATE was called in dry-run mode: {update_calls}"


def test_skip_already_encrypted_rows():
    """Bereits verschlüsselte Zeilen werden übersprungen (kein UPDATE)."""
    if not _VALID_FERNET_KEY:
        pytest.skip("cryptography not available")

    encrypted_config = {"password": "enc:gAAAAABencrypted", "username": "alice"}
    rows = [(1, 10, "itslearning", encrypted_config)]
    mock_ctx, mock_conn = _make_mock_db_context(rows=rows)

    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("backfill_enc_skip", SCRIPT_PATH)
    backfill_mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(backfill_mod)

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test", "ENCRYPTION_KEY": _VALID_FERNET_KEY}):
        with patch.object(backfill_mod, "_check_env"):
            with patch("backend.db.db_connection", return_value=mock_ctx):
                # encrypt_config returns same as input (already encrypted — no change)
                with patch("backend.crypto.encrypt_config", return_value=encrypted_config):
                    with patch("backend.crypto.decrypt_config", return_value=encrypted_config):
                        with patch("backend.crypto.is_encryption_enabled", return_value=True):
                            backfill_mod.backfill(dry_run=False)

    update_calls = [
        c for c in mock_conn.execute.call_args_list
        if "UPDATE" in str(c).upper()
    ]
    assert len(update_calls) == 0, f"UPDATE should not be called for already-encrypted row"


def test_normal_mode_executes_update_for_plaintext():
    """Normal mode (non-dry-run): plaintext-Zeile → UPDATE wird ausgeführt."""
    if not _VALID_FERNET_KEY:
        pytest.skip("cryptography not available")

    plaintext_config = {"password": "hunter2", "username": "alice"}
    encrypted_config = {"password": "enc:encrypted_value", "username": "alice"}
    rows = [(1, 10, "itslearning", plaintext_config)]
    mock_ctx, mock_conn = _make_mock_db_context(rows=rows)

    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("backfill_enc_live", SCRIPT_PATH)
    backfill_mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(backfill_mod)

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test", "ENCRYPTION_KEY": _VALID_FERNET_KEY}):
        with patch.object(backfill_mod, "_check_env"):
            with patch("backend.db.db_connection", return_value=mock_ctx):
                with patch("backend.crypto.encrypt_config", return_value=encrypted_config):
                    with patch("backend.crypto.decrypt_config") as mock_decrypt:
                        mock_decrypt.side_effect = [plaintext_config, plaintext_config]
                        with patch("backend.crypto.is_encryption_enabled", return_value=True):
                            backfill_mod.backfill(dry_run=False)

    update_calls = [
        c for c in mock_conn.execute.call_args_list
        if "UPDATE" in str(c).upper()
    ]
    assert len(update_calls) == 1, (
        f"Expected exactly 1 UPDATE for plaintext row, got {len(update_calls)}: {update_calls}"
    )


def test_backfill_function_check_env_missing_database_url(monkeypatch):
    """_check_env() gibt exit(1) aus wenn DATABASE_URL fehlt."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("backfill_enc_env", SCRIPT_PATH)
    backfill_mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(backfill_mod)

    with pytest.raises(SystemExit) as exc_info:
        backfill_mod._check_env()
    assert exc_info.value.code == 1


def test_backfill_function_check_env_missing_encryption_key(monkeypatch):
    """_check_env() gibt exit(1) aus wenn ENCRYPTION_KEY fehlt."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("backfill_enc_key", SCRIPT_PATH)
    backfill_mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(backfill_mod)

    with pytest.raises(SystemExit) as exc_info:
        backfill_mod._check_env()
    assert exc_info.value.code == 1
