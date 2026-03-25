"""Class notes store.

Reads and writes class note data via the shared persistence abstraction
(``backend.persistence.store``).  When ``DATABASE_URL`` is set the data lives
in PostgreSQL; otherwise it falls back to a local JSON file.

Public interface (unchanged for callers)
-----------------------------------------
- ``load_notes(path)``          → dict
- ``save_notes(path, notes)``   → dict
- ``create_note(data)``         → dict
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .persistence import store


def load_notes(path: Path) -> dict[str, Any]:
    if not store.exists(path):
        return {
            "status": "empty",
            "detail": "Noch keine Klassen-Notizen erfasst.",
            "updatedAt": "",
            "notes": [],
            "classes": [],
        }

    payload = store.read(path, default=None)

    if not isinstance(payload, dict):
        return {
            "status": "error",
            "detail": "Lokale Notizen konnten nicht gelesen werden.",
            "updatedAt": "",
            "notes": [],
            "classes": [],
        }

    notes = [_normalize_note(item) for item in payload.get("notes", []) if isinstance(item, dict)]
    notes = [item for item in notes if item["classLabel"]]
    classes = sorted({item["classLabel"] for item in notes})

    return {
        "status": "ok" if notes else "empty",
        "detail": (
            f"{len(notes)} Klassen-Notizen gespeichert."
            if notes
            else "Noch keine Klassen-Notizen erfasst."
        ),
        "updatedAt": payload.get("updatedAt", ""),
        "notes": notes,
        "classes": classes,
    }


def save_notes(path: Path, notes: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_notes = [_normalize_note(item) for item in notes if isinstance(item, dict)]
    normalized_notes = [item for item in normalized_notes if item["classLabel"]]
    now = datetime.now().astimezone()
    payload = {
        "updatedAt": now.strftime("%H:%M"),
        "savedAt": now.isoformat(),
        "notes": normalized_notes,
    }
    store.write(path, payload)
    return load_notes(path)


def create_note(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now().astimezone()
    return _normalize_note(
        {
            "classLabel": data.get("classLabel", ""),
            "text": data.get("text", ""),
            "updatedAt": data.get("updatedAt") or now.isoformat(),
        }
    )


def _normalize_note(note: dict[str, Any]) -> dict[str, str]:
    return {
        "classLabel": str(note.get("classLabel", "")).strip().upper(),
        "text": str(note.get("text", "")).strip(),
        "updatedAt": str(note.get("updatedAt", "")).strip(),
    }
