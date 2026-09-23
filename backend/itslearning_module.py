"""itslearning module data for the v2 API.

Two independent sources, both optional:
- calendar subscription (iCal link from itslearning → Kalender → Abonnieren):
  official, needs no password, delivers dates and deadlines.
- update feed via the stored login (HTML scraping, see itslearning_adapter).
"""
from __future__ import annotations

import dataclasses
import hashlib
import threading
import time as _time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from .http_utils import UnsafeUrlError, require_public_https_url
from .ical_utils import BERLIN, CalendarEntry, entries_between, fetch_calendar_text, parse_calendar

DEFAULT_BASE_URL = "https://berlin.itslearning.com"
CALENDAR_DAYS_AHEAD = 21
_CALENDAR_CACHE_SECONDS = 600

_cache_lock = threading.Lock()
_calendar_cache: dict[str, tuple[float, list[CalendarEntry]]] = {}


def is_configured(config: dict | None) -> bool:
    config = config or {}
    has_login = bool(config.get("username") and config.get("password"))
    return bool(config.get("calendar_url")) or has_login


def build_itslearning_payload(config: dict | None, now: datetime) -> dict[str, Any]:
    """Module result dict in the shape used by /api/v2/dashboard/data."""
    config = config or {}
    calendar_url = str(config.get("calendar_url") or "").strip()
    username = str(config.get("username") or "").strip()
    password = str(config.get("password") or "")
    # Onboarding stored the address as server_url; the adapter expects base_url.
    base_url = _origin(str(config.get("base_url") or config.get("server_url") or "")) or DEFAULT_BASE_URL

    if not calendar_url and not (username and password):
        return {"ok": True, "data": None, "configured": False, "error": "itslearning nicht konfiguriert"}

    if username and password:
        from .config import ItslearningSettings
        from .itslearning_adapter import fetch_itslearning_sync

        settings = ItslearningSettings(
            base_url=base_url,
            username=username,
            password=password,
            max_updates=int(config.get("max_updates", 6)),
        )
        data = dataclasses.asdict(fetch_itslearning_sync(settings, now))
    else:
        data = {
            "source": {
                "id": "itslearning",
                "name": "itslearning",
                "type": "Kalender",
                "status": "ok",
                "cadence": "Kalender-Abo",
                "lastSync": now.astimezone(BERLIN).strftime("%H:%M"),
                "nextStep": "",
                "detail": "Termine und Abgaben kommen über das Kalender-Abo aus itslearning.",
            },
            "messages": [],
            "priorities": [],
            "mode": "calendar",
            "note": "",
        }

    if calendar_url:
        data["calendar"] = fetch_itslearning_calendar(calendar_url, now)
    return {"ok": True, "data": data, "configured": True}


def _origin(url: str) -> str:
    """scheme://host of a typed address ('' if it is not an https URL)."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        return ""
    return f"https://{parsed.netloc}"


def fetch_itslearning_calendar(url: str, now: datetime) -> dict[str, Any]:
    """Upcoming calendar entries (today .. +21 days) from an itslearning iCal link."""
    try:
        entries = _cached_entries(require_public_https_url(url))
    except UnsafeUrlError as exc:
        return {"ok": False, "events": [], "error": str(exc)}
    except Exception as exc:  # network, HTTP or parse errors
        return {"ok": False, "events": [], "error": f"Kalender konnte nicht geladen werden ({type(exc).__name__})."}

    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    day_start = current.astimezone(BERLIN).replace(hour=0, minute=0, second=0, microsecond=0)
    window = entries_between(entries, day_start, day_start + timedelta(days=CALENDAR_DAYS_AHEAD))
    return {
        "ok": True,
        "events": [_event_dict(entry) for entry in window if entry.status != "CANCELLED"],
        "error": None,
        "fetched_at": current.isoformat(),
    }


def _cached_entries(url: str) -> list[CalendarEntry]:
    with _cache_lock:
        hit = _calendar_cache.get(url)
        if hit and _time.monotonic() - hit[0] < _CALENDAR_CACHE_SECONDS:
            return hit[1]
    entries = parse_calendar(fetch_calendar_text(url))
    with _cache_lock:
        _calendar_cache[url] = (_time.monotonic(), entries)
    return entries


def _event_dict(entry: CalendarEntry) -> dict[str, Any]:
    key = entry.uid or f"{entry.title}|{entry.start.isoformat()}"
    return {
        "id": "itslearning-cal-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12],
        "kind": entry.kind,
        "title": entry.title,
        "start": entry.start.isoformat(),
        "end": entry.end.isoformat() if entry.end else None,
        "allDay": entry.all_day,
        "location": entry.location,
        "url": entry.url,
        "detail": entry.description[:280],
    }
