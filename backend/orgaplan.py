"""Orgaplan: find the school's current Orgaplan PDF and read the whole school year.

The school publishes a *new* PDF with a new address every few weeks
(…/uploads/2026/09/Orgaplan-2026_27-31.08.2026.pdf), so a fixed link goes
stale. By default the cockpit looks up the newest "Orgaplan" PDF on the school
website itself:
  1. WordPress media search: /wp-json/wp/v2/media?search=Orgaplan (newest first)
  2. otherwise: PDF links on the given web page whose name contains the term.
Admins can pin a fixed PDF instead (mode "fixed").

Each PDF page is one month: "September Stand 31.08.2026" above a table with the
columns KW | Tag | allgemeine Termine | Mittelstufe | Bemerkungen | Oberstufe |
Bemerkungen, headed "Organisationsplan 2026/27". pdfplumber reads the table
cell by cell, so multi-line cells stay with their day. Without pdfplumber the
older position-based reader in plan_digest.py is used (current month only).

Settings (system_settings "orgaplan_source"):
  {"mode": "auto", "site": "https://…", "query": "Orgaplan"} | {"mode": "fixed", "pdf_url": "https://…"}
State (persistence store "orgaplan-state"): the last good result plus the last
error. Errors never wipe the last good entries.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urljoin, urlparse
from urllib.request import Request, urlopen

from .http_utils import UnsafeUrlError, require_public_https_url, tls_context
from .ical_utils import BERLIN

STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "orgaplan-state.json"
SETTING_KEY = "orgaplan_source"
DEFAULT_QUERY = "Orgaplan"

REFRESH_EVERY = timedelta(hours=6)
RETRY_AFTER_ERROR = timedelta(minutes=30)
REPARSE_EVERY = timedelta(hours=24)  # catches a PDF replaced under the same address
UPCOMING_DAYS = 42
MAX_PDF_BYTES = 15 * 1024 * 1024
TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; Lehrercockpit/1.0; +https://lehrercockpit.com)"

MONTH_NAMES = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
               "August", "September", "Oktober", "November", "Dezember"]
_MONTH_LOOKUP = {name.lower(): number for number, name in enumerate(MONTH_NAMES, start=1)}
_MONTH_LOOKUP["maerz"] = 3
_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

_PAGE_TITLE = re.compile(
    r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s*Stand\s*(\d{1,2})\.(\d{1,2})\.(\d{4})",
    re.IGNORECASE,
)
_SCHOOL_YEAR = re.compile(r"(?:Organisationsplan|Orgaplan)\s*(20\d{2})\s*/\s*(\d{2,4})", re.IGNORECASE)
_HIGHLIGHT_WORDS = ("konferenz", "deadline", "abgabe", "prüf", "pruef", "kein unterricht",
                    "zeugnis", "elternabend", "elternsprechtag", "notenschluss", "wandertag")
# German function words and adjectives end a wrapped line; nouns (capitalised) end an item.
_CONTINUES = re.compile(r"(?:[,(+&/:–-]|\b(?:ab|an|am|auf|aus|bei|bis|der|des|die|das|durch|für|"
                        r"im|in|mit|nach|über|und|oder|von|vom|zu|zum|zur))$", re.IGNORECASE)


class OrgaplanError(Exception):
    """Human-readable problem with finding or reading the Orgaplan."""


_lock = threading.Lock()
_refresh_thread: threading.Thread | None = None


# ── Source settings ──────────────────────────────────────────────────────────

def default_site() -> str:
    from .config import SCHOOL_WEBSITE_DEFAULT
    return SCHOOL_WEBSITE_DEFAULT


def normalize_source(raw: Any, legacy: dict[str, str] | None = None) -> dict[str, str]:
    """Stored setting (or the old orgaplan_pdf_url / orgaplan_url keys) → source dict."""
    if isinstance(raw, dict) and raw.get("mode") in ("auto", "fixed"):
        if raw["mode"] == "fixed" and raw.get("pdf_url"):
            return {"mode": "fixed", "pdf_url": str(raw["pdf_url"]).strip()}
        return {"mode": "auto", "site": str(raw.get("site") or default_site()).strip(),
                "query": str(raw.get("query") or DEFAULT_QUERY).strip()}
    legacy = legacy or {}
    pdf_url = (legacy.get("orgaplan_pdf_url") or "").strip()
    page_url = (legacy.get("orgaplan_url") or "").strip()
    for candidate in (pdf_url, page_url):
        # A WordPress upload is replaced by a new upload with the next version:
        # follow the site instead of pinning the old file.
        if "/wp-content/uploads/" in candidate:
            parsed = urlparse(candidate)
            return {"mode": "auto", "site": f"{parsed.scheme}://{parsed.netloc}", "query": DEFAULT_QUERY}
    if page_url and not page_url.lower().split("?")[0].endswith(".pdf"):
        return {"mode": "auto", "site": page_url, "query": DEFAULT_QUERY}
    if pdf_url or page_url:
        return {"mode": "fixed", "pdf_url": pdf_url or page_url}
    return {"mode": "auto", "site": default_site(), "query": DEFAULT_QUERY}


def load_source(conn) -> dict[str, str]:
    from .admin.admin_service import get_system_setting

    raw = get_system_setting(conn, SETTING_KEY, None)
    legacy = {}
    if not raw:
        for key in ("orgaplan_pdf_url", "orgaplan_url"):
            value = get_system_setting(conn, key, "")
            legacy[key] = value if isinstance(value, str) else ""
    return normalize_source(raw, legacy)


def validate_source(body: dict) -> dict[str, str]:
    """Admin input → source dict. Raises OrgaplanError with a German message."""
    mode = body.get("mode")
    if mode == "fixed":
        pdf_url = str(body.get("pdf_url") or "").strip()
        if not pdf_url.lower().startswith("https://"):
            raise OrgaplanError("Bitte den vollständigen PDF-Link (https://…) einfügen.")
        return {"mode": "fixed", "pdf_url": pdf_url[:2000]}
    if mode == "auto":
        site = str(body.get("site") or "").strip() or default_site()
        if not site.lower().startswith("https://"):
            raise OrgaplanError("Bitte die Adresse der Schulwebseite (https://…) einfügen.")
        query = str(body.get("query") or DEFAULT_QUERY).strip()[:60] or DEFAULT_QUERY
        return {"mode": "auto", "site": site[:500], "query": query}
    raise OrgaplanError("Unbekannte Einstellung für den Orgaplan.")


def source_key(source: dict[str, str]) -> str:
    return json.dumps(source, sort_keys=True, ensure_ascii=False)


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _get(url: str, *, accept: str = "*/*", max_bytes: int = 2_000_000) -> tuple[bytes, dict[str, str]]:
    url = require_public_https_url(url)
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with urlopen(request, timeout=TIMEOUT, context=tls_context()) as response:
            data = response.read(max_bytes + 1)
            headers = {k.lower(): v for k, v in response.headers.items()}
    except HTTPError as exc:
        raise OrgaplanError(f"{urlparse(url).netloc} antwortet mit HTTP {exc.code}.") from exc
    except OSError as exc:
        raise OrgaplanError(f"{urlparse(url).netloc} ist nicht erreichbar.") from exc
    if len(data) > max_bytes:
        raise OrgaplanError("Die Datei ist zu groß.")
    return data, headers


def file_name(url: str) -> str:
    return unquote(PurePosixPath(urlparse(url).path).name) or url


# ── Discovery ────────────────────────────────────────────────────────────────

def _matches(query: str, *texts: str) -> bool:
    needle = query.lower()
    return any(needle in (text or "").lower() for text in texts)


def _wordpress_media(site: str, query: str) -> dict[str, str] | None:
    parsed = urlparse(site)
    endpoint = (f"{parsed.scheme}://{parsed.netloc}/wp-json/wp/v2/media?search={quote(query)}"
                "&per_page=20&orderby=date&order=desc&_fields=date,source_url,title,slug,mime_type")
    try:
        data, headers = _get(endpoint, accept="application/json")
    except OrgaplanError:
        return None  # not a WordPress site (or the REST API is closed)
    if "json" not in headers.get("content-type", ""):
        return None
    try:
        items = json.loads(data.decode("utf-8"))
    except ValueError:
        return None
    if not isinstance(items, list):
        return None
    for item in items:  # newest first
        if not isinstance(item, dict):
            continue
        url = str(item.get("source_url") or "")
        title = item.get("title")
        title = title.get("rendered", "") if isinstance(title, dict) else str(title or "")
        is_pdf = item.get("mime_type") == "application/pdf" or url.lower().endswith(".pdf")
        if url.startswith("https://") and is_pdf and _matches(query, url, str(item.get("slug") or ""), title):
            return {"url": url, "name": file_name(url), "published": str(item.get("date") or ""), "via": "wordpress"}
    return None


def _pdf_rank(url: str, index: int) -> tuple:
    """Newest first: school year in the name, upload folder, date in the name, page order."""
    name = file_name(url)
    year = _SCHOOL_YEAR_IN_NAME.search(name)
    upload = re.search(r"/(20\d{2})/(\d{2})/", url)
    stamp = re.search(r"(\d{1,2})\.(\d{1,2})\.(20\d{2})", name)
    return (
        int(year.group(1)) if year else 0,
        (int(upload.group(1)), int(upload.group(2))) if upload else (0, 0),
        (int(stamp.group(3)), int(stamp.group(2)), int(stamp.group(1))) if stamp else (0, 0, 0),
        -index,
    )


_SCHOOL_YEAR_IN_NAME = re.compile(r"(20\d{2})\s*[_/-]\s*(\d{2,4})")


def _linked_pdf(page: str, query: str) -> dict[str, str] | None:
    from .school_scraper import _LinkExtractor

    data, headers = _get(page, accept="text/html")
    charset = "utf-8"
    match = re.search(r"charset=([\w-]+)", headers.get("content-type", ""))
    if match:
        charset = match.group(1)
    parser = _LinkExtractor()
    parser.feed(data.decode(charset, errors="replace"))
    candidates = []
    for index, (href, text) in enumerate(parser.links):
        url = urljoin(page, href).split("#")[0]
        if url.startswith("https://") and ".pdf" in url.lower() and _matches(query, unquote(url), text):
            candidates.append((_pdf_rank(url, index), url))
    if not candidates:
        return None
    best = max(candidates)[1]
    return {"url": best, "name": file_name(best), "published": "", "via": "webseite"}


def discover_latest_pdf(site: str, query: str = DEFAULT_QUERY) -> dict[str, str]:
    """Newest PDF on the school website whose name contains `query`."""
    host = urlparse(site).netloc or site
    found = _wordpress_media(site, query) or _linked_pdf(site, query)
    if not found:
        raise OrgaplanError(f"Auf {host} wurde keine PDF mit „{query}“ im Namen gefunden.")
    return found


# ── PDF reading ──────────────────────────────────────────────────────────────

def _clean_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()
    # Letter-spaced words from the spreadsheet ("n u r") → "nur"
    return re.sub(r"\b[a-zäöüß](?: [a-zäöüß]){2,}\b", lambda m: m.group(0).replace(" ", ""), line)


def join_cell(value: str | None) -> str:
    """Join the lines of one cell: wrapped lines with a space, separate items with " · "."""
    lines = [_clean_line(part) for part in str(value or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    text = lines[0]
    for line in lines[1:]:
        last_word = re.sub(r"[^\wäöüß]", "", text.split(" ")[-1]) if text else ""
        continues = (
            _CONTINUES.search(text) is not None
            or text.count("(") > text.count(")")
            or line[:1].islower() or line[:1] in "()"
            or (len(last_word) >= 2 and last_word.isalpha() and last_word.islower())
        )
        text = f"{text} {line}" if continues else f"{text} · {line}"
    return text


def _header_columns(header: list[str | None]) -> dict[str, int]:
    columns: dict[str, int] = {}
    seen_middle = seen_upper = False
    for index, cell in enumerate(header):
        label = re.sub(r"\s+", " ", str(cell or "")).strip().lower()
        if label == "kw":
            columns["kw"] = index
        elif label == "tag":
            columns["day"] = index
        elif label.startswith("allgemein"):
            columns["general"] = index
        elif label.startswith("mittelstufe"):
            columns["middle"] = index
            seen_middle = True
        elif label.startswith("oberstufe"):
            columns["upper"] = index
            seen_upper = True
        elif label.startswith("bemerkung"):
            if seen_upper:
                columns.setdefault("upperNotes", index)
            elif seen_middle:
                columns.setdefault("middleNotes", index)
    return columns


def _day_number(value: str | None) -> int | None:
    match = re.fullmatch(r"\s*(\d{1,2})\.?\s*", str(value or ""))
    if not match:
        return None
    day = int(match.group(1))
    return day if 1 <= day <= 31 else None


def _guess_day_column(rows: list[list[str | None]], general: int) -> int | None:
    best, best_hits = None, 0
    for column in range(general):
        hits = sum(1 for row in rows if column < len(row) and _day_number(row[column]))
        if hits > best_hits:
            best, best_hits = column, hits
    return best


def entries_from_table(rows: list[list[str | None]], year: int, month: int) -> list[dict[str, Any]]:
    """Table rows of one month page (header included) → entries."""
    header_index = next((i for i, row in enumerate(rows)
                         if any("allgemein" in str(cell or "").lower() for cell in row)), None)
    if header_index is None:
        return []
    columns = _header_columns(rows[header_index])
    body = rows[header_index + 1:]
    if "general" not in columns:
        return []
    day_column = columns.get("day")
    if day_column is None:
        day_column = _guess_day_column(body, columns["general"])
    if day_column is None:
        return []

    def cell(row: list[str | None], key: str) -> str:
        index = columns.get(key)
        return join_cell(row[index]) if index is not None and index < len(row) else ""

    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in body:
        day = _day_number(row[day_column] if day_column < len(row) else "")
        if day:
            try:
                current = {"date": date(year, month, day), "parts": {k: [] for k in _PARTS}}
            except ValueError:
                current = None
                continue
            entries.append(current)
        if current is None:
            continue
        for key in _PARTS:
            text = cell(row, key)
            if text:
                current["parts"][key].append(text)
    return [entry for entry in (_finish(item) for item in entries) if entry]


_PARTS = ("general", "middle", "middleNotes", "upper", "upperNotes")


def _finish(item: dict[str, Any]) -> dict[str, Any] | None:
    fields = {key: " · ".join(dict.fromkeys(values)) for key, values in item["parts"].items()}
    general = fields["general"]
    middle, middle_notes = fields["middle"], fields["middleNotes"]
    upper, upper_notes = fields["upper"], fields["upperNotes"]
    # The Bemerkungen columns often carry the actual item when the main column is empty.
    if not middle and middle_notes:
        middle, middle_notes = middle_notes, ""
    if not upper and upper_notes:
        upper, upper_notes = upper_notes, ""
    # The same text in "allgemein" and a level column means the whole school.
    if middle == general:
        middle = ""
    if upper == general:
        upper = ""
    if not any((general, middle, middle_notes, upper, upper_notes)):
        return None
    day: date = item["date"]
    parts = []
    if general:
        parts.append(f"Allgemein: {general}")
    if middle:
        parts.append(f"Mittelstufe: {middle}" + (f" ({middle_notes})" if middle_notes else ""))
    if upper:
        parts.append(f"Oberstufe: {upper}" + (f" ({upper_notes})" if upper_notes else ""))
    title_source = general or middle or upper or middle_notes or upper_notes
    return {
        "isoDate": day.isoformat(),
        "dateLabel": day.strftime("%d.%m."),
        "weekday": _WEEKDAYS[day.weekday()],
        "title": _compact_title(title_source),
        "text": " | ".join(parts),
        "general": general,
        "middle": middle,
        "middleNotes": middle_notes,
        "upper": upper,
        "upperNotes": upper_notes,
    }


def _compact_title(value: str) -> str:
    first = value.split(" · ", 1)[0]
    for separator in (" // ", " (", ", "):
        head = first.split(separator, 1)[0].strip()
        if 8 <= len(head) <= 72:
            return head
    return first if len(first) <= 72 else first[:69].rstrip() + "…"


def page_month(text: str, school_year: tuple[int, int] | None) -> tuple[int, int, str] | None:
    """(year, month, stand) from the page title "September Stand 31.08.2026"."""
    match = _PAGE_TITLE.search(text or "")
    if not match:
        return None
    month = _MONTH_LOOKUP[match.group(1).lower()]
    stand_day, stand_month, stand_year = int(match.group(2)), int(match.group(3)), int(match.group(4))
    if school_year:
        year = school_year[0] if month >= 8 else school_year[1]
    else:
        # Pages are edited up to ~3 months late and up to ~10 months ahead.
        year = stand_year
        if (month - stand_month) < -3:
            year += 1
        elif (month - stand_month) > 9:
            year -= 1
    return year, month, f"{stand_day:02d}.{stand_month:02d}.{stand_year}"


def school_year_of(text: str) -> tuple[int, int] | None:
    match = _SCHOOL_YEAR.search(text or "")
    if not match:
        return None
    start = int(match.group(1))
    return start, start + 1


def parse_pdf(data: bytes) -> dict[str, Any]:
    """All entries of an Orgaplan PDF. Raises OrgaplanError."""
    if not data.startswith(b"%PDF"):
        raise OrgaplanError("Die Datei ist keine PDF.")
    try:
        import pdfplumber
    except ImportError:
        return _parse_with_pypdf(data)

    entries: list[dict[str, Any]] = []
    stands: list[str] = []
    school_year: tuple[int, int] | None = None
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                school_year = school_year_of(text) or school_year
                located = page_month(text, school_year)
                if not located:
                    continue  # e.g. "Anlage: Vorbereitung 5. PK"
                year, month, stand = located
                tables = page.find_tables()
                if not tables:
                    continue
                table = max(tables, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1]))
                entries.extend(entries_from_table(table.extract(), year, month))
                stands.append(stand)
    except OrgaplanError:
        raise
    except Exception as exc:  # malformed PDF
        raise OrgaplanError(f"Die PDF konnte nicht gelesen werden ({type(exc).__name__}).") from exc

    if not entries:
        raise OrgaplanError("In der PDF wurden keine Termine erkannt – ist es wirklich der Orgaplan?")
    unique = {(e["isoDate"], e["text"]): e for e in entries}
    ordered = sorted(unique.values(), key=lambda e: e["isoDate"])
    return {
        "entries": ordered,
        "school_year": f"{school_year[0]}/{str(school_year[1])[-2:]}" if school_year else "",
        "stand": _latest_stand(stands),
        "first_date": ordered[0]["isoDate"],
        "last_date": ordered[-1]["isoDate"],
    }


def _latest_stand(stands: list[str]) -> str:
    def key(value: str) -> tuple[int, int, int]:
        d, m, y = (int(part) for part in value.split("."))
        return y, m, d
    return max(stands, key=key) if stands else ""


def _parse_with_pypdf(data: bytes) -> dict[str, Any]:
    """Fallback without pdfplumber: current and next month via plan_digest's reader."""
    from . import plan_digest

    now = datetime.now(timezone.utc)
    entries: list[dict[str, Any]] = []
    for offset in (0, 31):
        moment = now + timedelta(days=offset)
        try:
            found, _label = plan_digest._extract_orgaplan_entries(data, moment)
        except Exception as exc:
            raise OrgaplanError(f"Die PDF konnte nicht gelesen werden ({type(exc).__name__}).") from exc
        entries.extend(_from_plan_digest(entry) for entry in found)
    if not entries:
        raise OrgaplanError("In der PDF wurden keine Termine erkannt.")
    unique = {(e["isoDate"], e["text"]): e for e in entries}
    ordered = sorted(unique.values(), key=lambda e: e["isoDate"])
    return {"entries": ordered, "school_year": "", "stand": "",
            "first_date": ordered[0]["isoDate"], "last_date": ordered[-1]["isoDate"]}


