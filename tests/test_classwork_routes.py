"""Tests für die Klassenarbeitsplan-Sync-Endpunkte in backend/api/module_routes.py."""
from unittest.mock import MagicMock, patch

import pytest

import backend.api.helpers
import backend.api.module_routes as routes

URL = "https://1drv.ms/x/c/abc/PLAN?e=1"


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(routes.module_bp, url_prefix="/api/v2/modules")
    return app.test_client()


def _user(is_admin=False):
    user = MagicMock()
    user.id = 3
    user.is_active = True
    user.is_admin = is_admin
    user.full_name = "Anna Beispiel"
    return user


def _as(user):
    return patch.object(backend.api.helpers, "get_current_user", return_value=user)


def test_browser_sync_requires_login(client):
    with _as(None):
        assert client.post("/api/v2/modules/klassenarbeitsplan/browser-sync", data=b"x").status_code == 401


def test_browser_sync_stores_plan_with_onedrive_metadata(client):
    with _as(_user()), patch.object(routes, "_classwork_url", return_value=URL), \
            patch("backend.classwork_sync.store_plan", return_value={"status": "ok"}) as store_plan, \
            patch("backend.classwork_sync.record_browser_result") as record:
        response = client.post(
            "/api/v2/modules/klassenarbeitsplan/browser-sync",
            data=b"xlsx-bytes",
            headers={"Content-Type": "application/octet-stream", "X-Source-ETag": "e9",
                     "X-Source-Modified": "2026-09-22T18:00:00Z", "X-Source-Name": "Klassenarbeiten%202026.xlsx"},
        )
    assert response.status_code == 200
    args, kwargs = store_plan.call_args
    assert args == (b"xlsx-bytes",)
    assert kwargs["source"] == "onedrive-browser"
    assert kwargs["uploaded_by"] == "Anna Beispiel"
    assert kwargs["meta"] == {"etag": "e9", "modified": "2026-09-22T18:00:00Z", "name": "Klassenarbeiten 2026.xlsx"}
    record.assert_called_once()


def test_browser_sync_needs_onedrive_link(client):
    with _as(_user()), patch.object(routes, "_classwork_url", return_value="https://example.com/plan.xlsx"):
        response = client.post("/api/v2/modules/klassenarbeitsplan/browser-sync", data=b"x")
    assert response.status_code == 409


def test_browser_sync_rejects_unreadable_file(client):
    with _as(_user()), patch.object(routes, "_classwork_url", return_value=URL), \
            patch("backend.classwork_sync.store_plan", side_effect=ValueError("leer")):
        response = client.post("/api/v2/modules/klassenarbeitsplan/browser-sync", data=b"x")
    assert response.status_code == 422


def test_sync_confirm_requires_matching_etag(client):
    state = {"source_url": URL, "etag": "e1"}
    with _as(_user()), patch.object(routes, "_classwork_url", return_value=URL), \
            patch("backend.classwork_sync.load_state", return_value=state), \
            patch("backend.classwork_sync.record_browser_result") as record, \
            patch("backend.classwork_sync.sync_info", return_value={"onedrive": True}):
        mismatch = client.post("/api/v2/modules/klassenarbeitsplan/sync-confirm", json={"etag": "other"})
        match = client.post("/api/v2/modules/klassenarbeitsplan/sync-confirm", json={"etag": "e1"})
    assert mismatch.status_code == 409
    assert match.status_code == 200
    record.assert_called_once()
    assert record.call_args.kwargs["changed"] is False


def test_only_admins_change_the_school_link(client):
    with _as(_user(is_admin=False)):
        assert client.post("/api/v2/modules/klassenarbeitsplan/config", json={"url": URL}).status_code == 403
        assert client.post("/api/v2/modules/klassenarbeitsplan/fetch", json={"url": URL}).status_code == 403


def test_fetch_reports_when_browser_must_step_in(client):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    with _as(_user()), patch.object(routes, "db_connection", return_value=ctx), \
            patch.object(routes, "get_system_setting", side_effect=lambda conn, key, default=None: URL if key == "klassenarbeitsplan_url" else default), \
            patch("backend.classwork_sync.sync_from_server", return_value="blocked"), \
            patch("backend.classwork_sync.sync_info", return_value={"onedrive": True, "etag": "e1", "last_error": "HTTP 403"}):
        body = client.post("/api/v2/modules/klassenarbeitsplan/fetch", json={}).get_json()
    assert body["result"] == "blocked"
    assert body["sync"]["needs_browser"] is True
    assert body["error"] == "HTTP 403"
