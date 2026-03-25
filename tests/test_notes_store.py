"""Tests for backend/notes_store.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.notes_store import create_note, load_notes, save_notes


# ── load_notes ─────────────────────────────────────────────────────────────────

def test_load_notes_missing_file(tmp_path: Path) -> None:
    result = load_notes(tmp_path / "notes.json")
    assert result["status"] == "empty"
    assert result["notes"] == []
    assert result["classes"] == []


def test_load_notes_corrupt_file(tmp_path: Path) -> None:
    p = tmp_path / "notes.json"
    p.write_text("{broken", encoding="utf-8")
    result = load_notes(p)
    assert result["status"] == "error"
    assert result["notes"] == []


def test_load_notes_valid(tmp_path: Path) -> None:
    p = tmp_path / "notes.json"
    data = {
        "updatedAt": "11:00",
        "notes": [
            {"classLabel": "10a", "text": "Max fehlt freitags.", "updatedAt": "2026-03-01T11:00:00"},
        ],
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    result = load_notes(p)
    assert result["status"] == "ok"
    assert len(result["notes"]) == 1
    # classLabel must be uppercased
    assert result["notes"][0]["classLabel"] == "10A"


def test_load_notes_filters_empty_class_label(tmp_path: Path) -> None:
    p = tmp_path / "notes.json"
    data = {
        "notes": [
            {"classLabel": "", "text": "orphan", "updatedAt": ""},
            {"classLabel": "9C", "text": "ok", "updatedAt": ""},
        ]
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    result = load_notes(p)
    assert len(result["notes"]) == 1
    assert result["notes"][0]["classLabel"] == "9C"


# ── save_notes ────────────────────────────────────────────────────────────────

def test_save_notes_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "notes.json"
    note = create_note({"classLabel": "8B", "text": "Klasse hat Hausaufgaben vergessen."})
    result = save_notes(p, [note])
    assert result["status"] == "ok"
    assert result["notes"][0]["classLabel"] == "8B"
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert len(loaded["notes"]) == 1


def test_save_notes_creates_parent_dirs(tmp_path: Path) -> None:
    p = tmp_path / "nested" / "notes.json"
    save_notes(p, [])
    assert p.exists()


def test_save_notes_atomic_write(tmp_path: Path) -> None:
    p = tmp_path / "notes.json"
    save_notes(p, [])
    assert not p.with_suffix(".tmp").exists()


def test_save_notes_filters_empty_class_label(tmp_path: Path) -> None:
    p = tmp_path / "notes.json"
    notes = [
        {"classLabel": "", "text": "orphan", "updatedAt": ""},
        {"classLabel": "Q2", "text": "valid", "updatedAt": ""},
    ]
    result = save_notes(p, notes)
    assert len(result["notes"]) == 1


# ── create_note ────────────────────────────────────────────────────────────────

def test_create_note_uppercases_class_label() -> None:
    note = create_note({"classLabel": "q1", "text": "Achtung"})
    assert note["classLabel"] == "Q1"


def test_create_note_strips_whitespace() -> None:
    note = create_note({"classLabel": "  10b  ", "text": "  note  "})
    assert note["classLabel"] == "10B"
    assert note["text"] == "note"


def test_create_note_empty_text_allowed() -> None:
    note = create_note({"classLabel": "7A", "text": ""})
    assert note["text"] == ""


# ── classes aggregation ───────────────────────────────────────────────────────

def test_notes_classes_sorted(tmp_path: Path) -> None:
    p = tmp_path / "notes.json"
    notes = [
        create_note({"classLabel": "9C", "text": "a"}),
        create_note({"classLabel": "8A", "text": "b"}),
        create_note({"classLabel": "9B", "text": "c"}),
    ]
    result = save_notes(p, notes)
    assert result["classes"] == ["8A", "9B", "9C"]
