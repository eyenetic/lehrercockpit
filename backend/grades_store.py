"""Grade entries store.

Reads and writes grade data via the shared persistence abstraction
(``backend.persistence.store``).  When ``DATABASE_URL`` is set the data lives
in PostgreSQL; otherwise it falls back to a local JSON file.

Public interface (unchanged for callers)
-----------------------------------------
- ``load_gradebook(path)``   → dict
- ``save_gradebook(path, entries)`` → dict
- ``create_grade_entry(data)`` → dict
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .persistence import store


def load_gradebook(path: Path) -> dict[str, Any]:
    if not store.exists(path):
        return {
            "status": "empty",
            "detail": "Noch keine lokalen Noten erfasst.",
            "updatedAt": "",
            "entries": [],
            "classes": [],
        }

    payload = store.read(path, default=None)

    if not isinstance(payload, dict):
        return {
            "status": "error",
            "detail": "Lokale Noten konnten nicht gelesen werden.",
            "updatedAt": "",
            "entries": [],
            "classes": [],
        }

    entries = [
        _normalize_entry(item)
        for item in payload.get("entries", [])
        if isinstance(item, dict)
    ]
    classes = sorted({entry["classLabel"] for entry in entries if entry["classLabel"]})

    return {
        "status": "ok" if entries else "empty",
        "detail": (
            f"{len(entries)} lokale Noten-Eintraege."
            if entries
            else "Noch keine lokalen Noten erfasst."
        ),
        "updatedAt": payload.get("updatedAt", ""),
        "entries": entries,
        "classes": classes,
    }


def save_gradebook(path: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_entries = [
        _normalize_entry(item) for item in entries if isinstance(item, dict)
    ]
    now = datetime.now().astimezone()
    payload = {
        "updatedAt": now.strftime("%H:%M"),
        "savedAt": now.isoformat(),
        "entries": normalized_entries,
    }
    store.write(path, payload)
    return load_gradebook(path)


def create_grade_entry(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now().astimezone()
    return _normalize_entry(
        {
            "id": data.get("id") or uuid4().hex,
            "classLabel": data.get("classLabel", ""),
            "studentName": data.get("studentName", ""),
            "title": data.get("title", ""),
            "type": data.get("type", "Sonstiges"),
            "gradeValue": data.get("gradeValue", ""),
            "points": data.get("points", ""),
            "date": data.get("date") or now.date().isoformat(),
            "comment": data.get("comment", ""),
            "createdAt": data.get("createdAt") or now.isoformat(),
        }
    )


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry.get("id") or uuid4().hex),
        "classLabel": str(entry.get("classLabel", "")).strip(),
        "studentName": str(entry.get("studentName", "")).strip(),
        "title": str(entry.get("title", "")).strip(),
        "type": str(entry.get("type", "Sonstiges")).strip() or "Sonstiges",
        "gradeValue": str(entry.get("gradeValue", "")).strip(),
        "points": str(entry.get("points", "")).strip(),
        "date": str(entry.get("date", "")).strip(),
        "comment": str(entry.get("comment", "")).strip(),
        "createdAt": str(entry.get("createdAt", "")).strip(),
    }
