"""Unified entries ("Signale") from all sources, for "Neu & geändert" and push digests.

A signal is one thing a teacher may need to know or act on:
  id           stable per item, so state (seen/done/snoozed) survives refreshes
  source       webuntis | klassenarbeitsplan | orgaplan | itslearning | nextcloud | termine
  kind         entfall | klassenarbeit | termin | frist | datei | nachricht
  title, detail, date (YYYY-MM-DD or None), time (HH:MM or None), url
  classes      class labels it concerns (e.g. ["10B"])
  importance   0..3
  fingerprint  hash of the content; a new fingerprint means "geändert"

Only pure functions here; state lives in signal_store.py.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .ical_utils import BERLIN

KIND_LABELS = {
    "entfall": "Entfall",
    "klassenarbeit": "Klassenarbeit",
    "termin": "Termin",
    "frist": "Frist",
    "datei": "Datei",
    "nachricht": "Nachricht",
}

# Same pattern as extractClassLabels() in the frontend: 5a–13f, Q1, Q1/Q2 …
_CLASS_PATTERN = re.compile(r"\b(?:[5-9][A-Z]?|1[0-3][A-Z]?|Q\d(?:/Q?\d)?)\b", re.IGNORECASE)
_SEK_ONE = re.compile(r"^(?:[5-9]|1[0-3])[A-Z]$")
_UPPER = re.compile(r"^(?:Q\d|S\d)")

WINDOW_DAYS = {"entfall": 7, "klassenarbeit": 21, "termin": 14, "frist": 14}
ACTIVITY_DAYS = 7


def normalize_class(label: str) -> str:
    return re.sub(r"\s+", "", str(label or "")).upper()


def teacher_classes(webuntis_data: dict | None, preferred: list[str] | tuple = ()) -> set[str]:
    """Class labels from the teacher's own timetable plus the classes chosen in "Heute anpassen"."""
    classes = {normalize_class(c) for c in preferred if c}
    for event in (webuntis_data or {}).get("events") or []:
        haystack = " ".join(str(event.get(k) or "") for k in ("title", "detail", "description"))
        classes.update(normalize_class(m) for m in _CLASS_PATTERN.findall(haystack))
    # Bare grade numbers ("10") match the pattern but are not classes.
    return {c for c in classes if _SEK_ONE.match(c) or _UPPER.match(c)}


def _fingerprint(*parts: Any) -> str:
    return hashlib.sha1("\x1f".join(str(p or "") for p in parts).encode("utf-8")).hexdigest()[:16]


