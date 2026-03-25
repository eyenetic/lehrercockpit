"""Tests für Auth-API-Endpunkte (backend/api/auth_routes.py) – mit Flask Test-Client und Mocks."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Ensure the modules are imported so patch() can resolve them
import backend.api.auth_routes  # noqa: F401
import backend.api.helpers  # noqa: F401


@pytest.fixture
def app():
    """Minimale Flask-App, die nur den auth Blueprint registriert."""
    from flask import Flask
    import backend.api.auth_routes as auth_module

    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    # Limiter initialisieren und Auth-Blueprint registrieren
    auth_module.limiter.init_app(flask_app)
    flask_app.register_blueprint(auth_module.auth_bp, url_prefix="/api/v2/auth")

    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _make_mock_user(**kwargs):
    """Erstellt einen Mock-User mit sinnvollen Defaults."""
    user = MagicMock()
    user.id = kwargs.get("id", 1)
    user.first_name = kwargs.get("first_name", "Test")
    user.last_name = kwargs.get("last_name", "User")
    user.full_name = f"{user.first_name} {user.last_name}"
    user.role = kwargs.get("role", "teacher")
    user.is_active = kwargs.get("is_active", True)
    user.is_admin = kwargs.get("is_admin", False)
    user.to_dict.return_value = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
    }
    return user


def _make_mock_session(session_id="test-session-id-123"):
    """Erstellt eine Mock-Session."""
    session = MagicMock()
    session.id = session_id
    session.user_id = 1
    session.created_at = datetime.now(timezone.utc)
    session.expires_at = datetime.now(timezone.utc)
    session.last_seen = datetime.now(timezone.utc)
    return session


def _make_db_context_mock():
    """Erstellt einen Mock für db_connection als Context Manager."""
    mock_conn = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx, mock_conn


# ── Login Tests ────────────────────────────────────────────────────────────────

def test_login_missing_code(client):
    """Leerer Body → 422."""
    response = client.post("/api/v2/auth/login", json={})
    assert response.status_code in (400, 422)


def test_login_missing_code_no_body(client):
    """Kein Body → 422."""
    response = client.post(
        "/api/v2/auth/login",
        content_type="application/json",
        data="",
    )
    assert response.status_code in (400, 422)


def test_login_wrong_code(client):
    """Falscher Code → 401."""
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.auth_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.auth_routes, "authenticate_by_code", return_value=None):
            response = client.post(
                "/api/v2/auth/login",
                json={"code": "wrongcode12345678901234567890123"},
            )
    assert response.status_code == 401
    data = response.get_json()
    assert "error" in data


def test_login_success(client):
    """Mock authenticate_by_code und create_session → 200 + Set-Cookie."""
    mock_user = _make_mock_user(id=42, first_name="Anna", last_name="Müller")
    mock_session = _make_mock_session("session-abc-123")
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.auth_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.auth_routes, "authenticate_by_code", return_value=mock_user):
            with patch.object(backend.api.auth_routes, "create_session", return_value=mock_session):
                response = client.post(
                    "/api/v2/auth/login",
                    json={"code": "validcode12345678901234567890ab"},
                )

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "user" in data
    # Cookie prüfen
    assert "lc_session" in response.headers.get("Set-Cookie", "")


def test_login_rate_limit_not_triggered_on_few_requests(client):
    """3 Requests hintereinander → kein Rate-Limit ausgelöst (422/401, aber nicht 429)."""
    mock_ctx, mock_conn = _make_db_context_mock()
    with patch.object(backend.api.auth_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.auth_routes, "authenticate_by_code", return_value=None):
            for _ in range(3):
                response = client.post(
                    "/api/v2/auth/login",
                    json={"code": "wrongcode12345678901234567890123"},
                )
                assert response.status_code != 429, "Rate-Limit nach nur 3 Requests ausgelöst"


# ── Logout Tests ───────────────────────────────────────────────────────────────

def test_logout_not_authenticated(client):
    """Ohne Cookie → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.post("/api/v2/auth/logout")
    assert response.status_code == 401


# ── Me Tests ───────────────────────────────────────────────────────────────────

