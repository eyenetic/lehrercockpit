"""Tests für backend/classwork_sync.py (Klassenarbeitsplan aktuell halten)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend import classwork_cache, classwork_sync as cs
from backend.onedrive_share import OneDriveBlocked, OneDriveError

URL = "https://1drv.ms/x/c/abc/PLAN?e=1"
NOW = datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc)
META = {"name": "Plan.xlsx", "size": 10, "etag": "e1", "modified": "2026-09-22T18:00:00Z",
        "download_url": "https://dl.example/f"}


class _MemoryStore:
    def __init__(self):
        self.data = {}

    def read(self, path, default=None):
        return self.data.get(path.stem, default)

    def write(self, path, value):
        self.data[path.stem] = value


@pytest.fixture
def mem(monkeypatch):
    store = _MemoryStore()
    monkeypatch.setattr(cs, "store", store)
    monkeypatch.setattr(classwork_cache, "store", store)
    return store


def _parsed(file_bytes):
    return {"status": "ok", "structuredRows": [{"Klasse": "9b"}], "dataHash": file_bytes.decode()[:8]}


def test_server_sync_downloads_and_stores_plan(mem):
    with patch.object(cs, "resolve", return_value=dict(META)), \
            patch.object(cs, "download", return_value=(b"plan-v1", {k: v for k, v in META.items() if k != "download_url"})), \
            patch("backend.file_utils.parse_classwork_xlsx", side_effect=_parsed):
        assert cs.sync_from_server(URL, NOW) == "ok"
    cache = mem.data["classwork-cache"]
    assert cache["uploadSource"] == "onedrive"
    assert cache["sourceETag"] == "e1"
    assert cache["uploadedAt"] == "23.09.2026 08:00"  # Berlin time, not server UTC
    state = mem.data["classwork-sync"]
    assert state["last_result"] == "ok" and state["via"] == "server" and state["etag"] == "e1"


def test_unchanged_etag_skips_download(mem):
    mem.data["classwork-cache"] = {"status": "ok", "structuredRows": [1]}
    mem.data["classwork-sync"] = {"source_url": URL, "etag": "e1"}
    with patch.object(cs, "resolve", return_value=dict(META)), patch.object(cs, "download") as download:
        assert cs.sync_from_server(URL, NOW) == "unchanged"
    download.assert_not_called()
    assert mem.data["classwork-sync"]["last_success"] == NOW.isoformat()


def test_blocked_server_asks_browsers_once_stale(mem):
    with patch.object(cs, "resolve", side_effect=OneDriveBlocked("HTTP 403")):
        assert cs.sync_from_server(URL, NOW) == "blocked"
    info = cs.sync_info(URL, NOW)
    assert info["needs_browser"] is True  # never succeeded
    assert info["last_error"] == "HTTP 403"

    cs.record_browser_result(URL, {"etag": "e2"}, changed=True, now=NOW)
    assert cs.sync_info(URL, NOW + timedelta(hours=1))["needs_browser"] is False
    # Server blocked again later, and the last success is older than BROWSER_AFTER:
    with patch.object(cs, "resolve", side_effect=OneDriveBlocked("HTTP 403")):
        cs.sync_from_server(URL, NOW + timedelta(hours=2))
    assert cs.sync_info(URL, NOW + timedelta(hours=2))["needs_browser"] is False
    assert cs.sync_info(URL, NOW + cs.BROWSER_AFTER + timedelta(minutes=1))["needs_browser"] is True


def test_errors_are_recorded_not_raised(mem):
    with patch.object(cs, "resolve", side_effect=OneDriveError("Link weg")):
        assert cs.sync_from_server(URL, NOW) == "error"
    assert mem.data["classwork-sync"]["last_error"] == "Link weg"


def test_other_links_do_not_need_sync(mem):
    assert cs.sync_info("https://example.com/plan.xlsx", NOW) == {"onedrive": False, "needs_browser": False}
    assert cs.maybe_sync_in_background("https://example.com/plan.xlsx", NOW) is False


def test_background_sync_respects_interval(mem):
    mem.data["classwork-sync"] = {"source_url": URL, "last_attempt": (NOW - timedelta(minutes=10)).isoformat()}
    with patch.object(cs.threading, "Thread") as thread:
        assert cs.maybe_sync_in_background(URL, NOW) is False
        assert cs.maybe_sync_in_background(URL, NOW + cs.SERVER_INTERVAL) is True
    thread.return_value.start.assert_called_once()
    cs._sync_running = False


def test_changed_link_resets_state(mem):
    mem.data["classwork-sync"] = {"source_url": "https://1drv.ms/x/c/old", "etag": "old",
                                  "last_success": NOW.isoformat(), "last_result": "ok"}
    info = cs.sync_info(URL, NOW)
    assert info["etag"] == "" and info["last_success"] is None
