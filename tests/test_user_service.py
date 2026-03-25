"""Tests für backend/users/user_service.py – benötigt echte DB-Connection."""
import os
import pytest


@pytest.fixture
def db_conn():
    """Erstellt eine Test-DB-Connection mit Transaction-Rollback."""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        pytest.skip("DATABASE_URL nicht gesetzt")
    import psycopg
    conn = psycopg.connect(db_url)
    from backend.migrations import run_migrations
    run_migrations(conn)
    conn.commit()
    yield conn
    conn.rollback()
    conn.close()


@pytest.mark.db
def test_create_teacher_returns_user_and_code(db_conn):
    """gibt tuple (User, str) zurück."""
    from backend.users.user_service import create_teacher
    from backend.users.user_store import User
    result = create_teacher(db_conn, "Anna", "Müller")
    assert isinstance(result, tuple)
    assert len(result) == 2
    user, code = result
    assert isinstance(user, User)
    assert isinstance(code, str)


@pytest.mark.db
def test_create_teacher_code_is_plain(db_conn):
    """Code hat korrekte Länge (32)."""
    from backend.users.user_service import create_teacher
    from backend.auth.access_code import CODE_LENGTH
    _, code = create_teacher(db_conn, "Max", "Mustermann")
    assert len(code) == CODE_LENGTH


@pytest.mark.db
def test_create_teacher_code_not_stored_plaintext(db_conn):
    """Gespeicherter Hash ≠ plain code."""
    from backend.users.user_service import create_teacher
    from backend.users.user_store import get_access_code_hash
    user, plain_code = create_teacher(db_conn, "Petra", "Lehrerin")
    stored_hash = get_access_code_hash(db_conn, user.id)
    assert stored_hash is not None
    assert stored_hash != plain_code


@pytest.mark.db
def test_regenerate_access_code(db_conn):
    """Neuer Code ist anders als alter."""
    from backend.users.user_service import create_teacher, regenerate_access_code
    user, old_code = create_teacher(db_conn, "Regen", "User")
    new_code = regenerate_access_code(db_conn, user.id)
    assert new_code is not None
    assert new_code != old_code
    assert len(new_code) == 32


@pytest.mark.db
def test_regenerate_access_code_unknown_user(db_conn):
    """Gibt None zurück für unbekannten User."""
    from backend.users.user_service import regenerate_access_code
    result = regenerate_access_code(db_conn, 999999999)
    assert result is None


@pytest.mark.db
def test_authenticate_by_code_success(db_conn):
    """Correct code → User zurück."""
    from backend.users.user_service import create_teacher, authenticate_by_code
    user, plain_code = create_teacher(db_conn, "Auth", "Success")
    result = authenticate_by_code(db_conn, plain_code)
    assert result is not None
    assert result.id == user.id


@pytest.mark.db
def test_authenticate_by_code_wrong_code(db_conn):
    """Falscher Code → None."""
    from backend.users.user_service import create_teacher, authenticate_by_code
    from backend.auth.access_code import generate_code
    create_teacher(db_conn, "Auth", "Wrong")
    wrong_code = generate_code()
    result = authenticate_by_code(db_conn, wrong_code)
    assert result is None


@pytest.mark.db
def test_authenticate_by_code_inactive_user(db_conn):
    """Deaktivierter User → None."""
    from backend.users.user_service import create_teacher, authenticate_by_code
    from backend.users.user_store import update_user
    user, plain_code = create_teacher(db_conn, "Auth", "Inactive")
    update_user(db_conn, user.id, is_active=False)
    result = authenticate_by_code(db_conn, plain_code)
    assert result is None


@pytest.mark.db
def test_old_code_invalid_after_regenerate(db_conn):
    """Alten Code nach Regenerate → None."""
    from backend.users.user_service import create_teacher, regenerate_access_code, authenticate_by_code
    user, old_code = create_teacher(db_conn, "Regen", "Invalidate")
    regenerate_access_code(db_conn, user.id)
    result = authenticate_by_code(db_conn, old_code)
    assert result is None


# ── Additional gap-filling tests ──────────────────────────────────────────────

@pytest.mark.db
def test_create_teacher_creates_user_returns_id(db_conn):
    """create_teacher() erstellt einen User und gibt eine ID zurück."""
    from backend.users.user_service import create_teacher
    user, code = create_teacher(db_conn, "Test", "Lehrkraft")
    assert user.id is not None
    assert user.id > 0


@pytest.mark.db
def test_create_teacher_correct_names(db_conn):
    """Erstellter User hat korrekten first_name und last_name."""
    from backend.users.user_service import create_teacher
    user, _ = create_teacher(db_conn, "Klara", "Schmidt")
    assert user.first_name == "Klara"
    assert user.last_name == "Schmidt"


@pytest.mark.db
def test_create_teacher_default_role_is_teacher(db_conn):
    """create_teacher() erstellt User mit role='teacher' als Standard."""
    from backend.users.user_service import create_teacher
    user, _ = create_teacher(db_conn, "Default", "Role")
    assert user.role == "teacher"


@pytest.mark.db
def test_get_user_after_create(db_conn):
    """Erstellter User kann per get_user_by_id geladen werden."""
    from backend.users.user_service import create_teacher
    from backend.users.user_store import get_user_by_id
    user, _ = create_teacher(db_conn, "Retrievable", "User")
    loaded = get_user_by_id(db_conn, user.id)
    assert loaded is not None
    assert loaded.id == user.id


@pytest.mark.db
def test_get_user_nonexistent_returns_none(db_conn):
    """get_user_by_id(99999) → None für nicht-existenten User."""
    from backend.users.user_store import get_user_by_id
    result = get_user_by_id(db_conn, 99999)
    assert result is None


@pytest.mark.db
def test_update_user_display_name(db_conn):
    """update_user() aktualisiert first_name-Feld."""
    from backend.users.user_service import create_teacher
    from backend.users.user_store import update_user
    user, _ = create_teacher(db_conn, "Alt", "Name")
    updated = update_user(db_conn, user.id, first_name="Neu")
    assert updated is not None
    assert updated.first_name == "Neu"


@pytest.mark.db
def test_deactivate_user_sets_inactive(db_conn):
    """update_user(is_active=False) setzt is_active auf False."""
    from backend.users.user_service import create_teacher
    from backend.users.user_store import update_user, get_user_by_id
    user, _ = create_teacher(db_conn, "Aktiv", "User")
    update_user(db_conn, user.id, is_active=False)
    loaded = get_user_by_id(db_conn, user.id)
    assert loaded is not None
    assert loaded.is_active is False


@pytest.mark.db
def test_deactivated_user_still_retrievable(db_conn):
    """Deaktivierter User ist weiterhin per get_user_by_id abrufbar."""
    from backend.users.user_service import create_teacher
    from backend.users.user_store import update_user, get_user_by_id
    user, _ = create_teacher(db_conn, "Inactive", "Retrievable")
    update_user(db_conn, user.id, is_active=False)
    loaded = get_user_by_id(db_conn, user.id)
    assert loaded is not None
    assert loaded.is_active is False
