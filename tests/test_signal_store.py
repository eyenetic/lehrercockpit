"""Tests für backend/signal_store.py – benötigt echte DB-Connection."""
import os
from datetime import datetime, timedelta, timezone

import pytest

from backend import signal_store as store

NOW = datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_conn():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        pytest.skip("DATABASE_URL nicht gesetzt")
    import psycopg
    from backend.migrations import _migrate_signals_and_push, run_migrations

    conn = psycopg.connect(db_url)
    run_migrations(conn)
    _migrate_signals_and_push(conn)
    conn.commit()
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture
def user_id(db_conn):
    from backend.users.user_store import create_user
    return create_user(db_conn, "Signal", "Test").id


def _signal(sid, fingerprint="f1", importance=1, date="2026-09-24"):
    return {"id": sid, "kind": "termin", "title": sid, "date": date, "importance": importance,
            "fingerprint": fingerprint}


def _state(items, sid):
    return next(i["state"] for i in items if i["id"] == sid)


@pytest.mark.db
def test_first_sync_is_a_silent_baseline(db_conn, user_id):
    items = store.sync_signals(db_conn, user_id, [_signal("a"), _signal("b")], NOW)
    assert not any(i["state"]["new"] for i in items)


@pytest.mark.db
def test_new_and_changed_items(db_conn, user_id):
    store.sync_signals(db_conn, user_id, [_signal("a")], NOW)
    later = NOW + timedelta(hours=1)
    items = store.sync_signals(db_conn, user_id, [_signal("a", "f2"), _signal("b")], later)
    assert _state(items, "a") == {**_state(items, "a"), "changed": True, "new": False}
    assert _state(items, "b")["new"] is True
    payload = store.build_payload(items, {"10B"}, later)
    assert payload["new_count"] == 2 and payload["classes"] == ["10B"]


@pytest.mark.db
def test_actions_remove_items_from_the_new_list(db_conn, user_id):
    store.sync_signals(db_conn, user_id, [_signal("seed")], NOW)
    signals = [_signal("a"), _signal("b"), _signal("c"), _signal("d")]
    store.sync_signals(db_conn, user_id, signals, NOW)
    assert store.apply_action(db_conn, user_id, "a", "done", NOW)
    assert store.apply_action(db_conn, user_id, "b", "hide", NOW)
    assert store.apply_action(db_conn, user_id, "c", "snooze", NOW)
    assert store.mark_seen(db_conn, user_id, ["d"], NOW) == 1
    items = store.sync_signals(db_conn, user_id, signals, NOW + timedelta(minutes=5))
    assert not any(i["state"]["new"] for i in items)
    assert _state(items, "a")["status"] == "done"
    tomorrow = NOW + timedelta(days=1, hours=1)  # after 06:00 Berlin the next day
    items = store.sync_signals(db_conn, user_id, signals, tomorrow)
    assert _state(items, "c")["new"] is True  # snooze is over
    assert store.apply_action(db_conn, user_id, "missing", "done", NOW) is False


@pytest.mark.db
def test_changes_reopen_done_items(db_conn, user_id):
    store.sync_signals(db_conn, user_id, [_signal("seed")], NOW)
    store.sync_signals(db_conn, user_id, [_signal("a")], NOW)
    store.apply_action(db_conn, user_id, "a", "done", NOW)
    items = store.sync_signals(db_conn, user_id, [_signal("a", "moved")], NOW + timedelta(hours=2))
    assert _state(items, "a")["changed"] is True
    assert _state(items, "a")["status"] == "open"


@pytest.mark.db
def test_new_items_expire_after_a_week(db_conn, user_id):
    store.sync_signals(db_conn, user_id, [_signal("seed")], NOW)
    store.sync_signals(db_conn, user_id, [_signal("a")], NOW)
    items = store.sync_signals(db_conn, user_id, [_signal("a")], NOW + store.NEW_MAX_AGE + timedelta(hours=1))
    assert _state(items, "a")["new"] is False


@pytest.mark.db
def test_preferences_round_trip(db_conn, user_id):
    assert store.load_prefs(db_conn, user_id) == {}
    store.save_prefs(db_conn, user_id, {"classes": ["10B", "Q1"]})
    assert store.load_prefs(db_conn, user_id) == {"classes": ["10B", "Q1"]}
