"""„Neu im Cockpit“: welche Neuigkeit gerade gilt und wer sie schon gesehen hat.

Der Text steht in src/features/news.js. Für eine neue Neuigkeit dort und hier
dieselbe ID setzen – dann zeigt das Cockpit sie jeder Lehrkraft einmal.
Wer sein Konto erst nach SINCE angelegt hat, kennt den Stand schon aus der
Einrichtung und bekommt das Fenster nicht.
"""
from __future__ import annotations

from datetime import datetime, timezone

NEWS_ID = "2026-11-videos"
SINCE = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)


def migrate(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS news_seen (
            user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            news_id  TEXT NOT NULL,
            seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, news_id)
        )
        """
    )


def _aware(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def seen(conn, user_id: int, created_at=None, news_id: str = NEWS_ID) -> bool:
    created_at = _aware(created_at)
    if isinstance(created_at, datetime) and created_at >= SINCE:
        return True
    row = conn.execute(
        "SELECT 1 FROM news_seen WHERE user_id = %s AND news_id = %s",
        (user_id, news_id),
    ).fetchone()
    return row is not None


def mark_seen(conn, user_id: int, news_id: str = NEWS_ID) -> None:
    conn.execute(
        "INSERT INTO news_seen (user_id, news_id) VALUES (%s, %s) "
        "ON CONFLICT (user_id, news_id) DO NOTHING",
        (user_id, news_id),
    )


def status(conn, user_id: int, created_at=None) -> dict:
    return {"id": NEWS_ID, "seen": seen(conn, user_id, created_at)}
