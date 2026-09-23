"""Small, dependency-free iCalendar (RFC 5545) reader.

Handles what school feeds (WebUntis, itslearning, WordPress event calendars)
actually send: folded lines, escaped text, all-day dates, UTC times, IANA and
Windows time zone ids, floating times and VTODO deadlines. Recurrence rules
are not expanded; recurring series only yield their first occurrence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .http_utils import tls_context

BERLIN = ZoneInfo("Europe/Berlin")

# .NET-based systems (itslearning, Outlook) emit Windows zone names.
_WINDOWS_ZONES = {
    "w. europe standard time": "Europe/Berlin",
    "central europe standard time": "Europe/Berlin",
    "romance standard time": "Europe/Paris",
    "gmt standard time": "Europe/London",
    "utc": "UTC",
}


@dataclass
class CalendarEntry:
    uid: str
    kind: str            # "event" | "todo"
    title: str
    start: datetime      # aware, Europe/Berlin
    end: datetime | None
    all_day: bool
    location: str
    description: str
    url: str
    status: str


def fetch_calendar_text(url: str, *, timeout: int = 12, max_bytes: int = 5_000_000) -> str:
    """Download an iCal feed with verified TLS."""
    request = Request(url, headers={"User-Agent": "Lehrercockpit/1.0 (+https://lehrercockpit.com)"})
    with urlopen(request, timeout=timeout, context=tls_context()) as response:
        raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Kalender-Feed ist zu groß.")
    return raw.decode("utf-8", errors="replace")


def parse_calendar(text: str) -> list[CalendarEntry]:
    """Parse VEVENT and VTODO components into CalendarEntry objects, sorted by start."""
    entries: list[CalendarEntry] = []
    component: str | None = None
    props: dict[str, tuple[str, dict[str, str]]] = {}

    for line in _unfold(text):
        upper = line.upper()
        if upper in ("BEGIN:VEVENT", "BEGIN:VTODO"):
            component = "event" if upper.endswith("VEVENT") else "todo"
            props = {}
            continue
        if upper in ("END:VEVENT", "END:VTODO"):
            if component is not None:
                entry = _build_entry(component, props)
                if entry is not None:
                    entries.append(entry)
            component = None
            continue
        if component is None:
            continue
        name, params, value = _split_property(line)
        if name and name not in props:  # first occurrence wins
            props[name] = (value, params)

    entries.sort(key=lambda entry: entry.start)
    return entries


def entries_between(entries: list[CalendarEntry], start: datetime, end: datetime) -> list[CalendarEntry]:
    """Entries that overlap [start, end)."""
    result = []
    for entry in entries:
        entry_end = entry.end or entry.start
        if entry.start < end and entry_end >= start:
            result.append(entry)
    return result


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def _split_property(line: str) -> tuple[str, dict[str, str], str]:
    """Split 'NAME;PARAM=x;P2="a:b":value' respecting quoted parameter values."""
    in_quotes = False
    for index, char in enumerate(line):
        if char == '"':
            in_quotes = not in_quotes
        elif char == ":" and not in_quotes:
            head, value = line[:index], line[index + 1:]
            break
    else:
        return "", {}, ""
    parts = head.split(";")
    params: dict[str, str] = {}
    for part in parts[1:]:
        key, _, param_value = part.partition("=")
        params[key.strip().upper()] = param_value.strip().strip('"')
    return parts[0].strip().upper(), params, value


def _unescape(value: str) -> str:
    out = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            out.append("\n" if nxt in "nN" else nxt)
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out).strip()


def _zone(tzid: str):
    if not tzid:
        return None
    mapped = _WINDOWS_ZONES.get(tzid.strip().lower(), tzid.strip())
    try:
        return ZoneInfo(mapped)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def _parse_when(value: str, params: dict[str, str]) -> tuple[datetime | None, bool]:
    """Return (aware datetime in Europe/Berlin, is_all_day)."""
    value = value.strip()
    if not value:
        return None, False
    if params.get("VALUE", "").upper() == "DATE" or (len(value) == 8 and value.isdigit()):
        try:
            day = datetime.strptime(value[:8], "%Y%m%d").date()
        except ValueError:
            return None, True
        return datetime.combine(day, time.min, tzinfo=BERLIN), True

    is_utc = value.endswith("Z")
    raw = value.rstrip("Z")
    parsed = None
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            parsed = datetime.strptime(raw, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return None, False
    if is_utc:
        return parsed.replace(tzinfo=timezone.utc).astimezone(BERLIN), False
    zone = _zone(params.get("TZID", "")) or BERLIN  # floating time = school time
    return parsed.replace(tzinfo=zone).astimezone(BERLIN), False


def _parse_duration(value: str) -> timedelta | None:
    """Parse simple RFC 5545 durations like PT1H30M, P1D, -PT15M."""
    value = value.strip().upper()
    if not value:
        return None
    sign = -1 if value.startswith("-") else 1
    value = value.lstrip("+-")
    if not value.startswith("P"):
        return None
    days = hours = minutes = seconds = weeks = 0
    number = ""
    in_time = False
    for char in value[1:]:
        if char == "T":
            in_time = True
        elif char.isdigit():
            number += char
        elif number:
            amount = int(number)
            number = ""
            if char == "W":
                weeks = amount
            elif char == "D":
                days = amount
            elif char == "H" and in_time:
                hours = amount
            elif char == "M" and in_time:
                minutes = amount
            elif char == "S" and in_time:
                seconds = amount
    return sign * timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)


def _build_entry(kind: str, props: dict[str, tuple[str, dict[str, str]]]) -> CalendarEntry | None:
    def text(name: str) -> str:
        return _unescape(props.get(name, ("", {}))[0])

    end: datetime | None = None
    if kind == "todo":
        # For tasks the deadline is what matters; DTSTART is only a fallback.
        start, all_day = _parse_when(*props.get("DUE", ("", {})))
        if start is None:
            start, all_day = _parse_when(*props.get("DTSTART", ("", {})))
    else:
        start, all_day = _parse_when(*props.get("DTSTART", ("", {})))
        if start is not None:
            end, _ = _parse_when(*props.get("DTEND", ("", {})))
            if end is None and "DURATION" in props:
                duration = _parse_duration(props["DURATION"][0])
                if duration is not None:
                    end = start + duration
            if end is not None and all_day and end > start:
                end = end - timedelta(seconds=1)  # DTEND of all-day events is exclusive
    if start is None:
        return None
    # Many feeds (e.g. WordPress event calendars) send all-day events as
    # 00:00–23:59, or "no time" events as 00:00–00:00, instead of VALUE=DATE.
    if (
        kind == "event"
        and not all_day
        and start.time() == time.min
        and (end is None or end == start or end.time() >= time(23, 59))
    ):
        all_day = True
        if end is None or end == start:
            end = start.replace(hour=23, minute=59, second=59)

    return CalendarEntry(
        uid=text("UID"),
        kind=kind,
        title=text("SUMMARY") or "(Ohne Titel)",
        start=start,
        end=end if end is None or end >= start else None,
        all_day=all_day,
        location=text("LOCATION"),
        description=text("DESCRIPTION"),
        url=text("URL"),
        status=(text("STATUS") or "CONFIRMED").upper(),
    )


def berlin_today(now: datetime | None = None) -> date:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(BERLIN).date()
