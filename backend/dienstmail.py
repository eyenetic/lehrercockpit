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
        newest = uids[-limit:][::-1]
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
        return [messages[u] for u in newest if u in messages]
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
