"""
Adapter for fetching and parsing school calendar events from iCal feed.
Uses only stdlib — no icalendar dependency required.
"""
import logging
from datetime import datetime, date, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

ICAL_URL = "https://hermann-ehlers-schule.de/events/liste/?ical=1"
FETCH_TIMEOUT = 8  # seconds


@dataclass
class TerminEvent:
    uid: str
    title: str
    start: str          # ISO date string (date or datetime)
    end: Optional[str]  # ISO date string (date or datetime), may be None
    all_day: bool
    time_label: Optional[str]  # e.g. "09:00–11:00" for timed events
    location: Optional[str]
    description: Optional[str]


@dataclass
class WichtigeTermineResult:
    ok: bool
    mode: str           # 'live' | 'error' | 'empty'
    today_events: list  # list of TerminEvent as dicts
    upcoming_events: list  # list of TerminEvent as dicts, next 14 days
    error: Optional[str]
    fetched_at: Optional[str]


def _parse_ical(raw_text: str, now: datetime) -> tuple:
    """
    Minimal iCal parser. Handles VEVENT blocks.
    Returns (today_events, upcoming_events) as lists of TerminEvent dicts.
    """
    today = now.date()
    upcoming_cutoff = today + timedelta(days=14)

    events = []
    lines = raw_text.replace('\r\n', '\n').replace('\r', '\n').splitlines()

    # Unfold continuation lines (lines starting with space/tab)
    unfolded = []
    for line in lines:
        if line.startswith((' ', '\t')) and unfolded:
            unfolded[-1] += line.strip()
        else:
            unfolded.append(line)

    in_event = False
    current = {}
    for line in unfolded:
        if line == 'BEGIN:VEVENT':
            in_event = True
            current = {}
        elif line == 'END:VEVENT':
            if in_event and current:
                event = _build_event(current, today, upcoming_cutoff)
                if event:
                    events.append(event)
            in_event = False
            current = {}
        elif in_event and ':' in line:
            # Handle property parameters like DTSTART;VALUE=DATE:20260315
            key_part, _, value = line.partition(':')
            prop_name = key_part.split(';')[0].upper()
            params = key_part[len(prop_name):]
            current[prop_name] = (value, params)

    today_events = [e for e in events if e['event_date'] == today]
    upcoming_events = [e for e in events if today < e['event_date'] <= upcoming_cutoff]

    # Sort both lists by event_date
    today_events.sort(key=lambda e: (e['event_date'], e.get('time_label') or ''))
    upcoming_events.sort(key=lambda e: (e['event_date'], e.get('time_label') or ''))

    return today_events, upcoming_events


def _parse_ical_date(value: str, params: str):
    """Returns (date_object, is_all_day)."""
    value = value.strip()
    all_day = 'VALUE=DATE' in params.upper()

    if all_day or (len(value) == 8 and value.isdigit()):
        try:
            return datetime.strptime(value[:8], '%Y%m%d').date(), True
        except ValueError:
            return None, True

    # YYYYMMDDTHHMMSSZ or YYYYMMDDTHHMMSS
    try:
        dt_str = value[:15].replace('T', '')
        dt = datetime.strptime(dt_str[:14], '%Y%m%d%H%M%S')
        if value.endswith('Z'):
            dt = dt.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        return dt.date(), False
    except (ValueError, IndexError):
        return None, False


def _build_event(props: dict, today: date, cutoff: date):
    """Build a TerminEvent dict from parsed VEVENT properties. Returns None if unparseable."""
    try:
        start_raw, start_params = props.get('DTSTART', ('', ''))
        end_raw, end_params = props.get('DTEND', ('', ''))

        start_date, all_day = _parse_ical_date(start_raw, start_params)
        if not start_date:
            return None

        # Only include events on or after today and up to cutoff
        if start_date < today or start_date > cutoff:
            return None

        end_date = None
        if end_raw:
            end_date, _ = _parse_ical_date(end_raw, end_params)

        uid = props.get('UID', ('',))[0].strip()
        summary = props.get('SUMMARY', ('',))[0].strip()
        location_val = props.get('LOCATION', ('',))[0].strip() or None
        description_val = props.get('DESCRIPTION', ('',))[0].strip() or None

        time_label = None
        if not all_day and start_raw:
            try:
                start_time = datetime.strptime(start_raw[:15].replace('T', '')[:12], '%Y%m%d%H%M')
                time_label = start_time.strftime('%H:%M')
                if end_raw:
                    end_time = datetime.strptime(end_raw[:15].replace('T', '')[:12], '%Y%m%d%H%M')
                    time_label += f'\u2013{end_time.strftime("%H:%M")}'
            except ValueError:
                pass

        return {
            'uid': uid,
            'title': summary or '(Ohne Titel)',
            'start': start_date.isoformat(),
            'end': end_date.isoformat() if end_date else None,
            'all_day': all_day,
            'time_label': time_label,
            'location': location_val,
            'description': description_val,
            'event_date': start_date,  # internal, stripped before serialization
        }
    except Exception as e:
        logger.debug(f"Skipping unparseable VEVENT: {e}")
        return None


def fetch_wichtige_termine(ical_url: str, now: datetime) -> WichtigeTermineResult:
    """Fetch and parse iCal from school portal."""
    try:
        req = urllib.request.Request(
            ical_url,
            headers={'User-Agent': 'lehrercockpit/1.0 (+https://lehrercockpit.com)'}
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as response:
            raw = response.read().decode('utf-8', errors='replace')

        today_events, upcoming_events = _parse_ical(raw, now)

        # Strip internal `event_date` key before returning
        def strip_internal(ev):
            return {k: v for k, v in ev.items() if k != 'event_date'}

        return WichtigeTermineResult(
            ok=True,
            mode='live',
            today_events=[strip_internal(e) for e in today_events],
            upcoming_events=[strip_internal(e) for e in upcoming_events],
            error=None,
            fetched_at=now.isoformat(),
        )
    except urllib.error.URLError as e:
        logger.warning(f"Failed to fetch Wichtige Termine iCal: {e}")
        return WichtigeTermineResult(ok=False, mode='error', today_events=[], upcoming_events=[], error=str(e), fetched_at=None)
    except Exception as e:
        logger.error(f"Unexpected error in Wichtige Termine fetch: {e}")
        return WichtigeTermineResult(ok=False, mode='error', today_events=[], upcoming_events=[], error='Unbekannter Fehler', fetched_at=None)