def _from_plan_digest(entry: dict[str, Any]) -> dict[str, Any]:
    day: date = entry["date"]
    return {
        "isoDate": day.isoformat(), "dateLabel": day.strftime("%d.%m."), "weekday": _WEEKDAYS[day.weekday()],
        "title": entry.get("title", ""), "text": entry.get("text", ""),
        "general": entry.get("general", ""), "middle": entry.get("middle", ""),
        "middleNotes": entry.get("middleNotes", ""), "upper": entry.get("upper", ""),
        "upperNotes": entry.get("upperNotes", ""),
    }


# ── State and refresh ────────────────────────────────────────────────────────

def load_state() -> dict[str, Any]:
    from .persistence import store

    state = store.read(STATE_PATH, default=None)
    return state if isinstance(state, dict) else {}


def save_state(state: dict[str, Any]) -> None:
    from .persistence import store

    store.write(STATE_PATH, state)


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def refresh_due(state: dict[str, Any], source: dict[str, str], now: datetime) -> bool:
    if state.get("source_key") != source_key(source):
        return True
    checked = _parse_time(state.get("checked_at"))
    if checked is None:
        return True
    return now - checked >= (RETRY_AFTER_ERROR if state.get("error") else REFRESH_EVERY)


def refresh(source: dict[str, str], now: datetime | None = None) -> dict[str, Any]:
    """Find, download and read the current Orgaplan. Never raises; returns the new state."""
    now = now or datetime.now(timezone.utc)
    state = load_state()
    if state.get("source_key") != source_key(source):
        state["pdf_url"] = ""  # a different source: re-read even if the file looks the same
    state.update({"source_key": source_key(source), "mode": source["mode"], "checked_at": now.isoformat()})
    try:
        if source["mode"] == "fixed":
            target = {"url": source["pdf_url"], "name": file_name(source["pdf_url"]), "published": "", "via": "fest"}
        else:
            target = discover_latest_pdf(source["site"], source.get("query") or DEFAULT_QUERY)
        parsed_at = _parse_time(state.get("parsed_at"))
        fresh = (target["url"] == state.get("pdf_url") and parsed_at is not None
                 and now - parsed_at < REPARSE_EVERY and state.get("entries"))
        if not fresh:
            data, headers = _get(target["url"], accept="application/pdf", max_bytes=MAX_PDF_BYTES)
            parsed = parse_pdf(data)
            state.update({
                "pdf_url": target["url"],
                "name": target["name"],
                "published": target.get("published", ""),
                "via": target.get("via", ""),
                "last_modified": headers.get("last-modified", ""),
                "parsed_at": now.isoformat(),
                **parsed,
            })
        state.update({"error": None, "error_at": None})
    except (OrgaplanError, UnsafeUrlError) as exc:
        state.update({"error": str(exc), "error_at": now.isoformat()})
    except Exception as exc:  # never let a refresh crash the caller
        state.update({"error": f"Unerwarteter Fehler ({type(exc).__name__}).", "error_at": now.isoformat()})
    try:
        save_state(state)
    except Exception:
        pass
    return state


