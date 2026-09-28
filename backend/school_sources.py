"""School-wide sources: one setting per source and their status for "Verbindungen".

  Orgaplan            system_settings "orgaplan_source" (backend/orgaplan.py)
  Klassenarbeitsplan  system_settings "klassenarbeitsplan_url" (OneDrive file or folder link)
  Schultermine        system_settings "wichtige_termine_ical_url" (backend/school_calendar.py)

Admins edit them; every teacher sees their status.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .admin.admin_service import get_system_setting

CLASSWORK_KEY = "klassenarbeitsplan_url"
LEGACY_CLASSWORK_KEY = "classwork_url"
CLASSWORK_CANDIDATE_KEY = "klassenarbeitsplan_url_candidate"


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def classwork_url(conn) -> str:
    return _text(get_system_setting(conn, CLASSWORK_KEY, "")) or _text(get_system_setting(conn, LEGACY_CLASSWORK_KEY, ""))


def migrate_legacy_settings(conn) -> None:
    """One key per source. Idempotent; runs at startup.

    Klassenarbeitsplan: the cockpit always used "klassenarbeitsplan_url" first,
    so it stays. A different link from the admin form ("classwork_url") is kept
    as a candidate that admins can adopt with one click under "Verbindungen".
    """
    from .admin.admin_service import set_system_setting

    current = _text(get_system_setting(conn, CLASSWORK_KEY, ""))
    legacy = _text(get_system_setting(conn, LEGACY_CLASSWORK_KEY, ""))
    if legacy:
        if not current:
            set_system_setting(conn, CLASSWORK_KEY, legacy)
        elif legacy != current:
            set_system_setting(conn, CLASSWORK_CANDIDATE_KEY, legacy)
    conn.execute("DELETE FROM system_settings WHERE key = %s", (LEGACY_CLASSWORK_KEY,))

    if get_system_setting(conn, "orgaplan_source", None) is None:
        from .orgaplan import load_source

        set_system_setting(conn, "orgaplan_source", load_source(conn))
    # The old digest cache is replaced by the orgaplan state.
    conn.execute("DELETE FROM system_settings WHERE key IN ('orgaplan_cache', 'orgaplan_cache_ts', 'orgaplan_cache_url')")


# ── Status for "Verbindungen" ────────────────────────────────────────────────
# Settings are read inside a db_connection(); the status builders below read the
# persistence store with their own connections, so call them after it closed.

def load_settings(conn) -> dict[str, Any]:
    from .orgaplan import load_source
    from .school_calendar import feed_url

    return {
        "orgaplan_source": load_source(conn),
        "classwork_url": classwork_url(conn),
        "classwork_candidate": _text(get_system_setting(conn, CLASSWORK_CANDIDATE_KEY, "")),
        "calendar_url": feed_url(conn),
    }


def orgaplan_status(source: dict[str, str], is_admin: bool, now: datetime | None = None) -> dict[str, Any]:
    from . import orgaplan

    state = orgaplan.load_state()
    digest = orgaplan.build_digest(state, source, now or datetime.now(timezone.utc))
    return {
        "mode": source["mode"],
        "site": source.get("site", ""),
        "query": source.get("query", ""),
        "pdf_url": source.get("pdf_url", ""),
        "current_url": digest["sourceUrl"],
        "name": digest["sourceName"],
        "school_year": digest["schoolYear"],
        "stand": digest["stand"],
        "published_at": digest["publishedAt"],
        "checked_at": digest["checkedAt"],
        "status": digest["status"],
        "detail": digest["detail"],
        "error": digest["error"],
        "entries": len(state.get("entries") or []),
        "can_edit": bool(is_admin),
    }


def classwork_status(url: str, candidate: str, is_admin: bool, now: datetime | None = None) -> dict[str, Any]:
    """Link, last update, sync health and whether the stored plan is outdated.

    Reads the plan cache through the persistence store (own connections), so
    call it outside an open db_connection() transaction.
    """
    from .classwork_cache import load_cache
    from .classwork_sync import CACHE_PATH, plan_view, sync_info
    from .onedrive_share import is_onedrive_link

    try:
        cached = load_cache(CACHE_PATH)
        view = plan_view(cached, now) if cached.get("status") in ("ok", "outdated") else {}
        sync = sync_info(url, now)
    except Exception:
        cached, view, sync = {}, {}, {}
    return {
        "url": url,
        "onedrive": is_onedrive_link(url),
        "sync": sync,
        "uploaded_at": cached.get("uploadedAt", ""),
        "upload_source": cached.get("uploadSource", ""),
        "uploaded_by": cached.get("uploadedBy", ""),
        "plan": view.get("planStatus") or {},
        "candidate_url": candidate if is_admin else "",
        "can_edit": bool(is_admin),
    }


def calendar_status(url: str, is_admin: bool, now: datetime | None = None) -> dict[str, Any]:
    from .school_calendar import build_calendar, default_feed

    result = build_calendar(url, now)
    data = result.get("data") or {}
    return {
        "url": url,
        "is_default": url == default_feed(),
        "ok": bool(result.get("ok")),
        "error": data.get("error"),
        "upcoming": len(data.get("events") or []),
        "can_edit": bool(is_admin),
    }
