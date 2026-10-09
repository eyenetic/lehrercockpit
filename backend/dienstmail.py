"""Dienstmail (Berliner Lehrkräfte-Mail, mailcow) im Posteingang – nur lesen, nur Kopfzeilen.

Each teacher stores her address and an app password from the Dienstmail's device
management (Geräteverwaltung). The server logs in via IMAP and reads sender,
subject, date and the read flag of the newest messages:

- read-only: the mailbox is opened with EXAMINE and headers are fetched with
  BODY.PEEK, so nothing is marked as read, moved or deleted
- no message bodies, nothing stored – only a short in-memory cache
- the app password is encrypted at rest like every "*password" field (crypto.py)
"""
from __future__ import annotations

import email.utils
import imaplib
import os
import re
import socket
import threading
import time
from datetime import datetime, timezone
from email.header import decode_header, make_header
from typing import Any

from .http_utils import tls_context

IMAP_HOST = os.environ.get("DIENSTMAIL_IMAP_HOST", "lehrkraeftemail.schule.berlin.de").strip()
IMAP_PORT = 993
WEBMAIL_URL = "https://lehrkraeftemail.schule.berlin.de/?iam_sso=1"
MAX_MESSAGES = 15
TIMEOUT_SECONDS = 10
_CACHE_SECONDS = 120
_FORCE_MIN_SECONDS = 20

_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, dict[str, Any]]] = {}

_ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DienstmailError(Exception):
    """A problem the teacher can act on; the message is shown as is."""


def is_configured(config: dict | None) -> bool:
    config = config or {}
    return bool(config.get("address") and config.get("app_password"))


def valid_address(value: str) -> bool:
    return bool(_ADDRESS.match(value or ""))


