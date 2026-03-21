from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
import re
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


@dataclass
class DownloadResult:
    reachable: bool
    status_code: int | None
    content_type: str
    last_modified: str
    content_length: str
    data: bytes
    error: str


def build_plan_digest(orgaplan_url: str, now: datetime) -> dict[str, Any]:
    return {
        "orgaplan": _build_orgaplan_digest(orgaplan_url, now),
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

    try:
        month_entries, month_label = _extract_orgaplan_entries(download.data, now)
        upcoming = [entry for entry in month_entries if entry["date"] >= now.date()]
        if not upcoming:
            upcoming = month_entries[:5]
        section_counts = _count_orgaplan_sections(upcoming)

        return {
            "status": "ok",
            "title": "Orgaplan",
            "detail": (
                f"Live gelesen. Stand Quelle: {download.last_modified or 'ohne Zeitstempel'}. "
                f"{len(upcoming)} relevante Eintraege fuer {month_label}. "
                f"Allgemein {section_counts['general']}, Mittelstufe {section_counts['middle']}, Oberstufe {section_counts['upper']}."
            ),
            "monthLabel": month_label,
            "updatedAt": now.strftime("%H:%M"),
            "highlights": _build_orgaplan_highlights(upcoming),
            "upcoming": [_serialize_entry(entry) for entry in upcoming[:8]],
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
    try:
        return urlopen(request, timeout=18)
    except URLError as error:
        reason = getattr(error, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            insecure_context = ssl._create_unverified_context()
            return urlopen(request, timeout=18, context=insecure_context)
        raise


def _blocked_detail(title: str, download: DownloadResult) -> str:
    if download.status_code:
        return f"{title} wird bei jedem Refresh neu versucht, ist aber aktuell fuer den automatischen Abruf blockiert (HTTP {download.status_code})."
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
    match = re.match(r"^([A-Za-zÄÖÜäöü]+)\s+Stand\s+(\d{2})\.(\d{2})\.(\d{4})", page_text)
    if match:
        month_name = _ascii_month(match.group(1))
        month_number = next(
            (number for number, label in GERMAN_MONTHS.items() if label.lower() == month_name.lower()),
            now.month,
        )
        year = int(match.group(4))
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
        "orgaplan 2025/2026",
    )
    return any(marker in lowered for marker in markers)


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
