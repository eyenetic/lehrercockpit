"""Push digests: morning overview on school days, week preview on Sunday evening.

dispatch() is triggered by an external scheduler (GitHub Actions, see
.github/workflows/push-dispatch.yml). It decides from Berlin local time what is
due and sends each digest at most once per teacher and day (push_log).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .ical_utils import BERLIN
from .signals import KIND_LABELS
from .webpush import SubscriptionGone, VapidConfig, send, vapid_config

MORNING_WINDOW = (6, 30), (9, 30)   # school days, local time
WEEKLY_WINDOW = (17, 0), (21, 0)    # Sunday, local time
MAX_FAILURES = 5
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _in_window(local: datetime, window) -> bool:
    (start_h, start_m), (end_h, end_m) = window
    minutes = local.hour * 60 + local.minute
    return start_h * 60 + start_m <= minutes < end_h * 60 + end_m


def due_kinds(now: datetime) -> list[str]:
    local = now.astimezone(BERLIN)
    kinds = []
    if local.weekday() < 5 and _in_window(local, MORNING_WINDOW):
        kinds.append("morning")
    if local.weekday() == 6 and _in_window(local, WEEKLY_WINDOW):
        kinds.append("weekly")
    return kinds


# ── Subscriptions ─────────────────────────────────────────────────────────────

def save_subscription(conn, user_id: int, endpoint: str, p256dh: str, auth: str,
                      user_agent: str, prefs: dict[str, bool]) -> None:
    import psycopg.types.json as _pjson

    conn.execute(
        """
        INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, user_agent, prefs)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (endpoint) DO UPDATE SET
            user_id = EXCLUDED.user_id, p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth,
            user_agent = EXCLUDED.user_agent, prefs = EXCLUDED.prefs, failure_count = 0
        """,
        (user_id, endpoint, p256dh, auth, user_agent[:300], _pjson.Jsonb(prefs)),
    )


def delete_subscription(conn, user_id: int, endpoint: str) -> bool:
    result = conn.execute("DELETE FROM push_subscriptions WHERE user_id = %s AND endpoint = %s",
                          (user_id, endpoint))
    return result.rowcount > 0


def user_subscriptions(conn, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, endpoint, p256dh, auth, prefs FROM push_subscriptions WHERE user_id = %s",
        (user_id,),
    ).fetchall()
    return [_row(r) for r in rows]


def _row(r) -> dict[str, Any]:
    prefs = r[4] if isinstance(r[4], dict) else json.loads(r[4] or "{}")
    return {"id": r[0], "endpoint": r[1], "p256dh": r[2], "auth": r[3], "prefs": prefs}


def _deliver(conn, subscriptions: list[dict], payload: dict, config: VapidConfig) -> int:
    """Send to each subscription; forget gone ones, count failures. Returns successes."""
    delivered = 0
    for sub in subscriptions:
        try:
            status = send(sub, payload, config)
        except SubscriptionGone:
            conn.execute("DELETE FROM push_subscriptions WHERE id = %s", (sub["id"],))
            continue
        except Exception:
            status = 0
        if 200 <= status < 300:
            delivered += 1
            conn.execute("UPDATE push_subscriptions SET last_success_at = NOW(), failure_count = 0 "
                         "WHERE id = %s", (sub["id"],))
        else:
            conn.execute("UPDATE push_subscriptions SET failure_count = failure_count + 1 WHERE id = %s",
                         (sub["id"],))
            conn.execute("DELETE FROM push_subscriptions WHERE id = %s AND failure_count >= %s",
                         (sub["id"], MAX_FAILURES))
    return delivered


def send_test(conn, user_id: int, config: VapidConfig) -> int:
    payload = {"title": "Lehrercockpit", "body": "Push-Nachrichten funktionieren auf diesem Gerät. ✓",
               "url": "/", "tag": "test"}
    return _deliver(conn, user_subscriptions(conn, user_id), payload, config)


# ── Digest content ────────────────────────────────────────────────────────────

def _lessons_today(modules: dict, today: date) -> list[dict]:
    result = modules.get("webuntis") or {}
    events = ((result.get("data") or {}).get("events") or []) if result.get("ok") else []
    lessons = []
    for event in events:
        try:
            start = datetime.fromisoformat(str(event.get("startsAt")).replace("Z", "+00:00"))
        except ValueError:
            continue
        start = start.replace(tzinfo=BERLIN) if start.tzinfo is None else start.astimezone(BERLIN)
        if start.date() == today:
            lessons.append({"start": start, "title": event.get("title", ""), "cancelled": event.get("cancelled")})
    return sorted(lessons, key=lambda lesson: lesson["start"])


def morning_digest(modules: dict, items: list[dict], now: datetime) -> dict | None:
    """Notification payload for today's overview, or None if there is nothing to say."""
    local = now.astimezone(BERLIN)
    today = local.date()
    lines = []

    lessons = [lesson for lesson in _lessons_today(modules, today) if not lesson["cancelled"]]
    if lessons:
        lines.append(f"{len(lessons)} Stunde{'n' if len(lessons) != 1 else ''}, erste um {lessons[0]['start']:%H:%M}.")

    todays = [i for i in items if i.get("date") == today.isoformat()
              and i["state"]["status"] == "open" and i["kind"] in ("entfall", "klassenarbeit", "frist", "termin")]
    todays.sort(key=lambda i: -i["importance"])
    for item in todays[:2]:
        lines.append(f"{KIND_LABELS[item['kind']]}: {item['title']}")

    fresh = [i for i in items if i["state"]["new"] or i["state"]["changed"]]
    if fresh:
        lines.append(f"{len(fresh)} neue{'r' if len(fresh) == 1 else ''} Eintr{'ag' if len(fresh) == 1 else 'äge'} seit gestern.")

    if not lines:
        return None
    return {"title": f"Dein Tag – {WEEKDAYS[today.weekday()]} {today:%d.%m.}", "body": "\n".join(lines),
            "url": "/", "tag": f"morning-{today.isoformat()}"}


