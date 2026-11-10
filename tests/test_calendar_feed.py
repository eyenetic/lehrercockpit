"""Tests für das Kalender-Abo (backend/calendar_feed.py, backend/api/calendar_routes.py)."""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import backend.api.calendar_routes as routes
import backend.api.helpers
from backend import calendar_feed as cf

NOW = datetime(2026, 11, 9, 7, 0, tzinfo=timezone.utc)


def test_orgaplan_respects_level():
    digest = {"upcoming": [{"isoDate": "2026-11-10", "general": "Gesamtkonferenz", "middle": "Wandertag 7",
                            "upper": "Klausurwoche", "upperNotes": "Q1"}]}
    titles = lambda level: [e["title"] for e in cf._orgaplan_events(digest, level)]
    assert titles("all") == ["Gesamtkonferenz", "Mittelstufe: Wandertag 7", "Oberstufe: Klausurwoche (Q1)"]
    assert titles("middle") == ["Gesamtkonferenz", "Wandertag 7"]
    assert titles("upper") == ["Gesamtkonferenz", "Klausurwoche (Q1)"]


def test_classwork_only_own_classes_and_no_double_kind():
    entries = [
        {"isoDate": "2026-11-13", "classLabel": "9A", "kind": "Klassenarbeit", "title": "1. D Friedrich"},
        {"isoDate": "2026-11-23", "classLabel": "9A", "kind": "Klassenarbeit", "title": "2. KA E Er"},
        {"isoDate": "2026-11-10", "classLabel": "9A", "kind": "LEK", "title": "1. Bio Si"},
        {"isoDate": "2026-11-10", "classLabel": "10B", "kind": "LEK", "title": "Ph Bl"},
        {"isoDate": "2026-01-10", "classLabel": "9A", "kind": "LEK", "title": "alt"},
    ]
    titles = [e["title"] for e in cf._classwork_events(entries, {"9A"}, date(2026, 10, 10))]
    assert titles == ["9A KA: 1. D Friedrich", "9A: 2. KA E Er", "9A LEK: 1. Bio Si"]


def test_ics_all_day_end_is_exclusive_and_text_is_escaped():
    events = [
        {"uid": "sch", "title": "Projektwoche, Klasse 8; alle", "start": date(2026, 11, 11), "end": date(2026, 11, 15),
         "all_day": True, "location": "Aula", "description": "Zeile 1\nZeile 2", "url": "https://schule.de/a,b"},
        {"uid": "sch", "title": "Wege nach der 10. Klasse", "start": datetime(2026, 11, 10, 9, 50, tzinfo=timezone.utc),
         "end": datetime(2026, 11, 10, 11, 25, tzinfo=timezone.utc), "all_day": False},
    ]
    ics = cf.build_ics(events, NOW)
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert "DTSTART;VALUE=DATE:20261111\r\nDTEND;VALUE=DATE:20261116" in ics
    assert "SUMMARY:Projektwoche\\, Klasse 8\\; alle" in ics
    assert "DESCRIPTION:Zeile 1\\nZeile 2" in ics
    assert "URL:https://schule.de/a,b" in ics
    assert "DTSTART:20261110T095000Z\r\nDTEND:20261110T112500Z" in ics
    assert all(len(line.encode("utf-8")) <= 75 for line in ics.split("\r\n"))


def test_long_lines_are_folded():
    ics = cf.build_ics([{"uid": "org", "title": "Ä" * 120, "start": date(2026, 11, 10), "all_day": True}], NOW)
    unfolded = ics.replace("\r\n ", "")
    assert "SUMMARY:" + "Ä" * 120 in unfolded


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(routes.calendar_bp, url_prefix="/api/v2/calendar")
    return app.test_client()


def _db():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_feed_needs_a_valid_link(client):
    with patch.object(routes, "db_connection", return_value=_db()), patch.object(cf, "owner_of", return_value=None):
        response = client.get("/api/v2/calendar/feed/falsch.ics")
    assert response.status_code == 404


def test_feed_returns_calendar_without_login(client):
    with patch.object(routes, "db_connection", return_value=_db()), \
            patch.object(cf, "owner_of", return_value=(3, "middle", ["org", "sch"])), \
            patch.object(cf, "collect", return_value=[]) as collect:
        response = client.get("/api/v2/calendar/feed/geheim.ics")
    assert response.status_code == 200
    assert response.mimetype == "text/calendar"
    assert b"X-WR-CALNAME:Lehrercockpit" in response.data
    assert collect.call_args.args[1:] == (3, "middle", ["org", "sch"])


def test_creating_a_link_requires_login(client):
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        assert client.post("/api/v2/calendar", json={}).status_code == 401


def test_ics_reads_back_with_our_own_parser():
    from backend.ical_utils import parse_calendar

    events = cf._orgaplan_events({"upcoming": [{"isoDate": "2026-11-10", "general": "Gesamtkonferenz, Aula"}]}, "all")
    events += [{"uid": "sch", "title": "Projektwoche", "start": date(2026, 11, 11), "end": date(2026, 11, 13), "all_day": True}]
    parsed = sorted(parse_calendar(cf.build_ics(events, NOW)), key=lambda e: e.start)
    assert [p.title for p in parsed] == ["Gesamtkonferenz, Aula", "Projektwoche"]
    assert all(p.all_day for p in parsed)
    assert parsed[1].end.date() == date(2026, 11, 13)  # inclusive again after parsing


def test_sources_are_cleaned_and_ordered():
    assert cf.clean_sources(None) == ["org", "ka", "sch"]
    assert cf.clean_sources("sch,org") == ["org", "sch"]
    assert cf.clean_sources(["ka", "boese", "ka"]) == ["ka"]
    assert cf.clean_sources([]) == []


def test_collect_reads_only_chosen_sources_and_survives_a_failing_one():
    readers = {"org": MagicMock(side_effect=RuntimeError("PDF kaputt")),
               "ka": MagicMock(return_value=[{"uid": "ka"}]),
               "sch": MagicMock(return_value=[{"uid": "sch"}])}
    with patch.dict(cf._SOURCE_READERS, readers):
        events = cf.collect(MagicMock(), 3, "all", ["org", "sch"], NOW)
    assert events == [{"uid": "sch"}]
    readers["ka"].assert_not_called()


def test_at_least_one_source_is_needed(client):
    user = MagicMock(id=3, is_active=True, is_admin=False)
    with patch.object(backend.api.helpers, "get_current_user", return_value=user):
        assert client.post("/api/v2/calendar", json={"sources": []}).status_code == 422
        assert client.patch("/api/v2/calendar", json={"sources": ["nichts"]}).status_code == 422
