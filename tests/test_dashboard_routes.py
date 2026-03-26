"""Tests für GET /api/v2/dashboard/data (Phase 11f — Task F2).

Flask Test-Client + Mocks — no DB required.
"""
import pytest
from unittest.mock import patch, MagicMock

import backend.api.dashboard_routes  # noqa: F401
import backend.api.helpers  # noqa: F401


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Flask-App mit auth + dashboard Blueprints."""
    from flask import Flask
    import backend.api.auth_routes as auth_module
    import backend.api.dashboard_routes as dashboard_module

    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    auth_module.limiter.init_app(flask_app)
    flask_app.register_blueprint(auth_module.auth_bp, url_prefix="/api/v2/auth")
    flask_app.register_blueprint(dashboard_module.dashboard_bp, url_prefix="/api/v2/dashboard")

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


def _make_mock_user_module(module_id, is_visible=True):
    """Create a minimal mock UserModule."""
    um = MagicMock()
    um.module_id = module_id
    um.is_visible = is_visible
    um.sort_order = 10
    um.is_configured = True
    return um


# ── GET /api/v2/dashboard/data — auth tests ───────────────────────────────────

def test_dashboard_data_without_auth_returns_401(client):
    """GET /api/v2/dashboard/data ohne Auth → 401."""
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        response = client.get("/api/v2/dashboard/data")
    assert response.status_code == 401


# ── GET /api/v2/dashboard/data — happy-path tests ─────────────────────────────

def test_dashboard_data_with_teacher_auth_returns_200(client):
    """GET /api/v2/dashboard/data mit Teacher-Auth → 200 mit ok=true."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    # No active modules → empty fetcher map → fast path
    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=[]
            ):
                response = client.get("/api/v2/dashboard/data")

    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True


def test_dashboard_data_response_has_modules_key(client):
    """GET /api/v2/dashboard/data → response contains 'modules' key."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=[]
            ):
                response = client.get("/api/v2/dashboard/data")

    data = response.get_json()
    assert "modules" in data, f"Expected 'modules' key in response, got: {list(data.keys())}"
    assert isinstance(data["modules"], dict), (
        f"Expected 'modules' to be a dict, got: {type(data['modules'])}"
    )


def test_dashboard_data_response_has_user_key(client):
    """GET /api/v2/dashboard/data → response contains 'user' key with id and display_name."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=[]
            ):
                response = client.get("/api/v2/dashboard/data")

    data = response.get_json()
    assert "user" in data, f"Expected 'user' key in response, got: {list(data.keys())}"
    user = data["user"]
    assert "id" in user, f"Expected 'id' in user dict, got: {list(user.keys())}"
    assert "display_name" in user, (
        f"Expected 'display_name' in user dict, got: {list(user.keys())}"
    )


def test_dashboard_data_response_has_generated_at(client):
    """GET /api/v2/dashboard/data → response contains 'generated_at' ISO timestamp."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=[]
            ):
                response = client.get("/api/v2/dashboard/data")

    data = response.get_json()
    assert "generated_at" in data, (
        f"Expected 'generated_at' key in response, got: {list(data.keys())}"
    )
    assert isinstance(data["generated_at"], str), (
        f"Expected 'generated_at' to be a string, got: {type(data['generated_at'])}"
    )
    # Should be an ISO format timestamp (contains 'T' separator)
    assert "T" in data["generated_at"], (
        f"Expected ISO timestamp in 'generated_at', got: {data['generated_at']!r}"
    )


def test_dashboard_data_active_modules_appear_in_response(client):
    """GET /api/v2/dashboard/data mit sichtbaren Modulen → Module erscheinen in 'modules' dict."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    # Two visible modules
    mock_user_modules = [
        _make_mock_user_module("noten", is_visible=True),
        _make_mock_user_module("webuntis", is_visible=True),
    ]

    # Mock the noten and webuntis fetchers to return fast results
    def _mock_noten(user_id):
        return {"ok": True, "data": {"grades": [], "notes": []}}

    def _mock_webuntis(user_id):
        return {"ok": True, "data": None, "configured": False, "error": "no ical"}

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=mock_user_modules
            ):
                with patch.object(
                    backend.api.dashboard_routes, "_fetch_noten_data", side_effect=_mock_noten
                ):
                    with patch.object(
                        backend.api.dashboard_routes,
                        "_fetch_webuntis_data",
                        side_effect=_mock_webuntis,
                    ):
                        response = client.get("/api/v2/dashboard/data")

    assert response.status_code == 200
    data = response.get_json()
    assert "modules" in data
    modules = data["modules"]
    # Both active modules should appear in result
    assert "noten" in modules, f"Expected 'noten' in modules, got: {list(modules.keys())}"
    assert "webuntis" in modules, f"Expected 'webuntis' in modules, got: {list(modules.keys())}"


