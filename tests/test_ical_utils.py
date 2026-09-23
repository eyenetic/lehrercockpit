"""Tests für backend/ical_utils.py (iCal-Parser für WebUntis/itslearning/Schulkalender)."""
from datetime import datetime, timedelta

from backend.ical_utils import BERLIN, entries_between, parse_calendar


def _cal(*components: str) -> str:
    return "BEGIN:VCALENDAR\r\n" + "".join(components) + "END:VCALENDAR\r\n"


def _event(*lines: str) -> str:
    return "BEGIN:VEVENT\r\n" + "".join(line + "\r\n" for line in lines) + "END:VEVENT\r\n"


def test_windows_timezone_is_mapped_to_berlin():
    entries = parse_calendar(_cal(_event(
        "UID:1",
        'DTSTART;TZID="W. Europe Standard Time":20260925T080000',
        'DTEND;TZID="W. Europe Standard Time":20260925T093000',
        "SUMMARY:Mathe",
    )))
    assert entries[0].start == datetime(2026, 9, 25, 8, 0, tzinfo=BERLIN)
    assert entries[0].end == datetime(2026, 9, 25, 9, 30, tzinfo=BERLIN)
    assert entries[0].all_day is False


def test_utc_time_is_converted_and_duration_applied():
    entries = parse_calendar(_cal(_event("UID:2", "DTSTART:20260924T060000Z", "DURATION:PT45M", "SUMMARY:UTC")))
    assert entries[0].start == datetime(2026, 9, 24, 8, 0, tzinfo=BERLIN)
    assert entries[0].end - entries[0].start == timedelta(minutes=45)


def test_date_values_are_all_day_with_inclusive_end():
    entries = parse_calendar(_cal(_event(
        "UID:3", "DTSTART;VALUE=DATE:20260926", "DTEND;VALUE=DATE:20260927", "SUMMARY:Ganztag",
    )))
    entry = entries[0]
    assert entry.all_day is True
    assert entry.start.date() == entry.end.date()


def test_midnight_without_time_is_treated_as_all_day():
    entries = parse_calendar(_cal(_event(
        "UID:4",
        "DTSTART;TZID=Europe/Berlin:20260930T000000",
        "DTEND;TZID=Europe/Berlin:20260930T000000",
        "SUMMARY:Konferenz",
    )))
    assert entries[0].all_day is True
    assert entries[0].end.date() == entries[0].start.date()


def test_folded_lines_escapes_and_quoted_colons():
    entries = parse_calendar(_cal(_event(
        "UID:5",
        "DTSTART:20260925T080000",
        "SUMMARY:Abgabe\\, Kapitel 3\\; Teil 2",
        "DESCRIPTION:Zeile 1\\nZeile 2 mit langem",
        "  Text",
        'LOCATION;ALTREP="http://x.example/a:b":Raum 204',
    )))
    entry = entries[0]
    assert entry.title == "Abgabe, Kapitel 3; Teil 2"
    assert entry.description == "Zeile 1\nZeile 2 mit langem Text"
    assert entry.location == "Raum 204"


def test_vtodo_uses_due_date():
    text = _cal("BEGIN:VTODO\r\nUID:t1\r\nDTSTART:20260920T080000Z\r\nDUE:20260930T215900Z\r\nSUMMARY:Aufgabe\r\nEND:VTODO\r\n")
    entry = parse_calendar(text)[0]
    assert entry.kind == "todo"
    assert entry.start == datetime(2026, 9, 30, 23, 59, tzinfo=BERLIN)
    assert entry.all_day is False


def test_entries_are_sorted_and_windowed():
    entries = parse_calendar(_cal(
        _event("UID:b", "DTSTART:20261010T080000", "SUMMARY:Später"),
        _event("UID:a", "DTSTART:20260925T080000", "SUMMARY:Früher"),
    ))
    assert [e.uid for e in entries] == ["a", "b"]
    window = entries_between(entries, datetime(2026, 9, 24, tzinfo=BERLIN), datetime(2026, 10, 1, tzinfo=BERLIN))
    assert [e.uid for e in window] == ["a"]


def test_invalid_components_are_skipped():
    entries = parse_calendar(_cal(_event("UID:x", "SUMMARY:ohne Datum"), _event("UID:y", "DTSTART:kaputt")))
    assert entries == []
