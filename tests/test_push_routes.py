"""Tests für /api/v2/push (Geräte anmelden, Versand anstoßen)."""
from unittest.mock import MagicMock, patch

import pytest

import backend.api.helpers
import backend.api.push_routes as routes
from backend.webpush import VapidConfig

CONFIG = VapidConfig("PUBLIC", "PRIVATE", "mailto:x@y.de")


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(routes.push_bp, url_prefix="/api/v2/push")
    return app.test_client()


def _teacher():
    user = MagicMock()
    user.id = 4
    user.is_active = True
    return user


def _db():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_config_reports_public_key_only(client):
    with patch.object(routes, "vapid_config", return_value=CONFIG):
        body = client.get("/api/v2/push/config").get_json()
    assert body["enabled"] is True and body["public_key"] == "PUBLIC"
    assert "PRIVATE" not in str(body)


def test_subscribe_validates_and_stores(client):
    sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "k", "auth": "a"}}
    with patch.object(backend.api.helpers, "get_current_user", return_value=_teacher()), \
            patch.object(routes, "vapid_config", return_value=CONFIG), \
            patch.object(routes, "db_connection", return_value=_db()), \
            patch.object(routes, "save_subscription") as save:
        bad = client.post("/api/v2/push/subscribe", json={"subscription": {"endpoint": "http://x"}})
        good = client.post("/api/v2/push/subscribe", json={"subscription": sub, "prefs": {"weekly": False}})
    assert bad.status_code == 422
    assert good.status_code == 200
    args = save.call_args.args
    assert args[1:5] == (4, sub["endpoint"], "k", "a")
    assert args[6] == {"morning": True, "weekly": False}


def test_dispatch_requires_secret(client, monkeypatch):
    monkeypatch.setenv("PUSH_CRON_SECRET", "s3cret")
    with patch.object(routes, "dispatch", return_value={"sent": 0}) as run:
        assert client.post("/api/v2/push/dispatch").status_code == 403
        assert client.post("/api/v2/push/dispatch", headers={"X-Cron-Secret": "falsch"}).status_code == 403
        ok = client.post("/api/v2/push/dispatch", headers={"X-Cron-Secret": "s3cret"})
    assert ok.status_code == 200
    run.assert_called_once()


def test_dispatch_is_closed_without_configured_secret(client, monkeypatch):
    monkeypatch.delenv("PUSH_CRON_SECRET", raising=False)
    assert client.post("/api/v2/push/dispatch", headers={"X-Cron-Secret": ""}).status_code == 403
