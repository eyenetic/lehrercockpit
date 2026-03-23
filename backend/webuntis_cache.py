from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


def load_webuntis_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_payload()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_payload()

    events = [item for item in payload.get("events", []) if isinstance(item, dict)]
    schedule = [item for item in payload.get("schedule", []) if isinstance(item, dict)]
    priorities = [item for item in payload.get("priorities", []) if isinstance(item, dict)]

    return {
        "status": "ok" if events else "empty",
        "detail": payload.get("detail", ""),
        "updatedAt": payload.get("updatedAt", ""),
        "savedAt": payload.get("savedAt", ""),
        "events": events,
        "schedule": schedule,
        "priorities": priorities,
    }


def save_webuntis_cache(path: Path, *, events: list[dict[str, Any]], schedule: list[dict[str, Any]], priorities: list[dict[str, Any]], detail: str) -> None:
    now = datetime.now().astimezone()
    payload = {
        "updatedAt": now.strftime("%H:%M"),
        "savedAt": now.isoformat(),
        "detail": detail,
        "events": events,
        "schedule": schedule,
        "priorities": priorities,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def cache_is_recent(payload: dict[str, Any], *, max_hours: int = 24) -> bool:
    saved_at = str(payload.get("savedAt", "")).strip()
    if not saved_at:
        return False

    try:
        saved = datetime.fromisoformat(saved_at)
    except ValueError:
        return False

    age_seconds = (datetime.now().astimezone() - saved).total_seconds()
    return age_seconds <= max_hours * 3600


def _empty_payload() -> dict[str, Any]:
    return {
        "status": "empty",
        "detail": "",
        "updatedAt": "",
        "savedAt": "",
        "events": [],
        "schedule": [],
        "priorities": [],
    }
