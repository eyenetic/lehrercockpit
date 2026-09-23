"""Tests für backend/push_service.py (Versandfenster und Inhalte)."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from backend import push_service as ps


@pytest.mark.parametrize("utc,expected", [
    (datetime(2026, 9, 23, 4, 40, tzinfo=timezone.utc), ["morning"]),   # Mi 06:40 CEST
    (datetime(2026, 9, 23, 4, 20, tzinfo=timezone.utc), []),            # Mi 06:20 – zu früh
    (datetime(2026, 12, 2, 5, 45, tzinfo=timezone.utc), ["morning"]),   # Mi 06:45 CET (Winterzeit)
    (datetime(2026, 9, 26, 5, 0, tzinfo=timezone.utc), []),             # Sa
    (datetime(2026, 9, 27, 16, 0, tzinfo=timezone.utc), ["weekly"]),    # So 18:00 CEST
])
def test_due_kinds_follow_berlin_time(utc, expected):
    assert ps.due_kinds(utc) == expected


def _item(kind, title, date, *, new=False, importance=2):
    return {"id": title, "kind": kind, "title": title, "date": date, "importance": importance,
            "state": {"new": new, "changed": False, "status": "open"}}


def test_morning_digest_summarises_the_day():
    now = datetime(2026, 9, 23, 4, 45, tzinfo=timezone.utc)
    modules = {"webuntis": {"ok": True, "data": {"events": [
        {"title": "Mathe 10b", "startsAt": "2026-09-23T09:45:00", "cancelled": False},
        {"title": "Deutsch 9a", "startsAt": "2026-09-23T08:00:00", "cancelled": False},
        {"title": "Sport 7c", "startsAt": "2026-09-23T11:40:00", "cancelled": True},
    ]}}}
    items = [_item("klassenarbeit", "10b: Klassenarbeit: Mathe", "2026-09-23", importance=3),
             _item("datei", "Neu: Plan.xlsx", "2026-09-22", new=True)]
    digest = ps.morning_digest(modules, items, now)
    assert digest["title"] == "Dein Tag – Mi 23.09."
    assert digest["body"].splitlines() == [
        "2 Stunden, erste um 08:00.",
        "Klassenarbeit: 10b: Klassenarbeit: Mathe",
        "1 neuer Eintrag seit gestern.",
    ]


def test_morning_digest_is_skipped_when_empty():
    assert ps.morning_digest({}, [], datetime(2026, 9, 23, 4, 45, tzinfo=timezone.utc)) is None


def test_weekly_digest_previews_next_week():
    now = datetime(2026, 9, 27, 16, 0, tzinfo=timezone.utc)  # So 27.09.
    items = [_item("klassenarbeit", "9b: Mathe", "2026-09-28"), _item("klassenarbeit", "10a: Deutsch", "2026-10-01"),
             _item("termin", "GK 15:30", "2026-09-30"), _item("termin", "zu spät", "2026-10-06")]
    digest = ps.weekly_digest(items, now)
    assert digest["title"] == "Nächste Woche (28.09.–02.10.)"
    assert digest["body"].splitlines() == [
        "2 Klassenarbeiten: 9b: Mathe (Mo), 10a: Deutsch (Do)",
        "1 Termin: GK 15:30 (Mi)",
    ]


def test_dispatch_without_keys_does_nothing(monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    with patch("backend.db.db_connection") as connect:
        summary = ps.dispatch(datetime(2026, 9, 23, 4, 45, tzinfo=timezone.utc))
    assert summary["reason"] == "Push nicht konfiguriert"
    connect.assert_not_called()
