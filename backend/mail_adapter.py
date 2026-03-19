from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
import html
import imaplib
import re
from typing import Any

from .config import MailSettings


@dataclass
class MailSyncResult:
    source: dict[str, Any]
    messages: list[dict[str, Any]]
    priorities: list[dict[str, Any]]
    mode: str
    note: str


def fetch_mail_sync(settings: MailSettings, now: datetime) -> MailSyncResult:
    if not settings.configured:
        return MailSyncResult(
            source={
                "id": "mail",
                "name": "Dienstmail",
                "type": "E-Mail",
                "status": "warning",
                "cadence": "auf Abruf",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "MAIL_IMAP_HOST, MAIL_USERNAME und MAIL_PASSWORD setzen",
                "detail": "Dienstmail ist vorbereitet, aber noch nicht konfiguriert.",
            },
            messages=[],
            priorities=[],
            mode="demo",
            note="Demo-Daten aktiv, weil noch keine Mail-Zugangsdaten gesetzt sind.",
        )

    client: imaplib.IMAP4 | imaplib.IMAP4_SSL
    try:
        client = imaplib.IMAP4_SSL(settings.host, settings.port) if settings.use_ssl else imaplib.IMAP4(settings.host, settings.port)
        client.login(settings.username, settings.password)
        client.select(settings.folder, readonly=True)

        status, payload = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("Postfachsuche fehlgeschlagen.")

        message_ids = payload[0].split()[-settings.max_messages :]
        message_ids.reverse()

        messages = []
        priorities = []
        for raw_id in message_ids:
            fetch_status, fetch_payload = client.fetch(raw_id, "(RFC822)")
            if fetch_status != "OK" or not fetch_payload or not fetch_payload[0]:
                continue

            raw_message = fetch_payload[0][1]
            if not isinstance(raw_message, bytes):
                continue

            parsed_message = message_from_bytes(raw_message)
            mail_item = _normalize_message(raw_id.decode("ascii", "ignore"), parsed_message, now)
            messages.append(mail_item)

            if mail_item["priority"] in {"critical", "high"}:
                priorities.append(
                    {
                        "id": f"prio-mail-{mail_item['id']}",
                        "title": mail_item["title"],
                        "detail": mail_item["snippet"],
                        "priority": mail_item["priority"],
                        "source": "Dienstmail",
                        "due": "neu",
                    }
                )

        client.logout()

        return MailSyncResult(
            source={
                "id": "mail",
                "name": "Dienstmail",
                "type": "E-Mail",
                "status": "ok",
                "cadence": "manuell oder bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "Filter fuer Klassen, Elternmails und Schulleitungsinfos verfeinern",
                "detail": f"{len(messages)} Nachrichten aus {settings.folder} geladen.",
            },
            messages=messages,
            priorities=priorities[:3],
            mode="live-mail",
            note=f"Dienstmail ist live verbunden. Letzter Abruf: {now.strftime('%H:%M')}.",
        )
    except Exception as exc:
        return MailSyncResult(
            source={
                "id": "mail",
                "name": "Dienstmail",
                "type": "E-Mail",
                "status": "error",
                "cadence": "auf Abruf",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "IMAP-Zugang pruefen oder App-Passwort hinterlegen",
                "detail": f"Mail-Sync fehlgeschlagen: {type(exc).__name__}.",
            },
            messages=[],
            priorities=[],
            mode="demo",
            note="Dienstmail konnte nicht geladen werden. Demo-Daten bleiben sichtbar, bis der Zugang funktioniert.",
        )


def _normalize_message(message_id: str, parsed_message: Message, now: datetime) -> dict[str, Any]:
    sender_name, sender_address = parseaddr(parsed_message.get("From", ""))
    sender = sender_name or sender_address or "Unbekannt"
    title = parsed_message.get("Subject", "").strip() or "(ohne Betreff)"
    received_at = _parse_message_date(parsed_message, now)
    snippet = _extract_snippet(parsed_message)
    priority = _priority_for_message(title, sender, snippet)

    return {
        "id": f"mail-{message_id}",
        "channel": "mail",
        "channelLabel": "Dienstmail",
        "sender": sender,
        "title": title,
        "snippet": snippet,
        "priority": priority,
        "timestamp": received_at.strftime("%H:%M"),
        "unread": True,
    }


def _parse_message_date(parsed_message: Message, now: datetime) -> datetime:
    raw_date = parsed_message.get("Date")
    if not raw_date:
        return now

    try:
        parsed = parsedate_to_datetime(raw_date)
        return parsed.astimezone(now.tzinfo) if parsed.tzinfo else parsed.replace(tzinfo=now.tzinfo)
    except (TypeError, ValueError, IndexError):
        return now


def _extract_snippet(parsed_message: Message) -> str:
    for part in _walk_text_parts(parsed_message):
        cleaned = _cleanup_text(part)
        if cleaned:
            return cleaned[:220]

    return "Keine Textvorschau verfuegbar."


def _walk_text_parts(parsed_message: Message) -> list[str]:
    if parsed_message.is_multipart():
        parts: list[str] = []
        for part in parsed_message.walk():
            if part.get_content_maintype() == "multipart":
                continue

            content_disposition = part.get("Content-Disposition", "")
            if "attachment" in content_disposition.lower():
                continue

            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except LookupError:
                text = payload.decode("utf-8", errors="replace")
            parts.append(text)
        return parts

    payload = parsed_message.get_payload(decode=True)
    if payload is None:
        return []

    charset = parsed_message.get_content_charset() or "utf-8"
    try:
        text = payload.decode(charset, errors="replace")
    except LookupError:
        text = payload.decode("utf-8", errors="replace")
    return [text]


def _cleanup_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _priority_for_message(title: str, sender: str, snippet: str) -> str:
    haystack = f"{title} {sender} {snippet}".lower()
    critical_terms = ("dringend", "sofort", "ausfall", "vertretung", "raumwechsel")
    high_terms = ("eltern", "schulleitung", "konferenz", "frist", "zahlung", "aufsicht")

    if any(term in haystack for term in critical_terms):
        return "critical"
    if any(term in haystack for term in high_terms):
        return "high"
    return "medium"
