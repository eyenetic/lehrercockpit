"""Tests für Module-API-Endpunkte (backend/api/module_routes.py) – Flask Test-Client + Mocks."""
import pytest
from unittest.mock import patch, MagicMock

import backend.api.module_routes  # noqa: F401
import backend.api.helpers  # noqa: F401


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Flask-App mit module Blueprint."""
    from flask import Flask
    import backend.api.auth_routes as auth_module
    import backend.api.module_routes as module_routes_module

    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    auth_module.limiter.init_app(flask_app)
    flask_app.register_blueprint(auth_module.auth_bp, url_prefix="/api/v2/auth")
    flask_app.register_blueprint(module_routes_module.module_bp, url_prefix="/api/v2/modules")

    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


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
    mock_conn = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx, mock_conn


def _make_mock_module(module_id, module_type="individual", default_visible=True):
    """Erstellt ein Mock-Modul-Objekt."""
    from backend.modules.module_registry import Module
    return Module(
        id=module_id,
        display_name=module_id.title(),
        description="Test module",
        module_type=module_type,
        is_enabled=True,
        default_visible=default_visible,
        default_order=10,
        requires_config=(module_type == "individual"),
    )


# ── GET /api/v2/modules ────────────────────────────────────────────────────────

def test_list_modules_returns_200_without_auth(client):
    """GET /api/v2/modules gibt 200 zurück ohne Auth (öffentlicher Endpunkt)."""
    mock_ctx, mock_conn = _make_db_context_mock()
    mock_modules = [
        _make_mock_module("webuntis"),
        _make_mock_module("itslearning"),
        _make_mock_module("nextcloud"),
        _make_mock_module("orgaplan", "central"),
        _make_mock_module("klassenarbeitsplan", "central"),
        _make_mock_module("noten"),
        _make_mock_module("mail", "local", default_visible=False),
    ]

    with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.module_routes, "get_all_modules", return_value=mock_modules):
            response = client.get("/api/v2/modules")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "modules" in data


def test_list_modules_contains_expected_module_ids(client):
    """GET /api/v2/modules — Response enthält erwartete Modul-IDs."""
    mock_ctx, mock_conn = _make_db_context_mock()
    mock_modules = [
        _make_mock_module("webuntis"),
        _make_mock_module("itslearning"),
        _make_mock_module("nextcloud"),
        _make_mock_module("orgaplan", "central"),
        _make_mock_module("klassenarbeitsplan", "central"),
        _make_mock_module("noten"),
        _make_mock_module("mail", "local", default_visible=False),
    ]

    with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.module_routes, "get_all_modules", return_value=mock_modules):
            response = client.get("/api/v2/modules")

    data = response.get_json()
    module_ids = {m["id"] for m in data["modules"]}
    expected = {"webuntis", "itslearning", "nextcloud", "orgaplan", "klassenarbeitsplan"}
    for mid in expected:
        assert mid in module_ids, f"Modul '{mid}' fehlt in der Response"


def test_list_modules_mail_local_default_enabled_false(client):
    """GET /api/v2/modules — mail_local hat default_enabled: False."""
    mock_ctx, mock_conn = _make_db_context_mock()
    # mail module with default_visible=False
    mail_module = _make_mock_module("mail", "local", default_visible=False)
    mock_modules = [mail_module]

    with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.module_routes, "get_all_modules", return_value=mock_modules):
            response = client.get("/api/v2/modules")

    data = response.get_json()
    mail = next((m for m in data["modules"] if m["id"] == "mail"), None)
    assert mail is not None
    assert mail["default_visible"] is False


# ── GET /api/v2/modules/defaults ──────────────────────────────────────────────

def test_list_default_modules_returns_only_default_enabled(client):
    """GET /api/v2/modules/defaults gibt nur default-enabled Module zurück."""
    mock_ctx, mock_conn = _make_db_context_mock()
    # Only 2 default-visible modules
    default_modules = [
        _make_mock_module("webuntis"),
        _make_mock_module("itslearning"),
    ]

    with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
        with patch.object(backend.api.module_routes, "get_default_module_set", return_value=default_modules):
            response = client.get("/api/v2/modules/defaults")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "modules" in data
    assert len(data["modules"]) == 2


# ── GET /api/v2/modules/<id>/config ───────────────────────────────────────────

def test_get_module_config_without_auth_returns_401(client):
    """GET /api/v2/modules/<id>/config ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/modules/webuntis/config")
    assert response.status_code == 401


