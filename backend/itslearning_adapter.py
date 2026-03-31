from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import json
import socket
import ssl
import re
from typing import Any
from urllib.parse import urlencode, urljoin
import http.cookiejar
from urllib.error import URLError
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener

from .config import ItslearningSettings


@dataclass
class ItslearningSyncResult:
    source: dict[str, Any]
    messages: list[dict[str, Any]]
    priorities: list[dict[str, Any]]
    mode: str
    note: str


def fetch_itslearning_sync(settings: ItslearningSettings, now: datetime) -> ItslearningSyncResult:
    if not settings.configured:
        return ItslearningSyncResult(
            source={
                "id": "itslearning",
                "name": "itslearning",
                "type": "Lernplattform",
                "status": "warning",
                "cadence": "auf Abruf",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "ITSLEARNING_BASE_URL setzen",
                "detail": "itslearning ist noch nicht konfiguriert.",
            },
            messages=[],
            priorities=[],
            mode="missing",
            note="itslearning ist noch nicht angebunden.",
        )

    if not settings.native_login_configured:
        return ItslearningSyncResult(
            source={
                "id": "itslearning",
                "name": "itslearning",
                "type": "Lernplattform",
                "status": "warning",
                "cadence": "lokal bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "ITSLEARNING_USERNAME und ITSLEARNING_PASSWORD lokal in .env.local hinterlegen",
                "detail": "Der Updates-Feed ist vorbereitet. Fuer persoenliche itslearning-Updates fehlen noch lokale Zugangsdaten.",
            },
            messages=[],
            priorities=[],
            mode="prepared",
            note="itslearning ist als lokaler Updates-Feed vorbereitet, wartet aber noch auf Benutzername und Passwort.",
        )

    try:
        messages = _fetch_updates_with_retry(settings, now)
        if not messages:
            return ItslearningSyncResult(
                source={
                    "id": "itslearning",
                    "name": "itslearning",
                    "type": "Lernplattform",
                    "status": "warning",
                    "cadence": "lokal bei Reload",
                    "lastSync": now.strftime("%H:%M"),
                    "nextStep": "Nach dem naechsten Login die Updates-Seitenstruktur genauer zuordnen",
                    "detail": "Anmeldung gelang, aber die Updates konnten aus der aktuellen Seitenstruktur noch nicht eindeutig gelesen werden.",
                },
                messages=[],
                priorities=[],
                mode="connected-unparsed",
                note="itslearning ist verbunden, die Updates-Struktur muss aber noch genauer gemappt werden.",
            )

        priorities = [
            {
                "id": f"prio-itslearning-{message['id']}",
                "title": message["title"],
                "detail": message["snippet"],
                "priority": "high" if message["unread"] else "medium",
                "source": "itslearning",
                "due": message["timestamp"],
            }
            for message in messages[:2]
        ]

        return ItslearningSyncResult(
            source={
                "id": "itslearning",
                "name": "itslearning",
                "type": "Lernplattform",
                "status": "ok",
                "cadence": "lokal bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "Updates weiter verfeinern oder spaeter Deep Links pro Kurs ergaenzen",
                "detail": f"{len(messages)} itslearning-Updates geladen.",
            },
            messages=messages,
            priorities=priorities,
            mode="live-itslearning",
            note=f"itslearning-Updates sind lokal verbunden. Letzter Abruf: {now.strftime('%H:%M')}.",
        )
    except Exception as exc:
        return ItslearningSyncResult(
            source={
                "id": "itslearning",
                "name": "itslearning",
                "type": "Lernplattform",
                "status": "error",
                "cadence": "lokal bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": _error_next_step(exc),
                "detail": _error_detail(exc),
            },
            messages=[],
            priorities=[],
            mode="error",
            note="itslearning konnte gerade nicht geladen werden.",
        )


def _fetch_updates_with_retry(settings: ItslearningSettings, now: datetime) -> list[dict[str, Any]]:
    try:
        return _fetch_updates(settings, now, verify_ssl=True)
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            return _fetch_updates(settings, now, verify_ssl=False)
        raise