def weekly_digest(items: list[dict], now: datetime) -> dict | None:
    """Preview of the coming school week (Mon–Fri)."""
    local = now.astimezone(BERLIN).date()
    monday = local + timedelta(days=(7 - local.weekday()) % 7 or 7)
    friday = monday + timedelta(days=4)
    week = [i for i in items if i.get("date") and monday.isoformat() <= i["date"] <= friday.isoformat()
            and i["state"]["status"] == "open" and i["kind"] in ("klassenarbeit", "termin", "frist", "entfall")]
    if not week:
        return None
    lines = []
    for kind in ("klassenarbeit", "frist", "termin", "entfall"):
        of_kind = [i for i in week if i["kind"] == kind]
        if not of_kind:
            continue
        singular, plural = {"klassenarbeit": ("Klassenarbeit", "Klassenarbeiten"), "frist": ("Frist", "Fristen"),
                            "termin": ("Termin", "Termine"), "entfall": ("Entfall", "Entfälle")}[kind]
        label = singular if len(of_kind) == 1 else plural
        examples = ", ".join(
            f"{i['title']} ({WEEKDAYS[date.fromisoformat(i['date']).weekday()]})" for i in of_kind[:2]
        )
        lines.append(f"{len(of_kind)} {label}: {examples}")
    return {"title": f"Nächste Woche ({monday:%d.%m.}–{friday:%d.%m.})", "body": "\n".join(lines[:4]),
            "url": "/", "tag": f"weekly-{monday.isoformat()}"}


# ── Dispatch ─────────────────────────────────────────────────────────────────

def _collect_modules(user_id: int) -> dict:
    """Module data for one teacher outside of a request (same fetchers as the dashboard)."""
    from .api import dashboard_routes as dr

    fetchers = {
        "webuntis": lambda: dr._fetch_webuntis_data(user_id),
        "itslearning": lambda: dr._fetch_itslearning_data(user_id),
        "orgaplan": dr._fetch_orgaplan_data,
        "klassenarbeitsplan": dr._fetch_klassenarbeitsplan_data,
        "nextcloud": lambda: dr._fetch_nextcloud_data(user_id),
    }
    modules = {}
    for module_id, fetch in fetchers.items():
        try:
            modules[module_id] = fetch()
        except Exception:
            modules[module_id] = {"ok": False}
    return modules


def dispatch(now: datetime | None = None) -> dict[str, Any]:
    """Send all due digests. Returns a summary for the scheduler's log."""
    from .db import db_connection
    from .signal_store import load_prefs, sync_signals
    from .signals import build_signals

    now = now or datetime.now(timezone.utc)
    config = vapid_config()
    kinds = due_kinds(now)
    summary: dict[str, Any] = {"kinds": kinds, "sent": 0, "skipped": 0, "users": 0}
    if config is None or not kinds:
        summary["reason"] = "Push nicht konfiguriert" if config is None else "Kein Versandfenster"
        return summary

    today = now.astimezone(BERLIN).date()
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT id, user_id, endpoint, p256dh, auth, prefs FROM push_subscriptions ORDER BY user_id"
        ).fetchall()
        sent_rows = conn.execute("SELECT user_id, kind FROM push_log WHERE day = %s", (today,)).fetchall()
    already = {(r[0], r[1]) for r in sent_rows}
    by_user: dict[int, list[dict]] = {}
    for r in rows:
        sub = _row((r[0], r[2], r[3], r[4], r[5]))
        by_user.setdefault(r[1], []).append(sub)

    for user_id, subs in by_user.items():
        wanted = [k for k in kinds if (user_id, k) not in already
                  and any(s["prefs"].get(k, True) for s in subs)]
        if not wanted:
            continue
        summary["users"] += 1
        modules = _collect_modules(user_id)
        with db_connection() as conn:
            prefs = load_prefs(conn, user_id)
        signals, _classes = build_signals(modules, now, prefs.get("classes") or [])
        with db_connection() as conn:
            items = sync_signals(conn, user_id, signals, now)
            for kind in wanted:
                payload = morning_digest(modules, items, now) if kind == "morning" else weekly_digest(items, now)
                # Log even when there was nothing to say, so the next run skips this user.
                conn.execute("INSERT INTO push_log (user_id, kind, day) VALUES (%s, %s, %s) "
                             "ON CONFLICT DO NOTHING", (user_id, kind, today))
                if payload is None:
                    summary["skipped"] += 1
                    continue
                targets = [s for s in subs if s["prefs"].get(kind, True)]
                summary["sent"] += _deliver(conn, targets, payload, config)
    return summary
