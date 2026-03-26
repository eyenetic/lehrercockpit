"""Tests for Phase 13 is_admin flag separation from role field.

Tests cover:
  - _normalize_role_and_admin() in user_store.py
  - _normalize_role_and_admin_request() in admin_routes.py
  - Teacher with is_admin=False cannot access admin endpoints
  - Teacher with is_admin=True can access admin endpoints
  - User with role='teacher' + is_admin=True passes require_admin
  - User with role='admin' (legacy) passes require_admin (compat)

All tests use mocks — no DATABASE_URL required.
"""
import pytest
from unittest.mock import patch, MagicMock

import backend.api.admin_routes  # noqa: F401
import backend.api.helpers  # noqa: F401


# ── _normalize_role_and_admin (user_store) ────────────────────────────────────

def test_normalize_role_admin_returns_teacher_and_true():
    """role='admin' → ('teacher', True) — legacy compat."""
    from backend.users.user_store import _normalize_role_and_admin
    role, is_admin = _normalize_role_and_admin("admin")
    assert role == "teacher"
    assert is_admin is True


def test_normalize_role_teacher_is_admin_true():
    """role='teacher', is_admin=True → ('teacher', True) — canonical form."""
    from backend.users.user_store import _normalize_role_and_admin
    role, is_admin = _normalize_role_and_admin("teacher", True)
    assert role == "teacher"
    assert is_admin is True


def test_normalize_role_teacher_is_admin_false():
    """role='teacher', is_admin=False → ('teacher', False) — standard teacher."""
    from backend.users.user_store import _normalize_role_and_admin
    role, is_admin = _normalize_role_and_admin("teacher", False)
    assert role == "teacher"
    assert is_admin is False


def test_normalize_role_teacher_default_is_admin():
    """role='teacher', no is_admin → ('teacher', False) — default."""
    from backend.users.user_store import _normalize_role_and_admin
    role, is_admin = _normalize_role_and_admin("teacher")
    assert role == "teacher"
    assert is_admin is False


# ── _normalize_role_and_admin_request (admin_routes) ─────────────────────────

def test_normalize_request_admin_role():
    """role='admin' in request → ('teacher', True)."""
    from backend.api.admin_routes import _normalize_role_and_admin_request
    role, is_admin = _normalize_role_and_admin_request("admin", None)
    assert role == "teacher"
    assert is_admin is True


def test_normalize_request_teacher_is_admin_true():
    """role='teacher', is_admin=True → ('teacher', True)."""
    from backend.api.admin_routes import _normalize_role_and_admin_request
    role, is_admin = _normalize_role_and_admin_request("teacher", True)
    assert role == "teacher"
    assert is_admin is True


def test_normalize_request_teacher_is_admin_false():
    """role='teacher', is_admin=False → ('teacher', False)."""
    from backend.api.admin_routes import _normalize_role_and_admin_request
    role, is_admin = _normalize_role_and_admin_request("teacher", False)
    assert role == "teacher"
    assert is_admin is False