def _fetch_updates(settings: ItslearningSettings, now: datetime, *, verify_ssl: bool) -> list[dict[str, Any]]:
    opener = _build_opener(verify_ssl=verify_ssl)
    login_html = _read_text(opener, settings.base_url)
    form_state = _extract_login_form_state(login_html)

    payload = {
        "__EVENTTARGET": "__Page",
        "__EVENTARGUMENT": "NativeLoginButtonClicked",
        "__VIEWSTATE": form_state.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR": form_state.get("__VIEWSTATEGENERATOR", ""),
        "__EVENTVALIDATION": form_state.get("__EVENTVALIDATION", ""),
        "ctl00$ContentPlaceHolder1$Username": settings.username,
        "ctl00$ContentPlaceHolder1$Password": settings.password,
        "ctl00$ContentPlaceHolder1$ChromebookApp": "false",
        "ctl00$ContentPlaceHolder1$showNativeLoginValueField": "true",
    }

    login_result = _post_form(opener, settings.base_url, payload)
    if _looks_like_login_page(login_result):
        raise RuntimeError("Anmeldung wurde nicht bestaetigt")

    updates_html = ""
    for candidate in _candidate_urls(settings.base_url):
        candidate_html = _read_text(opener, candidate)
        if _looks_like_login_page(candidate_html):
            continue
        updates_html = candidate_html
        targeted_updates = _extract_dashboard_updates(candidate_html, settings.base_url, settings.max_updates)
        if targeted_updates:
            return targeted_updates
        if _contains_update_markers(candidate_html):
            break

    if not updates_html:
        updates_html = login_result

    return _extract_updates(updates_html, settings.base_url, settings.max_updates, now)


def _build_opener(*, verify_ssl: bool):
    cookie_jar = http.cookiejar.CookieJar()
    context = ssl.create_default_context() if verify_ssl else ssl._create_unverified_context()
    return build_opener(HTTPCookieProcessor(cookie_jar), HTTPSHandler(context=context))


def _read_text(opener: Any, url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "LehrerCockpit/1.0",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        },
    )
    with opener.open(request, timeout=15) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def _post_form(opener: Any, url: str, payload: dict[str, str]) -> str:
    body = urlencode(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "LehrerCockpit/1.0",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        },
    )
    with opener.open(request, timeout=15) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def _candidate_urls(base_url: str) -> list[str]:
    normalized = base_url.rstrip("/") + "/"
    return [
        urljoin(normalized, "Dashboard/Dashboard.aspx?LocationType=Personal&DashboardType=MyPage"),
        urljoin(normalized, "CourseCards"),
        urljoin(normalized, "DashboardMenu.aspx"),
        urljoin(normalized, "welcome.aspx"),
    ]


def _extract_login_form_state(html: str) -> dict[str, str]:
    fields = {}
    for field_name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        match = re.search(
            rf'name="{re.escape(field_name)}"[^>]*value="([^"]*)"',
            html,
            re.IGNORECASE,
        )
        fields[field_name] = unescape(match.group(1)) if match else ""
    return fields


def _looks_like_login_page(html: str) -> bool:
    lowered = html.lower()
    markers = (
        "itslearning-anmeldeseite",
        "mit dem berliner schulportal anmelden",
        "bei itslearning anmelden",
        "ctl00_contentplaceholder1_username",
    )
    return any(marker in lowered for marker in markers)


def _contains_update_markers(html: str) -> bool:
    lowered = html.lower()
    markers = (
        "update",
        "aktualisierung",
        "announcement",
        "mitteilung",
        "activity",
        "aufgabe",
        "task",
    )
    return any(marker in lowered for marker in markers)


class _UpdateBlockParser(HTMLParser):
    keywords = ("update", "announcement", "activity", "task", "assignment", "feed", "news")
    ignore_keywords = ("footer", "header", "navigation", "sidebar", "menu")

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[dict[str, Any]] = []
        self._ignore_depth = 0
        self._capture_depth = 0
        self._text_parts: list[str] = []
        self._title_candidates: list[str] = []
        self._links: list[tuple[str, str]] = []
        self._current_href = ""
        self._current_link_text: list[str] = []
        self._heading_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: (value or "") for key, value in attrs}
        attr_blob = " ".join(
            [
                tag,
                attr_map.get("class", ""),
                attr_map.get("id", ""),
                attr_map.get("data-testid", ""),
                attr_map.get("data-test-id", ""),
                attr_map.get("aria-label", ""),
            ]
        ).lower()

        if tag in {"script", "style"}:
            self._ignore_depth += 1
            return

        if self._ignore_depth:
            return

        if self._capture_depth == 0 and any(keyword in attr_blob for keyword in self.keywords) and not any(
            keyword in attr_blob for keyword in self.ignore_keywords
        ):
            self._start_capture()

        if self._capture_depth:
            self._capture_depth += 1
            if tag == "a":
                self._current_href = attr_map.get("href", "")
                self._current_link_text = []
            if tag in {"h1", "h2", "h3", "h4", "strong", "b"}:
                self._heading_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignore_depth:
            self._ignore_depth -= 1
            return

        if self._ignore_depth or not self._capture_depth:
            return

        if tag == "a" and self._current_href:
            text = _compact(" ".join(self._current_link_text))
            if text:
                self._links.append((text, self._current_href))
            self._current_href = ""
            self._current_link_text = []

        if tag in {"h1", "h2", "h3", "h4", "strong", "b"} and self._heading_depth:
            self._heading_depth -= 1

        self._capture_depth -= 1
        if self._capture_depth == 0:
            self._finish_block()

    def handle_data(self, data: str) -> None:
        if self._ignore_depth or not self._capture_depth:
            return

        clean = _compact(data)
        if not clean:
            return

        self._text_parts.append(clean)
        if self._current_href:
            self._current_link_text.append(clean)
        if self._heading_depth:
            self._title_candidates.append(clean)

    def _start_capture(self) -> None:
        self._capture_depth = 1
        self._text_parts = []
        self._title_candidates = []
        self._links = []
        self._current_href = ""
        self._current_link_text = []
        self._heading_depth = 0

    def _finish_block(self) -> None:
        text = _compact(" ".join(self._text_parts))
        title = next((item for item in self._title_candidates if len(item) > 4), "")
        if not title and self._links:
            title = self._links[0][0]
        if not title or len(text) < 20:
            return

        href = self._links[0][1] if self._links else ""
        self.blocks.append({"title": title, "text": text, "href": href})


