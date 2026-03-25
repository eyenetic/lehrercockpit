"""Persistence abstraction — JsonFileStore (local dev) or DbStore (Postgres/Render).

Which backend is active
-----------------------
- If ``DATABASE_URL`` is set in the environment, a :class:`DbStore` is used.
  All read/write operations go to a ``app_state`` table in PostgreSQL.
- Otherwise, :class:`JsonFileStore` is used, writing atomic JSON files to disk.

Public interface
----------------
All callers use the module-level ``store`` singleton::

    from backend.persistence import store

    data = store.read(path, default={})       # path: pathlib.Path
    store.write(path, data)                   # data: any JSON-serialisable value
    exists = store.exists(path)               # bool
    mtime = store.mtime(path)                 # float | None — epoch seconds of last write

Schema (PostgreSQL)
-------------------
::

    CREATE TABLE IF NOT EXISTS app_state (
        key         TEXT PRIMARY KEY,
        value       JSONB NOT NULL DEFAULT '{}',
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

The key is derived from ``path.stem`` (e.g. ``Path("data/grades-local.json").stem``
→ ``"grades-local"``).

Adding a DB backend
-------------------
Set ``DATABASE_URL`` on Render (Settings → Environment) to the Postgres connection
string provided by your database add-on.  The schema is initialised automatically
on the first request by calling :func:`init_schema`.

Swapping to a different store
-----------------------------
Implement a subclass of :class:`BaseStore`` and update the factory at the bottom of
this module.  The consuming modules (``grades_store``, ``notes_store``,
``classwork_cache``) do not need to change.
"""
from __future__ import annotations

import json
import os
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Environment detection ─────────────────────────────────────────────────────

DATABASE_URL: str = os.environ.get("DATABASE_URL", "").strip()

IS_RENDER = bool(
    os.environ.get("RENDER")
    or os.environ.get("RENDER_SERVICE_ID")
    or os.environ.get("IS_RENDER")
)


# ── Base interface ────────────────────────────────────────────────────────────

class BaseStore(ABC):
    """Common interface for all persistence backends."""

    @abstractmethod
    def read(self, path: Path, *, default: Any = None) -> Any:
        """Read stored data for *path*.  Returns *default* if absent."""

    @abstractmethod
    def write(self, path: Path, data: Any) -> None:
        """Persist *data* for *path*."""

    @abstractmethod
    def exists(self, path: Path) -> bool:
        """Return True if data for *path* has been stored."""

    @abstractmethod
    def mtime(self, path: Path) -> float | None:
        """Return epoch-seconds timestamp of last write, or None if absent."""

    def init_schema(self) -> None:
        """Idempotent schema initialisation.  No-op for file-based stores."""


# ── JSON file store (local development / fallback) ───────────────────────────

class JsonFileStore(BaseStore):
    """Atomic JSON file read/write.  Used when DATABASE_URL is not set."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def read(self, path: Path, *, default: Any = None) -> Any:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[persistence:file] read failed ({path}): {exc}", flush=True)
        return default

    def write(self, path: Path, data: Any) -> None:
        with self._lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                tmp.replace(path)
            except Exception as exc:
                print(f"[persistence:file] write failed ({path}): {exc}", flush=True)
                raise

    def exists(self, path: Path) -> bool:
        return path.exists()

    def mtime(self, path: Path) -> float | None:
        try:
            if path.exists():
                return path.stat().st_mtime
        except Exception:
            pass
        return None


# ── PostgreSQL store (production / Render) ────────────────────────────────────

class DbStore(BaseStore):
    """PostgreSQL-backed store using a single ``app_state`` key-value table.

    The key is derived from ``path.stem``.  Concurrent writes are serialised by
    ``INSERT … ON CONFLICT DO UPDATE`` (upsert), so no application-level lock is
    needed for correctness; the threading lock only avoids unnecessary round-trips.
    """

    _TABLE = "app_state"
    _CREATE_SQL = f"""
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            key        TEXT PRIMARY KEY,
            value      JSONB NOT NULL DEFAULT '{{}}',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._lock = threading.Lock()
        self._schema_initialised = False

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _key(path: Path) -> str:
        return path.stem

    def _connect(self):  # type: ignore[return]
        import psycopg  # type: ignore[import]
        return psycopg.connect(self._dsn, autocommit=True)

    # ── public interface ──────────────────────────────────────────────────────

    def init_schema(self) -> None:
        """Create the ``app_state`` table if it does not exist (idempotent)."""
        if self._schema_initialised:
            return
        try:
            with self._connect() as conn:
                conn.execute(self._CREATE_SQL)
            self._schema_initialised = True
            print("[persistence:db] schema initialised (app_state table ready)", flush=True)
        except Exception as exc:
            print(f"[persistence:db] schema init failed: {exc}", flush=True)
            raise

    def read(self, path: Path, *, default: Any = None) -> Any:
        key = self._key(path)
        try:
            with self._connect() as conn:
                row = conn.execute(
                    f"SELECT value FROM {self._TABLE} WHERE key = %s",
                    (key,),
                ).fetchone()
            if row is not None:
                # psycopg3 returns JSONB as a Python object already
                value = row[0]
                return value if value is not None else default
        except Exception as exc:
            print(f"[persistence:db] read failed (key={key}): {exc}", flush=True)
        return default

    def write(self, path: Path, data: Any) -> None:
        key = self._key(path)
        import psycopg.types.json as _pjson  # type: ignore[import]
        try:
            with self._lock:
                with self._connect() as conn:
                    conn.execute(
                        f"""
                        INSERT INTO {self._TABLE} (key, value, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT (key) DO UPDATE
                            SET value = EXCLUDED.value,
                                updated_at = EXCLUDED.updated_at
                        """,
                        (key, _pjson.Jsonb(data)),
                    )
        except Exception as exc:
            print(f"[persistence:db] write failed (key={key}): {exc}", flush=True)
            raise

    def exists(self, path: Path) -> bool:
        key = self._key(path)
        try:
            with self._connect() as conn:
                row = conn.execute(
                    f"SELECT 1 FROM {self._TABLE} WHERE key = %s",
                    (key,),
                ).fetchone()
            return row is not None
        except Exception as exc:
            print(f"[persistence:db] exists check failed (key={key}): {exc}", flush=True)
            return False

    def mtime(self, path: Path) -> float | None:
        """Return epoch-seconds of the row's ``updated_at``, or None if absent."""
        key = self._key(path)
        try:
            with self._connect() as conn:
                row = conn.execute(
                    f"SELECT updated_at FROM {self._TABLE} WHERE key = %s",
                    (key,),
                ).fetchone()
            if row and row[0]:
                ts: datetime = row[0]
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts.timestamp()
        except Exception as exc:
            print(f"[persistence:db] mtime failed (key={key}): {exc}", flush=True)
        return None


# ── Factory ───────────────────────────────────────────────────────────────────

def _make_store() -> BaseStore:
    if DATABASE_URL:
        print(
            f"[persistence] Using PostgreSQL store (DATABASE_URL is set). "
            "Data will survive Render redeploys.",
            flush=True,
        )
        return DbStore(DATABASE_URL)
    if IS_RENDER:
        print(
            "[persistence] WARNING: Using file store on Render — data is ephemeral. "
            "Set DATABASE_URL to enable durable Postgres persistence.",
            flush=True,
        )
    else:
        print("[persistence] Using local file store (no DATABASE_URL set).", flush=True)
    return JsonFileStore()


# Module-level singleton used by all consumers.
store: BaseStore = _make_store()
