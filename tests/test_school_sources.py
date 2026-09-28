"""Tests für schulweite Quellen: Schulkalender, Einstellungs-Übernahme, alte Endpunkte."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend import school_calendar, school_sources

NOW = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)  # Mo 08:00 Berlin

ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:fahrt
DTSTART;VALUE=DATE:20260927
DTEND;VALUE=DATE:20261003
SUMMARY:Kl. 10a & 10c Sprachenkulturfahrt nach Bilbao
END:VEVENT
BEGIN:VEVENT
UID:gestern
DTSTART;VALUE=DATE:20260927
DTEND;VALUE=DATE:20260928
SUMMARY:Gestern vorbei
END:VEVENT
BEGIN:VEVENT
UID:fk
DTSTART;TZID=Europe/Berlin:20261008T153000
DTEND;TZID=Europe/Berlin:20261008T170000
SUMMARY:FK Fremdsprachen
LOCATION:R 201
END:VEVENT
BEGIN:VEVENT
UID:ferien
DTSTART;VALUE=DATE:20261019
DTEND;VALUE=DATE:20261031
SUMMARY:Herbstferien
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture(autouse=True)
def _no_cache():
    school_calendar._cache.clear()
    yield
    school_calendar._cache.clear()


def _calendar():
    with patch.object(school_calendar, "fetch_calendar_text", return_value=ICS), \
            patch.object(school_calendar, "require_public_https_url", side_effect=lambda url: url):
        return school_calendar.build_calendar("https://schule.de/events/?ical=1", NOW)


def test_school_calendar_today_and_upcoming():
    result = _calendar()
    data = result["data"]
    assert result["ok"] is True
    assert [e["uid"] for e in data["events"]] == ["fahrt", "fk", "ferien"]  # yesterday's event is gone
    assert [e["uid"] for e in data["today_events"]] == ["fahrt"]
    trip = data["events"][0]
    assert trip["start"] == "2026-09-27" and trip["end"] == "2026-10-02" and trip["running"] is True
    fk = data["events"][1]
    assert fk["time_label"] == "15:30–17:00" and fk["location"] == "R 201"
    assert fk["start"].startswith("2026-10-08T15:30")
    assert [e["uid"] for e in data["upcoming_events"]] == ["fk"]  # next 14 days, starting tomorrow


def test_school_calendar_errors_do_not_raise():
    with patch.object(school_calendar, "fetch_calendar_text", side_effect=OSError("offline")), \
            patch.object(school_calendar, "require_public_https_url", side_effect=lambda url: url):
        result = school_calendar.build_calendar("https://schule.de/feed", NOW)
    assert result["ok"] is False and "nicht erreichbar" in result["data"]["error"]


# ── Settings migration ───────────────────────────────────────────────────────

class _Settings:
    def __init__(self, values):
        self.values = dict(values)
        self.conn = MagicMock()
        self.conn.execute.side_effect = self._execute

    def _execute(self, sql, params=()):
        if sql.startswith("DELETE FROM system_settings WHERE key = %s"):
            self.values.pop(params[0], None)
        elif sql.startswith("DELETE FROM system_settings WHERE key IN"):
            for key in ("orgaplan_cache", "orgaplan_cache_ts", "orgaplan_cache_url"):
                self.values.pop(key, None)
        return MagicMock()

    def get(self, conn, key, default=None):
        return self.values.get(key, default)

    def set(self, conn, key, value):
        self.values[key] = value


def _migrate(values):
    store = _Settings(values)
    with patch.object(school_sources, "get_system_setting", side_effect=store.get), \
            patch("backend.admin.admin_service.get_system_setting", side_effect=store.get), \
            patch("backend.admin.admin_service.set_system_setting", side_effect=store.set):
        school_sources.migrate_legacy_settings(store.conn)
    return store.values


def test_migration_keeps_the_link_in_use_and_offers_the_other_one():
    values = _migrate({"klassenarbeitsplan_url": "https://1drv.ms/x/alt",
                       "classwork_url": "https://1drv.ms/x/neu",
                       "orgaplan_pdf_url": "https://schule.de/wp-content/uploads/2026/03/Orgaplan-2025_26.pdf",
                       "orgaplan_cache": {"x": 1}})
    assert values["klassenarbeitsplan_url"] == "https://1drv.ms/x/alt"
    assert values["klassenarbeitsplan_url_candidate"] == "https://1drv.ms/x/neu"
    assert "classwork_url" not in values and "orgaplan_cache" not in values
    assert values["orgaplan_source"] == {"mode": "auto", "site": "https://schule.de", "query": "Orgaplan"}


def test_migration_moves_the_admin_link_when_nothing_else_is_set():
    values = _migrate({"classwork_url": "https://1drv.ms/x/neu"})
    assert values["klassenarbeitsplan_url"] == "https://1drv.ms/x/neu"
    assert "klassenarbeitsplan_url_candidate" not in values


def test_migration_is_idempotent():
    first = _migrate({"klassenarbeitsplan_url": "https://1drv.ms/x/a", "classwork_url": "https://1drv.ms/x/a"})
    assert _migrate(first) == first


# ── Legacy endpoints and static files ────────────────────────────────────────

def test_legacy_endpoints_are_closed_when_hosted():
    import app as app_module

    with patch.object(app_module, "_HOSTED", True):
        client = app_module.app.test_client()
        for path in ("/api/classwork", "/api/dashboard", "/api/grades", "/api/notes", "/api/mail",
                     "/api/local-settings/grades"):
            assert client.get(path).status_code == 404, path
        assert client.get("/api/health").status_code == 200
    assert app_module._legacy_disabled("/api/v2/dashboard/data") is False


@pytest.mark.parametrize("path,served", [
    ("index.html", True), ("src/app.js", True), ("icons/icon-192.png", True), ("data/mock-dashboard.js", True),
    ("app.py", False), ("backend/config.py", False), ("docs/operations_runbook.md", False),
    (".git/HEAD", False), ("requirements.txt", False), ("data/mock-dashboard.json", False),
    ("src/../app.py", False), ("tests/test_crypto.py", False),
])
def test_only_frontend_files_are_served(path, served):
    import app as app_module

    assert app_module.is_frontend_asset(path) is served