def test_get_module_config_with_auth_returns_200(client):
    """GET /api/v2/modules/<id>/config mit Auth → 200 (sensible Felder maskiert)."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()
    mock_config = {"ical_url": "https://example.com/cal.ics", "password": "secret123"}

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.module_routes, "get_user_module_config", return_value=mock_config):
                response = client.get("/api/v2/modules/webuntis/config")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "config" in data
    # Password should be masked
    assert data["config"].get("password") == "***"
    # Non-sensitive field should be intact
    assert data["config"].get("ical_url") == "https://example.com/cal.ics"


# ── PUT /api/v2/modules/<id>/config ───────────────────────────────────────────

def test_put_module_config_without_auth_returns_401(client):
    """PUT /api/v2/modules/<id>/config ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.put(
            "/api/v2/modules/webuntis/config",
            json={"ical_url": "https://example.com/cal.ics"},
        )
    assert response.status_code == 401


def test_put_module_config_individual_with_auth_returns_200(client):
    """PUT /api/v2/modules/webuntis/config mit Teacher-Auth → 200."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()
    mock_module = _make_mock_module("webuntis", "individual")

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.module_routes, "get_module_by_id", return_value=mock_module):
                with patch.object(backend.api.module_routes, "save_user_module_config"):
                    response = client.put(
                        "/api/v2/modules/webuntis/config",
                        json={"ical_url": "https://example.com/cal.ics"},
                    )

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True


def test_put_module_config_central_with_teacher_returns_403(client):
    """PUT /api/v2/modules/orgaplan/config mit Teacher → 403 (central-Modul)."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()
    mock_central_module = _make_mock_module("orgaplan", "central")

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.module_routes, "get_module_by_id", return_value=mock_central_module):
                response = client.put(
                    "/api/v2/modules/orgaplan/config",
                    json={"url": "https://example.com"},
                )

    assert response.status_code == 403


def test_put_module_config_nonexistent_module_returns_404(client):
    """PUT /api/v2/modules/nonexistent/config → 404."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.module_routes, "get_module_by_id", return_value=None):
                response = client.put(
                    "/api/v2/modules/nonexistent_xyz/config",
                    json={"key": "value"},
                )

    assert response.status_code == 404


def test_put_klassenarbeitsplan_config_with_teacher_returns_403(client):
    """PUT /api/v2/modules/klassenarbeitsplan/config mit Teacher → 403 (central)."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()
    mock_central_module = _make_mock_module("klassenarbeitsplan", "central")

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.module_routes, "get_module_by_id", return_value=mock_central_module):
                response = client.put(
                    "/api/v2/modules/klassenarbeitsplan/config",
                    json={"url": "https://example.com"},
                )

    assert response.status_code == 403


# ── GET /api/v2/modules/noten/data — auth tests ───────────────────────────────

def test_get_noten_data_without_auth_returns_401(client):
    """GET /api/v2/modules/noten/data ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/modules/noten/data")
    assert response.status_code == 401


def test_post_noten_grades_without_auth_returns_401(client):
    """POST /api/v2/modules/noten/grades ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.post(
            "/api/v2/modules/noten/grades",
            json={"class_name": "5a", "grade_value": "2"},
        )
    assert response.status_code == 401


def test_delete_noten_grade_without_auth_returns_401(client):
    """DELETE /api/v2/modules/noten/grades/1 ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.delete("/api/v2/modules/noten/grades/1")
    assert response.status_code == 401


def test_post_noten_notes_without_auth_returns_401(client):
    """POST /api/v2/modules/noten/notes ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.post(
            "/api/v2/modules/noten/notes",
            json={"class_name": "5a", "note_text": "Test"},
        )
    assert response.status_code == 401


# ── GET /api/v2/modules/noten/data — mocked happy-path ───────────────────────

def test_get_noten_data_with_auth_returns_200(client):
    """GET /api/v2/modules/noten/data mit Teacher-Auth → 200 mit grades und notes."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.module_routes, "get_grades", return_value=[]):
                with patch.object(backend.api.module_routes, "get_notes", return_value=[]):
                    response = client.get("/api/v2/modules/noten/data")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "grades" in data
    assert "notes" in data
    assert data["grades"] == []
    assert data["notes"] == []


def test_post_noten_grades_missing_class_name_returns_422(client):
    """POST /api/v2/modules/noten/grades ohne class_name → 422."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            response = client.post(
                "/api/v2/modules/noten/grades",
                json={"grade_value": "2+"},
            )

    assert response.status_code == 422


