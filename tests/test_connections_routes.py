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
            patch.object(routes, "save_user_module_config", side_effect=store.save):
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
