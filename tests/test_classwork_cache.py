"""Tests for backend/classwork_cache.py."""
from __future__ import annotations

import json
from pathlib import Path

from backend.classwork_cache import (
    _empty_cache,
    cache_age_minutes,
    get_previous_hash,
    load_cache,
    save_cache,
)


# ── load_cache ────────────────────────────────────────────────────────────────

def test_load_cache_missing_returns_empty(tmp_path: Path) -> None:
    result = load_cache(tmp_path / "cache.json")
    assert result["status"] == "pending"
    assert result["structuredRows"] == []
    assert result["previewRows"] == []


def test_load_cache_corrupt_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "cache.json"
    p.write_text("not json", encoding="utf-8")
    result = load_cache(p)
    # Should fall back to empty rather than raise
    assert result["status"] == "pending"


def test_load_cache_valid(tmp_path: Path) -> None:
    p = tmp_path / "cache.json"
    data = {
        "status": "ok",
        "title": "Klassenarbeitsplan",
        "structuredRows": [{"_sheet": "März", "Klasse": "10A"}],
        "previewRows": ["10A | 15.03."],
        "dataHash": "abc123",
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    result = load_cache(p)
    assert result["status"] == "ok"
    assert len(result["structuredRows"]) == 1
    assert result["dataHash"] == "abc123"


# ── save_cache ────────────────────────────────────────────────────────────────

def test_save_cache_creates_file(tmp_path: Path) -> None:
    p = tmp_path / "cache.json"
    data = {"status": "ok", "structuredRows": [], "dataHash": "xyz"}
    save_cache(p, data)
    assert p.exists()
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded["dataHash"] == "xyz"


def test_save_cache_creates_parent_dirs(tmp_path: Path) -> None:
    p = tmp_path / "nested" / "cache.json"
    save_cache(p, {"status": "ok"})
    assert p.exists()


def test_save_cache_no_tmp_file_remains(tmp_path: Path) -> None:
    p = tmp_path / "cache.json"
    save_cache(p, {"status": "ok"})
    assert not p.with_suffix(".tmp").exists()


def test_save_cache_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "cache.json"
    original = {"status": "ok", "structuredRows": [{"_sheet": "April", "Klasse": "Q1"}], "dataHash": "hash1"}
    save_cache(p, original)
    loaded = load_cache(p)
    assert loaded["status"] == "ok"
    assert loaded["structuredRows"][0]["Klasse"] == "Q1"


# ── get_previous_hash ─────────────────────────────────────────────────────────

def test_get_previous_hash_missing(tmp_path: Path) -> None:
    assert get_previous_hash(tmp_path / "no.json") == ""


def test_get_previous_hash_present(tmp_path: Path) -> None:
    p = tmp_path / "cache.json"
    p.write_text(json.dumps({"dataHash": "aabbcc"}), encoding="utf-8")
    assert get_previous_hash(p) == "aabbcc"


def test_get_previous_hash_no_field(tmp_path: Path) -> None:
    p = tmp_path / "cache.json"
    p.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    assert get_previous_hash(p) == ""


# ── cache_age_minutes ─────────────────────────────────────────────────────────

def test_cache_age_minutes_missing(tmp_path: Path) -> None:
    assert cache_age_minutes(tmp_path / "no.json") is None


def test_cache_age_minutes_fresh(tmp_path: Path) -> None:
    p = tmp_path / "cache.json"
    p.write_text("{}", encoding="utf-8")
    age = cache_age_minutes(p)
    assert age is not None
    assert 0 <= age < 1  # just written, should be less than 1 minute old


# ── _empty_cache ──────────────────────────────────────────────────────────────

def test_empty_cache_shape() -> None:
    ec = _empty_cache()
    assert ec["status"] == "pending"
    assert "structuredRows" in ec
    assert "previewRows" in ec
    assert "dataHash" in ec
