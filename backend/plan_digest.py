from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .http_utils import tls_context

from openpyxl import load_workbook
from pypdf import PdfReader
from pypdf.errors import PdfReadError


GERMAN_MONTHS = {
    1: "Januar",
    2: "Februar",
    3: "Maerz",
    4: "April",
    5: "Mai",
    6: "Juni",
    7: "Juli",
    8: "August",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Dezember",
}

GERMAN_MONTH_LOOKUP = {label.lower(): number for number, label in GERMAN_MONTHS.items()}


@dataclass
class DownloadResult:
    reachable: bool
    status_code: int | None
    content_type: str
    last_modified: str
    content_length: str
    data: bytes
    error: str


def build_plan_digest(orgaplan_url: str, classwork_url: str, classwork_local_path: str, now: datetime) -> dict[str, Any]:
    return {
        "orgaplan": _build_orgaplan_digest(orgaplan_url, now),
        "classwork": _build_classwork_digest(classwork_url, classwork_local_path, now),
    }


def _build_orgaplan_digest(url: str, now: datetime) -> dict[str, Any]:
    if not url:
        return {
            "status": "warning",
            "title": "Orgaplan",
            "detail": "Noch kein Orgaplan-Link hinterlegt.",
            "monthLabel": GERMAN_MONTHS[now.month],
            "updatedAt": now.strftime("%H:%M"),
            "highlights": [],
            "upcoming": [],
            "sourceUrl": "",
        }

    download = _download_document(url)
    if not download.reachable:
        return {
            "status": "warning" if download.status_code else "error",
            "title": "Orgaplan",
            "detail": _blocked_detail("Orgaplan", download),
            "monthLabel": GERMAN_MONTHS[now.month],
            "updatedAt": now.strftime("%H:%M"),
            "highlights": [],
            "upcoming": [],
            "sourceUrl": url,
        }

    try:  # table reader for the whole school year (backend/orgaplan.py)
        from .orgaplan import build_digest, parse_pdf

        parsed = parse_pdf(download.data)
        digest = build_digest({**parsed, "pdf_url": url, "checked_at": now.isoformat()},
                              {"mode": "fixed", "pdf_url": url}, now)
        digest["updatedAt"] = now.strftime("%H:%M")
        return digest
    except Exception:
        pass  # older position-based reader below

    try:
        month_entries, month_label = _extract_orgaplan_entries(download.data, now)
        today = _berlin_today(now)
        week_end = today + timedelta(days=6)
        upcoming = [entry for entry in month_entries if entry["date"] >= today]
        if not upcoming:
            upcoming = month_entries
        section_counts = _count_orgaplan_sections(upcoming)

        return {
            "status": "ok",
            "title": "Orgaplan",
            "detail": (
                f"Live gelesen. Stand Quelle: {download.last_modified or 'ohne Zeitstempel'}. "
                f"{len(upcoming)} relevante Einträge für {month_label}. "
                f"Allgemein {section_counts['general']}, Mittelstufe {section_counts['middle']}, Oberstufe {section_counts['upper']}."
            ),
            "monthLabel": month_label,
            "updatedAt": now.strftime("%H:%M"),
            "highlights": _build_orgaplan_highlights(upcoming),
            "upcoming": [_serialize_entry(entry) for entry in upcoming],
            "sourceUrl": url,
        }
    except Exception as exc:
        return {
            "status": "error",
            "title": "Orgaplan",
            "detail": f"Orgaplan konnte gelesen, aber nicht ausgewertet werden: {type(exc).__name__}.",
            "monthLabel": GERMAN_MONTHS[now.month],
            "updatedAt": now.strftime("%H:%M"),
            "highlights": [],
            "upcoming": [],
            "sourceUrl": url,
        }


