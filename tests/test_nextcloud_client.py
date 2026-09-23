"""Tests für backend/nextcloud_client.py (Login Flow v2, OCS-Aktivitäten)."""
import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from backend import nextcloud_client as nc


class _Response:
    def __init__(self, payload=None, status=200):
        self._body = json.dumps(payload).encode("utf-8") if payload is not None else b""
        self.status = status

    def read(self, *_args):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _http_error(code):
    return HTTPError("https://cloud.example/x", code, "err", {}, io.BytesIO(b""))


@pytest.fixture(autouse=True)
def _no_dns():
    with patch.object(nc, "require_public_https_url", side_effect=lambda url: url.rstrip("/")):
        yield


def test_start_login_flow_returns_login_and_poll_data():
    payload = {
        "poll": {"token": "tok", "endpoint": "https://cloud.example/index.php/login/v2/poll"},
        "login": "https://cloud.example/index.php/login/v2/flow/abc",
    }
    with patch.object(nc, "_open", return_value=_Response(payload)) as opened:
        flow = nc.start_login_flow("https://cloud.example/")
    request = opened.call_args[0][0]
    assert request.get_method() == "POST"
    assert request.full_url == "https://cloud.example/index.php/login/v2"
    assert flow == {
        "login_url": payload["login"],
        "poll_endpoint": payload["poll"]["endpoint"],
        "poll_token": "tok",
        "base_url": "https://cloud.example",
    }


def test_start_login_flow_rejects_foreign_poll_host():
    payload = {"poll": {"token": "t", "endpoint": "https://evil.example/poll"}, "login": "https://cloud.example/x"}
    with patch.object(nc, "_open", return_value=_Response(payload)):
        with pytest.raises(nc.NextcloudError):
            nc.start_login_flow("https://cloud.example")


def test_start_login_flow_on_non_nextcloud_server():
    with patch.object(nc, "_open", return_value=_Response({"hello": "world"})):
        with pytest.raises(nc.NextcloudError, match="keine Nextcloud"):
            nc.start_login_flow("https://example.org")


def test_poll_pending_returns_none():
    with patch.object(nc, "_open", side_effect=_http_error(404)):
        assert nc.poll_login_flow("https://cloud.example/poll", "tok") is None


def test_poll_success_returns_credentials_and_sends_token():
    payload = {"server": "https://cloud.example", "loginName": "anna", "appPassword": "secret-app-pw"}
    with patch.object(nc, "_open", return_value=_Response(payload)) as opened:
        credentials = nc.poll_login_flow("https://cloud.example/poll", "tok")
    assert opened.call_args[0][0].data == b"token=tok"
    assert credentials == {"server": "https://cloud.example", "login_name": "anna", "app_password": "secret-app-pw"}


def test_activity_is_normalized_and_uses_app_password():
    payload = {"ocs": {"data": [{
        "activity_id": 42, "datetime": "2026-09-23T08:00:00+00:00", "app": "files", "type": "file_changed",
        "subject": "Ben hat Fehlzeiten 10b.xlsx geändert", "object_name": "/Fehlzeiten 10b.xlsx",
        "link": "https://cloud.example/f/1", "user": "ben",
    }]}}
    with patch.object(nc, "_open", return_value=_Response(payload)) as opened:
        items = nc.fetch_activity("https://cloud.example", "anna", "pw")
    request = opened.call_args[0][0]
    assert "/ocs/v2.php/apps/activity/api/v2/activity/by?" in request.full_url
    assert request.get_header("Ocs-apirequest") == "true"
    assert request.get_header("Authorization").startswith("Basic ")
    assert items == [{
        "id": "nextcloud-activity-42", "activity_id": 42, "time": "2026-09-23T08:00:00+00:00",
        "app": "files", "type": "file_changed", "label": "geändert",
        "subject": "Ben hat Fehlzeiten 10b.xlsx geändert", "object_name": "/Fehlzeiten 10b.xlsx",
        "link": "https://cloud.example/f/1", "user": "ben",
    }]


@pytest.mark.parametrize("code", [304, 404])
def test_empty_or_missing_app_yields_no_items(code):
    with patch.object(nc, "_open", side_effect=_http_error(code)):
        assert nc.fetch_notifications("https://cloud.example", "anna", "pw") == []


def test_revoked_app_password_raises_auth_error():
    with patch.object(nc, "_open", side_effect=_http_error(401)):
        with pytest.raises(nc.NextcloudAuthError):
            nc.fetch_activity("https://cloud.example", "anna", "pw")


def test_revoke_is_best_effort():
    with patch.object(nc, "_open", side_effect=OSError("down")):
        assert nc.revoke_app_password("https://cloud.example", "anna", "pw") is False
    with patch.object(nc, "_open", return_value=_Response({}, status=200)) as opened:
        assert nc.revoke_app_password("https://cloud.example", "anna", "pw") is True
    assert opened.call_args[0][0].get_method() == "DELETE"
