"""Nextcloud module for the v2 API: connection state and "what is new" data.

Config keys in user_module_configs["nextcloud"]:
  base_url            school Nextcloud chosen by the teacher
  login_name          account name returned by Login Flow v2
  app_password        dedicated app password (encrypted at rest)
  connected_at        ISO timestamp
  pending_base_url / pending_poll_endpoint / pending_poll_token / pending_started_at
                      an unfinished Login Flow v2 (token encrypted at rest)
"""
from __future__ import annotations

import threading
import time as _time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from .http_utils import UnsafeUrlError
from .nextcloud_client import (
    NextcloudAuthError,
    NextcloudError,
    fetch_activity,
    fetch_notifications,
)

LOGIN_FLOW_TTL = timedelta(minutes=20)  # Nextcloud poll tokens expire after 20 minutes
_CACHE_SECONDS = 120
_ACTIVITY_LIMIT = 30

_cache_lock = threading.Lock()
_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}

PENDING_KEYS = ("pending_base_url", "pending_poll_endpoint", "pending_poll_token", "pending_started_at")
CREDENTIAL_KEYS = ("login_name", "app_password", "connected_at")


def origin(url: str) -> str:
    """https://host of an address, or '' if it is not an https URL."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https" or not parsed.netloc:
        return ""
    return f"https://{parsed.netloc}"


def suggested_server(settings: dict[str, Any]) -> str:
    """School Nextcloud to prefill: explicit setting, else derived from known Nextcloud links."""
    for key in ("nextcloud_url", "nextcloud_workspace_url", "fehlzeiten_11_url", "fehlzeiten_12_url"):
        value = settings.get(key)
        if isinstance(value, str) and origin(value):
            return origin(value)
    return ""


def is_connected(config: dict[str, Any] | None) -> bool:
    config = config or {}
    return bool(config.get("login_name") and config.get("app_password") and config.get("base_url"))


def pending_flow(config: dict[str, Any] | None, now: datetime) -> dict[str, str] | None:
    """The unfinished login flow, or None if there is none or it expired."""
    config = config or {}
    endpoint = config.get("pending_poll_endpoint")
    token = config.get("pending_poll_token")
    started = config.get("pending_started_at")
    if not (endpoint and token and started):
        return None
    try:
        started_at = datetime.fromisoformat(str(started))
    except ValueError:
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if now - started_at > LOGIN_FLOW_TTL:
        return None
    return {"poll_endpoint": str(endpoint), "poll_token": str(token)}


def status(config: dict[str, Any] | None, settings: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Connection status for the Verbindungen dialog (no secrets)."""
    config = config or {}
    return {
        "connected": is_connected(config),
        "account": config.get("login_name", "") if is_connected(config) else "",
        "server": config.get("base_url", ""),
        "suggested_server": config.get("base_url") or suggested_server(settings),
        "pending": pending_flow(config, now) is not None,
    }


def build_nextcloud_payload(config: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    """Module result dict for /api/v2/dashboard/data."""
    config = config or {}
    if not is_connected(config):
        return {"ok": True, "data": None, "configured": False}

    server = str(config["base_url"])
    login_name = str(config["login_name"])
    cache_key = (server, login_name)
    with _cache_lock:
        hit = _cache.get(cache_key)
        if hit and _time.monotonic() - hit[0] < _CACHE_SECONDS:
            return {"ok": True, "data": hit[1], "configured": True}

    data: dict[str, Any] = {
        "connected": True,
        "account": login_name,
        "server": server,
        "activity": [],
        "notifications": [],
        "revoked": False,
        "error": None,
        "fetched_at": now.isoformat(),
    }
    try:
        data["activity"] = fetch_activity(server, login_name, str(config["app_password"]), limit=_ACTIVITY_LIMIT)
        data["notifications"] = fetch_notifications(server, login_name, str(config["app_password"]))
    except NextcloudAuthError:
        data["revoked"] = True
        data["error"] = "Der Zugang wurde in Nextcloud widerrufen. Bitte unter „Verbindungen“ neu verbinden."
    except (NextcloudError, UnsafeUrlError) as exc:
        data["error"] = str(exc)

    if not data["error"]:
        with _cache_lock:
            _cache[cache_key] = (_time.monotonic(), data)
    return {"ok": True, "data": data, "configured": True}


def forget_cached(config: dict[str, Any] | None) -> None:
    config = config or {}
    with _cache_lock:
        _cache.pop((str(config.get("base_url", "")), str(config.get("login_name", ""))), None)