def test_normalize_request_teacher_no_is_admin():
    """role='teacher', is_admin=None → ('teacher', False) — not supplied."""
    from backend.api.admin_routes import _normalize_role_and_admin_request
    role, is_admin = _normalize_role_and_admin_request("teacher", None)
    assert role == "teacher"
    assert is_admin is False


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Flask app with admin blueprint."""
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


def _make_user(is_admin=False, role="teacher", is_active=True, user_id=10):
    """Build a mock user with given is_admin/role."""
    user = MagicMock()
    user.id = user_id
    user.first_name = "Test"
    user.last_name = "User"
    user.full_name = "Test User"
    user.role = role
    user.is_active = is_active
    user.is_admin = is_admin
    user.to_dict.return_value = {
        "id": user_id,
        "first_name": "Test",
        "last_name": "User",
        "full_name": "Test User",
        "role": role,
        "is_active": is_active,
        "is_admin": is_admin,
    }
    return user


def _make_db_ctx():
    conn = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=conn)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx, conn


# ── require_admin: teacher with is_admin=False → 403 ─────────────────────────

def test_teacher_no_admin_flag_blocked_from_admin_endpoint(client):
    """Teacher with is_admin=False → 403 on admin endpoint."""
    teacher = _make_user(is_admin=False, role="teacher")
    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        response = client.get("/api/v2/admin/users")
    assert response.status_code == 403


def test_teacher_no_admin_flag_blocked_from_audit_log(client):
    """Teacher with is_admin=False → 403 on audit-log endpoint."""
    teacher = _make_user(is_admin=False, role="teacher")
    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        response = client.get("/api/v2/admin/audit-log")
    assert response.status_code == 403


# ── require_admin: teacher with is_admin=True → allowed ──────────────────────

def test_teacher_with_admin_flag_can_access_users_endpoint(client):
    """Teacher with is_admin=True can access GET /api/v2/admin/users."""
    teacher_admin = _make_user(is_admin=True, role="teacher")
    ctx, conn = _make_db_ctx()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher_admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=ctx):
            with patch.object(backend.api.admin_routes, "get_user_overview", return_value=[]):
                response = client.get("/api/v2/admin/users")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True


def test_teacher_with_admin_flag_can_create_user(client):
    """Teacher with is_admin=True can POST /api/v2/admin/users."""
    teacher_admin = _make_user(is_admin=True, role="teacher", user_id=5)
    ctx, conn = _make_db_ctx()

    mock_new_user = MagicMock()
    mock_new_user.id = 77
    mock_new_user.to_dict.return_value = {
        "id": 77, "first_name": "New", "last_name": "Teacher",
        "role": "teacher", "is_active": True, "is_admin": False,
    }

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher_admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=ctx):
            with patch.object(backend.api.admin_routes, "create_teacher",
                              return_value=(mock_new_user, "plaincode1234567890abcdef12345678")):
                with patch.object(backend.api.admin_routes, "initialize_user_modules"):
                    response = client.post(
                        "/api/v2/admin/users",
                        json={"first_name": "New", "last_name": "Teacher", "role": "teacher"},
                    )

    assert response.status_code == 201


# ── Legacy role='admin' still passes require_admin ───────────────────────────

def test_legacy_admin_role_still_passes_require_admin(client):
    """User with role='admin' (legacy) and is_admin=True passes require_admin."""
    legacy_admin = _make_user(is_admin=True, role="admin")
    ctx, conn = _make_db_ctx()

    with patch.object(backend.api.helpers, "get_current_user", return_value=legacy_admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=ctx):
            with patch.object(backend.api.admin_routes, "get_user_overview", return_value=[]):
                response = client.get("/api/v2/admin/users")

    assert response.status_code == 200


# ── POST /api/v2/admin/users with role='admin' normalizes to is_admin=True ───

def test_create_user_with_admin_role_normalizes_to_is_admin_true(client):
    """POST /api/v2/admin/users with role='admin' → create_teacher called with is_admin=True."""
    admin = _make_user(is_admin=True, role="teacher", user_id=1)
    ctx, conn = _make_db_ctx()

    mock_new_user = MagicMock()
    mock_new_user.id = 88
    mock_new_user.to_dict.return_value = {
        "id": 88, "first_name": "Admin", "last_name": "User",
        "role": "teacher", "is_active": True, "is_admin": True,
    }

    captured_kwargs = {}

    def mock_create_teacher(conn, first_name, last_name, role, is_admin=False):
        captured_kwargs["role"] = role
        captured_kwargs["is_admin"] = is_admin
        return mock_new_user, "code1234567890abcdef1234567890ab"

    with patch.object(backend.api.helpers, "get_current_user", return_value=admin):
        with patch.object(backend.api.admin_routes, "db_connection", return_value=ctx):
            with patch.object(backend.api.admin_routes, "create_teacher",
                              side_effect=mock_create_teacher):
                with patch.object(backend.api.admin_routes, "initialize_user_modules"):
                    response = client.post(
                        "/api/v2/admin/users",
                        json={"first_name": "Admin", "last_name": "User", "role": "admin"},
                    )

    assert response.status_code == 201
    # After normalization, create_teacher receives role='teacher', is_admin=True
    assert captured_kwargs.get("role") == "teacher", (
        f"Expected role='teacher' after normalization, got: {captured_kwargs.get('role')!r}"
    )
    assert captured_kwargs.get("is_admin") is True, (
        f"Expected is_admin=True after normalization, got: {captured_kwargs.get('is_admin')!r}"
    )


# ── User dataclass: is_admin as persisted field ───────────────────────────────

def test_user_is_admin_attribute_defaults_false():
    """User dataclass is_admin defaults to False."""
    from datetime import datetime, timezone
    from backend.users.user_store import User
    now = datetime.now(timezone.utc)
    user = User(id=1, first_name="A", last_name="B", role="teacher",
                is_active=True, created_at=now, updated_at=now)
    assert user.is_admin is False


def test_user_is_admin_attribute_can_be_true():
    """User dataclass is_admin can be set to True."""
    from datetime import datetime, timezone
    from backend.users.user_store import User
    now = datetime.now(timezone.utc)
    user = User(id=1, first_name="A", last_name="B", role="teacher",
                is_active=True, created_at=now, updated_at=now, is_admin=True)
    assert user.is_admin is True


def test_user_to_dict_includes_is_admin():
    """User.to_dict() includes is_admin field."""
    from datetime import datetime, timezone
    from backend.users.user_store import User
    now = datetime.now(timezone.utc)
    user = User(id=1, first_name="A", last_name="B", role="teacher",
                is_active=True, created_at=now, updated_at=now, is_admin=True)
    d = user.to_dict()
    assert "is_admin" in d
    assert d["is_admin"] is True


def test_user_to_dict_is_admin_false_by_default():
    """User.to_dict() is_admin=False for standard teacher."""
    from datetime import datetime, timezone
    from backend.users.user_store import User
    now = datetime.now(timezone.utc)
    user = User(id=1, first_name="A", last_name="B", role="teacher",
                is_active=True, created_at=now, updated_at=now)
    d = user.to_dict()
    assert "is_admin" in d
    assert d["is_admin"] is False


# ── DB-backed tests (skipped without DATABASE_URL) ───────────────────────────

import os as _os


@pytest.mark.db
@pytest.mark.skipif(
    not _os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_create_user_with_is_admin_false_persists():
    """create_user(is_admin=False) → persisted is_admin=False."""
    import psycopg
    from backend.migrations import run_migrations
    from backend.users.user_store import create_user, get_user_by_id

    db_url = _os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()
    try:
        user = create_user(conn, "Normal", "Teacher", role="teacher", is_admin=False)
        loaded = get_user_by_id(conn, user.id)
        assert loaded is not None
        assert loaded.is_admin is False
        assert loaded.role == "teacher"
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.db
@pytest.mark.skipif(
    not _os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_create_user_with_is_admin_true_persists():
    """create_user(is_admin=True) → persisted is_admin=True."""
    import psycopg
    from backend.migrations import run_migrations
    from backend.users.user_store import create_user, get_user_by_id

    db_url = _os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()
    try:
        user = create_user(conn, "Super", "Teacher", role="teacher", is_admin=True)
        loaded = get_user_by_id(conn, user.id)
        assert loaded is not None
        assert loaded.is_admin is True
        assert loaded.role == "teacher"
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.db
@pytest.mark.skipif(
    not _os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_create_user_with_legacy_admin_role_normalizes():
    """create_user(role='admin') → role='teacher', is_admin=True (compat layer)."""
    import psycopg
    from backend.migrations import run_migrations
    from backend.users.user_store import create_user, get_user_by_id

    db_url = _os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()
    try:
        user = create_user(conn, "Legacy", "Admin", role="admin")
        loaded = get_user_by_id(conn, user.id)
        assert loaded is not None
        assert loaded.is_admin is True
        # After normalization, role is stored as 'teacher'
        assert loaded.role == "teacher"
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.db
@pytest.mark.skipif(
    not _os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_create_teacher_with_is_admin_true_via_service():
    """create_teacher(is_admin=True) → User with is_admin=True."""
    import psycopg
    from backend.migrations import run_migrations
    from backend.users.user_service import create_teacher
    from backend.users.user_store import get_user_by_id

    db_url = _os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()
    try:
        user, _ = create_teacher(conn, "Admin", "Teacher", role="teacher", is_admin=True)
        loaded = get_user_by_id(conn, user.id)
        assert loaded is not None
        assert loaded.is_admin is True
        assert loaded.role == "teacher"
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.db
@pytest.mark.skipif(
    not _os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_create_teacher_legacy_role_admin_normalizes():
    """create_teacher(role='admin') → role='teacher', is_admin=True via compat."""
    import psycopg
    from backend.migrations import run_migrations
    from backend.users.user_service import create_teacher

    db_url = _os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()
    try:
        user, _ = create_teacher(conn, "Bootstrap", "Admin", role="admin")
        assert user.is_admin is True
        assert user.role == "teacher"
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.db
@pytest.mark.skipif(
    not _os.environ.get("DATABASE_URL"),
    reason="Requires DATABASE_URL"
)
def test_bootstrap_admin_has_is_admin_true():
    """Bootstrap admin created with is_admin=True (not just role='admin')."""
    import psycopg
    from backend.migrations import run_migrations
    from backend.users.user_service import create_teacher
    from backend.users.user_store import get_user_by_id

    db_url = _os.environ.get("DATABASE_URL", "").strip()
    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()
    try:
        # Simulate what bootstrap.py does (canonical form)
        user, _ = create_teacher(conn, "Bootstrap", "Admin", role="teacher", is_admin=True)
        loaded = get_user_by_id(conn, user.id)
        assert loaded is not None
        assert loaded.is_admin is True
        d = loaded.to_dict()
        assert d["is_admin"] is True
    finally:
        conn.rollback()
        conn.close()