def _short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def _local(value: str) -> datetime | None:
    """Parse an ISO timestamp; naive values are school (Berlin) time."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=BERLIN) if parsed.tzinfo is None else parsed.astimezone(BERLIN)


def _iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _within(day: date | None, today: date, days: int) -> bool:
    return day is not None and today <= day <= today + timedelta(days=days)


def _importance(day: date | None, today: date, *, urgent_days: int, base: int) -> int:
    if day is not None and (day - today).days <= urgent_days:
        return min(3, base + 1)
    return base


def _signal(**fields: Any) -> dict[str, Any]:
    signal = {"detail": "", "date": None, "time": None, "classes": [], "url": "", "importance": 1}
    signal.update(fields)
    signal["fingerprint"] = _fingerprint(signal["title"], signal["detail"], signal["date"],
                                         signal["time"], signal["url"])
    return signal


def _data(modules: dict, module_id: str) -> dict:
    result = modules.get(module_id) or {}
    if not result.get("ok"):
        return {}
    return result.get("data") or {}


def _from_webuntis(data: dict, today: date) -> list[dict]:
    signals = []
    for event in data.get("events") or []:
        if not event.get("cancelled"):
            continue
        start = _local(event.get("startsAt", ""))
        day = start.date() if start else None
        if not _within(day, today, WINDOW_DAYS["entfall"]):
            continue
        signals.append(_signal(
            id=f"entfall:{event.get('id') or start.isoformat()}",
            source="webuntis",
            kind="entfall",
            title=f"Entfall: {event.get('title') or 'Stunde'}",
            detail=str(event.get("location") or ""),
            date=day.isoformat(),
            time=start.strftime("%H:%M"),
            classes=sorted(teacher_classes({"events": [event]})),
            importance=_importance(day, today, urgent_days=1, base=2),
        ))
    return signals


def _from_classwork(data: dict, today: date, classes: set[str]) -> list[dict]:
    if not classes:
        return []  # without the teacher's classes the whole school's plan would be noise
    signals = []
    for entry in data.get("entries") or []:
        label = normalize_class(entry.get("classLabel", ""))
        day = _iso_date(entry.get("isoDate", ""))
        if label not in classes or not _within(day, today, WINDOW_DAYS["klassenarbeit"]):
            continue
        title = str(entry.get("summary") or entry.get("title") or "Klassenarbeit")
        signals.append(_signal(
            id=f"klassenarbeit:{label}:{day.isoformat()}:{_short_hash(title)}",
            source="klassenarbeitsplan",
            kind="klassenarbeit",
            title=f"{entry.get('classLabel', label)}: {title}",
            date=day.isoformat(),
            classes=[label],
            importance=_importance(day, today, urgent_days=2, base=2),
        ))
    return signals


def _from_orgaplan(data: dict, today: date, classes: set[str]) -> list[dict]:
    teaches_sek_one = not classes or any(_SEK_ONE.match(c) for c in classes)
    teaches_upper = not classes or any(_UPPER.match(c) for c in classes)
    signals = []
    for entry in data.get("upcoming") or data.get("entries") or []:
        day = _iso_date(entry.get("isoDate", ""))
        if not _within(day, today, WINDOW_DAYS["termin"]):
            continue
        parts = [str(entry.get("general") or "").strip()]
        if teaches_sek_one:
            parts.append(str(entry.get("middle") or "").strip())
        if teaches_upper:
            parts.append(str(entry.get("upper") or "").strip())
        parts = [p for p in parts if p]
        if not parts:
            continue  # nothing for this teacher's levels
        title = parts[0]
        signals.append(_signal(
            id=f"orgaplan:{day.isoformat()}:{_short_hash(str(entry.get('text') or title))}",
            source="orgaplan",
            kind="termin",
            title=title,
            detail=" · ".join(parts[1:]),
            date=day.isoformat(),
            importance=_importance(day, today, urgent_days=1, base=1),
        ))
    return signals


def _from_itslearning(data: dict, today: date) -> list[dict]:
    calendar = data.get("calendar") or {}
    signals = []
    for event in calendar.get("events") or []:
        start = _local(event.get("start", ""))
        day = start.date() if start else None
        kind = "frist" if event.get("kind") == "todo" else "termin"
        if not _within(day, today, WINDOW_DAYS[kind]):
            continue
        signals.append(_signal(
            id=f"itslearning:{event.get('id')}",
            source="itslearning",
            kind=kind,
            title=str(event.get("title") or "itslearning"),
            detail=str(event.get("location") or ""),
            date=day.isoformat(),
            time=None if event.get("allDay") else start.strftime("%H:%M"),
            url=str(event.get("url") or ""),
            importance=_importance(day, today, urgent_days=2, base=2 if kind == "frist" else 1),
        ))
    return signals


def _from_nextcloud(data: dict, now: datetime) -> list[dict]:
    signals = []
    for note in data.get("notifications") or []:
        when = _local(note.get("time", ""))
        signals.append(_signal(
            id=str(note.get("id")),
            source="nextcloud",
            kind="nachricht",
            title=str(note.get("subject") or "Nextcloud"),
            detail=str(note.get("message") or ""),
            date=when.date().isoformat() if when else None,
            url=str(note.get("link") or ""),
            importance=2,
        ))
    cutoff = now - timedelta(days=ACTIVITY_DAYS)
    for activity in data.get("activity") or []:
        when = _local(activity.get("time", ""))
        if when is None or when < cutoff:
            continue
        signals.append(_signal(
            id=str(activity.get("id")),
            source="nextcloud",
            kind="datei",
            title=str(activity.get("subject") or "Nextcloud"),
            date=when.date().isoformat(),
            url=str(activity.get("link") or ""),
            importance=1,
        ))
    return signals


def _from_school_calendar(data: dict, today: date) -> list[dict]:
    signals = []
    for event in (data.get("today_events") or []) + (data.get("upcoming_events") or []):
        day = _iso_date(event.get("start", ""))
        if not _within(day, today, WINDOW_DAYS["termin"]):
            continue
        signals.append(_signal(
            id=f"termine:{event.get('uid') or _short_hash(str(event.get('title')) + day.isoformat())}",
            source="termine",
            kind="termin",
            title=str(event.get("title") or "Termin"),
            detail=str(event.get("location") or ""),
            date=day.isoformat(),
            time=(event.get("time_label") or "")[:5] or None,
            importance=_importance(day, today, urgent_days=1, base=1),
        ))
    return signals


def build_signals(modules: dict, now: datetime | None = None,
                  preferred_classes: list[str] | tuple = ()) -> tuple[list[dict], set[str]]:
    """All signals from the module results of /api/v2/dashboard/data.

    Returns (signals sorted by date/importance, the teacher's classes).
    """
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(BERLIN).date()
    webuntis = _data(modules, "webuntis")
    classes = teacher_classes(webuntis, preferred_classes)

    signals: list[dict] = []
    builders = (
        lambda: _from_webuntis(webuntis, today),
        lambda: _from_classwork(_data(modules, "klassenarbeitsplan"), today, classes),
        lambda: _from_orgaplan(_data(modules, "orgaplan"), today, classes),
        lambda: _from_itslearning(_data(modules, "itslearning"), today),
        lambda: _from_nextcloud(_data(modules, "nextcloud"), now),
        lambda: _from_school_calendar(_data(modules, "wichtige-termine"), today),
    )
    for build in builders:
        try:
            signals.extend(build())
        except Exception:
            continue  # one broken source must not hide the others

    unique = {s["id"]: s for s in signals}
    ordered = sorted(unique.values(), key=lambda s: (s["date"] or "9999", -s["importance"], s["title"]))
    return ordered, classes