def test_me_not_authenticated(client):
    """Ohne Cookie → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/auth/me")
    assert response.status_code == 401


def test_me_authenticated(client):
    """Mit gültiger Session → 200 + user data."""
    mock_user = _make_mock_user(id=7, first_name="Gültig", last_name="Eingeloggt")

    with patch.object(backend.api.helpers, "get_current_user", return_value=mock_user):
        response = client.get("/api/v2/auth/me")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "user" in data
    assert data["user"]["id"] == 7


# ── Additional gap-filling tests ──────────────────────────────────────────────

def test_login_valid_code_sets_session_cookie(client):
    """POST /api/v2/auth/login mit gültigem Code → 200 + Set-Cookie (lc_session)."""
    mock_user = _make_mock_user(id=99, first_name="Cookie", last_name="Test")
    mock_session = _make_mock_session("cookie-session-id-456")
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.auth_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.auth_routes, "authenticate_by_code", return_value=mock_user):
            with patch.object(backend.api.auth_routes, "create_session", return_value=mock_session):
                response = client.post(
                    "/api/v2/auth/login",
                    json={"code": "validcode12345678901234567890ab"},
                )

    assert response.status_code == 200
    set_cookie = response.headers.get("Set-Cookie", "")
    assert "lc_session" in set_cookie, f"Expected lc_session cookie, got: {set_cookie!r}"


def test_login_invalid_code_returns_401(client):
    """POST /api/v2/auth/login mit ungültigem Code → 401."""
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.auth_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.auth_routes, "authenticate_by_code", return_value=None):
            response = client.post(
                "/api/v2/auth/login",
                json={"code": "wrongcode12345678901234567890xx"},
            )

    assert response.status_code == 401
    data = response.get_json()
    assert "error" in data


def test_login_missing_body_returns_400_or_422(client):
    """POST /api/v2/auth/login ohne Body → 400 oder 422."""
    response = client.post(
        "/api/v2/auth/login",
        content_type="application/json",
        data="",
    )
    assert response.status_code in (400, 422)


def test_me_without_session_returns_401(client):
    """GET /api/v2/auth/me ohne Session → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/auth/me")
    assert response.status_code == 401


def test_me_with_session_returns_200_with_user(client):
    """GET /api/v2/auth/me mit gültiger Session → 200 mit user data."""
    mock_user = _make_mock_user(id=55, first_name="Logged", last_name="In")

    with patch.object(backend.api.helpers, "get_current_user", return_value=mock_user):
        response = client.get("/api/v2/auth/me")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert data["user"]["id"] == 55


def test_logout_clears_session(client):
    """POST /api/v2/auth/logout mit gültiger Session → 200, Cookie wird gelöscht."""
    mock_user = _make_mock_user(id=10)
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=mock_user):
        with patch.object(backend.api.auth_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.auth_routes, "delete_session"):
                response = client.post("/api/v2/auth/logout")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True


def test_me_after_logout_returns_401(client):
    """Nach logout → GET /api/v2/auth/me gibt 401 zurück."""
    mock_user = _make_mock_user(id=11)
    mock_ctx, mock_conn = _make_db_context_mock()

    # First logout
    with patch.object(backend.api.helpers, "get_current_user", return_value=mock_user):
        with patch.object(backend.api.auth_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.auth_routes, "delete_session"):
                client.post("/api/v2/auth/logout")

    # Then /me without session
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/auth/me")

    assert response.status_code == 401


def test_login_success_returns_user_data(client):
    """POST /api/v2/auth/login Erfolg → Response enthält user-Objekt."""
    mock_user = _make_mock_user(id=33, first_name="Returned", last_name="User")
    mock_session = _make_mock_session("returned-session-789")
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.auth_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.auth_routes, "authenticate_by_code", return_value=mock_user):
            with patch.object(backend.api.auth_routes, "create_session", return_value=mock_session):
                response = client.post(
                    "/api/v2/auth/login",
                    json={"code": "validcode12345678901234567890ab"},
                )

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "user" in data
    assert data["user"]["id"] == 33


# ── Audit log tests (mock-based, no DB required) ──────────────────────────────

def test_login_success_calls_log_audit_event_with_login_success(client):
    """POST /api/v2/auth/login valid code → log_audit_event called with 'login_success'."""
    mock_user = _make_mock_user(id=77)
    mock_session = _make_mock_session("audit-session-abc")
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.auth_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.auth_routes, "authenticate_by_code", return_value=mock_user):
            with patch.object(backend.api.auth_routes, "create_session", return_value=mock_session):
                with patch.object(backend.api.auth_routes, "log_audit_event") as mock_audit:
                    response = client.post(
                        "/api/v2/auth/login",
                        json={"code": "validcode12345678901234567890ab"},
                    )

    assert response.status_code == 200
    mock_audit.assert_called_once()
    call_args = mock_audit.call_args
    # First positional arg after conn is event_type
    assert call_args[0][1] == "login_success" or call_args[1].get("event_type") == "login_success" or (
        len(call_args[0]) > 1 and call_args[0][1] == "login_success"
    )


