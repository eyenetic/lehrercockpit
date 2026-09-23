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

import threading
from datetime import datetime, timedelta, timezone
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
            "sourceETag": meta.get("etag", ""),
            "sourceModified": meta.get("modified", ""),
        })
    save_cache(CACHE_PATH, result)
    return result


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
        "last_success": state.get("last_success"),
        "last_result": state.get("last_result"),
        "last_error": state.get("last_error"),
        "via": state.get("via"),
        "needs_browser": bool(stale and server_failed),
    }