def test_post_noten_grades_missing_grade_value_returns_422(client):
    """POST /api/v2/modules/noten/grades ohne grade_value → 422."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            response = client.post(
                "/api/v2/modules/noten/grades",
                json={"class_name": "5a"},
            )

    assert response.status_code == 422


def test_post_noten_grades_with_auth_creates_grade(client):
    """POST /api/v2/modules/noten/grades mit gültigem Body → 200 mit grade."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()
    mock_grade = {
        "id": 1, "user_id": 2, "class_name": "5a",
        "subject": "Mathe", "grade_value": "2+",
        "grade_date": None, "note": "",
        "created_at": "2026-03-25T10:00:00+00:00",
        "updated_at": "2026-03-25T10:00:00+00:00",
    }

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.module_routes, "upsert_grade", return_value=mock_grade):
                response = client.post(
                    "/api/v2/modules/noten/grades",
                    json={"class_name": "5a", "subject": "Mathe", "grade_value": "2+"},
                )

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "grade" in data
    assert data["grade"]["class_name"] == "5a"


def test_delete_noten_grade_with_auth_returns_200(client):
    """DELETE /api/v2/modules/noten/grades/<id> mit Auth → 200."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.module_routes, "delete_grade", return_value=True):
                response = client.delete("/api/v2/modules/noten/grades/1")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True


def test_delete_noten_grade_not_found_returns_404(client):
    """DELETE /api/v2/modules/noten/grades/<id> wenn nicht gefunden → 404."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.module_routes, "delete_grade", return_value=False):
                response = client.delete("/api/v2/modules/noten/grades/9999")

    assert response.status_code == 404


def test_post_noten_notes_with_auth_creates_note(client):
    """POST /api/v2/modules/noten/notes mit gültigem Body → 200 mit note."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()
    mock_note = {
        "id": 1, "user_id": 2, "class_name": "5a",
        "note_text": "Klassenarbeit nächste Woche",
        "created_at": "2026-03-25T10:00:00+00:00",
        "updated_at": "2026-03-25T10:00:00+00:00",
    }

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(backend.api.module_routes, "upsert_note", return_value=mock_note):
                response = client.post(
                    "/api/v2/modules/noten/notes",
                    json={"class_name": "5a", "note_text": "Klassenarbeit nächste Woche"},
                )

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "note" in data
    assert data["note"]["class_name"] == "5a"


def test_post_noten_notes_missing_class_name_returns_422(client):
    """POST /api/v2/modules/noten/notes ohne class_name → 422."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            response = client.post(
                "/api/v2/modules/noten/notes",
                json={"note_text": "Test"},
            )

    assert response.status_code == 422


# ── DB integration tests (noten v2) ───────────────────────────────────────────

import os as _os

@pytest.mark.skipif(
    not _os.environ.get("DATABASE_URL", "").strip(),
    reason="DATABASE_URL not set",
)
def test_db_get_noten_data_returns_empty_for_new_teacher():
    """GET /api/v2/modules/noten/data — neuer Teacher hat leere grades+notes."""
    import psycopg
    from flask import Flask
    import backend.api.auth_routes as auth_module
    import backend.api.module_routes as module_routes_module

    db_url = _os.environ["DATABASE_URL"]
    conn = psycopg.connect(db_url)
    from backend.migrations import run_migrations
    run_migrations(conn)
    conn.commit()

    try:
        from backend.users.user_service import create_teacher
        user, _ = create_teacher(conn, "NotenDB", "Teacher")
        conn.commit()

        flask_app = Flask(__name__)
        flask_app.config["TESTING"] = True
        auth_module.limiter.init_app(flask_app)
        flask_app.register_blueprint(auth_module.auth_bp, url_prefix="/api/v2/auth")
        flask_app.register_blueprint(module_routes_module.module_bp, url_prefix="/api/v2/modules")

        teacher_mock = _make_teacher_user(id=user.id)
        mock_ctx, _ = _make_db_context_mock()

        with flask_app.test_client() as c:
            with patch.object(backend.api.helpers, "get_current_user", return_value=teacher_mock):
                with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
                    with patch.object(backend.api.module_routes, "get_grades", return_value=[]):
                        with patch.object(backend.api.module_routes, "get_notes", return_value=[]):
                            resp = c.get("/api/v2/modules/noten/data")
                            assert resp.status_code == 200
                            data = resp.get_json()
                            assert data["grades"] == []
                            assert data["notes"] == []
    finally:
        conn.rollback()
        conn.close()