def _build_classwork_digest(url: str, local_path: str, now: datetime) -> dict[str, Any]:
    local_file = Path(local_path) if local_path else None
    if local_file and local_file.exists():
        try:
            return _read_classwork_workbook(
                local_file.read_bytes(),
                now,
                detail="Lokale XLSX-Datei importiert und für das Cockpit vorbereitet.",
                source_url=url,
            )
        except Exception as exc:
            return {
                "status": "warning",
                "title": "Klassenarbeitsplan",
                "detail": f"Lokale Datei gefunden, aber noch nicht auswertbar: {type(exc).__name__}.",
                "updatedAt": now.strftime("%H:%M"),
                "previewRows": [],
                "classes": [],
                "entries": [],
                "defaultClass": "",
                "sourceUrl": url,
            }

    if not url:
        return {
            "status": "warning",
            "title": "Klassenarbeitsplan",
            "detail": "Noch kein Link für den Klassenarbeitsplan hinterlegt.",
            "updatedAt": now.strftime("%H:%M"),
            "previewRows": [],
            "classes": [],
            "entries": [],
            "defaultClass": "",
            "sourceUrl": "",
        }

    download = _download_document(url)
    if not download.reachable:
        return {
            "status": "warning" if download.status_code else "error",
            "title": "Klassenarbeitsplan",
            "detail": _blocked_detail("Klassenarbeitsplan", download),
            "updatedAt": now.strftime("%H:%M"),
            "previewRows": [],
            "classes": [],
            "entries": [],
            "defaultClass": "",
            "sourceUrl": url,
        }

    try:
        return _read_classwork_workbook(
            download.data,
            now,
            detail="Excel-Datei wurde live gelesen und für das Cockpit vorbereitet.",
            source_url=url,
        )
    except Exception as exc:
        return {
            "status": "warning",
            "title": "Klassenarbeitsplan",
            "detail": f"Datei erreichbar, aber noch nicht auswertbar: {type(exc).__name__}.",
            "updatedAt": now.strftime("%H:%M"),
            "previewRows": [],
            "classes": [],
            "entries": [],
            "defaultClass": "",
            "sourceUrl": url,
        }


MAX_CLASSWORK_ENTRIES = 1500


def _read_classwork_workbook(data: bytes, now: datetime, *, detail: str, source_url: str) -> dict[str, Any]:
    """All entries of the plan. Filtering by date happens when the plan is shown,
    so a stored plan never keeps last week's view (see classwork_sync.plan_view)."""
    workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
    school_year = now.year if now.month >= 8 else now.year - 1
    all_entries: list[dict[str, Any]] = []

    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        all_entries.extend(_extract_classwork_entries(sheet, sheet_name, school_year))

    unique = {(e["classLabel"], e["date"], e["title"]): e for e in all_entries}
    all_entries = sorted(unique.values(),
                         key=lambda entry: (entry["date"], _class_sort_key(entry["classLabel"]), entry["title"]))
    upcoming_entries = [entry for entry in all_entries if entry["date"] >= now.date()]

    classes = sorted({entry["classLabel"] for entry in all_entries}, key=_class_sort_key)
    default_class = classes[0] if classes else ""
    preview_rows = [
        f"{entry['classLabel']} | {entry['dateLabel']} | {entry['title']}"
        for entry in upcoming_entries[:8]
    ]

    if all_entries:
        resolved_detail = f"{detail} {len(all_entries)} Einträge für {len(classes)} Klassen erkannt."
    else:
        sheets = ", ".join(f"„{name}“" for name in workbook.sheetnames[:8])
        resolved_detail = (
            f"{detail} In der Datei wurden keine Klassenarbeiten erkannt (Tabellenblätter: {sheets}). "
            "Erwartet wird je Klasse eine Zeile oder Spalte mit Datumsangaben und Einträgen wie „KA“, "
            "„LEK“ oder „Klausur“."
        )

    return {
        "status": "ok" if all_entries else "warning",
        "title": "Klassenarbeitsplan",
        "detail": resolved_detail,
        "updatedAt": now.strftime("%H:%M"),
        "previewRows": preview_rows,
        "classes": classes,
        "entries": [_serialize_classwork_entry(entry) for entry in all_entries[:MAX_CLASSWORK_ENTRIES]],
        "firstDate": all_entries[0]["date"].isoformat() if all_entries else "",
        "lastDate": all_entries[-1]["date"].isoformat() if all_entries else "",
        "sheetNames": list(workbook.sheetnames[:20]),
        "defaultClass": default_class,
        "sourceUrl": source_url,
    }


