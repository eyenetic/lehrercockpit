"""Klassenarbeitsplan cache store.

Reads and writes classwork cache data via the shared persistence abstraction
(``backend.persistence.store``).  When ``DATABASE_URL`` is set the data lives
in PostgreSQL; otherwise it falls back to a local JSON file.

Public interface (unchanged for callers)
-----------------------------------------
- ``load_cache(path)``              → dict
- ``save_cache(path, result)``      → None
- ``get_previous_hash(path)``       → str
- ``cache_age_minutes(path)``       → float | None
- ``_empty_cache()``                → dict  (exported for tests)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .persistence import store


def load_cache(cache_path: Path) -> dict[str, Any]:
    """Load cached classwork data, or return an empty placeholder."""
    result = store.read(cache_path, default=None)
    if isinstance(result, dict):
        return result
    return _empty_cache()


def save_cache(cache_path: Path, result: dict[str, Any]) -> None:
    """Persist classwork cache data."""
    store.write(cache_path, result)


def get_previous_hash(cache_path: Path) -> str:
    """Return the ``dataHash`` of the last cached result, or empty string."""
    data = store.read(cache_path, default=None)
    if isinstance(data, dict):
        return data.get("dataHash", "")
    return ""


def cache_age_minutes(cache_path: Path) -> float | None:
    """Return how many minutes ago the cache was last written, or None if absent."""
    ts = store.mtime(cache_path)
    if ts is not None:
        return (datetime.now().timestamp() - ts) / 60
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
