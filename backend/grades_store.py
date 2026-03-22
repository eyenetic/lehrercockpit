from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


def load_gradebook(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "empty",
            "detail": "Noch keine lokalen Noten erfasst.",
            "updatedAt": "",
            "entries": [],
            "classes": [],
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "error",
            "detail": f"Lokale Noten konnten nicht gelesen werden: {type(exc).__name__}: {exc}",
            "updatedAt": "",
            "entries": [],
            "classes": [],
        }

    entries = [_normalize_entry(item) for item in payload.get("entries", []) if isinstance(item, dict)]
    classes = sorted({entry["classLabel"] for entry in entries if entry["classLabel"]})

    return {
        "status": "ok" if entries else "empty",
        "detail": f"{len(entries)} lokale Noten-Eintraege." if entries else "Noch keine lokalen Noten erfasst.",
        "updatedAt": payload.get("updatedAt", ""),
        "entries": entries,
        "classes": classes,
    }


def save_gradebook(path: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_entries = [_normalize_entry(item) for item in entries if isinstance(item, dict)]
    now = datetime.now().astimezone()
    payload = {
        "updatedAt": now.strftime("%H:%M"),
        "savedAt": now.isoformat(),
        "entries": normalized_entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
    class_label = str(entry.get("classLabel", "")).strip()
    student_name = str(entry.get("studentName", "")).strip()
    title = str(entry.get("title", "")).strip()
    entry_type = str(entry.get("type", "Sonstiges")).strip() or "Sonstiges"
    grade_value = str(entry.get("gradeValue", "")).strip()
    points = str(entry.get("points", "")).strip()
    date = str(entry.get("date", "")).strip()
    comment = str(entry.get("comment", "")).strip()
    created_at = str(entry.get("createdAt", "")).strip()
    normalized = {
        "id": str(entry.get("id") or uuid4().hex),
        "classLabel": class_label,
        "studentName": student_name,
        "title": title,
        "type": entry_type,
        "gradeValue": grade_value,
        "points": points,
        "date": date,
        "comment": comment,
        "createdAt": created_at,
    }
    return normalized
