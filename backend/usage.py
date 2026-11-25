"""Nutzung zählen – nur Tagessummen, keine Personen, keine IP-Adressen.

usage_counts hält je Tag und Kennzahl eine Zahl, z. B. (2026-11-25, "open", 14).
Kennzahlen:
    open, open:phone, open:desktop, open:app   Cockpit geöffnet (angemeldet)
    active                                      erste Öffnung einer Lehrkraft an diesem Tag
    invite                                      Einladungsseite geöffnet
    video:<id>:start, video:<id>:end           Erklärvideo gestartet / bis zum Ende angesehen

Für „active“ merkt sich users.last_counted_day nur den letzten Tag, an dem die
Lehrkraft gezählt wurde – nicht mehr als das ohnehin gespeicherte „zuletzt aktiv“.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
DEVICES = ("phone", "desktop", "app")
VIDEOS = ("lehrercockpit", "einrichtung")
MAX_DAYS = 90


def migrate(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_counts (
            day     DATE NOT NULL,
            metric  TEXT NOT NULL,
            value   INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (day, metric)
        )
        """
    )
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_counted_day DATE")


def today() -> date:
    return datetime.now(BERLIN).date()


def bump(conn, metric: str, day: date | None = None) -> None:
    conn.execute(
        "INSERT INTO usage_counts (day, metric, value) VALUES (%s, %s, 1) "
        "ON CONFLICT (day, metric) DO UPDATE SET value = usage_counts.value + 1",
        (day or today(), metric),
    )


def record_open(conn, user_id: int, device: str) -> None:
    day = today()
    bump(conn, "open", day)
    if device in DEVICES:
        bump(conn, f"open:{device}", day)
    first = conn.execute(
        "UPDATE users SET last_counted_day = %s WHERE id = %s "
        "AND (last_counted_day IS NULL OR last_counted_day < %s) RETURNING id",
        (day, user_id, day),
    ).fetchone()
    if first:
        bump(conn, "active", day)


def record_video(conn, video: str, ended: bool) -> bool:
    if video not in VIDEOS:
        return False
    bump(conn, f"video:{video}:{'end' if ended else 'start'}")
    return True


def summary(conn, days: int = 28) -> dict:
    """Daily numbers of the last `days` days plus this week and the week before (7-day totals)."""
    days = max(7, min(MAX_DAYS, int(days)))
    end = today()
    start = end - timedelta(days=days - 1)
    week = end - timedelta(days=6)
    before = week - timedelta(days=7)
    rows = conn.execute(
        "SELECT day, metric, value FROM usage_counts WHERE day >= %s AND day <= %s",
        (min(start, before), end),
    ).fetchall()
    by_day: dict[date, dict[str, int]] = {}
    for day, metric, value in rows:
        by_day.setdefault(day, {})[metric] = int(value)
    series = []
    for i in range(days):
        day = start + timedelta(days=i)
        series.append({"day": day.isoformat(), **by_day.get(day, {})})

    def total(metric: str, first: date, last: date) -> int:
        return sum(int(v) for d, m, v in rows if m == metric and first <= d <= last)

    metrics = ["open", "active", "invite", "open:phone", "open:desktop", "open:app"] + [
        f"video:{v}:{k}" for v in VIDEOS for k in ("start", "end")]
    teachers = conn.execute(
        "SELECT COUNT(*) FILTER (WHERE last_counted_day >= %s), "
        "       COUNT(*) FILTER (WHERE last_counted_day >= %s), "
        "       COUNT(*) FILTER (WHERE is_active) "
        "FROM users",
        (week, end - timedelta(days=27)),
    ).fetchone()
    return {
        "days": series,
        "week": {m: total(m, week, end) for m in metrics},
        "previous_week": {m: total(m, before, week - timedelta(days=1)) for m in metrics},
        "teachers": {"active_7": int(teachers[0] or 0), "active_28": int(teachers[1] or 0),
                     "accounts": int(teachers[2] or 0)},
        "since": _first_day(conn),
    }


def _first_day(conn) -> str | None:
    row = conn.execute("SELECT MIN(day) FROM usage_counts").fetchone()
    return row[0].isoformat() if row and row[0] else None
