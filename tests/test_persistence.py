"""Tests for backend/persistence.py.

Split into two sections:
1. Unit tests for the store factory and JsonFileStore — always run, no DB needed.
2. DB integration tests (marked with ``pytest.mark.db``) — skipped unless
   ``TEST_DATABASE_URL`` is set in the environment.

Running locally without a database:
    pytest tests/test_persistence.py -v

Running with a live Postgres database:
    TEST_DATABASE_URL="postgresql://..." pytest tests/test_persistence.py -v -m db
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def fresh_persistence_module(monkeypatch: pytest.MonkeyPatch, database_url: str = "") -> Any:
    """Return a freshly-imported persistence module with DATABASE_URL patched."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RENDER_SERVICE_ID", raising=False)
    # Force re-import so the module-level store is re-created
    import backend.persistence as mod
    importlib.reload(mod)
    return mod


# ── Factory / store selection ─────────────────────────────────────────────────

class TestStoreFactory:
    def test_no_database_url_gives_file_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = fresh_persistence_module(monkeypatch, database_url="")
        assert isinstance(mod.store, mod.JsonFileStore)

    def test_database_url_gives_db_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = fresh_persistence_module(monkeypatch, database_url="postgresql://fake/db")
        assert isinstance(mod.store, mod.DbStore)

    def test_db_store_stores_dsn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = fresh_persistence_module(monkeypatch, database_url="postgresql://fake/db")
        assert mod.store._dsn == "postgresql://fake/db"


# ── JsonFileStore ─────────────────────────────────────────────────────────────

class TestJsonFileStore:
    @pytest.fixture()
    def file_store(self) -> "JsonFileStore":
        from backend.persistence import JsonFileStore
        return JsonFileStore()

    def test_read_missing_returns_default(self, file_store, tmp_path: Path) -> None:
        assert file_store.read(tmp_path / "nope.json") is None
        assert file_store.read(tmp_path / "nope.json", default={}) == {}

    def test_write_creates_file(self, file_store, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        file_store.write(p, {"key": "value"})
        assert p.exists()

    def test_roundtrip(self, file_store, tmp_path: Path) -> None:
        p = tmp_path / "data.json"
        payload = {"entries": [{"id": "abc", "classLabel": "10A"}]}
        file_store.write(p, payload)
        loaded = file_store.read(p, default={})
        assert loaded == payload

    def test_write_is_atomic(self, file_store, tmp_path: Path) -> None:
        """No .tmp file should remain after a successful write."""
        p = tmp_path / "data.json"
        file_store.write(p, {"x": 1})
        assert not p.with_suffix(".tmp").exists()

    def test_exists_false_when_missing(self, file_store, tmp_path: Path) -> None:
        assert not file_store.exists(tmp_path / "missing.json")

    def test_exists_true_after_write(self, file_store, tmp_path: Path) -> None:
        p = tmp_path / "present.json"
        file_store.write(p, {})
        assert file_store.exists(p)

    def test_mtime_none_when_missing(self, file_store, tmp_path: Path) -> None:
        assert file_store.mtime(tmp_path / "missing.json") is None

    def test_mtime_returns_float_after_write(self, file_store, tmp_path: Path) -> None:
        p = tmp_path / "ts.json"
        file_store.write(p, {})
        mt = file_store.mtime(p)
        assert isinstance(mt, float)
        assert mt > 0

    def test_creates_parent_directories(self, file_store, tmp_path: Path) -> None:
        p = tmp_path / "nested" / "dir" / "data.json"
        file_store.write(p, {"ok": True})
        assert p.exists()

    def test_init_schema_is_noop(self, file_store) -> None:
        # Should not raise
        file_store.init_schema()

    def test_read_corrupt_file_returns_default(self, file_store, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("not valid json", encoding="utf-8")
        result = file_store.read(p, default={"fallback": True})
        assert result == {"fallback": True}

    def test_write_and_overwrite(self, file_store, tmp_path: Path) -> None:
        p = tmp_path / "data.json"
        file_store.write(p, {"v": 1})
        file_store.write(p, {"v": 2})
        assert file_store.read(p)["v"] == 2


# ── DbStore (key derivation — no live DB needed) ──────────────────────────────

class TestDbStoreKey:
    @pytest.fixture()
    def db_store(self) -> "DbStore":
        from backend.persistence import DbStore
        return DbStore("postgresql://fake/db")

    def test_key_from_stem(self, db_store) -> None:
        assert db_store._key(Path("data/grades-local.json")) == "grades-local"

    def test_key_from_stem_classwork(self, db_store) -> None:
        assert db_store._key(Path("data/classwork-cache.json")) == "classwork-cache"

    def test_key_from_stem_notes(self, db_store) -> None:
        assert db_store._key(Path("/absolute/path/class-notes-local.json")) == "class-notes-local"


# ── DB integration tests (require TEST_DATABASE_URL) ─────────────────────────

DB_URL = os.environ.get("TEST_DATABASE_URL", "")
db_required = pytest.mark.skipif(
    not DB_URL,
    reason="Set TEST_DATABASE_URL to run DB integration tests",
)


@db_required
class TestDbStoreIntegration:
    """Live DB tests — only run when TEST_DATABASE_URL is set.

    Each test uses a unique key prefix to avoid cross-test interference.
    The app_state table is created by init_schema(); tests clean up after themselves.
    """

    @pytest.fixture()
    def db_store(self) -> "DbStore":
        from backend.persistence import DbStore
        s = DbStore(DB_URL)
        s.init_schema()
        return s

    def _path(self, name: str) -> Path:
        return Path(f"test-{name}.json")

    def _cleanup(self, db_store, path: Path) -> None:
        try:
            with db_store._connect() as conn:
                conn.execute(
                    f"DELETE FROM {db_store._TABLE} WHERE key = %s",
                    (db_store._key(path),),
                )
        except Exception:
            pass

    def test_roundtrip(self, db_store) -> None:
        p = self._path("roundtrip")
        try:
            payload = {"entries": [{"id": "x1", "classLabel": "9B"}], "updatedAt": "10:00"}
            db_store.write(p, payload)
            loaded = db_store.read(p)
            assert loaded["entries"][0]["classLabel"] == "9B"
        finally:
            self._cleanup(db_store, p)

    def test_exists_false_before_write(self, db_store) -> None:
        p = self._path("exists-false")
        assert not db_store.exists(p)

    def test_exists_true_after_write(self, db_store) -> None:
        p = self._path("exists-true")
        try:
            db_store.write(p, {"ok": True})
            assert db_store.exists(p)
        finally:
            self._cleanup(db_store, p)

    def test_overwrite(self, db_store) -> None:
        p = self._path("overwrite")
        try:
            db_store.write(p, {"v": 1})
            db_store.write(p, {"v": 2})
            assert db_store.read(p)["v"] == 2
        finally:
            self._cleanup(db_store, p)

    def test_mtime_set_after_write(self, db_store) -> None:
        p = self._path("mtime")
        try:
            db_store.write(p, {"ts": "now"})
            mt = db_store.mtime(p)
            assert mt is not None
            assert mt > 0
        finally:
            self._cleanup(db_store, p)

    def test_read_absent_returns_default(self, db_store) -> None:
        p = self._path("absent")
        assert db_store.read(p, default={"fallback": True}) == {"fallback": True}

    def test_init_schema_idempotent(self, db_store) -> None:
        # Calling twice must not raise
        db_store.init_schema()
        db_store.init_schema()