def _extract_updates(html: str, base_url: str, max_updates: int, now: datetime) -> list[dict[str, Any]]:
    dashboard_updates = _extract_dashboard_updates(html, base_url, max_updates)

    parser = _UpdateBlockParser()
    parser.feed(html)

    seen: set[str] = set()
    messages: list[dict[str, Any]] = []
    for message in dashboard_updates:
        dedupe_key = f"{message['title']}|{message['snippet'][:80]}"
        if dedupe_key in seen:
          continue
        seen.add(dedupe_key)
        messages.append(message)

    for index, block in enumerate(parser.blocks, start=1):
        title = _compact(block["title"])
        text = _compact(block["text"])
        if not title or title.lower() in {"updates", "news", "aktualisierungen"}:
            continue

        dedupe_key = f"{title}|{text[:80]}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        snippet = text
        if snippet.startswith(title):
            snippet = _compact(snippet[len(title) :])
        if not snippet:
            snippet = "Neue Aktivitaet in itslearning."

        timestamp = _extract_timestamp(text) or now.strftime("%H:%M")
        link = block["href"]
        if link:
            link = urljoin(base_url.rstrip("/") + "/", link)

        messages.append(
            {
                "id": f"itslearning-{len(messages) + 1}",
                "channel": "itslearning",
                "channelLabel": "itslearning",
                "sender": "itslearning",
                "title": title[:120],
                "snippet": snippet[:220],
                "priority": _itslearning_priority(title, snippet),
                "timestamp": timestamp,
                "unread": True,
                "url": link,
            }
        )

        if len(messages) >= max_updates:
            break

    return messages


