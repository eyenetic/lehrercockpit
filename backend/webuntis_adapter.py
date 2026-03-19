from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import ssl
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass
class WebUntisEvent:
    uid: str
    start: datetime
    end: datetime
    summary: str
    location: str
    description: str


@dataclass
class WebUntisSyncResult:
    source: dict[str, Any]
    schedule: list[dict[str, str]]
    priorities: list[dict[str, str]]
    events: list[dict[str, str]]
    mode: str
    note: str


def fetch_webuntis_sync(base_url: str, ical_url: str, now: datetime) -> WebUntisSyncResult:
    if not ical_url:
        if base_url:
            return WebUntisSyncResult(
                source={
                    "id": "webuntis",
                    "name": "WebUntis",
                    "type": "Stundenplan",
                    "status": "warning",
                    "cadence": "manuell",
                    "lastSync": now.strftime("%H:%M"),
                    "nextStep": "Persoenlichen iCal-Link in WEBUNTIS_ICAL_URL hinterlegen",
                    "detail": "WebUntis ist als Schulzugang eingetragen, aber noch nicht live mit deinem Stundenplan verbunden.",
                },
                schedule=[],
                priorities=[],
                events=[],
                mode="link-only",
                note="WebUntis ist nur als Link vorbereitet.",
            )

        return WebUntisSyncResult(
            source={
                "id": "webuntis",
                "name": "WebUntis",
                "type": "Stundenplan",
                "status": "warning",
                "cadence": "nicht verbunden",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "WEBUNTIS_BASE_URL und persoenlichen iCal-Link hinterlegen",
                "detail": "Noch kein WebUntis-Zugang konfiguriert.",
            },
            schedule=[],
            priorities=[],
            events=[],
            mode="missing",
            note="WebUntis ist noch nicht eingerichtet.",
        )

    try:
        calendar_text = _download_ical(ical_url)
        events = _parse_events(calendar_text, now)
        visible_events = _visible_events(events, now)
        schedule = [_to_schedule_item(event, now) for event in visible_events]
        priorities = _build_priorities(events, now)

        return WebUntisSyncResult(
            source={
                "id": "webuntis",
                "name": "WebUntis",
                "type": "Stundenplan",
                "status": "ok",
                "cadence": "bei jedem Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "Als Naechstes koennen wir Vertretungen, Ausfaelle und Delta-Aenderungen hervorheben",
                "detail": f"{len(events)} Termine aus deinem persoenlichen WebUntis-iCal geladen.",
            },
            schedule=schedule,
            priorities=priorities,
            events=[_to_event_item(event, now) for event in visible_events],
            mode="live-webuntis",
            note="WebUntis laeuft live ueber deinen persoenlichen iCal-Export.",
        )
    except Exception as exc:
        return WebUntisSyncResult(
            source={
                "id": "webuntis",
                "name": "WebUntis",
                "type": "Stundenplan",
                "status": "error",
                "cadence": "bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "iCal-Link pruefen oder in WebUntis neu erzeugen",
                "detail": f"WebUntis-iCal konnte nicht geladen werden: {type(exc).__name__}.",
            },
            schedule=[],
            priorities=[],
            events=[],
            mode="webuntis-error",
            note="WebUntis konnte gerade nicht geladen werden.",
        )


def _download_ical(url: str) -> str:
    request = Request(url, headers={"User-Agent": "LehrerCockpit/1.0"})

    try:
        with urlopen(request, timeout=15) as response:
            return response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        if isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError):
            insecure_context = ssl._create_unverified_context()
            with urlopen(request, timeout=15, context=insecure_context) as response:
                return response.read().decode("utf-8", errors="replace")
        raise


