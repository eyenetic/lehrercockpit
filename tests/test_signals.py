"""Tests für backend/signals.py (einheitliche Einträge aus allen Quellen)."""
from datetime import datetime, timezone

from backend.signals import build_signals, teacher_classes

NOW = datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc)  # Mi 23.09., 08:00 Berlin


def _ok(data):
    return {"ok": True, "data": data}


WEBUNTIS = _ok({"events": [
    {"id": "webuntis-1", "title": "Mathe 10b", "detail": "", "startsAt": "2026-09-24T08:00:00",
     "location": "R 204", "cancelled": True},
    {"id": "webuntis-2", "title": "Deutsch 9A", "startsAt": "2026-09-23T09:45:00", "cancelled": False},
    {"id": "webuntis-3", "title": "Mathe Q1/Q2", "startsAt": "2026-09-23T11:40:00", "cancelled": False},
    {"id": "webuntis-old", "title": "Mathe 10b", "startsAt": "2026-09-01T08:00:00", "cancelled": True},
]})


def test_teacher_classes_from_timetable_and_preferences():
    classes = teacher_classes(WEBUNTIS["data"], ["7c", "10"])
    assert classes == {"10B", "9A", "Q1/Q2", "7C"}  # "10" alone is not a class


def test_cancelled_lessons_become_entfall_signals():
    signals, _ = build_signals({"webuntis": WEBUNTIS}, NOW)
    entfall = [s for s in signals if s["kind"] == "entfall"]
    assert len(entfall) == 1  # the one from 01.09. is outside the window
    assert entfall[0]["title"] == "Entfall: Mathe 10b"
    assert entfall[0]["date"] == "2026-09-24" and entfall[0]["time"] == "08:00"
    assert entfall[0]["importance"] == 3  # tomorrow


def test_classwork_only_for_own_classes():
    classwork = _ok({"entries": [
        {"classLabel": "10b", "isoDate": "2026-09-25", "title": "KA Mathe", "summary": "Klassenarbeit: Mathe"},
        {"classLabel": "8a", "isoDate": "2026-09-25", "title": "KA Englisch", "summary": "Klassenarbeit: Englisch"},
        {"classLabel": "10b", "isoDate": "2026-11-30", "title": "KA Physik", "summary": "Klassenarbeit: Physik"},
    ]})
    signals, _ = build_signals({"webuntis": WEBUNTIS, "klassenarbeitsplan": classwork}, NOW)
    titles = [s["title"] for s in signals if s["kind"] == "klassenarbeit"]
    assert titles == ["10b: Klassenarbeit: Mathe"]


def test_classwork_is_skipped_without_known_classes():
    classwork = _ok({"entries": [{"classLabel": "10b", "isoDate": "2026-09-25", "title": "KA"}]})
    signals, classes = build_signals({"klassenarbeitsplan": classwork}, NOW)
    assert classes == set()
    assert signals == []


def test_orgaplan_respects_teaching_levels():
    orgaplan = _ok({"upcoming": [
        {"isoDate": "2026-09-24", "title": "x", "text": "a", "general": "GK 15:30", "middle": "Elternabend Sek I",
         "upper": "Q1 Klausurtag"},
        {"isoDate": "2026-09-25", "title": "y", "text": "b", "general": "", "middle": "Nur Mittelstufe", "upper": ""},
    ]})
    only_upper = _ok({"events": [{"id": "e", "title": "Mathe Q1", "startsAt": "2026-09-23T08:00:00"}]})
    signals, _ = build_signals({"webuntis": only_upper, "orgaplan": orgaplan}, NOW)
    termine = [s for s in signals if s["source"] == "orgaplan"]
    assert len(termine) == 1
    assert termine[0]["title"] == "GK 15:30"
    assert termine[0]["detail"] == "Q1 Klausurtag"


def test_itslearning_deadlines_and_recent_nextcloud_activity():
    modules = {
        "itslearning": _ok({"calendar": {"events": [
            {"id": "itslearning-cal-1", "kind": "todo", "title": "Abgabe Essay", "start": "2026-09-24T21:59:00+02:00"},
        ]}}),
        "nextcloud": _ok({
            "notifications": [{"id": "nextcloud-notification-5", "subject": "Du wurdest erwähnt",
                               "time": "2026-09-23T05:00:00+00:00"}],
            "activity": [
                {"id": "nextcloud-activity-1", "subject": "Neu: Plan.xlsx", "time": "2026-09-22T10:00:00+00:00"},
                {"id": "nextcloud-activity-2", "subject": "Alt", "time": "2026-08-01T10:00:00+00:00"},
            ],
        }),
    }
    signals, _ = build_signals(modules, NOW)
    kinds = {s["id"]: s["kind"] for s in signals}
    assert kinds == {"itslearning:itslearning-cal-1": "frist", "nextcloud-notification-5": "nachricht",
                     "nextcloud-activity-1": "datei"}


def test_fingerprint_changes_with_content_and_ids_are_stable():
    first, _ = build_signals({"webuntis": WEBUNTIS}, NOW)
    moved = {"ok": True, "data": {"events": [dict(WEBUNTIS["data"]["events"][0], location="R 101")]}}
    second, _ = build_signals({"webuntis": moved}, NOW)
    assert first[0]["id"] == second[0]["id"]
    assert first[0]["fingerprint"] != second[0]["fingerprint"]


def test_broken_source_does_not_hide_others():
    modules = {"webuntis": WEBUNTIS, "orgaplan": {"ok": True, "data": {"upcoming": "kaputt"}}}
    signals, _ = build_signals(modules, NOW)
    assert any(s["kind"] == "entfall" for s in signals)
