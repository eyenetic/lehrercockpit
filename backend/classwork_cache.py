"""Persistent JSON cache for scraped Klassenarbeitsplan data with diff support."""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


_lock = threading.Lock()


def load_cache(cache_path: Path) -> dict[str, Any]:
    """Load cached classwork data from disk, or return empty placeholder."""
    try:
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return _empty_cache()


def save_cache(cache_path: Path, result: dict[str, Any]) -> None:
    """Persist scrape result to disk atomically."""
    with _lock:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = cache_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(cache_path)
        except Exception as exc:
            print(f"[classwork_cache] Failed to save cache: {exc}")


def get_previous_hash(cache_path: Path) -> str:
    """Return the dataHash of the last cached result, or empty string."""
    try:
        if cache_path.exists():
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return data.get("dataHash", "")
    except Exception:
        pass
    return ""


def cache_age_minutes(cache_path: Path) -> float | None:
    """Return how many minutes ago the cache was last written, or None if missing."""
    try:
        if cache_path.exists():
            mtime = cache_path.stat().st_mtime
            return (datetime.now().timestamp() - mtime) / 60
    except Exception:
        pass
    return None


def _empty_cache() -> dict[str, Any]:
    return {
        "status": "pending",
        "title": "Klassenarbeitsplan",
        "detail": "Noch kein Upload. Klicke auf '📂 Hochladen', um eine XLS/XLSX-Datei einzulesen.",
        "updatedAt": "--:--",
        "scrapedAt": None,
        "previewRows": [],
        "structuredRows": [],
        "sourceUrl": "",
        "scrapeMode": "upload",
        "dataHash": "",
        "hasChanges": False,
        "noChanges": False,
    }
