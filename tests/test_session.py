"""Tests für backend/auth/session.py – benötigt echte DB-Connection."""
import os
import uuid
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


@pytest.fixture
def test_user_id(db_conn):
    """Erstellt einen Test-User und gibt dessen ID zurück."""
    from backend.users.user_store import create_user
    user = create_user(db_conn, "Session", "TestUser")
    return user.id


@pytest.mark.db
def test_create_session(db_conn, test_user_id):
    """Session wird erstellt, ID ist nicht leer."""
    from backend.auth.session import create_session
    session = create_session(db_conn, test_user_id)
    assert session.id
    assert len(session.id) > 0
    assert session.user_id == test_user_id


@pytest.mark.db
def test_get_session_valid(db_conn, test_user_id):
    """Frische Session kann geladen werden."""
    from backend.auth.session import create_session, get_session
    session = create_session(db_conn, test_user_id)
    loaded = get_session(db_conn, session.id)
    assert loaded is not None
    assert loaded.id == session.id
    assert loaded.user_id == test_user_id


@pytest.mark.db
def test_get_session_not_found(db_conn):
    """Unbekannte ID → None."""
    from backend.auth.session import get_session
    result = get_session(db_conn, str(uuid.uuid4()))
    assert result is None


@pytest.mark.db
def test_get_session_expired(db_conn, test_user_id):
    """Abgelaufene Session → None."""
    session_id = str(uuid.uuid4())
    db_conn.execute(
        "INSERT INTO sessions (id, user_id, expires_at) VALUES (%s, %s, NOW() - INTERVAL '1 hour')",
        (session_id, test_user_id),
    )
    from backend.auth.session import get_session
    result = get_session(db_conn, session_id)
    assert result is None


@pytest.mark.db
def test_delete_session(db_conn, test_user_id):
    """Nach Delete → None."""
    from backend.auth.session import create_session, delete_session, get_session
    session = create_session(db_conn, test_user_id)
    delete_session(db_conn, session.id)
    result = get_session(db_conn, session.id)
    assert result is None


@pytest.mark.db
def test_refresh_session(db_conn, test_user_id):
    """last_seen wird aktualisiert."""
    import time
    from backend.auth.session import create_session, refresh_session, get_session
    session = create_session(db_conn, test_user_id)
    original_last_seen = session.last_seen

    # kleine Pause damit der Timestamp sich ändert
    time.sleep(0.01)
    result = refresh_session(db_conn, session.id)
    assert result is True

    refreshed = get_session(db_conn, session.id)
    assert refreshed is not None
    # last_seen sollte >= original sein (kann gleich sein bei schnellen DBs)
    assert refreshed.last_seen >= original_last_seen


@pytest.mark.db
def test_cleanup_expired_sessions(db_conn, test_user_id):
    """Abgelaufene Sessions werden gelöscht, gültige nicht."""
    from backend.auth.session import create_session, cleanup_expired_sessions, get_session

    # Gültige Session erstellen
    valid_session = create_session(db_conn, test_user_id)

    # Abgelaufene Session direkt per SQL einfügen
    expired_id = str(uuid.uuid4())
    db_conn.execute(
        "INSERT INTO sessions (id, user_id, expires_at) VALUES (%s, %s, NOW() - INTERVAL '1 hour')",
        (expired_id, test_user_id),
    )

    deleted_count = cleanup_expired_sessions(db_conn)
    assert deleted_count >= 1

    # Gültige Session noch vorhanden
    assert get_session(db_conn, valid_session.id) is not None

    # Abgelaufene Session weg
    result = db_conn.execute(
        "SELECT id FROM sessions WHERE id = %s", (expired_id,)
    ).fetchone()
    assert result is None


# ── Additional gap-filling tests ──────────────────────────────────────────────

@pytest.mark.db
def test_create_session_returns_string_token(db_conn, test_user_id):
    """Session-Token ist ein nicht-leerer String, nicht die user_id selbst."""
    from backend.auth.session import create_session
    session = create_session(db_conn, test_user_id)
    assert isinstance(session.id, str)
    assert len(session.id) > 0
    # Token must not equal the user_id
    assert session.id != str(test_user_id)


@pytest.mark.db
def test_create_session_has_user_id(db_conn, test_user_id):
    """Erstellte Session hat korrektes user_id-Feld."""
    from backend.auth.session import create_session
    session = create_session(db_conn, test_user_id)
    assert session.user_id == test_user_id


@pytest.mark.db
def test_get_session_empty_string_returns_none(db_conn):
    """get_session mit leerem String → None (kein Absturz)."""
    from backend.auth.session import get_session
    result = get_session(db_conn, "")
    assert result is None


@pytest.mark.db
def test_get_session_returns_dict_with_user_id(db_conn, test_user_id):
    """Geladene Session enthält user_id-Attribut."""
    from backend.auth.session import create_session, get_session
    session = create_session(db_conn, test_user_id)
    loaded = get_session(db_conn, session.id)
    assert loaded is not None
    assert hasattr(loaded, "user_id")
    assert loaded.user_id == test_user_id


@pytest.mark.db
def test_delete_session_then_get_returns_none(db_conn, test_user_id):
    """Nach delete_session gibt get_session None zurück."""
    from backend.auth.session import create_session, delete_session, get_session
    session = create_session(db_conn, test_user_id)
    delete_session(db_conn, session.id)
    assert get_session(db_conn, session.id) is None


@pytest.mark.db
def test_session_token_is_not_user_id(db_conn, test_user_id):
    """Session-Token enthält nicht die User-ID als einzigen Wert."""
    from backend.auth.session import create_session
    session = create_session(db_conn, test_user_id)
    assert session.id != str(test_user_id)
    assert session.id != test_user_id
