"""Tests for backend/grades_store.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.grades_store import create_grade_entry, load_gradebook, save_gradebook


# ── load_gradebook ─────────────────────────────────────────────────────────────

def test_load_gradebook_missing_file(tmp_path: Path) -> None:
    result = load_gradebook(tmp_path / "grades.json")
    assert result["status"] == "empty"
    assert result["entries"] == []
    assert result["classes"] == []


def test_load_gradebook_corrupt_file(tmp_path: Path) -> None:
    p = tmp_path / "grades.json"
    p.write_text("not valid json", encoding="utf-8")
    result = load_gradebook(p)
    assert result["status"] == "error"
    assert result["entries"] == []


def test_load_gradebook_valid(tmp_path: Path) -> None:
    p = tmp_path / "grades.json"
    data = {
        "updatedAt": "10:00",
        "entries": [
            {
                "id": "abc123",
                "classLabel": "10A",
                "studentName": "Max Mustermann",
                "title": "3. KA",
                "type": "Klassenarbeit",
                "gradeValue": "2",
                "points": "",
                "date": "2026-03-01",
                "comment": "",
                "createdAt": "2026-03-01T10:00:00",
            }
        ],
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    result = load_gradebook(p)
    assert result["status"] == "ok"
    assert len(result["entries"]) == 1
    assert result["classes"] == ["10A"]
    assert result["entries"][0]["classLabel"] == "10A"


def test_load_gradebook_empty_entries(tmp_path: Path) -> None:
    p = tmp_path / "grades.json"
    p.write_text(json.dumps({"updatedAt": "09:00", "entries": []}), encoding="utf-8")
    result = load_gradebook(p)
    assert result["status"] == "empty"
    assert result["entries"] == []


# ── save_gradebook ─────────────────────────────────────────────────────────────

def test_save_gradebook_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "grades.json"
    entry = create_grade_entry(
        {
            "classLabel": "9B",
            "studentName": "Anna Schmidt",
            "title": "LEK Physik",
            "type": "LEK",
            "gradeValue": "1+",
            "date": "2026-04-10",
        }
    )
    result = save_gradebook(p, [entry])
    assert result["status"] == "ok"
    assert result["entries"][0]["studentName"] == "Anna Schmidt"
    # File must exist and be valid JSON
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert len(loaded["entries"]) == 1


def test_save_gradebook_creates_parent_dirs(tmp_path: Path) -> None:
    p = tmp_path / "nested" / "dir" / "grades.json"
    save_gradebook(p, [])
    assert p.exists()


def test_save_gradebook_atomic_write(tmp_path: Path) -> None:
    """No .tmp file should remain after a successful write."""
    p = tmp_path / "grades.json"
    save_gradebook(p, [])
    tmp = p.with_suffix(".tmp")
    assert not tmp.exists()


# ── create_grade_entry ─────────────────────────────────────────────────────────

def test_create_grade_entry_defaults() -> None:
    entry = create_grade_entry({"classLabel": "11C", "studentName": "Eva", "title": "Test"})
    assert entry["classLabel"] == "11C"
    assert entry["type"] == "Sonstiges"
    assert entry["id"]  # must have a non-empty id


def test_create_grade_entry_preserves_id() -> None:
    entry = create_grade_entry({"id": "fixed-id", "classLabel": "Q1", "studentName": "X", "title": "Y"})
    assert entry["id"] == "fixed-id"


def test_create_grade_entry_strips_whitespace() -> None:
    entry = create_grade_entry({"classLabel": "  10A  ", "studentName": " Max ", "title": " KA "})
    assert entry["classLabel"] == "10A"
    assert entry["studentName"] == "Max"
    assert entry["title"] == "KA"


# ── classes aggregation ────────────────────────────────────────────────────────

def test_gradebook_classes_sorted_and_deduped(tmp_path: Path) -> None:
    p = tmp_path / "grades.json"
    entries = [
        create_grade_entry({"classLabel": "10B", "studentName": "A", "title": "T"}),
        create_grade_entry({"classLabel": "10A", "studentName": "B", "title": "T"}),
        create_grade_entry({"classLabel": "10B", "studentName": "C", "title": "T"}),
    ]
    result = save_gradebook(p, entries)
    assert result["classes"] == ["10A", "10B"]
