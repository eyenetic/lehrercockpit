"""Kalender-Abo: die Termine des Cockpits für den eigenen Kalender (Apple, Outlook, Google).

Jede Lehrkraft kann einen geheimen Link erzeugen. Kalender-Apps rufen ihn ohne
Anmeldung ab, deshalb ist der Link selbst der Schlüssel: gespeichert werden nur
ein Prüfwert (SHA-256) zum Wiederfinden und der Link verschlüsselt, damit er
der Lehrkraft erneut angezeigt werden kann.

Inhalt nach Wahl der Lehrkraft: Orgaplan (alle Stufen, Mittel- oder Oberstufe),
Klassenarbeiten der eigenen Klassen (wie unter „Heute anpassen“ gewählt),
Schultermine, der eigene itslearning-Kalender, der eigene Stundenplan sowie
Ferien und Feiertage. Private Kalender bleiben auf den Geräten der Lehrkraft.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

LEVELS = ("all", "middle", "upper")
# Orgaplan, Klassenarbeiten, Schultermine, itslearning, Stundenplan, Ferien und Feiertage
SOURCES = ("org", "ka", "sch", "its", "lessons", "breaks")
DEFAULT_SOURCES = ("org", "ka", "sch")  # links made before the choice existed
_KIND_SHORT = {"Klassenarbeit": "KA", "LEK": "LEK", "Klausur": "Klausur", "Test": "Test", "VERA": "VERA"}


# ── Storage ───────────────────────────────────────────────────────────────────

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def load(conn, user_id: int) -> dict[str, Any] | None:
    """{"token", "level", "sources", "created_at", "last_fetch_at"} or None."""
    from .crypto import decrypt_config

    row = conn.execute(
        "SELECT token_enc, level, sources, created_at, last_fetch_at FROM calendar_feeds WHERE user_id = %s", (user_id,)
    ).fetchone()
    if not row:
        return None
    token = decrypt_config({"token": row[0]}).get("token") or ""
    return {"token": token, "level": row[1], "sources": clean_sources(row[2]), "created_at": row[3], "last_fetch_at": row[4]}


def create(conn, user_id: int, level: str, sources: Any = DEFAULT_SOURCES) -> str:
    """A new secret link (the old one stops working)."""
    from .crypto import encrypt_config

    token = secrets.token_urlsafe(32)
    conn.execute(
        """
        INSERT INTO calendar_feeds (user_id, token_hash, token_enc, level, sources)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET token_hash = EXCLUDED.token_hash, token_enc = EXCLUDED.token_enc,
            level = EXCLUDED.level, sources = EXCLUDED.sources, created_at = NOW(), last_fetch_at = NULL
        """,
        (user_id, _hash(token), encrypt_config({"token": token})["token"], clean_level(level),
         ",".join(clean_sources(sources))),
    )
    return token


def set_options(conn, user_id: int, level: str, sources: Any) -> bool:
    """What the feed contains – the link stays the same."""
    return conn.execute("UPDATE calendar_feeds SET level = %s, sources = %s WHERE user_id = %s",
                        (clean_level(level), ",".join(clean_sources(sources)), user_id)).rowcount > 0


def delete(conn, user_id: int) -> bool:
    return conn.execute("DELETE FROM calendar_feeds WHERE user_id = %s", (user_id,)).rowcount > 0


def owner_of(conn, token: str) -> tuple[int, str, list[str]] | None:
    """(user_id, level, sources) for an active link of an active teacher, else None."""
    if not token or len(token) > 100:
        return None
    row = conn.execute(
        """
        SELECT f.user_id, f.level, f.sources FROM calendar_feeds f JOIN users u ON u.id = f.user_id
        WHERE f.token_hash = %s AND u.is_active
        """,
        (_hash(token),),
    ).fetchone()
    if not row:
        return None
    conn.execute("UPDATE calendar_feeds SET last_fetch_at = NOW() WHERE user_id = %s", (row[0],))
    return int(row[0]), str(row[1]), clean_sources(row[2])


def clean_level(level: Any) -> str:
    return level if level in LEVELS else "all"


def clean_sources(sources: Any) -> list[str]:
    """Known sources in a fixed order; a comma list or a list. None/missing → the original three."""
    if sources is None:
        return list(DEFAULT_SOURCES)
    items = sources.split(",") if isinstance(sources, str) else sources if isinstance(sources, (list, tuple)) else []
    chosen = {str(item).strip() for item in items}
    return [source for source in SOURCES if source in chosen]


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


def _orgaplan_source(conn, user_id: int, level: str, now: datetime) -> list[dict[str, Any]]:
    from . import orgaplan
    return _orgaplan_events(orgaplan.current(orgaplan.load_source(conn), now, wait=8.0), level)


def _classwork_source(conn, user_id: int, level: str, now: datetime) -> list[dict[str, Any]]:
    from .classwork_cache import load_cache
    from .classwork_sync import CACHE_PATH
    from .signal_store import load_prefs
    classes = {str(c).replace(" ", "").upper() for c in (load_prefs(conn, user_id).get("classes") or []) if c}
    if not classes:
        return []
    return _classwork_events(load_cache(CACHE_PATH).get("entries") or [], classes, now.date() - timedelta(days=30))


def _school_source(conn, user_id: int, level: str, now: datetime) -> list[dict[str, Any]]:
    from .school_calendar import build_calendar, feed_url
    return _school_events(build_calendar(feed_url(conn), now).get("data") or {})


def _itslearning_source(conn, user_id: int, level: str, now: datetime) -> list[dict[str, Any]]:
    """The teacher's itslearning calendar (link under Verbindungen), the next three weeks."""
    from .itslearning_module import fetch_itslearning_calendar
    from .modules.module_registry import get_user_module_config
    url = str((get_user_module_config(conn, user_id, "itslearning") or {}).get("calendar_url") or "").strip()
    if not url:
        return []
    events = []
    for event in fetch_itslearning_calendar(url, now).get("events") or []:
        all_day = bool(event.get("allDay"))
        start = _date(event.get("start")) if all_day else _datetime(event.get("start"))
        end = (_date(event.get("end")) if all_day else _datetime(event.get("end"))) if event.get("end") else None
        if not start:
            continue
        events.append({"uid": "its", "title": ("Abgabe: " if event.get("kind") == "todo" else "") + (event.get("title") or ""),
                       "start": start, "end": end or start, "all_day": all_day, "location": event.get("location") or "",
                       "description": event.get("detail") or "", "url": event.get("url") or ""})
    return events