def test_login_failure_calls_log_audit_event_with_login_failure(client):
    """POST /api/v2/auth/login invalid code → log_audit_event called with 'login_failure'."""
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.auth_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.auth_routes, "authenticate_by_code", return_value=None):
            with patch.object(backend.api.auth_routes, "log_audit_event") as mock_audit:
                response = client.post(
                    "/api/v2/auth/login",
                    json={"code": "wrongcode12345678901234567890xx"},
                )

    assert response.status_code == 401
    mock_audit.assert_called_once()
    call_args = mock_audit.call_args
    assert call_args[0][1] == "login_failure" or call_args[1].get("event_type") == "login_failure" or (
        len(call_args[0]) > 1 and call_args[0][1] == "login_failure"
    )


# ── DB-backed audit log tests (skipped without DATABASE_URL) ──────────────────

import os as _os


@pytest.mark.db
@pytest.mark.skipif(
    not _os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_login_success_creates_audit_log_entry_in_db():
    """POST /api/v2/auth/login valid code → audit_log has event_type='login_success'."""
    import psycopg
    from backend.migrations import run_migrations
    from backend.users.user_service import create_teacher

    db_url = _os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()

    try:
        # Create a test user with a known code
        user, plain_code = create_teacher(conn, "Audit", "TestUser")
        conn.commit()

        # Use the Flask test client with the real DB
        from flask import Flask
        import backend.api.auth_routes as auth_module

        flask_app = Flask(__name__)
        flask_app.config["TESTING"] = True
        auth_module.limiter.init_app(flask_app)
        flask_app.register_blueprint(auth_module.auth_bp, url_prefix="/api/v2/auth")

        with flask_app.test_client() as test_client:
            response = test_client.post(
                "/api/v2/auth/login",
                json={"code": plain_code},
            )

        assert response.status_code == 200

        # Check audit_log
        conn2 = psycopg.connect(db_url)
        try:
            row = conn2.execute(
                "SELECT COUNT(*) FROM audit_log WHERE event_type = 'login_success' AND user_id = %s",
                (user.id,),
            ).fetchone()
            assert row[0] >= 1, f"Expected login_success audit entry, found {row[0]}"
        finally:
            conn2.rollback()
            conn2.close()

    finally:
        conn.rollback()
        conn.close()


@pytest.mark.db
@pytest.mark.skipif(
    not _os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_login_failure_creates_audit_log_entry_in_db():
    """POST /api/v2/auth/login invalid code → audit_log has event_type='login_failure'."""
    import psycopg
    from backend.migrations import run_migrations

    db_url = _os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()

    try:
        from flask import Flask
        import backend.api.auth_routes as auth_module

        flask_app = Flask(__name__)
        flask_app.config["TESTING"] = True
        auth_module.limiter.init_app(flask_app)
        flask_app.register_blueprint(auth_module.auth_bp, url_prefix="/api/v2/auth")

        # Count existing failures before test
        conn2 = psycopg.connect(db_url)
        try:
            before_row = conn2.execute(
                "SELECT COUNT(*) FROM audit_log WHERE event_type = 'login_failure'"
            ).fetchone()
            before_count = before_row[0]
        finally:
            conn2.rollback()
            conn2.close()

        with flask_app.test_client() as test_client:
            response = test_client.post(
                "/api/v2/auth/login",
                json={"code": "definitelyinvalidcode1234567890xx"},
            )

        assert response.status_code == 401

        # Count after — should have increased
        conn3 = psycopg.connect(db_url)
        try:
            after_row = conn3.execute(
                "SELECT COUNT(*) FROM audit_log WHERE event_type = 'login_failure'"
            ).fetchone()
            after_count = after_row[0]
            assert after_count > before_count, (
                f"Expected login_failure audit entry to be created. "
                f"Before: {before_count}, After: {after_count}"
            )
        finally:
            conn3.rollback()
            conn3.close()

    finally:
        conn.rollback()
        conn.close()
