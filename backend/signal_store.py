"""Per-teacher state of signals: new/changed, seen, done, hidden, snoozed.

Rules
- The very first sync of a teacher records everything as already seen, so the
  "Neu & geändert" list starts empty instead of listing the whole school year.
- A changed fingerprint reopens an item and marks it unseen ("geändert").
- Items count as new for NEW_MAX_AGE at most, even if never acknowledged.
"""
from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from typing import Any

from .ical_utils import BERLIN

NEW_MAX_AGE = timedelta(days=7)
CLEANUP_AFTER = timedelta(days=45)
ACTIONS = ("seen", "done", "hide", "snooze", "reopen")
MAX_PREFERRED_CLASSES = 40


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _next_morning(now: datetime) -> datetime:
    """06:00 school time on the next day (end of a "später")."""
    local = now.astimezone(BERLIN)
    return datetime.combine(local.date() + timedelta(days=1), time(6, 0), tzinfo=BERLIN)


def _is_unseen(row: dict[str, Any], now: datetime) -> bool:
    if row["seen_at"] is not None or row["status"] != "open":
        return False
    if row["snoozed_until"] is not None and row["snoozed_until"] > now:
        return False
    since = row["changed_at"] or row["first_seen_at"]
    return since is not None and now - since <= NEW_MAX_AGE


def sync_signals(conn, user_id: int, signals: list[dict], now: datetime) -> list[dict]:
    """Record current signals and return them with their state attached."""
    rows = conn.execute(
        "SELECT signal_id, fingerprint, first_seen_at, changed_at, seen_at, status, snoozed_until "
        "FROM user_signal_state WHERE user_id = %s",
        (user_id,),
    ).fetchall()
    known = {
        r[0]: {"fingerprint": r[1], "first_seen_at": r[2], "changed_at": r[3], "seen_at": r[4],
               "status": r[5], "snoozed_until": r[6]}
        for r in rows
    }
    baseline = not known

    result = []
    unchanged_ids = []
    for signal in signals:
        row = known.get(signal["id"])
        if row is None:
            row = {"fingerprint": signal["fingerprint"], "first_seen_at": now, "changed_at": None,
                   "seen_at": now if baseline else None, "status": "open", "snoozed_until": None}
            conn.execute(
                "INSERT INTO user_signal_state (user_id, signal_id, fingerprint, first_seen_at, seen_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (user_id, signal_id) DO NOTHING",
                (user_id, signal["id"], signal["fingerprint"], now, row["seen_at"], now),
            )
        elif row["fingerprint"] != signal["fingerprint"]:
            row.update({"fingerprint": signal["fingerprint"], "changed_at": now, "seen_at": None,
                        "status": "open", "snoozed_until": None})
            conn.execute(
                "UPDATE user_signal_state SET fingerprint = %s, changed_at = %s, seen_at = NULL, "
                "status = 'open', snoozed_until = NULL, updated_at = %s "
                "WHERE user_id = %s AND signal_id = %s",
                (signal["fingerprint"], now, now, user_id, signal["id"]),
            )
        else:
            unchanged_ids.append(signal["id"])
        result.append({**signal, "state": {
            "new": _is_unseen(row, now) and row["changed_at"] is None,
            "changed": _is_unseen(row, now) and row["changed_at"] is not None,
            "status": row["status"],
            "snoozed_until": _iso(row["snoozed_until"]),
            "first_seen_at": _iso(row["first_seen_at"]),
        }})

    if unchanged_ids:  # keep still-present items from being cleaned up
        conn.execute(
            "UPDATE user_signal_state SET updated_at = %s WHERE user_id = %s AND signal_id = ANY(%s)",
            (now, user_id, unchanged_ids),
        )
    conn.execute(
        "DELETE FROM user_signal_state WHERE user_id = %s AND updated_at < %s",
        (user_id, now - CLEANUP_AFTER),
    )
    return result


def apply_action(conn, user_id: int, signal_id: str, action: str, now: datetime) -> bool:
    """seen / done / hide / snooze (until tomorrow 06:00) / reopen. False if unknown."""
    if action not in ACTIONS:
        raise ValueError(action)
    updates = {
        "seen": ("seen_at = %s", (now,)),
        "done": ("status = 'done', seen_at = %s", (now,)),
        "hide": ("status = 'hidden', seen_at = %s", (now,)),
        "snooze": ("snoozed_until = %s", (_next_morning(now),)),
        "reopen": ("status = 'open', snoozed_until = NULL", ()),
    }
    clause, params = updates[action]
    result = conn.execute(
        f"UPDATE user_signal_state SET {clause}, updated_at = %s WHERE user_id = %s AND signal_id = %s",
        (*params, now, user_id, signal_id),
    )
    return result.rowcount > 0


def mark_seen(conn, user_id: int, signal_ids: list[str], now: datetime) -> int:
    if not signal_ids:
        return 0
    result = conn.execute(
        "UPDATE user_signal_state SET seen_at = %s, updated_at = %s "
        "WHERE user_id = %s AND signal_id = ANY(%s) AND seen_at IS NULL",
        (now, now, user_id, list(signal_ids)),
    )
    return result.rowcount


def load_prefs(conn, user_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT value FROM system_settings WHERE key = %s",
                       (f"signal_prefs_{user_id}",)).fetchone()
    value = row[0] if row else {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = {}
    return value if isinstance(value, dict) else {}


def save_prefs(conn, user_id: int, prefs: dict[str, Any]) -> None:
    import psycopg.types.json as _pjson

    conn.execute(
        "INSERT INTO system_settings (key, value, updated_at) VALUES (%s, %s, NOW()) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
        (f"signal_prefs_{user_id}", _pjson.Jsonb(prefs)),
    )


def build_payload(items: list[dict], classes: set[str], now: datetime) -> dict[str, Any]:
    """Response section for the dashboard: all items plus the ordered "new" list."""
    fresh = [i for i in items if i["state"]["new"] or i["state"]["changed"]]
    fresh.sort(key=lambda i: (-i["importance"], i["date"] or "9999", i["title"]))
    return {
        "items": items,
        "new_ids": [i["id"] for i in fresh],
        "new_count": len(fresh),
        "classes": sorted(classes),
        "classes_known": bool(classes),
        "generated_at": now.isoformat(),
    }