def _lessons_source(conn, user_id: int, level: str, now: datetime) -> list[dict[str, Any]]:
    """The teacher's WebUntis timetable (link under Verbindungen): last week and four ahead."""
    from .modules.module_registry import get_user_module_config
    from .webuntis_adapter import fetch_webuntis_sync
    config = get_user_module_config(conn, user_id, "webuntis") or {}
    if not config.get("ical_url"):
        return []
    result = fetch_webuntis_sync(config.get("base_url", ""), config["ical_url"], now)
    events = []
    for item in result.events or []:
        start, end = _datetime(item.get("startsAt")), _datetime(item.get("endsAt"))
        if not start:
            continue
        title = item.get("title") or "Unterricht"
        events.append({"uid": "lessons", "title": ("Entfällt: " if item.get("cancelled") else "") + title,
                       "start": start, "end": end or start, "all_day": False, "location": item.get("location") or ""})
    return events


def _breaks_source(conn, user_id: int, level: str, now: datetime) -> list[dict[str, Any]]:
    from .school_year import free_days_between
    today = now.date()
    return [{"uid": "breaks", "title": b["name"], "start": b["start"], "end": b["end"], "all_day": True}
            for b in free_days_between(today - timedelta(days=30), today + timedelta(days=400))]


_SOURCE_READERS = {"org": _orgaplan_source, "ka": _classwork_source, "sch": _school_source,
                   "its": _itslearning_source, "lessons": _lessons_source, "breaks": _breaks_source}


def collect(conn, user_id: int, level: str, sources: Any = SOURCES,
            now: datetime | None = None) -> list[dict[str, Any]]:
    """Events of the chosen sources. A failing source is left out, the others still come."""
    now = now or datetime.now(timezone.utc)
    events: list[dict[str, Any]] = []
    for source in clean_sources(sources):
        try:
            events += _SOURCE_READERS[source](conn, user_id, level, now)
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
