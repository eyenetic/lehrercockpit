"""End-to-end-Test für push_service.dispatch() gegen eine echte Datenbank."""
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from backend import push_service as ps
from backend.webpush import VapidConfig

MORNING = datetime(2026, 9, 23, 4, 45, tzinfo=timezone.utc)  # Mi 06:45 Berlin


@pytest.fixture
def db_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        pytest.skip("DATABASE_URL nicht gesetzt")
    return url


@pytest.fixture
def teacher(db_url):
    import psycopg
    from backend.migrations import _migrate_signals_and_push, run_migrations
    from backend.users.user_store import create_user

    conn = psycopg.connect(db_url)
    run_migrations(conn)
    _migrate_signals_and_push(conn)
    user = create_user(conn, "Push", "Test")
    ps.save_subscription(conn, user.id, f"https://push.example/sub/{user.id}", "p", "a", "UA",
                         {"morning": True, "weekly": True})
    conn.commit()
    yield user.id
    conn.execute("DELETE FROM users WHERE id = %s", (user.id,))
    conn.commit()
    conn.close()


@contextmanager
def _only_user(user_id):
    """dispatch() iterates over all subscriptions; restrict it to the test teacher."""
    original = ps._collect_modules
    modules = {"webuntis": {"ok": True, "data": {"events": [
        {"title": "Mathe 10b", "startsAt": "2026-09-23T08:00:00", "cancelled": False},
    ]}}}
    with patch.object(ps, "_collect_modules", side_effect=lambda uid: modules if uid == user_id else original(uid)):
        yield


@pytest.mark.db
def test_morning_digest_is_sent_once_per_day(teacher, db_url, monkeypatch):
    monkeypatch.setattr(ps, "vapid_config", lambda: VapidConfig("pub", "priv", "mailto:x@y.de"))
    sent = []
    with _only_user(teacher), patch.object(ps, "send", side_effect=lambda sub, payload, cfg: sent.append(
            (sub["endpoint"], payload)) or 201):
        first = ps.dispatch(MORNING)
        second = ps.dispatch(MORNING)

    mine = [p for endpoint, p in sent if endpoint.endswith(f"/{teacher}")]
    assert len(mine) == 1
    assert mine[0]["title"] == "Dein Tag – Mi 23.09."
    assert "1 Stunde, erste um 08:00." in mine[0]["body"]
    assert first["kinds"] == ["morning"]
    assert second["kinds"] == ["morning"]

    import psycopg
    with psycopg.connect(db_url) as conn:
        logged = conn.execute("SELECT kind FROM push_log WHERE user_id = %s", (teacher,)).fetchall()
        success = conn.execute("SELECT last_success_at FROM push_subscriptions WHERE user_id = %s",
                               (teacher,)).fetchone()[0]
    assert logged == [("morning",)]
    assert success is not None


@pytest.mark.db
def test_gone_subscription_is_removed(teacher, db_url, monkeypatch):
    from backend.webpush import SubscriptionGone

    monkeypatch.setattr(ps, "vapid_config", lambda: VapidConfig("pub", "priv", "mailto:x@y.de"))

    def gone(sub, payload, cfg):
        if sub["endpoint"].endswith(f"/{teacher}"):
            raise SubscriptionGone("410")
        return 201

    with _only_user(teacher), patch.object(ps, "send", side_effect=gone):
        ps.dispatch(MORNING)

    import psycopg
    with psycopg.connect(db_url) as conn:
        remaining = conn.execute("SELECT COUNT(*) FROM push_subscriptions WHERE user_id = %s",
                                 (teacher,)).fetchone()[0]
    assert remaining == 0