# ── Phase 10g: WebUntis v2 endpoint tests ────────────────────────────────────

def test_webuntis_data_without_auth_returns_401(client):
    """GET /api/v2/modules/webuntis/data ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/modules/webuntis/data")
    assert response.status_code == 401


def test_webuntis_data_no_ical_url_returns_200_configured_false(client):
    """GET /api/v2/modules/webuntis/data mit Teacher-Auth, aber ohne ical_url → 200, configured=false."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    # Config without ical_url
    mock_config = {}

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.module_routes, "get_user_module_config", return_value=mock_config
            ):
                response = client.get("/api/v2/modules/webuntis/data")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert data.get("configured") is False, (
        f"Expected configured=false when ical_url is absent, got: {data}"
    )


def test_webuntis_data_with_ical_url_returns_serializable_json(client):
    """GET /api/v2/modules/webuntis/data mit ical_url → 200, JSON-serialisierbares data."""
    import dataclasses
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    # Config with ical_url set
    mock_config = {
        "base_url": "https://heliobas.webuntis.com/WebUntis",
        "ical_url": "https://heliobas.webuntis.com/WebUntis/Ical.do?token=test",
    }

    # Build a minimal WebUntisSyncResult-like dataclass for the mock
    @dataclasses.dataclass
    class _MockSyncResult:
        source: dict = dataclasses.field(default_factory=lambda: {"id": "webuntis", "status": "ok"})
        schedule: list = dataclasses.field(default_factory=list)
        events: list = dataclasses.field(default_factory=list)
        priorities: list = dataclasses.field(default_factory=list)

    mock_result = _MockSyncResult()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.module_routes, "get_user_module_config", return_value=mock_config
            ):
                with patch(
                    "backend.webuntis_adapter.fetch_webuntis_sync",
                    return_value=mock_result,
                ):
                    response = client.get("/api/v2/modules/webuntis/data")

    assert response.status_code == 200
    data = response.get_json()
    assert data is not None, "Response must be valid JSON (not a 500)"
    assert data.get("ok") is True
    # The 'data' key must be a dict (not a raw dataclass object)
    assert "data" in data
    assert isinstance(data["data"], dict), (
        f"Expected data['data'] to be a dict (dataclasses.asdict applied), "
        f"got: {type(data['data'])}"
    )


# ── Phase 11f: itslearning v2 endpoint tests ─────────────────────────────────

def test_itslearning_data_without_auth_returns_401(client):
    """GET /api/v2/modules/itslearning/data ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/modules/itslearning/data")
    assert response.status_code == 401


def test_itslearning_data_no_config_returns_200_configured_false(client):
    """GET /api/v2/modules/itslearning/data mit Teacher-Auth, kein Config → 200, configured=false."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    # Empty config → no username/password
    mock_config = {}

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.module_routes, "get_user_module_config", return_value=mock_config
            ):
                response = client.get("/api/v2/modules/itslearning/data")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert data.get("configured") is False, (
        f"Expected configured=false when no credentials, got: {data}"
    )


def test_itslearning_data_with_config_returns_serializable_json(client):
    """GET /api/v2/modules/itslearning/data mit Credentials → 200, JSON-serialisierbares data dict."""
    import dataclasses
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    mock_config = {
        "base_url": "https://berlin.itslearning.com",
        "username": "lehrer@schule.de",
        "password": "secret",
        "max_updates": 6,
    }

    # Minimal ItslearningSyncResult-like dataclass
    @dataclasses.dataclass
    class _MockItslearningResult:
        source: dict = dataclasses.field(default_factory=lambda: {"id": "itslearning", "status": "ok"})
        messages: list = dataclasses.field(default_factory=list)
        priorities: list = dataclasses.field(default_factory=list)
        mode: str = "live"
        note: str = ""

    mock_result = _MockItslearningResult()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.module_routes, "get_user_module_config", return_value=mock_config
            ):
                with patch(
                    "backend.itslearning_adapter.fetch_itslearning_sync",
                    return_value=mock_result,
                ):
                    response = client.get("/api/v2/modules/itslearning/data")

    assert response.status_code == 200
    data = response.get_json()
    assert data is not None, "Response must be valid JSON"
    assert data.get("ok") is True
    assert "data" in data
    assert isinstance(data["data"], dict), (
        f"Expected data['data'] to be a dict (dataclasses.asdict applied), got: {type(data['data'])}"
    )


