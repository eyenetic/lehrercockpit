"""Tests für backend/itslearning_module.py (Kalender-Abo + optionaler Login)."""
import dataclasses
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from backend import itslearning_module
from backend.itslearning_module import build_itslearning_payload, is_configured

NOW = datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)

FEED = (
    "BEGIN:VCALENDAR\r\n"
    "BEGIN:VEVENT\r\nUID:e1\r\nDTSTART:20260925T080000Z\r\nSUMMARY:Elternabend\r\nEND:VEVENT\r\n"
    "BEGIN:VEVENT\r\nUID:e2\r\nDTSTART:20260901T080000Z\r\nSUMMARY:Vergangen\r\nEND:VEVENT\r\n"
    "BEGIN:VEVENT\r\nUID:e3\r\nDTSTART:20260926T080000Z\r\nSTATUS:CANCELLED\r\nSUMMARY:Abgesagt\r\nEND:VEVENT\r\n"
    "BEGIN:VTODO\r\nUID:t1\r\nDUE:20260930T215900Z\r\nSUMMARY:Abgabe 10a\r\nEND:VTODO\r\n"
    "END:VCALENDAR\r\n"
)


@pytest.fixture(autouse=True)
def _clear_cache():
    itslearning_module._calendar_cache.clear()
    yield
    itslearning_module._calendar_cache.clear()


def _calendar_only(url="https://berlin.itslearning.com/cal.ics"):
    with patch.object(itslearning_module, "require_public_https_url", side_effect=lambda u: u), \
            patch.object(itslearning_module, "fetch_calendar_text", return_value=FEED):
        return build_itslearning_payload({"calendar_url": url}, NOW)


def test_not_configured_without_calendar_or_login():
    result = build_itslearning_payload({}, NOW)
    assert result == {"ok": True, "data": None, "configured": False, "error": "itslearning nicht konfiguriert"}
    assert is_configured({"username": "a"}) is False
    assert is_configured({"calendar_url": "https://x"}) is True


def test_calendar_only_returns_upcoming_entries_without_login():
    result = _calendar_only()
    assert result["configured"] is True
    data = result["data"]
    assert data["mode"] == "calendar"
    assert data["messages"] == []
    events = data["calendar"]["events"]
    assert [e["title"] for e in events] == ["Elternabend", "Abgabe 10a"]
    assert events[1]["kind"] == "todo"
    assert events[0]["id"].startswith("itslearning-cal-")


def test_calendar_errors_are_reported_not_raised():
    with patch.object(itslearning_module, "require_public_https_url", side_effect=lambda u: u), \
            patch.object(itslearning_module, "fetch_calendar_text", side_effect=OSError("down")):
        result = build_itslearning_payload({"calendar_url": "https://berlin.itslearning.com/c.ics"}, NOW)
    calendar = result["data"]["calendar"]
    assert calendar["ok"] is False
    assert calendar["events"] == []


def test_unsafe_calendar_url_is_rejected():
    result = build_itslearning_payload({"calendar_url": "http://127.0.0.1/cal.ics"}, NOW)
    assert result["data"]["calendar"]["ok"] is False


def test_login_uses_server_url_alias_and_keeps_calendar():
    @dataclasses.dataclass
    class _Result:
        source: dict = dataclasses.field(default_factory=lambda: {"id": "itslearning"})
        messages: list = dataclasses.field(default_factory=list)
        priorities: list = dataclasses.field(default_factory=list)
        mode: str = "live"
        note: str = ""

    captured = {}

    def fake_sync(settings, now):
        captured["base_url"] = settings.base_url
        return _Result()

    config = {"server_url": "https://schule.itslearning.com/index.aspx", "username": "u", "password": "p"}
    with patch("backend.itslearning_adapter.fetch_itslearning_sync", side_effect=fake_sync):
        result = build_itslearning_payload(config, NOW)
    assert captured["base_url"] == "https://schule.itslearning.com"
    assert result["data"]["mode"] == "live"
    assert "calendar" not in result["data"]
