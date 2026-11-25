"""Nutzung zählen: nur Tagessummen, keine IP, keine Personen."""
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import backend.api.helpers
import backend.api.usage_routes as usage_routes
from backend import usage

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(usage_routes.usage_bp, url_prefix="/api/v2/usage")
    return app.test_client()


def _db(conn=None):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=conn or MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _user(admin=False):
    return MagicMock(id=7, is_active=True, is_admin=admin)


def _metrics(conn):
    return [c.args[1][1] for c in conn.execute.call_args_list if "INSERT INTO usage_counts" in c.args[0]]


def test_open_counts_device_and_first_visit_of_the_day():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (7,)        # first visit today
    usage.record_open(conn, 7, "phone")
    assert _metrics(conn) == ["open", "open:phone", "active"]

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None         # already counted today
    usage.record_open(conn, 7, "toaster")                         # unknown device: only "open"
    assert _metrics(conn) == ["open"]


def test_only_known_videos_are_counted():
    conn = MagicMock()
    assert usage.record_video(conn, "lehrercockpit", ended=True) is True
    assert usage.record_video(conn, "<script>", ended=False) is False
    assert _metrics(conn) == ["video:lehrercockpit:end"]


def test_events_need_the_right_shape(client):
    conn = MagicMock()
    with patch.object(usage_routes, "db_connection", return_value=_db(conn)), \
            patch.object(backend.api.helpers, "get_current_user", return_value=None):
        assert client.post("/api/v2/usage/event", json={"event": "open"}).status_code == 401
        assert client.post("/api/v2/usage/event", json={"event": "invite"}).status_code == 204
        assert client.post("/api/v2/usage/event", json={"event": "video", "video": "einrichtung"}).status_code == 204
        assert client.post("/api/v2/usage/event", json={"event": "video", "video": "x"}).status_code == 400
        assert client.post("/api/v2/usage/event", json={"event": "klick"}).status_code == 400
    assert _metrics(conn) == ["invite", "video:einrichtung:start"]


def test_counting_errors_never_reach_the_page(client):
    with patch.object(usage_routes, "db_connection", side_effect=RuntimeError("DB weg")):
        assert client.post("/api/v2/usage/event", json={"event": "invite"}).status_code == 204


def test_summary_is_for_admins_only(client):
    with patch.object(backend.api.helpers, "get_current_user", return_value=_user()):
        assert client.get("/api/v2/usage/admin").status_code == 403
    with patch.object(backend.api.helpers, "get_current_user", return_value=_user(admin=True)), \
            patch.object(usage_routes, "db_connection", return_value=_db()), \
            patch.object(usage, "summary", return_value={"days": []}) as summary:
        resp = client.get("/api/v2/usage/admin?days=14")
    assert resp.status_code == 200 and summary.call_args.args[1] == 14


def test_summary_adds_up_days_and_weeks():
    conn = MagicMock()
    today = date(2026, 11, 25)
    rows = [(date(2026, 11, 25), "open", 5), (date(2026, 11, 20), "open", 3),
            (date(2026, 11, 15), "open", 4), (date(2026, 11, 25), "video:lehrercockpit:start", 2)]
    conn.execute.return_value.fetchall.return_value = rows
    conn.execute.return_value.fetchone.side_effect = [(3, 5, 9), (date(2026, 11, 1),)]
    with patch.object(usage, "today", return_value=today):
        data = usage.summary(conn, 28)
    assert len(data["days"]) == 28 and data["days"][-1] == {"day": "2026-11-25", "open": 5, "video:lehrercockpit:start": 2}
    assert data["week"]["open"] == 8 and data["previous_week"]["open"] == 4
    assert data["teachers"] == {"active_7": 3, "active_28": 5, "accounts": 9}
    assert data["since"] == "2026-11-01"


def test_no_ip_addresses_are_stored():
    source = (ROOT / "backend" / "usage.py").read_text() + (ROOT / "backend" / "api" / "usage_routes.py").read_text()
    assert "remote_addr" not in source and "X-Forwarded-For" not in source
