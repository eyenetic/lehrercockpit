"""Tests für backend/admin/admin_service.py – benötigt echte DB-Connection."""
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


# ── create_teacher ─────────────────────────────────────────────────────────────

@pytest.mark.db
def test_create_teacher_returns_user_and_code(db_conn):
    """create_teacher(conn, ...) gibt (user_id, plaintext_code) zurück."""
    from backend.admin.admin_service import create_teacher
    user, plain_code = create_teacher(db_conn, "Test", "Teacher")
    assert user is not None
    assert user.id > 0
    assert isinstance(plain_code, str)
    assert len(plain_code) > 0


@pytest.mark.db
def test_create_teacher_plaintext_code_nonempty(db_conn):
    """plaintext_code ist ein nicht-leerer String."""
    from backend.admin.admin_service import create_teacher
    _, plain_code = create_teacher(db_conn, "Plain", "Code")
    assert plain_code
    assert len(plain_code) == 32


@pytest.mark.db
def test_create_teacher_code_is_not_hash(db_conn):
    """plaintext_code beginnt NICHT mit '$argon2' oder '$2b$' — ist kein Hash."""
    from backend.admin.admin_service import create_teacher
    _, plain_code = create_teacher(db_conn, "Not", "Hash")
    assert not plain_code.startswith("$argon2"), (
        "plaintext_code sollte nicht wie ein argon2-Hash aussehen"
    )
    assert not plain_code.startswith("$2b$"), (
        "plaintext_code sollte nicht wie ein bcrypt-Hash aussehen"
    )


# ── get_all_users ──────────────────────────────────────────────────────────────

@pytest.mark.db
def test_get_all_users_returns_list(db_conn):
    """get_all_users(conn) gibt eine Liste zurück."""
    from backend.admin.admin_service import get_all_users
    result = get_all_users(db_conn)
    assert isinstance(result, list)


@pytest.mark.db
def test_created_teacher_appears_in_get_all_users(db_conn):
    """Nach create_teacher ist der User in get_all_users() enthalten."""
    from backend.admin.admin_service import create_teacher, get_all_users
    user, _ = create_teacher(db_conn, "Visible", "InList")
    users = get_all_users(db_conn)
    user_ids = [u["id"] for u in users]
    assert user.id in user_ids


# ── get_user ───────────────────────────────────────────────────────────────────

@pytest.mark.db
def test_get_user_returns_created_teacher(db_conn):
    """get_user(conn, user_id) gibt den erstellten Teacher zurück."""
    from backend.admin.admin_service import create_teacher, get_user
    user, _ = create_teacher(db_conn, "GetMe", "Please")
    result = get_user(db_conn, user.id)
    assert result is not None
    assert result["id"] == user.id


@pytest.mark.db
def test_get_user_nonexistent_returns_none(db_conn):
    """get_user(conn, 99999) gibt None zurück."""
    from backend.admin.admin_service import get_user
    result = get_user(db_conn, 99999)
    assert result is None


# ── update_user (via user_store.update_user used in admin routes) ──────────────

@pytest.mark.db
def test_update_user_display_name(db_conn):
    """update_user über user_store aktualisiert first_name-Feld."""
    from backend.admin.admin_service import create_teacher
    from backend.users.user_store import update_user
    user, _ = create_teacher(db_conn, "Before", "Update")
    updated = update_user(db_conn, user.id, first_name="After")
    assert updated is not None
    assert updated.first_name == "After"


# ── deactivate_user ────────────────────────────────────────────────────────────

@pytest.mark.db
def test_deactivate_user_sets_inactive(db_conn):
    """deactivate_user(conn, user_id) setzt is_active=False."""
    from backend.admin.admin_service import create_teacher, deactivate_user, get_user
    user, _ = create_teacher(db_conn, "Active", "Now")
    result = deactivate_user(db_conn, user.id)
    assert result is True
    loaded = get_user(db_conn, user.id)
    assert loaded is not None
    assert loaded["is_active"] is False


@pytest.mark.db
def test_deactivate_user_nonexistent_returns_false(db_conn):
    """deactivate_user für nicht-existenten User → False."""
    from backend.admin.admin_service import deactivate_user
    result = deactivate_user(db_conn, 99999999)
    assert result is False


# ── rotate_access_code ─────────────────────────────────────────────────────────

@pytest.mark.db
def test_rotate_access_code_returns_new_code(db_conn):
    """rotate_access_code(conn, user_id) gibt neuen Plaintext-Code zurück."""
    from backend.admin.admin_service import create_teacher, rotate_access_code
    user, old_code = create_teacher(db_conn, "Rotate", "Me")
    new_code = rotate_access_code(db_conn, user.id)
    assert new_code is not None
    assert isinstance(new_code, str)
    assert len(new_code) > 0


@pytest.mark.db
def test_rotate_access_code_differs_from_old(db_conn):
    """Neuer Code ist verschieden vom alten."""
    from backend.admin.admin_service import create_teacher, rotate_access_code
    user, old_code = create_teacher(db_conn, "Rotate", "Differ")
    new_code = rotate_access_code(db_conn, user.id)
    assert new_code != old_code


# ── get_system_setting ─────────────────────────────────────────────────────────

@pytest.mark.db
def test_get_system_setting_nonexistent_returns_none(db_conn):
    """get_system_setting für nicht-existenten Key → None (kein Fehler)."""
    from backend.admin.admin_service import get_system_setting
    result = get_system_setting(db_conn, "totally_nonexistent_key_xyz_12345")
    assert result is None


@pytest.mark.db
def test_get_system_setting_returns_default_if_not_found(db_conn):
    """get_system_setting gibt default zurück wenn Key fehlt."""
    from backend.admin.admin_service import get_system_setting
    result = get_system_setting(db_conn, "nonexistent_key_abc", default="fallback")
    assert result == "fallback"


# ── set_system_setting + get_system_setting round-trip ────────────────────────

@pytest.mark.db
def test_set_and_get_system_setting(db_conn):
    """set_system_setting + get_system_setting: Wert wird gespeichert und zurückgegeben."""
    from backend.admin.admin_service import set_system_setting, get_system_setting
    key = "test_admin_service_key_xyz"
    value = "test_value_abc"
    set_system_setting(db_conn, key, value)
    result = get_system_setting(db_conn, key)
    assert result == value


@pytest.mark.db
def test_set_system_setting_overwrites_existing(db_conn):
    """set_system_setting überschreibt bestehenden Wert (upsert)."""
    from backend.admin.admin_service import set_system_setting, get_system_setting
    key = "test_admin_overwrite_key"
    set_system_setting(db_conn, key, "first_value")
    set_system_setting(db_conn, key, "second_value")
    result = get_system_setting(db_conn, key)
    assert result == "second_value"


# ── get_all_system_settings ────────────────────────────────────────────────────

@pytest.mark.db
def test_get_all_system_settings_returns_dict(db_conn):
    """get_all_system_settings(conn) gibt ein Dictionary zurück."""
    from backend.admin.admin_service import get_all_system_settings
    result = get_all_system_settings(db_conn)
    assert isinstance(result, dict)


@pytest.mark.db
def test_get_all_system_settings_contains_set_key(db_conn):
    """Nach set_system_setting erscheint der Key in get_all_system_settings."""
    from backend.admin.admin_service import set_system_setting, get_all_system_settings
    key = "test_all_settings_key"
    set_system_setting(db_conn, key, {"hello": "world"})
    all_settings = get_all_system_settings(db_conn)
    assert key in all_settings