def _parse_events(calendar_text: str, now: datetime) -> list[WebUntisEvent]:
    events: list[WebUntisEvent] = []
    current: dict[str, str] | None = None

    for line in _unfold_lines(calendar_text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue

        if line == "END:VEVENT":
            if current is not None:
                event = _build_event(current, now)
                if event is not None:
                    events.append(event)
            current = None
            continue

        if current is None or ":" not in line:
            continue

        raw_key, value = line.split(":", 1)
        key = raw_key.split(";", 1)[0]
        current[key] = value

    return sorted(events, key=lambda event: event.start)


def _unfold_lines(calendar_text: str) -> list[str]:
    unfolded: list[str] = []
    for raw_line in calendar_text.splitlines():
        if not raw_line:
            continue

        if raw_line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += raw_line[1:]
        else:
            unfolded.append(raw_line)
    return unfolded


def _build_event(payload: dict[str, str], now: datetime) -> WebUntisEvent | None:
    start = _parse_datetime(payload.get("DTSTART", ""), now)
    end = _parse_datetime(payload.get("DTEND", ""), now)
    if start is None or end is None:
        return None

    return WebUntisEvent(
        uid=payload.get("UID", ""),
        start=start,
        end=end,
        summary=_decode_ical_text(payload.get("SUMMARY", "")),
        location=_decode_ical_text(payload.get("LOCATION", "")),
        description=_clean_description(_decode_ical_text(payload.get("DESCRIPTION", ""))),
    )


def _parse_datetime(raw_value: str, now: datetime) -> datetime | None:
    if not raw_value:
        return None

    value = raw_value.rstrip("Z")
    formats = ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d")
    parsed: datetime | None = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            break
        except ValueError:
            continue

    if parsed is None:
        return None

    if len(value) == 8:
        parsed = parsed.replace(hour=0, minute=0)

    return parsed.replace(tzinfo=now.tzinfo)


def _decode_ical_text(value: str) -> str:
    return (
        value.replace("\\n", " ")
        .replace("\\N", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _visible_events(events: list[WebUntisEvent], now: datetime) -> list[WebUntisEvent]:
    week_start = _start_of_week(now)
    week_end = week_start + timedelta(days=7)
    visible = [event for event in events if week_start <= event.start < week_end]
    if visible:
        return visible

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    fallback = [event for event in events if event.end >= day_start]
    return fallback[:16]


def _to_schedule_item(event: WebUntisEvent, now: datetime) -> dict[str, str]:
    title = _format_event_title(event)
    location = f"Ort: {event.location}." if event.location else "Ort offen."
    context = f" Kontext: {event.description}." if event.description else ""

    return {
        "id": f"webuntis-{event.uid or event.start.isoformat()}",
        "title": title,
        "time": f"{event.start.strftime('%H:%M')} - {event.end.strftime('%H:%M')}",
        "dateLabel": _date_label(event.start, now),
        "detail": f"{location}{context} Quelle: WebUntis-iCal.",
        "category": _event_category(event),
    }


def _to_event_item(event: WebUntisEvent, now: datetime) -> dict[str, str]:
    return {
        "id": f"webuntis-{event.uid or event.start.isoformat()}",
        "title": _format_event_title(event),
        "detail": _event_detail(event),
        "startsAt": event.start.isoformat(),
        "endsAt": event.end.isoformat(),
        "time": f"{event.start.strftime('%H:%M')} - {event.end.strftime('%H:%M')}",
        "dateLabel": _date_label(event.start, now),
        "weekdayLabel": _weekday_label(event.start),
        "category": _event_category(event),
        "location": event.location,
        "description": event.description,
    }


def _build_priorities(events: list[WebUntisEvent], now: datetime) -> list[dict[str, str]]:
    priorities: list[dict[str, str]] = []
    next_event = next((event for event in events if event.end >= now), None)
    if next_event is not None:
        location = f" in {next_event.location}" if next_event.location else ""
        priorities.append(
            {
                "id": f"webuntis-next-{next_event.uid or next_event.start.isoformat()}",
                "title": f"Naechster WebUntis-Termin: {_format_event_title(next_event)}",
                "detail": (
                    f"{_date_label(next_event.start, now)} ab {next_event.start.strftime('%H:%M')}{location}. "
                    f"{_short_description(next_event)}"
                ).strip(),
                "priority": "high" if next_event.start.date() == now.date() else "medium",
                "source": "WebUntis",
                "due": f"{_date_label(next_event.start, now)}, {next_event.start.strftime('%H:%M')}",
            }
        )

    today_events = [event for event in events if event.start.date() == now.date()]
    if today_events:
        priorities.append(
            {
                "id": "webuntis-today",
                "title": f"Heute {len(today_events)} WebUntis-Termine im Account",
                "detail": (
                    f"Erster Termin um {today_events[0].start.strftime('%H:%M')}, "
                    f"letzter Termin endet um {today_events[-1].end.strftime('%H:%M')}."
                ),
                "priority": "medium",
                "source": "WebUntis",
                "due": "heute",
            }
        )

    overlap = _first_overlap(events, now)
    if overlap is not None:
        first, second = overlap
        priorities.append(
            {
                "id": f"webuntis-overlap-{first.uid or first.start.isoformat()}",
                "title": "Ueberschneidung im WebUntis-Kalender",
                "detail": (
                    f"{_format_event_title(first)} und {_format_event_title(second)} starten beide um "
                    f"{first.start.strftime('%H:%M')}."
                ),
                "priority": "critical",
                "source": "WebUntis",
                "due": f"{_date_label(first.start, now)}, {first.start.strftime('%H:%M')}",
            }
        )

    return priorities[:3]


def _first_overlap(events: list[WebUntisEvent], now: datetime) -> tuple[WebUntisEvent, WebUntisEvent] | None:
    future_events = [event for event in events if event.end >= now]
    for index, event in enumerate(future_events):
        for other in future_events[index + 1 :]:
            if other.start >= event.end:
                break
            if other.start < event.end:
                return event, other
    return None


def _format_event_title(event: WebUntisEvent) -> str:
    summary = event.summary.strip()
    description = event.description.strip()
    if summary and description:
        return f"{summary} - {description}"
    if summary:
        return summary
    if description:
        return description
    if event.location:
        return f"Aufsicht - {event.location}"
    return "WebUntis-Termin"


def _short_description(event: WebUntisEvent) -> str:
    if event.description:
        return f"Kontext: {event.description}."
    if event.location:
        return f"Ort: {event.location}."
    return ""


def _event_detail(event: WebUntisEvent) -> str:
    parts = []
    if event.location:
        parts.append(f"Ort: {event.location}")
    if event.description:
        parts.append(f"Kontext: {event.description}")
    return ". ".join(parts) + ("." if parts else "")


def _event_category(event: WebUntisEvent) -> str:
    location = event.location.lower()
    if "online" in location:
        return "Online"
    if not event.summary:
        return "Aufsicht"
    if event.summary.lower() in {"ber", "beratung"}:
        return "Beratung"
    return "Unterricht"


def _start_of_week(value: datetime) -> datetime:
    start = value - timedelta(days=value.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def _weekday_label(value: datetime) -> str:
    labels = {
        0: "Montag",
        1: "Dienstag",
        2: "Mittwoch",
        3: "Donnerstag",
        4: "Freitag",
        5: "Samstag",
        6: "Sonntag",
    }
    return labels[value.weekday()]


def _clean_description(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""

    if ";" in cleaned:
        parts = [part.strip() for part in cleaned.split(";") if part.strip()]
        if len(parts) > 1 and _looks_like_teacher_code(parts[-1]):
            cleaned = "; ".join(parts[:-1]).strip()
    else:
        words = cleaned.split()
        if len(words) > 1 and _looks_like_teacher_code(words[-1]):
            cleaned = " ".join(words[:-1]).strip()
        elif len(words) == 1 and _looks_like_teacher_code(words[0]):
            cleaned = ""

    return cleaned


def _looks_like_teacher_code(value: str) -> bool:
    compact = value.replace(".", "").strip()
    return compact.isalpha() and 1 <= len(compact) <= 3


def _date_label(value: datetime, now: datetime) -> str:
    delta_days = (value.date() - now.date()).days
    if delta_days == 0:
        return "Heute"
    if delta_days == 1:
        return "Morgen"
    if 1 < delta_days < 7:
        labels = {
            0: "Montag",
            1: "Dienstag",
            2: "Mittwoch",
            3: "Donnerstag",
            4: "Freitag",
            5: "Samstag",
            6: "Sonntag",
        }
        return labels[value.weekday()]
    return value.strftime("%d.%m.")
