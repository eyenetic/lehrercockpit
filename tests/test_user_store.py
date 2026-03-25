"""Tests für backend/users/user_store.py – benötigt echte DB-Connection."""
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
def test_create_user(db_conn):
    """User anlegen: ID > 0, first_name korrekt."""
    from backend.users.user_store import create_user
    user = create_user(db_conn, "Anna", "Müller")
    assert user.id > 0
    assert user.first_name == "Anna"
    assert user.last_name == "Müller"


@pytest.mark.db
def test_create_user_default_role(db_conn):
    """default role ist 'teacher'."""
    from backend.users.user_store import create_user
    user = create_user(db_conn, "Max", "Mustermann")
    assert user.role == "teacher"


@pytest.mark.db
def test_get_user_by_id(db_conn):
    """Nach Anlegen wieder laden."""
    from backend.users.user_store import create_user, get_user_by_id
    user = create_user(db_conn, "Klara", "Schmidt")
    loaded = get_user_by_id(db_conn, user.id)
    assert loaded is not None
    assert loaded.id == user.id
    assert loaded.first_name == "Klara"


@pytest.mark.db
def test_get_user_by_id_not_found(db_conn):
    """Unbekannte ID → None."""
    from backend.users.user_store import get_user_by_id
    result = get_user_by_id(db_conn, 999999999)
    assert result is None


@pytest.mark.db
def test_get_all_users(db_conn):
    """Leere Liste wenn keine User, dann nach Anlegen 1+ User."""
    from backend.users.user_store import create_user, get_all_users
    before = get_all_users(db_conn)
    count_before = len(before)

    create_user(db_conn, "Test", "User")
    after = get_all_users(db_conn)
    assert len(after) == count_before + 1


@pytest.mark.db
def test_update_user_name(db_conn):
    """first_name ändern."""
    from backend.users.user_store import create_user, update_user
    user = create_user(db_conn, "Alt", "Name")
    updated = update_user(db_conn, user.id, first_name="Neu")
    assert updated is not None
    assert updated.first_name == "Neu"
    assert updated.last_name == "Name"


@pytest.mark.db
def test_update_user_is_active(db_conn):
    """Deaktivieren."""
    from backend.users.user_store import create_user, update_user
    user = create_user(db_conn, "Aktiv", "User")
    assert user.is_active is True
    updated = update_user(db_conn, user.id, is_active=False)
    assert updated is not None
    assert updated.is_active is False


@pytest.mark.db
def test_update_user_invalid_field(db_conn):
    """ValueError bei unbekanntem Feld."""
    from backend.users.user_store import create_user, update_user
    user = create_user(db_conn, "Test", "Invalid")
    with pytest.raises(ValueError):
        update_user(db_conn, user.id, password="hacked")


@pytest.mark.db
def test_delete_user(db_conn):
    """Nach Delete: get_user_by_id gibt None."""
    from backend.users.user_store import create_user, delete_user, get_user_by_id
    user = create_user(db_conn, "ZuLöschen", "User")
    result = delete_user(db_conn, user.id)
    assert result is True
    assert get_user_by_id(db_conn, user.id) is None


@pytest.mark.db
def test_set_and_get_access_code_hash(db_conn):
    """Hash speichern und laden."""
    from backend.users.user_store import create_user, set_access_code, get_access_code_hash
    user = create_user(db_conn, "Code", "User")
    set_access_code(db_conn, user.id, "test_hash_value")
    loaded_hash = get_access_code_hash(db_conn, user.id)
    assert loaded_hash == "test_hash_value"


@pytest.mark.db
def test_user_full_name_property(db_conn):
    """user.full_name == 'Anna Müller'."""
    from backend.users.user_store import create_user
    user = create_user(db_conn, "Anna", "Müller")
    assert user.full_name == "Anna Müller"


@pytest.mark.db
def test_user_is_admin_property(db_conn):
    """teacher → False, admin → True."""
    from backend.users.user_store import create_user
    teacher = create_user(db_conn, "Lehrer", "Person", role="teacher")
    admin = create_user(db_conn, "Admin", "Person", role="admin")
    assert teacher.is_admin is False
    assert admin.is_admin is True


@pytest.mark.db
def test_user_to_dict_no_password(db_conn):
    """to_dict() hat kein 'password'-Feld."""
    from backend.users.user_store import create_user
    user = create_user(db_conn, "Dict", "User")
    d = user.to_dict()
    assert "password" not in d
    assert "id" in d
    assert "first_name" in d
    assert "full_name" in d