MAX_SHEET_ROWS = 400
MAX_SHEET_COLUMNS = 400


def _extract_classwork_entries(sheet: Any, sheet_name: str, school_year: int | None = None) -> list[dict[str, Any]]:
    """Entries of one sheet. Two layouts are understood:

    - dates across: a header row with dates, one row per class (first column)
    - dates down:   a header row with classes, one row per date (first columns)

    The year comes from the date cell, else from the sheet name ("November 2025"),
    else from the school year (August–December → its first calendar year).
    """
    rows = [list(row[:MAX_SHEET_COLUMNS])
            for _, row in zip(range(MAX_SHEET_ROWS), sheet.iter_rows(values_only=True))]
    if not rows:
        return []
    context = _sheet_month_year(sheet_name)
    return _entries_dates_across(rows, context, school_year) or _entries_dates_down(rows, context, school_year)


def _make_entry(class_label: str, entry_date: date, raw_value: str) -> dict[str, Any]:
    return {
        "classLabel": class_label,
        "date": entry_date,
        "dateLabel": entry_date.strftime("%d.%m."),
        "title": raw_value,
        "kind": _classwork_kind(raw_value),
    }


def _entries_dates_across(rows: list[list[Any]], context, school_year) -> list[dict[str, Any]]:
    header_index, header_dates = _best_row(rows, lambda value: _cell_date(value, context, school_year))
    if header_index is None or len(header_dates) < 2:
        return []
    entries = []
    for row in rows[header_index + 1:]:
        class_label = next((label for label in (_normalize_class_label(v) for v in row[:2]) if label), "")
        if not class_label:
            continue
        for column, entry_date in header_dates.items():
            raw_value = _normalize_cell(row[column] if column < len(row) else None)
            if raw_value and _is_relevant_classwork_cell(raw_value):
                entries.append(_make_entry(class_label, entry_date, raw_value))
    return entries


def _entries_dates_down(rows: list[list[Any]], context, school_year) -> list[dict[str, Any]]:
    header_index, header_classes = _best_row(rows, _normalize_class_label)
    if header_index is None or len(header_classes) < 2:
        return []
    body = rows[header_index + 1:]
    date_column, best = None, 0
    for column in range(min(3, max((len(r) for r in body), default=0))):
        hits = sum(1 for r in body if column < len(r) and _cell_date(r[column], context, school_year))
        if hits > best:
            date_column, best = column, hits
    if date_column is None:
        return []
    entries = []
    for row in body:
        entry_date = _cell_date(row[date_column] if date_column < len(row) else None, context, school_year)
        if not entry_date:
            continue
        for column, class_label in header_classes.items():
            raw_value = _normalize_cell(row[column] if column < len(row) else None)
            if raw_value and _is_relevant_classwork_cell(raw_value):
                entries.append(_make_entry(class_label, entry_date, raw_value))
    return entries


def _best_row(rows: list[list[Any]], parse) -> tuple[int | None, dict[int, Any]]:
    """Among the first rows, the one with the most cells that `parse` understands."""
    best_index, best = None, {}
    for index, row in enumerate(rows[:6]):
        found = {}
        for column, value in enumerate(row):
            parsed = parse(value)
            if parsed:
                found[column] = parsed
        if len(found) > len(best):
            best_index, best = index, found
    return best_index, best


_MONTH_ABBREVIATIONS = {
    "jan": 1, "feb": 2, "mar": 3, "maer": 3, "mrz": 3, "apr": 4, "mai": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "okt": 10, "oct": 10, "nov": 11, "dez": 12, "dec": 12,
}


def _month_from_name(name: str) -> int | None:
    token = _ascii_month(name).lower().rstrip(".")
    return GERMAN_MONTH_LOOKUP.get(token) or _MONTH_ABBREVIATIONS.get(token) or _MONTH_ABBREVIATIONS.get(token[:3])


