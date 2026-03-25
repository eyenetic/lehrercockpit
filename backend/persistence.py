"""Persistence abstraction for JSON-backed local stores.

All grades, notes, and classwork cache data is currently stored as JSON files
on the local filesystem.  This module centralises read/write so that a future
DB-backed store (e.g. PostgreSQL via DATABASE_URL) can be dropped in by
replacing ``JsonFileStore`` with an alternative implementation.

Usage
-----
    from backend.persistence import store

    data = store.read(path, default={})
    store.write(path, data)

Production note
---------------
On Render's free tier the filesystem is **ephemeral** — all writes to
``data/*.json`` are lost when the dyno restarts or is swapped.  This is
acceptable for the current development phase, but means that any data saved
via the API (grades, notes, classwork uploads) will not survive a redeploy.

To make persistence durable, replace ``JsonFileStore`` with a ``DbStore``
that reads/writes from a Postgres database using ``DATABASE_URL``.  The
calling code in ``grades_store.py``, ``notes_store.py``, and
``classwork_cache.py`` does not need to change because they all call
``store.read()`` / ``store.write()``.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

# True when running on Render (Render always sets IS_RENDER or RENDER_SERVICE_ID)
IS_RENDER = bool(
    os.environ.get("RENDER")
    or os.environ.get("RENDER_SERVICE_ID")
    or os.environ.get("IS_RENDER")
)


class JsonFileStore:
    """Atomic JSON file read/write with a threading lock per instance."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def read(self, path: Path, *, default: Any = None) -> Any:
        """Read and parse JSON from *path*.

        Returns *default* (``None`` unless overridden) when the file does not
        exist or is unreadable.
        """
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[persistence] read failed ({path}): {exc}", flush=True)
        return default

    def write(self, path: Path, data: Any) -> None:
        """Write *data* as JSON to *path* atomically (tmp → rename).

        Creates parent directories as needed.  Logs a warning on Render where
        writes are ephemeral.
        """
        if IS_RENDER:
            print(
                f"[persistence] WARNING: writing to {path} on Render — "
                "this file is ephemeral and will be lost on the next redeploy or restart.",
                flush=True,
            )
        with self._lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                tmp.replace(path)
            except Exception as exc:
                print(f"[persistence] write failed ({path}): {exc}", flush=True)
                raise

    def exists(self, path: Path) -> bool:
        return path.exists()


# Module-level singleton — import and use ``store`` directly.
store = JsonFileStore()
