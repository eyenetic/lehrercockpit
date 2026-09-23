"""Nextcloud client: Login Flow v2 (app password) and the OCS activity/notification APIs.

Login Flow v2 lets the teacher sign in on the school's own Nextcloud page
(SSO and two-factor included). The cockpit only ever receives a dedicated
app password, which the teacher can revoke under Settings → Security.
Docs: https://docs.nextcloud.com/server/stable/developer_manual/client_apis/LoginFlow/
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .http_utils import require_public_https_url, tls_context

# Shown as the app password's name under Nextcloud → Settings → Security.
USER_AGENT = "Lehrercockpit"
TIMEOUT = 12


class NextcloudError(Exception):
    """Nextcloud could not be reached or answered unexpectedly."""


class NextcloudAuthError(NextcloudError):
    """The stored app password was rejected (revoked in Nextcloud)."""


def _open(request: Request):
    return urlopen(request, timeout=TIMEOUT, context=tls_context())


def _read_json(response) -> Any:
    raw = response.read(2_000_000)
    return json.loads(raw.decode("utf-8") or "null")


def _auth_headers(login_name: str, app_password: str) -> dict[str, str]:
    token = base64.b64encode(f"{login_name}:{app_password}".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "OCS-APIRequest": "true",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }


def start_login_flow(base_url: str) -> dict[str, str]:
    """Start Login Flow v2. Returns login_url (for the browser) and the poll data."""
    base = require_public_https_url(base_url)
    request = Request(
        base + "/index.php/login/v2",
        method="POST",
        data=b"",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with _open(request) as response:
            payload = _read_json(response)
    except HTTPError as exc:
        raise NextcloudError(f"Nextcloud antwortet mit HTTP {exc.code}.") from exc
    except OSError as exc:
        raise NextcloudError("Nextcloud ist nicht erreichbar.") from exc

    try:
        login_url = str(payload["login"])
        poll_token = str(payload["poll"]["token"])
        poll_endpoint = str(payload["poll"]["endpoint"])
    except (KeyError, TypeError) as exc:
        raise NextcloudError("Die Adresse ist keine Nextcloud (Login Flow v2 fehlt).") from exc

    # The poll endpoint must live on the same server we were asked to contact.
    if urlparse(poll_endpoint).hostname != urlparse(base).hostname:
        raise NextcloudError("Nextcloud lieferte eine unerwartete Poll-Adresse.")
    require_public_https_url(poll_endpoint)
    return {"login_url": login_url, "poll_endpoint": poll_endpoint, "poll_token": poll_token, "base_url": base}


def poll_login_flow(poll_endpoint: str, poll_token: str) -> dict[str, str] | None:
    """Poll once. None while the teacher has not finished; credentials when done.

    Nextcloud hands the credentials out exactly once.
    """
    request = Request(
        require_public_https_url(poll_endpoint),
        method="POST",
        data=urlencode({"token": poll_token}).encode("ascii"),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with _open(request) as response:
            payload = _read_json(response)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise NextcloudError(f"Nextcloud antwortet mit HTTP {exc.code}.") from exc
    except OSError as exc:
        raise NextcloudError("Nextcloud ist nicht erreichbar.") from exc

    try:
        return {
            "server": require_public_https_url(str(payload["server"])),
            "login_name": str(payload["loginName"]),
            "app_password": str(payload["appPassword"]),
        }
    except (KeyError, TypeError) as exc:
        raise NextcloudError("Unerwartete Antwort von Nextcloud.") from exc


def revoke_app_password(server: str, login_name: str, app_password: str) -> bool:
    """Delete the app password in Nextcloud. Best effort: returns False on failure."""
    try:
        request = Request(
            require_public_https_url(server) + "/ocs/v2.php/core/apppassword",
            method="DELETE",
            headers=_auth_headers(login_name, app_password),
        )
        with _open(request) as response:
            return 200 <= response.status < 300
    except (HTTPError, OSError, ValueError):
        return False


def _ocs_get(server: str, login_name: str, app_password: str, path: str, params: dict[str, Any]) -> list[dict]:
    query = urlencode({**params, "format": "json"})
    request = Request(
        require_public_https_url(server) + path + "?" + query,
        headers=_auth_headers(login_name, app_password),
    )
    try:
        with _open(request) as response:
            if response.status in (204, 304):
                return []
            payload = _read_json(response)
    except HTTPError as exc:
        if exc.code in (204, 304):
            return []
        if exc.code == 401:
            raise NextcloudAuthError("Der Nextcloud-Zugang wurde widerrufen.") from exc
        if exc.code == 404:
            return []  # app (activity/notifications) not installed
        raise NextcloudError(f"Nextcloud antwortet mit HTTP {exc.code}.") from exc
    except OSError as exc:
        raise NextcloudError("Nextcloud ist nicht erreichbar.") from exc
    data = ((payload or {}).get("ocs") or {}).get("data")
    return data if isinstance(data, list) else []


def fetch_activity(server: str, login_name: str, app_password: str, *, limit: int = 30) -> list[dict[str, Any]]:
    """Recent activities by other people (changed/shared files, comments …)."""
    items = _ocs_get(server, login_name, app_password,
                     "/ocs/v2.php/apps/activity/api/v2/activity/by", {"limit": limit})
    return [normalize_activity(item) for item in items if isinstance(item, dict)]


def fetch_notifications(server: str, login_name: str, app_password: str) -> list[dict[str, Any]]:
    """Open Nextcloud notifications (mentions, shares, Talk, Deck, reminders …)."""
    items = _ocs_get(server, login_name, app_password,
                     "/ocs/v2.php/apps/notifications/api/v2/notifications", {})
    return [normalize_notification(item) for item in items if isinstance(item, dict)]


_ACTIVITY_KINDS = {
    "file_created": "neu",
    "file_changed": "geändert",
    "file_deleted": "gelöscht",
    "file_restored": "wiederhergestellt",
    "shared": "geteilt",
    "remote_share": "geteilt",
    "public_links": "geteilt",
    "comments": "Kommentar",
    "calendar": "Kalender",
    "calendar_event": "Kalender",
    "calendar_todo": "Aufgabe",
}


def _iso(value: Any) -> str:
    text = str(value or "")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return text


def normalize_activity(item: dict[str, Any]) -> dict[str, Any]:
    kind = str(item.get("type") or "")
    return {
        "id": f"nextcloud-activity-{item.get('activity_id')}",
        "activity_id": item.get("activity_id"),
        "time": _iso(item.get("datetime")),
        "app": str(item.get("app") or ""),
        "type": kind,
        "label": _ACTIVITY_KINDS.get(kind, ""),
        "subject": str(item.get("subject") or "").strip(),
        "object_name": str(item.get("object_name") or "").strip(),
        "link": str(item.get("link") or ""),
        "user": str(item.get("user") or ""),
    }


def normalize_notification(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"nextcloud-notification-{item.get('notification_id')}",
        "time": _iso(item.get("datetime")),
        "app": str(item.get("app") or ""),
        "subject": str(item.get("subject") or "").strip(),
        "message": str(item.get("message") or "").strip()[:280],
        "link": str(item.get("link") or ""),
    }
