"""Keep the school's Klassenarbeitsplan fresh from its OneDrive sharing link.

The plan stays on OneDrive. The server tries to fetch it itself (at most once
per SERVER_INTERVAL, in a background thread). If Microsoft refuses the server,
sync_info() tells the teachers' browsers to fetch it instead
(src/features/onedrive-sync.js), which then post the file to the API.

Sync state lives in the persistence store under "classwork-sync":
  source_url, etag, modified, name, last_attempt, last_result
  ("ok" | "unchanged" | "blocked" | "error"), last_error, last_success, via
"""
from __future__ import annotations

import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .classwork_cache import load_cache, save_cache
from .ical_utils import BERLIN
from .onedrive_share import OneDriveBlocked, OneDriveError, download, is_onedrive_link, resolve
from .persistence import store

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_PATH = DATA_DIR / "classwork-cache.json"
STATE_PATH = DATA_DIR / "classwork-sync.json"

SERVER_INTERVAL = timedelta(hours=1)
# Browsers step in when the server could not confirm the plan for this long.
BROWSER_AFTER = timedelta(hours=3)

_sync_lock = threading.Lock()
_sync_running = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_state() -> dict[str, Any]:
    state = store.read(STATE_PATH, default=None)
    return state if isinstance(state, dict) else {}


def save_state(state: dict[str, Any]) -> None:
    store.write(STATE_PATH, state)


