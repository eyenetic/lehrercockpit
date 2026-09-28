"""School calendar: events from the school website's iCal feed ("Schultermine").

Same result shape as the former wichtige_termine_adapter (today_events,
upcoming_events with uid/title/start/end/all_day/time_label/location), plus
"events" for the next weeks. Times are Europe/Berlin (backend/ical_utils.py).
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .http_utils import UnsafeUrlError, require_public_https_url
from .ical_utils import BERLIN, entries_between, fetch_calendar_text, parse_calendar

SETTING_KEY = "wichtige_termine_ical_url"
UPCOMING_DAYS = 42
CACHE_SECONDS = 30 * 60

_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, list]] = {}


def default_feed() -> str:
    from .config import SCHOOL_WEBSITE_DEFAULT

    return SCHOOL_WEBSITE_DEFAULT.rstrip("/") + "/events/liste/?ical=1"


def feed_url(conn) -> str:
    from .admin.admin_service import get_system_setting

    value = get_system_setting(conn, SETTING_KEY, "")
    return value.strip() if isinstance(value, str) and value.strip() else default_feed()


def _entries(url: str, *, force: bool = False) -> list:
    with _cache_lock:
        hit = _cache.get(url)
    if hit and not force and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    entries = parse_calendar(fetch_calendar_text(require_public_https_url(url)))
    with _cache_lock:
        _cache[url] = (time.monotonic(), entries)
    return entries


def _serialize(entry, today: date) -> dict[str, Any]:
    start = entry.start.astimezone(BERLIN)
    end = entry.end.astimezone(BERLIN) if entry.end else None  # all-day: inclusive (ical_utils)
    time_label = None
    if not entry.all_day:
        time_label = start.strftime("%H:%M") + (f"–{end:%H:%M}" if end and end.date() == start.date() else "")
    return {
        "uid": entry.uid,
        "title": entry.title or "(ohne Titel)",
        "start": start.date().isoformat() if entry.all_day else start.isoformat(),
        "end": (end.date().isoformat() if entry.all_day else end.isoformat()) if end else None,
        "all_day": entry.all_day,
        "time_label": time_label,
        "location": entry.location or None,
        "description": (entry.description or "")[:500] or None,
        "url": entry.url or None,
        "running": start.date() < today,  # multi-day event that started before today
    }


def build_calendar(url: str, now: datetime | None = None, *, force: bool = False) -> dict[str, Any]:
    """Module result for the dashboard: {"ok", "data": {...}}; never raises."""
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(BERLIN).date()
    try:
        entries = _entries(url, force=force)
    except UnsafeUrlError as exc:
        return {"ok": False, "data": {"mode": "error", "error": str(exc), "today_events": [],
                                      "upcoming_events": [], "events": [], "feed_url": url}}
    except Exception as exc:
        return {"ok": False, "data": {"mode": "error", "error": f"Schulkalender nicht erreichbar ({type(exc).__name__}).",
                                      "today_events": [], "upcoming_events": [], "events": [], "feed_url": url}}

    day_start = datetime(today.year, today.month, today.day, tzinfo=BERLIN)
    window = entries_between(entries, day_start, day_start + timedelta(days=UPCOMING_DAYS))
    today_iso = today.isoformat()
    events = [e for e in (_serialize(entry, today) for entry in window)
              if (e["end"] or e["start"])[:10] >= today_iso]  # drop all-day events that ended yesterday
    tomorrow_iso = (today + timedelta(days=1)).isoformat()
    todays = [e for e in events if e["start"][:10] <= today_iso and (e["end"] or e["start"])[:10] >= today_iso]
    upcoming = [e for e in events if e["start"][:10] >= tomorrow_iso][:40]
    return {"ok": True, "data": {
        "mode": "live",
        "error": None,
        "today_events": todays,
        "upcoming_events": [e for e in upcoming if e["start"][:10] <= (today + timedelta(days=14)).isoformat()],
        "events": events[:60],
        "feed_url": url,
        "fetched_at": now.isoformat(),
    }}