def test_dashboard_data_each_module_entry_has_ok_key(client):
    """GET /api/v2/dashboard/data — jedes Modul-Ergebnis hat einen 'ok'-Key."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    mock_user_modules = [_make_mock_user_module("noten", is_visible=True)]

    def _mock_noten(user_id):
        return {"ok": True, "data": {"grades": [], "notes": []}}

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=mock_user_modules
            ):
                with patch.object(
                    backend.api.dashboard_routes, "_fetch_noten_data", side_effect=_mock_noten
                ):
                    response = client.get("/api/v2/dashboard/data")

    data = response.get_json()
    modules = data.get("modules", {})
    for module_id, module_entry in modules.items():
        assert "ok" in module_entry, (
            f"Module '{module_id}' entry missing 'ok' key: {module_entry}"
        )


def test_dashboard_data_user_id_matches_teacher(client):
    """GET /api/v2/dashboard/data → user.id entspricht dem angemeldeten Teacher."""
    teacher = _make_teacher_user(id=42)
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=[]
            ):
                response = client.get("/api/v2/dashboard/data")

    data = response.get_json()
    assert data["user"]["id"] == 42, (
        f"Expected user.id=42, got: {data['user']['id']}"
    )


def test_dashboard_data_invisible_modules_not_fetched(client):
    """GET /api/v2/dashboard/data — unsichtbare Module werden nicht gefetcht."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    # One module visible, one not
    mock_user_modules = [
        _make_mock_user_module("noten", is_visible=True),
        _make_mock_user_module("itslearning", is_visible=False),
    ]

    def _mock_noten(user_id):
        return {"ok": True, "data": {"grades": [], "notes": []}}

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=mock_user_modules
            ):
                with patch.object(
                    backend.api.dashboard_routes, "_fetch_noten_data", side_effect=_mock_noten
                ):
                    response = client.get("/api/v2/dashboard/data")

    data = response.get_json()
    modules = data.get("modules", {})
    # itslearning was not visible → should not appear in result
    assert "itslearning" not in modules, (
        f"Invisible module 'itslearning' should not appear in modules, got: {list(modules.keys())}"
    )
    # noten was visible → should appear
    assert "noten" in modules, f"Visible module 'noten' should appear in modules"


# ── Phase 12: base section tests ─────────────────────────────────────────────

def test_dashboard_data_response_has_base_key(client):
    """GET /api/v2/dashboard/data → response contains 'base' key (Phase 12)."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=[]
            ):
                with patch.object(
                    backend.api.dashboard_routes, "_fetch_base_data",
                    return_value={"ok": True, "data": {"quick_links": [], "workspace": {}, "berlin_focus": [], "documents": None}}
                ):
                    response = client.get("/api/v2/dashboard/data")

    assert response.status_code == 200
    data = response.get_json()
    assert "base" in data, f"Expected 'base' key in response, got: {list(data.keys())}"
    assert isinstance(data["base"], dict), (
        f"Expected 'base' to be a dict, got: {type(data['base'])}"
    )


def test_dashboard_data_base_has_quick_links(client):
    """GET /api/v2/dashboard/data → base.quick_links exists and is a list."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    mock_quick_links = [
        {"id": "schoolportal", "title": "Berliner Schulportal", "url": "https://portal.berlin.de", "kind": "Portal", "note": ""}
    ]

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=[]
            ):
                with patch.object(
                    backend.api.dashboard_routes, "_fetch_base_data",
                    return_value={"ok": True, "data": {
                        "quick_links": mock_quick_links,
                        "workspace": {"eyebrow": "Berlin Lehrer-Cockpit", "title": "Test", "description": ""},
                        "berlin_focus": [],
                        "documents": None,
                    }}
                ):
                    response = client.get("/api/v2/dashboard/data")

    data = response.get_json()
    base = data.get("base", {})
    assert "quick_links" in base, f"Expected 'quick_links' in base, got: {list(base.keys())}"
    assert isinstance(base["quick_links"], list), (
        f"Expected 'quick_links' to be a list, got: {type(base['quick_links'])}"
    )
    assert len(base["quick_links"]) >= 1, "Expected at least one quick_link entry"


def test_dashboard_data_base_has_workspace(client):
    """GET /api/v2/dashboard/data → base.workspace exists."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=[]
            ):
                with patch.object(
                    backend.api.dashboard_routes, "_fetch_base_data",
                    return_value={"ok": True, "data": {
                        "quick_links": [],
                        "workspace": {"eyebrow": "Berlin Lehrer-Cockpit", "title": "Dein Tagesstart", "description": ""},
                        "berlin_focus": [],
                        "documents": None,
                    }}
                ):
                    response = client.get("/api/v2/dashboard/data")

    data = response.get_json()
    base = data.get("base", {})
    assert "workspace" in base, f"Expected 'workspace' in base, got: {list(base.keys())}"
    assert isinstance(base["workspace"], dict), (
        f"Expected 'workspace' to be a dict, got: {type(base['workspace'])}"
    )


def test_dashboard_data_base_sections_independent_on_base_failure(client):
    """GET /api/v2/dashboard/data → if _fetch_base_data fails, base defaults to empty values."""
    teacher = _make_teacher_user()
    mock_ctx, mock_conn = _make_db_context_mock()

    def _failing_base():
        raise RuntimeError("simulated base failure")

    with patch.object(backend.api.helpers, "get_current_user", return_value=teacher):
        with patch.object(backend.api.dashboard_routes, "db_connection", return_value=mock_ctx):
            with patch.object(
                backend.api.dashboard_routes, "get_user_modules", return_value=[]
            ):
                with patch.object(
                    backend.api.dashboard_routes, "_fetch_base_data",
                    side_effect=_failing_base
                ):
                    response = client.get("/api/v2/dashboard/data")

    # Should still return 200 with ok=true — base failure must not crash the endpoint
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("ok") is True
    # base section should exist with safe defaults
    assert "base" in data
    base = data["base"]
    assert isinstance(base.get("quick_links"), list)
    assert isinstance(base.get("workspace"), dict)
