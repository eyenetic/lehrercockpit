"""Tests für Admin-API-Endpunkte (backend/api/admin_routes.py) – Flask Test-Client + Mocks."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import backend.api.admin_routes  # noqa: F401
import backend.api.helpers  # noqa: F401


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Flask-App mit auth + admin Blueprints."""
    from flask import Flask
    import backend.api.auth_routes as auth_module
    import backend.api.admin_routes as admin_module

    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    auth_module.limiter.init_app(flask_app)
    flask_app.register_blueprint(auth_module.auth_bp, url_prefix="/api/v2/auth")
    flask_app.register_blueprint(admin_module.admin_bp, url_prefix="/api/v2/admin")

    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _make_admin_user(**kwargs):
    """Erstellt einen Mock-Admin-User."""
    user = MagicMock()
    user.id = kwargs.get("id", 1)
    user.first_name = kwargs.get("first_name", "Admin")
    user.last_name = kwargs.get("last_name", "User")
    user.full_name = f"{user.first_name} {user.last_name}"
    user.role = "admin"
    user.is_active = True
    user.is_admin = True
    user.to_dict.return_value = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "role": "admin",
        "is_active": True,
        "is_admin": True,
    }
    return user


def _make_teacher_user(**kwargs):
    """Erstellt einen Mock-Teacher-User."""
    user = MagicMock()
    user.id = kwargs.get("id", 2)
    user.first_name = kwargs.get("first_name", "Teacher")
    user.last_name = kwargs.get("last_name", "User")
    user.full_name = f"{user.first_name} {user.last_name}"
    user.role = "teacher"
    user.is_active = True
    user.is_admin = False
    user.to_dict.return_value = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "role": "teacher",
        "is_active": True,
        "is_admin": False,
    }
    return user


def _make_db_context_mock():
    """Erstellt einen Mock für db_connection als Context Manager."""
    mock_conn = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx, mock_conn


# ── GET /api/v2/admin/users ────────────────────────────────────────────────────

def test_list_users_without_auth_returns_401(client):
    """GET /api/v2/admin/users ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/admin/users")
    assert response.status_code == 401


def test_list_users_with_teacher_returns_403(client):
    """GET /api/v2/admin/users mit Teacher-Auth → 403."""
    teacher = _make_teacher_user()
    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        response = client.get("/api/v2/admin/users")
    assert response.status_code == 403


def test_list_users_with_admin_returns_200(client):
    """GET /api/v2/admin/users mit Admin-Auth → 200."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.admin_routes, "get_user_overview", return_value=[]):
                response = client.get("/api/v2/admin/users")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "users" in data


# ── POST /api/v2/admin/users ───────────────────────────────────────────────────

def test_create_user_with_admin_returns_201_with_access_code(client):
    """POST /api/v2/admin/users mit Admin-Auth und gültigem Body → 201 + access_code."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    mock_new_user = MagicMock()
    mock_new_user.id = 99
    mock_new_user.to_dict.return_value = {
        "id": 99, "first_name": "New", "last_name": "Teacher",
        "full_name": "New Teacher", "role": "teacher",
        "is_active": True, "is_admin": False,
    }

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.admin_routes, "create_teacher",
                              return_value=(mock_new_user, "plaincode12345678901234567890ab")):
                with patch.object(backend.api.admin_routes, "initialize_user_modules"):
                    response = client.post(
                        "/api/v2/admin/users",
                        json={"first_name": "New", "last_name": "Teacher", "role": "teacher"},
                    )

    assert response.status_code == 201
    data = response.get_json()
    assert data.get("ok") is True
    assert "access_code" in data
    assert len(data["access_code"]) > 0


def test_create_user_without_auth_returns_401(client):
    """POST /api/v2/admin/users ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.post(
            "/api/v2/admin/users",
            json={"first_name": "X", "last_name": "Y"},
        )
    assert response.status_code == 401


def test_create_user_missing_first_name_returns_422(client):
    """POST /api/v2/admin/users ohne first_name → 422."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            response = client.post(
                "/api/v2/admin/users",
                json={"last_name": "OnlyLast"},
            )

    assert response.status_code == 422


# ── POST /api/v2/admin/users/<id>/rotate-code ─────────────────────────────────

def test_rotate_code_with_admin_returns_access_code(client):
    """POST /api/v2/admin/users/<id>/rotate-code mit Admin → 200 + access_code."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.admin_routes, "regenerate_access_code",
                              return_value="newcode12345678901234567890ab"):
                response = client.post("/api/v2/admin/users/5/rotate-code")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "access_code" in data
    assert len(data["access_code"]) > 0