def store_plan(file_bytes: bytes, *, source: str, uploaded_by: str = "",
               meta: dict[str, Any] | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Parse a plan file and make it the current Klassenarbeitsplan.

    Raises ValueError when the file cannot be read as a plan.
    """
    from .file_utils import parse_classwork_xlsx

    now = now or _now()
    result = parse_classwork_xlsx(file_bytes)
    previous = load_cache(CACHE_PATH)
    local = now.astimezone(BERLIN)
    result.update({
        "uploadedAt": local.strftime("%d.%m.%Y %H:%M"),
        "updatedAt": local.strftime("%d.%m.%Y um %H:%M"),
        "uploadSource": source,
        "uploadedBy": uploaded_by,
        "hasChanges": bool(previous.get("dataHash")) and previous.get("dataHash") != result.get("dataHash"),
    })
    if meta:
        result.update({
            "sourceName": meta.get("name", ""),
            "sourceFolder": meta.get("folder", ""),
            "sourceETag": meta.get("etag", ""),
            "sourceModified": meta.get("modified", ""),
        })
    save_cache(CACHE_PATH, result)
    return result


# ── How the stored plan is shown today ───────────────────────────────────────

_SCHOOL_YEAR_IN_NAME = re.compile(r"(20\d{2})\s*[_/-]\s*(20\d{2}|\d{2})")


def current_school_year(today: date) -> int:
    """Start year of the school year containing `today` (a school year starts on 1 August)."""
    return today.year if today.month >= 8 else today.year - 1


def school_year_from_name(name: str) -> int | None:
    """"Klassenarbeitsplan_2025_2026.xlsx" → 2025."""
    for match in _SCHOOL_YEAR_IN_NAME.finditer(name or ""):
        start, end = int(match.group(1)), match.group(2)
        end_year = int(end) if len(end) == 4 else 2000 + int(end)
        if end_year == start + 1:
            return start
    return None


def _school_year_label(start: int) -> str:
    return f"{start}/{(start + 1) % 100:02d}"


def _de_date(iso: str) -> str:
    try:
        return date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return iso


def plan_view(cache: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """The stored plan as it should be shown today.

    Only entries from today on; "planStatus" says whether the plan is outdated
    (typically: the link still points to last school year's file).
    """
    now = now or _now()
    today = now.astimezone(BERLIN).date()
    today_iso = today.isoformat()
    entries = [e for e in cache.get("entries") or [] if isinstance(e, dict) and e.get("isoDate")]
    upcoming = [e for e in entries if e["isoDate"] >= today_iso]
    last_date = max((e["isoDate"] for e in entries), default="")
    first_date = min((e["isoDate"] for e in entries), default="")
    name = str(cache.get("sourceName") or "")
    name_year = school_year_from_name(name)
    if name_year is None and first_date:
        name_year = current_school_year(date.fromisoformat(first_date))

    if not entries:
        state, message = "empty", "Im Plan wurden keine Klassenarbeiten erkannt."
    elif not upcoming:
        state = "outdated"
        if name_year is not None and name_year < current_school_year(today):
            message = (f"Der hinterlegte Plan{f' „{name}“' if name else ''} ist vom Schuljahr "
                       f"{_school_year_label(name_year)} und enthält keine kommenden Termine "
                       f"(letzter Eintrag: {_de_date(last_date)}).")
        else:
            message = (f"Der Plan enthält keine kommenden Termine (letzter Eintrag: {_de_date(last_date)}). "
                       "Vermutlich gibt es inzwischen eine neue Datei.")
    else:
        state, message = "ok", ""

    classes = sorted({e.get("classLabel", "") for e in upcoming} - {""}, key=_class_key)
    view = dict(cache)
    view.update({
        "entries": upcoming,
        "classes": classes,
        "previewRows": [f"{e.get('classLabel')} | {e.get('dateLabel')} | {e.get('title')}" for e in upcoming[:8]],
        "planStatus": {
            "state": state,
            "message": message,
            "upcomingCount": len(upcoming),
            "firstDate": first_date,
            "lastDate": last_date,
            "schoolYear": _school_year_label(name_year) if name_year is not None else "",
            "fileName": name,
            "folder": str(cache.get("sourceFolder") or ""),
            "fileModified": str(cache.get("sourceModified") or ""),
            "storedAt": str(cache.get("uploadedAt") or ""),
            "source": str(cache.get("uploadSource") or ""),
        },
    })
    if state == "outdated":
        view["status"] = "outdated"
        view["detail"] = message
    return view


def _class_key(label: str) -> tuple[int, str]:
    match = re.match(r"^(\d{1,2})([A-Z])$", label.upper())
    if match:
        return int(match.group(1)), match.group(2)
    return 100, label.upper()


def _record(state: dict[str, Any], *, url: str, now: datetime, result: str,
            via: str, error: str | None = None, meta: dict[str, Any] | None = None) -> None:
    state.update({"source_url": url, "last_attempt": now.isoformat(), "last_result": result,
                  "last_error": error})
    if result in ("ok", "unchanged"):
        state.update({"last_success": now.isoformat(), "via": via})
    if meta:
        state.update({"etag": meta.get("etag", ""), "modified": meta.get("modified", ""),
                      "name": meta.get("name", "")})
    save_state(state)


def sync_from_server(url: str, now: datetime | None = None) -> str:
    """Fetch the plan server-side. Returns the result code; never raises."""
    now = now or _now()
    state = load_state()
    try:
        meta = resolve(url)
        cached = load_cache(CACHE_PATH)
        unchanged = (
            state.get("source_url") == url
            and meta.get("etag")
            and meta["etag"] == state.get("etag")
            and cached.get("status") == "ok"
        )
        if unchanged:
            _record(state, url=url, now=now, result="unchanged", via="server", meta=meta)
            return "unchanged"
        data, meta = download(url)
        store_plan(data, source="onedrive", meta=meta, now=now)
        _record(state, url=url, now=now, result="ok", via="server", meta=meta)
        return "ok"
    except OneDriveBlocked as exc:
        _record(state, url=url, now=now, result="blocked", via="server", error=str(exc))
        return "blocked"
    except (OneDriveError, ValueError) as exc:
        _record(state, url=url, now=now, result="error", via="server", error=str(exc))
        return "error"


def maybe_sync_in_background(url: str, now: datetime | None = None) -> bool:
    """Start a server-side sync if due. Returns True if one was started."""
    global _sync_running
    if not is_onedrive_link(url):
        return False
    now = now or _now()
    state = load_state()
    last_attempt = _parse_time(state.get("last_attempt"))
    if state.get("source_url") == url and last_attempt and now - last_attempt < SERVER_INTERVAL:
        return False
    with _sync_lock:
        if _sync_running:
            return False
        _sync_running = True

    def _run() -> None:
        global _sync_running
        try:
            sync_from_server(url)
        finally:
            with _sync_lock:
                _sync_running = False

    threading.Thread(target=_run, name="classwork-onedrive-sync", daemon=True).start()
    return True


def record_browser_result(url: str, meta: dict[str, Any], *, changed: bool, now: datetime | None = None) -> None:
    """A teacher's browser fetched (changed) or confirmed (unchanged) the plan."""
    _record(load_state(), url=url, now=now or _now(), result="ok" if changed else "unchanged",
            via="browser", meta=meta)


def sync_info(url: str, now: datetime | None = None) -> dict[str, Any]:
    """What the frontend needs to decide whether a browser fetch is required."""
    now = now or _now()
    if not is_onedrive_link(url):
        return {"onedrive": False, "needs_browser": False}
    state = load_state()
    if state.get("source_url") != url:
        state = {}  # link changed: nothing known about the new one yet
    last_success = _parse_time(state.get("last_success"))
    stale = last_success is None or now - last_success > BROWSER_AFTER
    server_failed = state.get("last_result") in ("blocked", "error")
    return {
        "onedrive": True,
        "etag": state.get("etag", ""),
        "name": state.get("name", ""),
        "modified": state.get("modified", ""),
        "last_attempt": state.get("last_attempt"),
        "last_success": state.get("last_success"),
        "last_result": state.get("last_result"),
        "last_error": state.get("last_error"),
        "via": state.get("via"),
        "needs_browser": bool(stale and server_failed),
    }