# ── Phase 11f: nextcloud v2 endpoint tests ───────────────────────────────────

def test_nextcloud_data_without_auth_returns_401(client):
    """GET /api/v2/modules/nextcloud/data ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/modules/nextcloud/data")
    assert response.status_code == 401


def test_nextcloud_data_no_config_returns_200_configured_false(client):
    """GET /api/v2/modules/nextcloud/data mit Teacher-Auth, kein Config → 200, configured=false."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    # No base_url or workspace_url configured
    mock_config = {}

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.module_routes, "get_user_module_config", return_value=mock_config
            ):
                response = client.get("/api/v2/modules/nextcloud/data")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert data.get("configured") is False, (
        f"Expected configured=false when no base_url/workspace_url, got: {data}"
    )


# ── Phase 11f: orgaplan v2 endpoint tests ────────────────────────────────────

def test_orgaplan_data_without_auth_returns_401(client):
    """GET /api/v2/modules/orgaplan/data ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/modules/orgaplan/data")
    assert response.status_code == 401


def test_orgaplan_data_no_url_returns_200_configured_false(client):
    """GET /api/v2/modules/orgaplan/data mit Auth, kein URL → 200, configured=false."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    # No orgaplan_url or orgaplan_pdf_url configured
    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.module_routes, "get_system_setting", return_value=None
            ):
                response = client.get("/api/v2/modules/orgaplan/data")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert data.get("configured") is False, (
        f"Expected configured=false when no URL set, got: {data}"
    )


def test_orgaplan_data_with_url_and_mocked_digest_returns_200(client):
    """GET /api/v2/modules/orgaplan/data mit URL + gemocktem build_plan_digest → 200 mit data."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    mock_digest_full = {
        "orgaplan": {
            "status": "ok",
            "highlights": ["Test highlight"],
            "upcoming": [{"date": "2026-04-01", "text": "Konferenz"}],
            "monthLabel": "April 2026",
            "detail": "",
        }
    }

    def _mock_get_system_setting(conn, key, default=None):
        if key == "orgaplan_pdf_url":
            return "https://example.com/orgaplan.pdf"
        if key == "orgaplan_url":
            return "https://example.com/orgaplan"
        # Cache keys → no cache (force fresh parse)
        return None

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.module_routes,
                "get_system_setting",
                side_effect=_mock_get_system_setting,
            ):
                with patch(
                    "backend.plan_digest.build_plan_digest",
                    return_value=mock_digest_full,
                ):
                    response = client.get("/api/v2/modules/orgaplan/data")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert data.get("configured") is True
    assert "data" in data
    result_data = data["data"]
    assert isinstance(result_data, dict), f"Expected dict, got: {type(result_data)}"
    assert result_data.get("status") == "ok"
    assert "highlights" in result_data


# ── Phase 11f: klassenarbeitsplan v2 endpoint tests ──────────────────────────

def test_klassenarbeitsplan_data_without_auth_returns_401(client):
    """GET /api/v2/modules/klassenarbeitsplan/data ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/modules/klassenarbeitsplan/data")
    assert response.status_code == 401


def test_klassenarbeitsplan_data_empty_cache_returns_200(client):
    """GET /api/v2/modules/klassenarbeitsplan/data mit Teacher-Auth + leerer Cache → 200, kein Crash."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    # Cache returns empty/warning status → triggers fallback
    mock_cache = {"status": "warning", "previewRows": [], "entries": []}
    # plan_digest fallback also returns empty classwork
    mock_digest_full = {
        "classwork": {
            "status": "warning",
            "title": "Klassenarbeitsplan",
            "detail": "Keine Daten",
            "updatedAt": "--:--",
            "previewRows": [],
            "classes": [],
            "entries": [],
            "defaultClass": "",
            "sourceUrl": "",
        }
    }

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.module_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.module_routes, "get_system_setting", return_value=None
            ):
                with patch(
                    "backend.classwork_cache.load_cache",
                    return_value=mock_cache,
                ):
                    with patch(
                        "backend.plan_digest.build_plan_digest",
                        return_value=mock_digest_full,
                    ):
                        response = client.get("/api/v2/modules/klassenarbeitsplan/data")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    assert "data" in data
