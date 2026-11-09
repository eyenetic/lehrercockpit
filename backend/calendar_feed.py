"""Kalender-Abo: die Termine des Cockpits für den eigenen Kalender (Apple, Outlook, Google).

Jede Lehrkraft kann einen geheimen Link erzeugen. Kalender-Apps rufen ihn ohne
Anmeldung ab, deshalb ist der Link selbst der Schlüssel: gespeichert werden nur
ein Prüfwert (SHA-256) zum Wiederfinden und der Link verschlüsselt, damit er
der Lehrkraft erneut angezeigt werden kann.

Inhalt: Orgaplan (nach der gewählten Stufe), Klassenarbeiten der eigenen
Klassen (wie unter „Heute anpassen“ gewählt) und die Schultermine. Nichts
Privates – private Kalender bleiben auf den Geräten der Lehrkraft.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

LEVELS = ("all", "middle", "upper")
_KIND_SHORT = {"Klassenarbeit": "KA", "LEK": "LEK", "Klausur": "Klausur", "Test": "Test", "VERA": "VERA"}


# ── Storage ───────────────────────────────────────────────────────────────────

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def load(conn, user_id: int) -> dict[str, Any] | None:
    """{"token", "level", "created_at", "last_fetch_at"} or None."""
    from .crypto import decrypt_config

    row = conn.execute(
        "SELECT token_enc, level, created_at, last_fetch_at FROM calendar_feeds WHERE user_id = %s", (user_id,)
    ).fetchone()
    if not row:
        return None
    token = decrypt_config({"token": row[0]}).get("token") or ""
    return {"token": token, "level": row[1], "created_at": row[2], "last_fetch_at": row[3]}


def create(conn, user_id: int, level: str) -> str:
    """A new secret link (the old one stops working)."""
    from .crypto import encrypt_config

    token = secrets.token_urlsafe(32)
    conn.execute(
        """
        INSERT INTO calendar_feeds (user_id, token_hash, token_enc, level)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET token_hash = EXCLUDED.token_hash, token_enc = EXCLUDED.token_enc,
            level = EXCLUDED.level, created_at = NOW(), last_fetch_at = NULL
        """,
        (user_id, _hash(token), encrypt_config({"token": token})["token"], clean_level(level)),
    )
    return token


def set_level(conn, user_id: int, level: str) -> bool:
    return conn.execute("UPDATE calendar_feeds SET level = %s WHERE user_id = %s",
                        (clean_level(level), user_id)).rowcount > 0


def delete(conn, user_id: int) -> bool:
    return conn.execute("DELETE FROM calendar_feeds WHERE user_id = %s", (user_id,)).rowcount > 0


def owner_of(conn, token: str) -> tuple[int, str] | None:
    """(user_id, level) for an active link of an active teacher, else None."""
    if not token or len(token) > 100:
        return None
    row = conn.execute(
        """
        SELECT f.user_id, f.level FROM calendar_feeds f JOIN users u ON u.id = f.user_id
        WHERE f.token_hash = %s AND u.is_active
        """,
        (_hash(token),),
    ).fetchone()
    if not row:
        return None
    conn.execute("UPDATE calendar_feeds SET last_fetch_at = NOW() WHERE user_id = %s", (row[0],))
    return int(row[0]), str(row[1])


def clean_level(level: Any) -> str:
    return level if level in LEVELS else "all"


# ── Events ────────────────────────────────────────────────────────────────────

def _orgaplan_events(digest: dict[str, Any], level: str) -> list[dict[str, Any]]:
    events = []
    for entry in digest.get("upcoming") or []:
        day = _date(entry.get("isoDate"))
        if not day:
            continue
        parts = [("", entry.get("general"), "")]
        if level in ("all", "middle"):
            parts.append(("Mittelstufe: " if level == "all" else "", entry.get("middle"), entry.get("middleNotes")))
        if level in ("all", "upper"):
            parts.append(("Oberstufe: " if level == "all" else "", entry.get("upper"), entry.get("upperNotes")))
        for prefix, text, notes in parts:
            text = " ".join(str(text or "").split())
            notes = " ".join(str(notes or "").split())
            if not text and not notes:
                continue
            title = prefix + (f"{text} ({notes})" if text and notes else text or notes)
            events.append({"uid": "org", "title": title, "start": day, "end": day, "all_day": True,
                           "description": "Orgaplan"})
    return events


def _classwork_events(entries: list[dict[str, Any]], classes: set[str], since: date) -> list[dict[str, Any]]:
    events = []
    for entry in entries:
        day = _date(entry.get("isoDate"))
        label = str(entry.get("classLabel") or "").replace(" ", "").upper()
        if not day or day < since or label not in classes:
            continue
        title = " ".join(str(entry.get("title") or entry.get("summary") or "").split())
        short = _KIND_SHORT.get(entry.get("kind") or "", "")
        prefix = label + (f" {short}" if short and short.lower() not in title.lower().split() else "")
        events.append({"uid": "ka", "title": f"{prefix}: {title}", "start": day, "end": day, "all_day": True,
                       "description": f"Klassenarbeitsplan · {entry.get('kind') or ''}".rstrip(" ·")})
    return events


def _school_events(calendar: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    for event in calendar.get("events") or []:
        all_day = bool(event.get("all_day"))
        start = _date(event.get("start")) if all_day else _datetime(event.get("start"))
        end = (_date(event.get("end")) if all_day else _datetime(event.get("end"))) if event.get("end") else None
        if not start:
            continue
        events.append({"uid": "sch", "title": event.get("title") or "", "start": start, "end": end or start,
                       "all_day": all_day, "location": event.get("location") or "",
                       "description": event.get("description") or "", "url": event.get("url") or ""})
    return events


def collect(conn, user_id: int, level: str, now: datetime | None = None) -> list[dict[str, Any]]:
    """All events of the feed. Each source is optional: a failing one is left out."""
    now = now or datetime.now(timezone.utc)
    events: list[dict[str, Any]] = []
    try:
        from . import orgaplan
        events += _orgaplan_events(orgaplan.current(orgaplan.load_source(conn), now, wait=8.0), level)
    except Exception:
        pass
    try:
        from .classwork_cache import load_cache
        from .classwork_sync import CACHE_PATH
        from .signal_store import load_prefs
        classes = {str(c).replace(" ", "").upper() for c in (load_prefs(conn, user_id).get("classes") or []) if c}
        if classes:
            since = now.date() - timedelta(days=30)
            events += _classwork_events(load_cache(CACHE_PATH).get("entries") or [], classes, since)
    except Exception:
        pass
    try:
        from .school_calendar import build_calendar, feed_url
        events += _school_events(build_calendar(feed_url(conn), now).get("data") or {})
    except Exception:
        pass
    return events


# ── iCalendar ─────────────────────────────────────────────────────────────────

def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None
    if parsed and parsed.tzinfo is None:
        from .ical_utils import BERLIN
        parsed = parsed.replace(tzinfo=BERLIN)
    return parsed


def _text(value: Any) -> str:
    return (str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line after a space (RFC 5545)."""
    out, current = [], b""
    for char in line:
        encoded = char.encode("utf-8")
        if len(current) + len(encoded) > (75 if not out else 74):
            out.append(current.decode("utf-8"))
            current = b""
        current += encoded
    out.append(current.decode("utf-8"))
    return "\r\n ".join(out)


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(events: list[dict[str, Any]], now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Lehrercockpit//Kalender-Abo//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Lehrercockpit",
        "X-WR-CALDESC:Orgaplan\\, Klassenarbeiten und Schultermine aus dem Lehrercockpit",
        "X-WR-TIMEZONE:Europe/Berlin",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]
    seen: set[str] = set()
    for event in events:
        start, end = event["start"], event.get("end") or event["start"]
        key = f"{event['uid']}|{start.isoformat()}|{event['title']}"
        uid = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20] + "@lehrercockpit.com"
        if uid in seen:
            continue
        seen.add(uid)
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{_utc(now)}"]
        if event.get("all_day"):
            last = end if isinstance(end, date) and not isinstance(end, datetime) else start
            lines += [f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
                      f"DTEND;VALUE=DATE:{(max(last, start) + timedelta(days=1)):%Y%m%d}",  # exclusive
                      "TRANSP:TRANSPARENT"]
        else:
            finish = end if isinstance(end, datetime) and end > start else start + timedelta(hours=1)
            lines += [f"DTSTART:{_utc(start)}", f"DTEND:{_utc(finish)}"]
        lines.append(f"SUMMARY:{_text(event['title'])}")
        if event.get("location"):
            lines.append(f"LOCATION:{_text(event['location'])}")
        if event.get("description"):
            lines.append(f"DESCRIPTION:{_text(str(event['description'])[:1000])}")
        if event.get("url"):
            lines.append("URL:" + str(event["url"]).replace("\r", "").replace("\n", ""))
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
