"""Tests für /api/v2/connections (Verbindungen-Dialog)."""
from unittest.mock import MagicMock, patch

import pytest

import backend.api.connections_routes as routes
import backend.api.helpers


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(routes.connections_bp, url_prefix="/api/v2/connections")
    return app.test_client()


def _teacher():
    user = MagicMock()
    user.id = 7
    user.is_active = True
    user.is_admin = False
    return user


class _Store:
    """In-memory stand-in for user_module_configs."""

    def __init__(self, configs=None):
        self.configs = {k: dict(v) for k, v in (configs or {}).items()}
        self.conn = MagicMock()

    def get(self, conn, user_id, module_id):
        return dict(self.configs.get(module_id, {}))

    def save(self, conn, user_id, module_id, config):
        self.configs[module_id] = dict(config)


def _call(client, store, method, path, **kwargs):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=store.conn)
    ctx.__exit__ = MagicMock(return_value=False)
    with patch.object(backend.api.helpers, "get_current_user", return_value=_teacher()), \
            patch.object(routes, "db_connection", return_value=ctx), \
            patch.object(routes, "get_user_module_config", side_effect=store.get), \
            patch.object(routes, "save_user_module_config", side_effect=store.save), \
            patch.object(routes, "_school_settings", return_value={"nextcloud_url": "https://cloud.schule.de"}), \
            patch.object(routes, "_classwork_status", return_value={"url": "", "onedrive": False}), \
            patch.object(routes, "log_audit_event"):
        return getattr(client, method)(path, **kwargs)


def test_requires_login(client):
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        assert client.get("/api/v2/connections").status_code == 401


def test_status_never_exposes_secrets(client):
    store = _Store({"itslearning": {"calendar_url": "https://x/secret", "username": "u", "password": "p"}})
    response = _call(client, store, "get", "/api/v2/connections")
    body = response.get_json()
    assert response.status_code == 200
    assert body["connections"]["itslearning"] == {"calendar": True, "login": True, "username": "u"}
    assert "secret" not in response.get_data(as_text=True)


def test_patch_merges_fields_instead_of_replacing(client):
    store = _Store({"itslearning": {"username": "u", "password": "p"}})
    response = _call(client, store, "patch", "/api/v2/connections/itslearning",
                     json={"calendar_url": "webcal://berlin.itslearning.com/cal?key=1"})
    assert response.status_code == 200
    assert store.configs["itslearning"] == {
        "username": "u",
        "password": "p",
        "calendar_url": "https://berlin.itslearning.com/cal?key=1",
    }


def test_patch_null_removes_field(client):
    store = _Store({"itslearning": {"calendar_url": "https://x", "username": "u", "password": "p"}})
    _call(client, store, "patch", "/api/v2/connections/itslearning", json={"username": None, "password": None})
    assert store.configs["itslearning"] == {"calendar_url": "https://x"}


@pytest.mark.parametrize("body,status", [
    ({"calendar_url": "http://unsicher.example/cal"}, 422),
    ({"unbekannt": "x"}, 422),
    ({}, 422),
])
def test_patch_validates_input(client, body, status):
    store = _Store()
    response = _call(client, store, "patch", "/api/v2/connections/itslearning", json=body)
    assert response.status_code == status
    assert store.configs == {}


def test_patch_unknown_module_is_404(client):
    response = _call(client, _Store(), "patch", "/api/v2/connections/noten", json={"x": "y"})
    assert response.status_code == 404


# ── Nextcloud Login Flow v2 ──────────────────────────────────────────────────

def test_status_suggests_school_nextcloud(client):
    body = _call(client, _Store(), "get", "/api/v2/connections").get_json()
    assert body["connections"]["nextcloud"]["suggested_server"] == "https://cloud.schule.de"
    assert body["connections"]["nextcloud"]["connected"] is False


def test_nextcloud_start_stores_pending_flow_but_not_credentials(client):
    store = _Store()
    flow = {"login_url": "https://cloud.schule.de/login/flow/x", "poll_endpoint": "https://cloud.schule.de/poll",
            "poll_token": "tok", "base_url": "https://cloud.schule.de"}
    with patch.object(routes, "start_login_flow", return_value=flow) as start:
        response = _call(client, store, "post", "/api/v2/connections/nextcloud/start", json={})
    assert response.status_code == 200
    assert response.get_json()["login_url"] == flow["login_url"]
    start.assert_called_once_with("https://cloud.schule.de")
    config = store.configs["nextcloud"]
    assert config["pending_poll_token"] == "tok"
    assert "app_password" not in config


def test_nextcloud_start_rejects_unsafe_address(client):
    from backend.http_utils import UnsafeUrlError
    with patch.object(routes, "start_login_flow", side_effect=UnsafeUrlError("intern")):
        response = _call(client, _Store(), "post", "/api/v2/connections/nextcloud/start",
                         json={"base_url": "https://intern.example"})
    assert response.status_code == 422


def _pending_store():
    from datetime import datetime, timezone
    return _Store({"nextcloud": {
        "base_url": "https://cloud.schule.de",
        "pending_base_url": "https://cloud.schule.de",
        "pending_poll_endpoint": "https://cloud.schule.de/poll",
        "pending_poll_token": "tok",
        "pending_started_at": datetime.now(timezone.utc).isoformat(),
    }})


def test_nextcloud_poll_pending(client):
    with patch.object(routes, "poll_login_flow", return_value=None):
        body = _call(client, _pending_store(), "post", "/api/v2/connections/nextcloud/poll").get_json()
    assert body["status"] == "pending"


def test_nextcloud_poll_success_saves_app_password_and_clears_pending(client):
    store = _pending_store()
    credentials = {"server": "https://cloud.schule.de", "login_name": "anna", "app_password": "app-pw"}
    with patch.object(routes, "poll_login_flow", return_value=credentials):
        body = _call(client, store, "post", "/api/v2/connections/nextcloud/poll").get_json()
    assert body["status"] == "connected"
    assert body["connections"]["nextcloud"]["account"] == "anna"
    config = store.configs["nextcloud"]
    assert config["app_password"] == "app-pw"
    assert not any(key.startswith("pending_") for key in config)
    assert "app-pw" not in str(body)


def test_nextcloud_poll_without_flow_is_expired(client):
    body = _call(client, _Store(), "post", "/api/v2/connections/nextcloud/poll").get_json()
    assert body["status"] == "expired"


def test_nextcloud_disconnect_revokes_and_removes_credentials(client):
    store = _Store({"nextcloud": {"base_url": "https://cloud.schule.de", "login_name": "anna",
                                  "app_password": "app-pw", "connected_at": "x"}})
    with patch.object(routes, "revoke_app_password", return_value=True) as revoke:
        body = _call(client, store, "delete", "/api/v2/connections/nextcloud").get_json()
    revoke.assert_called_once_with("https://cloud.schule.de", "anna", "app-pw")
    assert body["revoked"] is True
    assert store.configs["nextcloud"] == {"base_url": "https://cloud.schule.de"}