def _text(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:
        return raw.strip()


def _parse_headers(header_bytes: bytes) -> dict[str, str]:
    message = email.message_from_bytes(header_bytes)
    # Split first, decode after: an encoded name may contain a comma ("Müller, Anna").
    name, addr = email.utils.parseaddr(str(message.get("From") or ""))
    name = _text(name)
    when = ""
    try:
        parsed = email.utils.parsedate_to_datetime(message.get("Date", ""))
        if parsed is not None:
            when = (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        pass
    return {"from": name or addr or "Unbekannt", "from_address": addr, "subject": _text(message.get("Subject")) or "(kein Betreff)", "date": when}


def fetch_headers(address: str, app_password: str, *, limit: int = MAX_MESSAGES) -> list[dict[str, Any]]:
    """Newest messages of the INBOX, newest first. Raises DienstmailError with a readable message."""
    try:
        client = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=tls_context(), timeout=TIMEOUT_SECONDS)
    except (OSError, socket.timeout) as exc:
        raise DienstmailError("Die Dienstmail ist gerade nicht erreichbar – das Cockpit versucht es beim nächsten Laden wieder.") from exc
    try:
        try:
            client.login(address, app_password)
        except imaplib.IMAP4.error as exc:
            raise DienstmailError("Anmeldung abgelehnt – bitte Adresse und App-Passwort prüfen (das App-Passwort aus der Geräteverwaltung der Dienstmail, nicht das Schulportal-Passwort).") from exc
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise DienstmailError("Der Posteingang der Dienstmail konnte nicht geöffnet werden.")
        status, data = client.uid("search", None, "ALL")
        uids = (data[0] or b"").split() if status == "OK" and data else []
        # UIDs follow the order mails arrived in this folder, not their date
        # (moved or imported mails) – read a few more and sort by date below.
        newest = uids[-(limit + 10):][::-1]
        if not newest:
            return []
        status, rows = client.uid("fetch", b",".join(newest), "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if status != "OK":
            raise DienstmailError("Die Dienstmail hat die Nachrichtenliste nicht geliefert.")
        messages: dict[bytes, dict[str, Any]] = {}
        for row in rows or []:
            if not isinstance(row, tuple) or len(row) < 2:
                continue
            meta = row[0] or b""
            uid_match = re.search(rb"UID (\d+)", meta)
            if not uid_match:
                continue
            item = _parse_headers(row[1] or b"")
            item["id"] = uid_match.group(1).decode()
            item["unread"] = b"\\Seen" not in meta
            messages[uid_match.group(1)] = item
        ordered = sorted((messages[u] for u in newest if u in messages),
                         key=lambda m: m["date"] or "", reverse=True)
        return ordered[:limit]
    finally:
        try:
            client.logout()
        except Exception:
            pass


def build_payload(config: dict | None, now: datetime, *, force: bool = False) -> dict[str, Any]:
    """Module result for /api/v2/dashboard/data."""
    config = config or {}
    if not is_configured(config):
        return {"ok": True, "data": None, "configured": False}
    address = str(config["address"])
    with _cache_lock:
        hit = _cache.get(address)
    if hit and time.monotonic() - hit[0] < (_FORCE_MIN_SECONDS if force else _CACHE_SECONDS):
        return {"ok": True, "data": hit[1], "configured": True}
    data: dict[str, Any] = {"address": address, "webmail_url": WEBMAIL_URL, "messages": [], "error": None,
                            "fetched_at": now.isoformat()}
    try:
        data["messages"] = fetch_headers(address, str(config["app_password"]))
    except DienstmailError as exc:
        data["error"] = str(exc)
    except Exception as exc:  # protocol oddities – never break the dashboard
        data["error"] = f"Die Dienstmail konnte nicht gelesen werden ({type(exc).__name__})."
    if not data["error"]:
        with _cache_lock:
            _cache[address] = (time.monotonic(), data)
    return {"ok": True, "data": data, "configured": True}


def forget(address: str) -> None:
    with _cache_lock:
        _cache.pop(address, None)


# ── Einzelne Mail lesen (nur auf Klick) ─────────────────────────────────────
MAX_BODY_BYTES = 300_000   # partial fetch: the text comes first, attachments are cut off
MAX_TEXT_CHARS = 8_000


def _html_to_text(html_text: str) -> str:
    from html import unescape
    text = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", html_text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h[1-6]>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def _body_text(raw: bytes) -> tuple[str, list[str]]:
    from email import policy
    message = email.message_from_bytes(raw, policy=policy.default)
    attachments = [part.get_filename() for part in message.iter_attachments() if part.get_filename()] \
        if message.is_multipart() else []
    body = message.get_body(preferencelist=("plain", "html"))
    if body is None:
        return "", attachments
    try:
        content = body.get_content()
    except Exception:
        payload = body.get_payload(decode=True) or b""
        content = payload.decode(body.get_content_charset() or "utf-8", errors="replace")
    if body.get_content_type() == "text/html":
        content = _html_to_text(content)
    return content.strip(), [str(a) for a in attachments]


def fetch_message(address: str, app_password: str, uid: str) -> dict[str, Any]:
    """Text of one message (read-only: BODY.PEEK, the mail stays unread)."""
    if not re.fullmatch(r"\d{1,10}", uid or ""):
        raise DienstmailError("Unbekannte Nachricht.")
    try:
        client = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=tls_context(), timeout=TIMEOUT_SECONDS)
    except (OSError, socket.timeout) as exc:
        raise DienstmailError("Die Dienstmail ist gerade nicht erreichbar.") from exc
    try:
        try:
            client.login(address, app_password)
        except imaplib.IMAP4.error as exc:
            raise DienstmailError("Anmeldung abgelehnt – bitte das App-Passwort unter Verbindungen prüfen.") from exc
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise DienstmailError("Der Posteingang der Dienstmail konnte nicht geöffnet werden.")
        status, rows = client.uid("fetch", uid.encode(), f"(BODY.PEEK[]<0.{MAX_BODY_BYTES}>)")
        raw = next((row[1] for row in rows or [] if isinstance(row, tuple) and len(row) > 1), None)
        if status != "OK" or not raw:
            raise DienstmailError("Diese Mail gibt es nicht mehr – vielleicht wurde sie verschoben oder gelöscht.")
        text, attachments = _body_text(raw)
        truncated = len(text) > MAX_TEXT_CHARS
        return {"text": text[:MAX_TEXT_CHARS], "truncated": truncated, "attachments": attachments[:10]}
    finally:
        try:
            client.logout()
        except Exception:
            pass