def refresh_in_background(source: dict[str, str]) -> threading.Thread | None:
    """Start one refresh at a time per process. Returns the running thread."""
    global _refresh_thread
    with _lock:
        if _refresh_thread is not None and _refresh_thread.is_alive():
            return _refresh_thread
        _refresh_thread = threading.Thread(target=refresh, args=(source,), name="orgaplan-refresh", daemon=True)
        _refresh_thread.start()
        return _refresh_thread


# ── Digest for the dashboard ─────────────────────────────────────────────────

def _berlin_today(now: datetime) -> date:
    return now.astimezone(BERLIN).date()


def _highlights(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    picked = [e for e in entries if any(word in e["text"].lower() for word in _HIGHLIGHT_WORDS)][:4]
    return [{"dateLabel": e["dateLabel"], "isoDate": e["isoDate"], "title": e["title"], "detail": e["text"]}
            for e in (picked or entries[:4])]


def build_digest(state: dict[str, Any], source: dict[str, str], now: datetime) -> dict[str, Any]:
    """Frontend shape (upcoming / today_entries / week_entries / highlights) plus source info."""
    today = _berlin_today(now)
    entries = [e for e in state.get("entries") or [] if isinstance(e, dict) and e.get("isoDate")]
    horizon = (today + timedelta(days=UPCOMING_DAYS)).isoformat()
    week_end = (today + timedelta(days=6)).isoformat()
    today_iso = today.isoformat()
    upcoming = [e for e in entries if today_iso <= e["isoDate"] <= horizon]
    covers_today = bool(entries) and entries[-1]["isoDate"] >= today_iso
    error = state.get("error")

    if not entries:
        status = "error" if error else "pending"
        detail = error or "Der Orgaplan wird gerade geladen …"
    elif not covers_today:
        status = "outdated"
        detail = (f"Der Orgaplan {state.get('school_year') or ''} reicht nur bis "
                  f"{_de_date(entries[-1]['isoDate'])}. Ein aktueller Plan wurde noch nicht gefunden.").replace("  ", " ")
    else:
        status = "ok"
        detail = f"{len(upcoming)} Einträge in den nächsten sechs Wochen."

    return {
        "status": status,
        "title": "Orgaplan",
        "detail": detail,
        "monthLabel": MONTH_NAMES[today.month - 1],
        "sourceUrl": state.get("pdf_url", ""),
        "sourceName": state.get("name", ""),
        "schoolYear": state.get("school_year", ""),
        "stand": state.get("stand", ""),
        "publishedAt": state.get("published", ""),
        "checkedAt": state.get("checked_at", ""),
        "mode": source.get("mode", "auto"),
        "site": source.get("site", ""),
        "error": error,
        "upcoming": upcoming,
        "entries": upcoming,
        "today_entries": [e for e in upcoming if e["isoDate"] == today_iso],
        "week_entries": [e for e in upcoming if e["isoDate"] <= week_end],
        "highlights": _highlights(upcoming),
    }


def _de_date(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d.%m.%Y")
    except ValueError:
        return iso


def current(source: dict[str, str], now: datetime | None = None, *, wait: float = 4.0,
            force: bool = False) -> dict[str, Any]:
    """Digest for the dashboard; refreshes in the background when due.

    Waits up to `wait` seconds only when nothing is known yet (or on force).
    """
    now = now or datetime.now(timezone.utc)
    state = load_state()
    if force or refresh_due(state, source, now):
        thread = refresh_in_background(source)
        if thread is not None and (force or not state.get("entries")):
            thread.join(timeout=wait)
            state = load_state()
    return build_digest(state, source, now)
