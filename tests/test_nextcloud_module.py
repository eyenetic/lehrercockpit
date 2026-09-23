"""Tests für backend/nextcloud_module.py (Status, Login-Flow-Zustand, Datenabruf)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend import nextcloud_module as ncm
from backend.nextcloud_client import NextcloudAuthError, NextcloudError

NOW = datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)
CONNECTED = {"base_url": "https://cloud.example", "login_name": "anna", "app_password": "pw"}


@pytest.fixture(autouse=True)
def _clear_cache():
    ncm._cache.clear()
    yield
    ncm._cache.clear()


def test_suggested_server_prefers_setting_then_known_links():
    assert ncm.suggested_server({"nextcloud_url": "https://cloud.a/"}) == "https://cloud.a"
    assert ncm.suggested_server({"fehlzeiten_11_url": "https://cloud.b/index.php/f/12"}) == "https://cloud.b"
    assert ncm.suggested_server({"nextcloud_url": "http://unsicher"}) == ""


def test_pending_flow_expires_after_twenty_minutes():
    config = {"pending_poll_endpoint": "https://cloud.example/poll", "pending_poll_token": "t",
              "pending_started_at": (NOW - timedelta(minutes=5)).isoformat()}
    assert ncm.pending_flow(config, NOW) == {"poll_endpoint": "https://cloud.example/poll", "poll_token": "t"}
    config["pending_started_at"] = (NOW - timedelta(minutes=21)).isoformat()
    assert ncm.pending_flow(config, NOW) is None


def test_status_hides_secrets():
    status = ncm.status(CONNECTED, {}, NOW)
    assert status == {"connected": True, "account": "anna", "server": "https://cloud.example",
                      "suggested_server": "https://cloud.example", "pending": False}


def test_payload_not_connected():
    assert ncm.build_nextcloud_payload({}, NOW) == {"ok": True, "data": None, "configured": False}


def test_payload_combines_activity_and_notifications_and_caches():
    with patch.object(ncm, "fetch_activity", return_value=[{"id": "a"}]) as activity, \
            patch.object(ncm, "fetch_notifications", return_value=[{"id": "n"}]):
        first = ncm.build_nextcloud_payload(CONNECTED, NOW)
        second = ncm.build_nextcloud_payload(CONNECTED, NOW)
    assert first["data"]["activity"] == [{"id": "a"}]
    assert first["data"]["notifications"] == [{"id": "n"}]
    assert second["data"] is first["data"]
    assert activity.call_count == 1


def test_revoked_password_is_reported():
    with patch.object(ncm, "fetch_activity", side_effect=NextcloudAuthError("x")):
        data = ncm.build_nextcloud_payload(CONNECTED, NOW)["data"]
    assert data["revoked"] is True
    assert "neu verbinden" in data["error"]


def test_network_errors_are_not_cached():
    with patch.object(ncm, "fetch_activity", side_effect=NextcloudError("down")):
        ncm.build_nextcloud_payload(CONNECTED, NOW)
    assert ncm._cache == {}