def test_rotate_code_for_nonexistent_user_returns_404(client):
    """POST /api/v2/admin/users/<id>/rotate-code für unbekannten User → 404."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.admin_routes, "regenerate_access_code", return_value=None):
                response = client.post("/api/v2/admin/users/99999/rotate-code")

    assert response.status_code == 404


# ── POST /api/v2/admin/users/<id>/deactivate ─────────────────────────────────

def test_deactivate_user_with_admin_returns_200(client):
    """POST /api/v2/admin/users/<id>/deactivate mit Admin → 200."""
    admin = _make_admin_user(id=1)
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.admin_routes, "deactivate_user", return_value=True):
                response = client.post("/api/v2/admin/users/5/deactivate")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True


def test_deactivate_own_account_returns_400(client):
    """POST /api/v2/admin/users/<own_id>/deactivate → 400 (eigenes Konto)."""
    admin = _make_admin_user(id=1)
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            response = client.post("/api/v2/admin/users/1/deactivate")

    assert response.status_code == 400


# ── GET /api/v2/admin/modules/defaults ────────────────────────────────────────

def test_get_module_defaults_with_admin_returns_200(client):
    """GET /api/v2/admin/modules/defaults mit Admin → 200."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.admin_routes, "get_default_module_order",
                              return_value=["webuntis", "itslearning"]):
                with patch.object(backend.api.admin_routes, "get_default_enabled_modules",
                                  return_value=["webuntis"]):
                    response = client.get("/api/v2/admin/modules/defaults")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "default_order" in data
    assert "default_enabled" in data


def test_get_module_defaults_without_auth_returns_401(client):
    """GET /api/v2/admin/modules/defaults ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/admin/modules/defaults")
    assert response.status_code == 401


# ── PUT /api/v2/admin/modules/defaults ────────────────────────────────────────

def test_put_module_defaults_with_admin_returns_200(client):
    """PUT /api/v2/admin/modules/defaults mit Admin und gültigem Body → 200."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.admin_routes, "set_default_module_order"):
                with patch.object(backend.api.admin_routes, "set_default_enabled_modules"):
                    response = client.put(
                        "/api/v2/admin/modules/defaults",
                        json={
                            "default_order": ["webuntis", "itslearning"],
                            "default_enabled": ["webuntis"],
                        },
                    )

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True


# ── GET /api/v2/admin/audit-log ───────────────────────────────────────────────

def test_get_audit_log_without_auth_returns_401(client):
    """GET /api/v2/admin/audit-log ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/admin/audit-log")
    assert response.status_code == 401


def test_get_audit_log_with_teacher_returns_403(client):
    """GET /api/v2/admin/audit-log mit Teacher-Auth → 403."""
    teacher = _make_teacher_user()
    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        response = client.get("/api/v2/admin/audit-log")
    assert response.status_code == 403


def test_get_audit_log_with_admin_returns_200(client):
    """GET /api/v2/admin/audit-log mit Admin-Auth → 200 mit events, total, limit, offset."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    # Mock COUNT(*) → returns (0,)
    mock_conn.execute.return_value.fetchone.return_value = (0,)
    mock_conn.execute.return_value.fetchall.return_value = []

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            response = client.get("/api/v2/admin/audit-log")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "events" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


def test_get_audit_log_respects_limit_parameter(client):
    """GET /api/v2/admin/audit-log?limit=10&offset=0 — limit wird zurückgegeben."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    mock_conn.execute.return_value.fetchone.return_value = (0,)
    mock_conn.execute.return_value.fetchall.return_value = []

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            response = client.get("/api/v2/admin/audit-log?limit=10&offset=0")

    assert response.status_code == 200
    data = response.get_json()
    assert data["limit"] == 10
    assert data["offset"] == 0


def test_get_audit_log_event_type_filter_mocked(client):
    """GET /api/v2/admin/audit-log?event_type=login_success — filtert nach event_type (mock)."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    now = datetime(2026, 3, 25, 10, 0, 0, tzinfo=timezone.utc)
    mock_event_row = (
        42,               # id
        "login_success",  # event_type
        3,                # user_id
        "Anna Müller",    # user_name
        "82.113.42.1",    # ip_address
        {},               # details
        now,              # created_at
    )

    # First call → COUNT, second → rows
    mock_conn.execute.return_value.fetchone.return_value = (1,)
    mock_conn.execute.return_value.fetchall.return_value = [mock_event_row]

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            response = client.get("/api/v2/admin/audit-log?event_type=login_success")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    # The mock returns the same fetchone for count and fetchall for rows,
    # so we just verify structure is correct
    assert "events" in data
    assert "total" in data


def test_get_audit_log_default_limit_is_50(client):
    """GET /api/v2/admin/audit-log ohne limit → default limit=50."""
    admin = _make_admin_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    mock_conn.execute.return_value.fetchone.return_value = (0,)
    mock_conn.execute.return_value.fetchall.return_value = []

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=mock_ctx):
            response = client.get("/api/v2/admin/audit-log")

    assert response.status_code == 200
    data = response.get_json()
    assert data["limit"] == 50
    assert data["offset"] == 0
