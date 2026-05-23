"""
school_scraper.py — Extrahiert sinnvolle Links von Schulwebseiten.
Verwendet nur Python-Builtins (urllib + html.parser).
"""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen, Request as UrlRequest
from urllib.error import URLError, HTTPError


# ── Keyword-Kategorisierung ───────────────────────────────────────────────────

_CATEGORY_KEYWORDS: dict = {
    "tools": [
        "nextcloud", "itslearning", "webuntis", "portal", "schulportal",
        "moodle", "teams", "sharepoint", "office",
    ],
    "dokumente": [
        ".pdf", "plan", "liste", "bücherliste", "bücherlist",
        "klassenarbeitsplan", "orgaplan", ".xlsx", ".docx",
        "formulare", "downloads",
    ],
    "kalender": [
        "kalender", "calendar", "termine", "stundenplan",
        "pausenzeiten", "ical",
    ],
    "kontakt": [
        "kontakt", "lehrkräfte", "kollegium", "sekretariat",
        "impressum", "email", "mail",
    ],
}

_CATEGORY_ICONS: dict = {
    "tools": "🔧",
    "dokumente": "📄",
    "kalender": "📅",
    "kontakt": "👥",
    "sonstiges": "↗",
}

# Priority order for sorting (lower = higher priority)
_CATEGORY_PRIORITY: dict = {
    "tools": 0,
    "dokumente": 1,
    "kalender": 2,
    "kontakt": 3,
    "sonstiges": 4,
}


class _LinkExtractor(HTMLParser):
    """Simple HTMLParser subclass that collects all <a href> links with text."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []  # (href, text)
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "a":
            attr_dict = dict(attrs)
            href = attr_dict.get("href", "").strip()
            if href:
                self._current_href = href
                self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            text = " ".join(self._current_text).strip()
            if text:
                self.links.append((self._current_href, text))
            self._current_href = None
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            stripped = data.strip()
            if stripped:
                self._current_text.append(stripped)


def _categorize(url: str, text: str) -> str:
    """Bestimmt die Kategorie eines Links anhand von URL und Linktext."""
    combined = (url + " " + text).lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                return category
    return "sonstiges"


def _is_internal_navigation(link_url: str, base_domain: str) -> bool:
    """True wenn der Link intern ist UND keine relevanten Keywords enthält."""
    parsed = urlparse(link_url)
    link_domain = parsed.netloc.lower()
    # External links are not "internal navigation"
    if link_domain and link_domain != base_domain:
        return False
    # Internal link – check for keywords
    path_and_query = (parsed.path + "?" + parsed.query).lower()
    text_to_check = path_and_query
    all_keywords = [kw for kws in _CATEGORY_KEYWORDS.values() for kw in kws]
    for kw in all_keywords:
        if kw in text_to_check:
            return False
    return True


def _clean_text(text: str, max_len: int = 40) -> str:
    """Bereinigt den Linktext: strip, max 40 Zeichen."""
    cleaned = " ".join(text.split())
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len - 1].rstrip() + "…"
    return cleaned


def scrape_school_links(url: str) -> list[dict]:
    """
    Fetcht eine Schulwebseite und gibt kategorisierte Links zurück.
    Jeder Link: { "title": str, "url": str, "category": str, "icon": str }
    Kategorien: "tools", "dokumente", "kalender", "kontakt", "sonstiges"
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; LehrerCockpit/1.0; "
            "+https://lehrercockpit.com)"
        )
    }
    req = UrlRequest(url, headers=headers)
    try:
        with urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in content_type:
                try:
                    charset = content_type.split("charset=")[-1].strip().split(";")[0].strip()
                except Exception:
                    charset = "utf-8"
            raw = resp.read()
    except HTTPError as exc:
        raise Exception(f"HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise Exception(f"Verbindungsfehler: {exc.reason}") from exc
    except TimeoutError as exc:
        raise Exception("Timeout: Webseite hat nicht rechtzeitig geantwortet") from exc

    try:
        html_text = raw.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        html_text = raw.decode("utf-8", errors="replace")

    parser = _LinkExtractor()
    try:
        parser.feed(html_text)
    except Exception as exc:
        raise Exception(f"HTML konnte nicht geparst werden: {exc}") from exc

    base_parsed = urlparse(url)
    base_domain = base_parsed.netloc.lower()

    seen_urls: set[str] = set()
    raw_links: list[dict] = []

    for href, text in parser.links:
        # Resolve relative URLs
        abs_url = urljoin(url, href)
        parsed_link = urlparse(abs_url)

        # Only http/https
        if parsed_link.scheme not in ("http", "https"):
            continue

        # Ignore pure fragment links
        if not parsed_link.path and parsed_link.fragment:
            continue

        # Ignore empty text
        text_clean = _clean_text(text)
        if not text_clean:
            continue

        # Deduplicate by URL (normalize by removing fragment)
        url_key = abs_url.split("#")[0]
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)

        # Skip internal navigation links (same domain, no keyword match)
        if _is_internal_navigation(url_key, base_domain):
            continue

        category = _categorize(url_key, text_clean)

        # Skip sonstiges internal links (same domain → pure navigation)
        if category == "sonstiges":
            link_domain = parsed_link.netloc.lower()
            if not link_domain or link_domain == base_domain:
                continue

        raw_links.append({
            "title": text_clean,
            "url": url_key,
            "category": category,
            "icon": _CATEGORY_ICONS.get(category, "↗"),
        })

    # Sort by category priority
    raw_links.sort(key=lambda l: _CATEGORY_PRIORITY.get(l["category"], 99))

    # Return max 40 links
    return raw_links[:40]