def _extract_dashboard_updates(html: str, base_url: str, max_updates: int) -> list[dict[str, Any]]:
    def extract_stream_blocks(fragment: str) -> list[str]:
        blocks: list[str] = []
        item_starts = list(
            re.finditer(
                r'<li\b[^>]*class="[^"]*itsl-cb-stream-item[^"]*"',
                fragment,
                re.IGNORECASE | re.DOTALL,
            )
        )
        for index, match in enumerate(item_starts):
            start = match.start()
            end = item_starts[index + 1].start() if index + 1 < len(item_starts) else len(fragment)
            blocks.append(fragment[start:end])
        return blocks

    widget_match = re.search(r"<h2>\s*Letzte Aktualisierungen\s*</h2>(.*?)</ul>\s*</div>", html, re.IGNORECASE | re.DOTALL)
    if not widget_match:
        return []

    widget_html = widget_match.group(1)
    blocks = extract_stream_blocks(widget_html)
    if len(blocks) < min(max_updates, 2):
        pagewide_blocks = extract_stream_blocks(html)
        if len(pagewide_blocks) > len(blocks):
            blocks = pagewide_blocks
    if not blocks:
        return []

    messages = []
    for index, block in enumerate(blocks[:max_updates], start=1):
        sender_match = re.search(r'itsl-notifications-person">(.*?)</span>', block, re.IGNORECASE | re.DOTALL)
        course_match = re.search(r'in <a [^>]*><span>(.*?)</span></a>', block, re.IGNORECASE | re.DOTALL)
        timestamp_match = re.search(
            r'itsl-cb-stream-item-timestamp.*?<span[^>]*title="([^"]+)"[^>]*>(.*?)</span>',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        link_match = re.search(r'href="([^"]+/main\.aspx\?CourseID=\d+[^"]*)"', block, re.IGNORECASE)
        attachment_match = re.search(
            r'itsl-light-bulletins-elementlink-elementname\s*">\s*(.*?)\s*</div>',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        shared_match = re.search(
            r'data-light-bulletin-single-item-shared-data-svelte="([^"]+)"',
            block,
            re.IGNORECASE | re.DOTALL,
        )

        sender = _compact(sender_match.group(1) if sender_match else "itslearning")
        course = _compact(course_match.group(1) if course_match else "itslearning")
        title = f"{sender} in {course}" if course else sender
        title = title[:120]

        snippet = _extract_bulletin_snippet(shared_match.group(1) if shared_match else "")
        attachment = _compact(attachment_match.group(1) if attachment_match else "")
        if attachment:
            snippet = f"{snippet} Datei: {attachment}." if snippet else f"Datei: {attachment}."
        if not snippet:
            snippet = "Neue Aktivitaet in itslearning."

        timestamp = ""
        unread = True
        if timestamp_match:
            timestamp = _compact(timestamp_match.group(2))
            unread = "vor " in timestamp.lower() or "heute" in timestamp.lower()
        sort_key = _compact(timestamp_match.group(1) if timestamp_match else "")

        link = urljoin(base_url.rstrip("/") + "/", link_match.group(1)) if link_match else base_url

        messages.append(
            {
                "id": f"itslearning-dashboard-{index}",
                "channel": "itslearning",
                "channelLabel": "itslearning",
                "sender": course or "itslearning",
                "title": title,
                "snippet": snippet[:220],
                "priority": _itslearning_priority(title, snippet),
                "timestamp": timestamp or "Update",
                "sortKey": sort_key,
                "unread": unread,
                "url": link,
            }
        )

    return messages


def _extract_bulletin_snippet(shared_attr: str) -> str:
    if not shared_attr:
        return ""

    try:
        shared_data = json.loads(unescape(shared_attr))
        rtf_content = shared_data.get("rtfContent")
        if not rtf_content:
            return _compact(shared_data.get("text") or "")

        rich_text = json.loads(rtf_content)
        text_parts: list[str] = []
        _collect_rich_text(rich_text, text_parts)
        return _compact(" ".join(text_parts[:4]))
    except Exception:
        decoded = unescape(shared_attr)
        matches = re.findall(r"\\u0022text\\u0022:\\u0022(.*?)\\u0022", decoded)
        clean_matches = [_compact(item) for item in matches if _compact(item)]
        return _compact(" ".join(clean_matches[:4]))


def _collect_rich_text(node: Any, parts: list[str]) -> None:
    if isinstance(node, dict):
        text = _compact(str(node.get("text", "")))
        if text:
            parts.append(text)
        for child in node.values():
            _collect_rich_text(child, parts)
        return

    if isinstance(node, list):
        for item in node:
            _collect_rich_text(item, parts)


def _itslearning_priority(title: str, snippet: str) -> str:
    lowered = f"{title} {snippet}".lower()
    if any(keyword in lowered for keyword in ("abgabe", "frist", "deadline", "important", "wichtig")):
        return "high"
    return "medium"


def _extract_timestamp(text: str) -> str:
    match = re.search(r"\b(\d{1,2}:\d{2})\b", text)
    if match:
        return match.group(1)

    match = re.search(r"\b(\d{1,2}\.\d{1,2}\.(?:\d{2,4})?)\b", text)
    if match:
        return match.group(1)

    lowered = text.lower()
    if "heute" in lowered:
        return "Heute"
    if "gestern" in lowered:
        return "Gestern"
    return ""


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def _error_detail(exc: Exception) -> str:
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.gaierror):
            return "itslearning konnte gerade nicht geladen werden, weil der lokale Server keinen DNS-/Internet-Zugriff hat."
        if isinstance(reason, ssl.SSLCertVerificationError):
            return "itslearning konnte wegen eines lokalen Zertifikatsproblems nicht geladen werden."
        if reason:
            return f"itslearning-Login fehlgeschlagen: {reason}."
    return f"itslearning-Login fehlgeschlagen: {type(exc).__name__}."


def _error_next_step(exc: Exception) -> str:
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.gaierror):
            return "Den lokalen Server mit Internetzugriff starten oder direkt im Mac-Terminal ausfuehren."
        if isinstance(reason, ssl.SSLCertVerificationError):
            return "Python-Zertifikate auf dem Mac pruefen oder den lokalen Zertifikats-Fallback im Cockpit nutzen."
    return "Zugangsdaten pruefen oder Seite nach erfolgreichem Login einmal im Browser aufrufen"