def _sheet_month_year(sheet_name: str) -> tuple[int, int | None] | None:
    """"November 2025", "Nov. 25", "September", "09.2026", "2026-09" → (month, year or None)."""
    name = str(sheet_name).strip()
    match = re.match(r"^([A-Za-zÄÖÜäöü]+)\.?\s*(\d{4}|\d{2})?$", name)
    if match:
        month = _month_from_name(match.group(1))
        if not month:
            return None
        year = match.group(2)
        if not year:
            return month, None
        return month, int(year) if len(year) == 4 else 2000 + int(year)
    match = re.match(r"^(\d{1,2})[./-](\d{4})$", name)
    if match and 1 <= int(match.group(1)) <= 12:
        return int(match.group(1)), int(match.group(2))
    match = re.match(r"^(\d{4})[./-](\d{1,2})$", name)
    if match and 1 <= int(match.group(2)) <= 12:
        return int(match.group(2)), int(match.group(1))
    return None


def _cell_date(value: Any, context: tuple[int, int | None] | None = None,
               school_year: int | None = None) -> date | None:
    """A date in a header cell: real Excel dates, "Mo 01.09.", "1.9.", "01.09.2026", "2026-09-01"."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _normalize_cell(value)
    if not text or len(text) > 30:
        return None
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    match = re.search(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.?(\d{4}|\d{2}(?!\d))?", text)
    if not match:
        return None
    day, month = int(match.group(1)), int(match.group(2))
    year_text = match.group(3)
    if year_text:
        year = int(year_text) if len(year_text) == 4 else 2000 + int(year_text)
    elif context and context[1]:
        year = context[1]
        if context[0] == 12 and month == 1:
            year += 1  # a January date on the December sheet
        elif context[0] == 1 and month == 12:
            year -= 1
    elif school_year:
        year = school_year if month >= 8 else school_year + 1
    else:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _header_date(raw_header: str, month: int, year: int) -> date | None:
    """The date in a header cell of a month sheet (kept for older callers)."""
    return _cell_date(raw_header, (month, year), None)


def _normalize_cell(value: Any) -> str:
    if value in (None, ""):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


_CLASS_LABEL = re.compile(r"^(?:kl(?:asse)?\.?\s*)?0?(\d{1,2})\s*([a-z])(?![a-z])", re.IGNORECASE)
_PHASE_LABEL = re.compile(r"^(Q\s*[1-4])(?:\s*/\s*Q?\s*([1-4]))?(?![\d])", re.IGNORECASE)


def _normalize_class_label(value: Any) -> str:
    """"7a", "07A", "Kl. 7a", "7 a (Mü)" → "7A"; "Q1", "Q1/Q2", "Q3/4" → "Q1", "Q1/2", "Q3/4"."""
    if isinstance(value, (datetime, date)):
        return ""
    label = _normalize_cell(value)
    if not label or len(label) > 24:
        return ""
    match = _CLASS_LABEL.match(label)
    if match and 5 <= int(match.group(1)) <= 13:
        return f"{int(match.group(1))}{match.group(2).upper()}"
    match = _PHASE_LABEL.match(label)
    if match:
        first = match.group(1).replace(" ", "").upper()
        return f"{first}/{match.group(2)}" if match.group(2) else first
    return ""


# Whole words only: "KA" must not match "Vokabeltest" or "Karfreitag".
_CLASSWORK_KINDS = (
    ("VERA", re.compile(r"\bVERA\b")),
    ("LEK", re.compile(r"\bLEK\b")),
    ("Klausur", re.compile(r"\bKLA\b|KLAUSUR")),
    ("Klassenarbeit", re.compile(r"\bKA\b|ARBEIT")),
    ("Test", re.compile(r"TEST")),
    ("Prüfung", re.compile(r"\bMSA\b|PRÜF")),
)


def _classwork_kind(value: str) -> str:
    upper = value.upper()
    for kind, pattern in _CLASSWORK_KINDS:
        if pattern.search(upper):
            return kind
    return "Eintrag"


def _is_relevant_classwork_cell(value: str) -> bool:
    return _classwork_kind(value) != "Eintrag"


def _serialize_classwork_entry(entry: dict[str, Any]) -> dict[str, str]:
    return {
        "classLabel": entry["classLabel"],
        "dateLabel": entry["dateLabel"],
        "weekdayLabel": entry["date"].strftime("%A"),
        "title": entry["title"],
        "kind": entry["kind"],
        "summary": _classwork_summary(entry["title"], entry["kind"]),
        "isoDate": entry["date"].isoformat(),
    }


def _classwork_summary(value: str, kind: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    clean = re.sub(r"^\d+\.\s*", "", clean)
    clean = re.sub(r"\bKA\b", "Klassenarbeit", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bKLA\b", "Klausur", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bmdl\.\s*", "muendlich ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip(" -")

    if clean.upper().startswith(kind.upper()):
        return clean

    return f"{kind}: {clean}"


def _class_sort_key(value: str) -> tuple[int, str]:
    match = re.match(r"^(\d{1,2})([A-Z])$", value.upper())
    if match:
        return int(match.group(1)), match.group(2)
    qmatch = re.match(r"^Q(\d(?:/\d)?)$", value.upper())
    if qmatch:
        return 100, qmatch.group(1)
    return 999, value.upper()
def _berlin_today(now: datetime) -> date:
    """Return today's date in Europe/Berlin time (UTC+1 winter, UTC+2 summer).

    Uses stdlib only — no pytz/zoneinfo dependency.
    Approximation: if the system UTC offset for Berlin cannot be determined we
    add 2 hours (CEST) which is correct from late March to late October.
    """
    try:
        import zoneinfo  # Python 3.9+
        berlin = zoneinfo.ZoneInfo("Europe/Berlin")
        return datetime.now(berlin).date()
    except Exception:
        # Fallback: assume UTC+2 (CEST) — safe for April–October school year
        from datetime import timezone as _tz
        berlin_offset = timedelta(hours=2)
        return (now.replace(tzinfo=timezone.utc) + berlin_offset).date()


def _download_document(url: str) -> DownloadResult:
    request = Request(url, headers={"User-Agent": "LehrerCockpit/1.0"})

    try:
        with _open_request(request) as response:
            return DownloadResult(
                reachable=True,
                status_code=response.status,
                content_type=response.headers.get("Content-Type", ""),
                last_modified=response.headers.get("Last-Modified", ""),
                content_length=response.headers.get("Content-Length", ""),
                data=response.read(),
                error="",
            )
    except HTTPError as exc:
        return DownloadResult(
            reachable=False,
            status_code=exc.code,
            content_type="",
            last_modified="",
            content_length="",
            data=b"",
            error=type(exc).__name__,
        )
    except URLError as exc:
        return DownloadResult(
            reachable=False,
            status_code=None,
            content_type="",
            last_modified="",
            content_length="",
            data=b"",
            error=type(exc).__name__,
        )


def _open_request(request: Request):
    return urlopen(request, timeout=18, context=tls_context())


def _blocked_detail(title: str, download: DownloadResult) -> str:
    if download.status_code:
        return f"{title} wird bei jedem Refresh neu versucht, ist aber aktuell für den automatischen Abruf blockiert (HTTP {download.status_code})."
    return f"{title} wird bei jedem Refresh neu versucht, war aber gerade nicht erreichbar."


def _extract_orgaplan_entries(data: bytes, now: datetime) -> tuple[list[dict[str, Any]], str]:
    reader = PdfReader(BytesIO(data))
    month_label = GERMAN_MONTHS[now.month]
    next_month = GERMAN_MONTHS[1 if now.month == 12 else now.month + 1]

    page_info = _locate_orgaplan_month_page(reader.pages, month_label)
    fallback_info = _locate_orgaplan_month_page(reader.pages, next_month)

    if not page_info and fallback_info:
        page_info = fallback_info
        month_label = next_month

    if not page_info:
        return [], month_label

    page, page_text = page_info
    month_number = now.month
    year = now.year
    match = re.match(r"^([A-Za-zÄÖÜäöü]+)\s*Stand\s*(\d{2})\.(\d{2})\.(\d{4})", page_text)
    if match:
        month_name = _ascii_month(match.group(1))
        month_number = next(
            (number for number, label in GERMAN_MONTHS.items() if label.lower() == month_name.lower()),
            now.month,
        )
        # "Stand" is when the page was edited, not its month: January pages are
        # edited in December. The school year in the header decides.
        from .orgaplan import page_month, school_year_of

        located = page_month(page_text, school_year_of(page_text))
        year = located[0] if located else int(match.group(4))
        month_label = GERMAN_MONTHS[month_number]

    structured_entries = _extract_positioned_orgaplan_entries(page, year, month_number)
    if structured_entries:
        return structured_entries, month_label

    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    return _extract_orgaplan_entries_from_lines(lines, year, month_number), month_label


def _locate_orgaplan_month_page(pages: Any, month_label: str):
    for page in pages:
        page_text = _normalize_text(page.extract_text() or "")
        if _ascii_month(page_text).startswith(month_label):
            return page, page_text
    return None


def _extract_orgaplan_entries_from_lines(lines: list[str], year: int, month_number: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current_day: int | None = None
    current_lines: list[str] = []

    for raw_line in lines[1:]:
        line = re.sub(r"^(\d{2})(?=\d\.)", r"\1 ", raw_line)
        line = re.sub(r"^(\d{1,2})(?=[A-ZÄÖÜQ])", r"\1 ", line)

        if line.startswith("Organisationsplan"):
            break

        if line.startswith("KWTag"):
            continue

        day_with_text = re.match(r"^(\d{1,2})\s+(.+)$", line)
        if re.fullmatch(r"\d{1,2}", line):
            if current_day is not None and current_lines:
                entries.append(_build_entry(year, month_number, current_day, current_lines))
            current_day = int(line)
            current_lines = []
            continue

        if day_with_text:
            if current_day is not None and current_lines:
                entries.append(_build_entry(year, month_number, current_day, current_lines))
            current_day = int(day_with_text.group(1))
            current_lines = [day_with_text.group(2)]
            continue

        if current_day is not None:
            current_lines.append(line)

    if current_day is not None and current_lines:
        entries.append(_build_entry(year, month_number, current_day, current_lines))

    return [entry for entry in entries if entry["text"]]


def _extract_positioned_orgaplan_entries(page: Any, year: int, month_number: int) -> list[dict[str, Any]]:
    rows = _extract_orgaplan_rows(page)
    if not rows:
        return []

    entries: list[dict[str, Any]] = []
    current_entry: dict[str, Any] | None = None

    for row in rows:
        cells = row["cells"]
        day = _extract_day_from_cell(cells["day"])
        if not day:
            day = _extract_day_from_cell(cells["general"])

        if day:
            if current_entry and _entry_has_content(current_entry):
                entries.append(_finalize_structured_entry(current_entry))
            current_entry = _empty_orgaplan_entry(year, month_number, day)

        if current_entry is None:
            continue

        general = _strip_day_prefix(cells["general"], day)
        _append_if_text(current_entry["general"], general)
        _append_if_text(current_entry["middle"], cells["middle"])
        _append_if_text(current_entry["middleNotes"], cells["middleNotes"])
        _append_if_text(current_entry["upper"], cells["upper"])
        _append_if_text(current_entry["upperNotes"], cells["upperNotes"])

    if current_entry and _entry_has_content(current_entry):
        entries.append(_finalize_structured_entry(current_entry))

    return entries


def _extract_orgaplan_rows(page: Any) -> list[dict[str, Any]]:
    fragments: list[tuple[float, float, str]] = []
    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)

    def visitor(text: str, cm: Any, tm: Any, font_dict: Any, font_size: Any) -> None:
        cleaned = _normalize_text(text)
        if not cleaned:
            return
        fragments.append((float(tm[4]), float(tm[5]), cleaned))

    try:
        page.extract_text(visitor_text=visitor)
    except (TypeError, PdfReadError):
        return []

    if not fragments:
        return []

    grouped: list[dict[str, Any]] = []
    for x, y, text in sorted(fragments, key=lambda item: (-item[1], item[0])):
        if y < 52 or y > page_height - 56:
            continue
        if not grouped or abs(grouped[-1]["y"] - y) > 4:
            grouped.append({"y": y, "fragments": []})
        grouped[-1]["fragments"].append((x, text))

    rows: list[dict[str, Any]] = []
    for row in grouped:
        cells = {
            "day": [],
            "general": [],
            "middle": [],
            "middleNotes": [],
            "upper": [],
            "upperNotes": [],
        }
        for x, text in row["fragments"]:
            column = _orgaplan_column_for_x(x, page_width)
            cells[column].append(text)

        merged = {name: _dedupe_join(parts) for name, parts in cells.items()}
        row_text = " ".join(value for value in merged.values() if value)
        if not row_text or _is_orgaplan_header_row(row_text):
            continue
        rows.append({"y": row["y"], "cells": merged})

    return rows


def _orgaplan_column_for_x(x: float, page_width: float) -> str:
    if x < page_width * 0.13:
        return "day"
    if x < page_width * 0.31:
        return "general"
    if x < page_width * 0.49:
        return "middle"
    if x < page_width * 0.64:
        return "middleNotes"
    if x < page_width * 0.83:
        return "upper"
    return "upperNotes"


def _is_orgaplan_header_row(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "kwtag",
        "allg. termine",
        "mittelstufentermine",
        "oberstufentermine",
        "bemerkungen",
        "organisationsplan",
        "stand ",
    )
    return any(marker in lowered for marker in markers) or bool(re.search(r"orgaplan \d{4}/\d{2,4}", lowered))


def _extract_day_from_cell(value: str) -> int | None:
    match = re.match(r"^(\d{1,2})(?:\D|$)", value)
    if not match:
        return None
    day = int(match.group(1))
    if 1 <= day <= 31:
        return day
    return None


def _strip_day_prefix(value: str, day: int | None) -> str:
    if not day:
        return value
    return re.sub(rf"^{day}\s*", "", value, count=1).strip()


def _empty_orgaplan_entry(year: int, month: int, day: int) -> dict[str, Any]:
    return {
        "date": date(year, month, day),
        "dateLabel": date(year, month, day).strftime("%d.%m."),
        "general": [],
        "middle": [],
        "middleNotes": [],
        "upper": [],
        "upperNotes": [],
    }


def _append_if_text(bucket: list[str], value: str) -> None:
    cleaned = _clean_orgaplan_cell(value)
    if cleaned:
        bucket.append(cleaned)


def _clean_orgaplan_cell(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    text = re.sub(r"\b\d{4,}\b", "", text).strip()
    return text


def _entry_has_content(entry: dict[str, Any]) -> bool:
    return any(entry[key] for key in ("general", "middle", "middleNotes", "upper", "upperNotes"))


def _finalize_structured_entry(entry: dict[str, Any]) -> dict[str, Any]:
    general = _dedupe_join(entry["general"])
    middle = _dedupe_join(entry["middle"])
    middle_notes = _dedupe_join(entry["middleNotes"])
    upper = _dedupe_join(entry["upper"])
    upper_notes = _dedupe_join(entry["upperNotes"])

    if middle_notes and _looks_like_upper_text(middle_notes):
        upper = _merge_text_parts(middle_notes, upper)
        middle_notes = ""

    if not upper and upper_notes:
        upper = upper_notes
        upper_notes = ""

    if not middle and middle_notes and not _looks_like_upper_text(middle_notes):
        middle = middle_notes
        middle_notes = ""

    text = _compose_orgaplan_text(general, middle, middle_notes, upper, upper_notes)
    return {
        "date": entry["date"],
        "dateLabel": entry["dateLabel"],
        "title": _structured_entry_title(general, middle, upper, upper_notes),
        "text": text,
        "general": general,
        "middle": middle,
        "middleNotes": middle_notes,
        "upper": upper,
        "upperNotes": upper_notes,
    }


def _compose_orgaplan_text(
    general: str,
    middle: str,
    middle_notes: str,
    upper: str,
    upper_notes: str,
) -> str:
    parts = []
    if general:
        parts.append(f"Allgemein: {general}")
    if middle:
        details = f" ({middle_notes})" if middle_notes else ""
        parts.append(f"Mittelstufe: {middle}{details}")
    if upper:
        details = f" ({upper_notes})" if upper_notes else ""
        parts.append(f"Oberstufe: {upper}{details}")
    return " | ".join(parts)


def _dedupe_join(parts: list[str]) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = _clean_orgaplan_cell(part)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(normalized)
    return " ".join(cleaned)


def _merge_text_parts(left: str, right: str) -> str:
    if left and right:
        return f"{left} {right}".strip()
    return left or right


def _looks_like_upper_text(value: str) -> bool:
    lowered = value.lower()
    return bool(re.search(r"\bq[1-4]\b", lowered)) or "abitur" in lowered or "5.pk" in lowered


def _structured_entry_title(general: str, middle: str, upper: str, upper_notes: str) -> str:
    for candidate in (general, middle, upper, upper_notes):
        if candidate:
            return _compact_orgaplan_title(candidate)
    return "Orgaplan-Eintrag"


def _compact_orgaplan_title(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    for separator in (" // ", " (", ", "):
        head = normalized.split(separator, 1)[0].strip()
        if 8 <= len(head) <= 72:
            return head
    if len(normalized) <= 72:
        return normalized
    return f"{normalized[:69].rstrip()}..."


def _build_entry(year: int, month: int, day: int, lines: list[str]) -> dict[str, Any]:
    event_date = date(year, month, day)
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b\d{4,}\b", "", text).strip()
    return {
        "date": event_date,
        "dateLabel": event_date.strftime("%d.%m."),
        "title": _entry_title(text),
        "text": text,
    }


def _entry_title(text: str) -> str:
    separators = [" // ", ":"]
    for separator in separators:
        if separator in text:
            head = text.split(separator, 1)[0].strip()
            if len(head) >= 5:
                return head
    return text[:80].strip()


def _build_orgaplan_highlights(upcoming: list[dict[str, Any]]) -> list[dict[str, str]]:
    interesting = []
    keywords = ("konferenz", "deadline", "abgabe", "pruefung", "prüf", "kein unterricht", "gesamtkonferenz", "zulassung")
    for entry in upcoming:
        text = entry["text"].lower()
        if any(keyword in text for keyword in keywords):
            interesting.append(
                {
                    "dateLabel": entry["dateLabel"],
                    "title": entry["title"],
                    "detail": entry["text"],
                }
            )
        if len(interesting) >= 4:
            break

    if interesting:
        return interesting

    return [
        {
            "dateLabel": entry["dateLabel"],
            "title": entry["title"],
            "detail": entry["text"],
        }
        for entry in upcoming[:4]
    ]


def _serialize_entry(entry: dict[str, Any]) -> dict[str, str]:
    return {
        "dateLabel": entry["dateLabel"],
        "isoDate": entry["date"].isoformat(),
        "title": entry["title"],
        "text": entry["text"],
        "general": entry.get("general", ""),
        "middle": entry.get("middle", ""),
        "middleNotes": entry.get("middleNotes", ""),
        "upper": entry.get("upper", ""),
        "upperNotes": entry.get("upperNotes", ""),
    }


def _count_orgaplan_sections(entries: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "general": sum(1 for entry in entries if entry.get("general")),
        "middle": sum(1 for entry in entries if entry.get("middle")),
        "upper": sum(1 for entry in entries if entry.get("upper")),
    }


def _normalize_text(value: str) -> str:
    return value.replace("\xa0", " ").replace("\u202f", " ").strip()


def _ascii_month(value: str) -> str:
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    result = value
    for source, target in replacements.items():
        result = result.replace(source, target)
    return result
