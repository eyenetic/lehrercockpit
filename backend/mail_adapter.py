from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
import html
import imaplib
import json
import re
import subprocess
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
                "nextStep": "MAIL_LOCAL_SOURCE=apple_mail setzen oder IMAP-Zugang hinterlegen",
                "detail": "Mail-Vorschau ist vorbereitet, aber noch nicht konfiguriert.",
            },
            messages=[],
            priorities=[],
            mode="demo",
            note="Demo-Daten aktiv, weil weder Apple Mail noch IMAP als Mailquelle aktiviert sind.",
        )

    if settings.apple_mail_enabled:
        return _fetch_apple_mail_sync(settings, now)

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


def _fetch_apple_mail_sync(settings: MailSettings, now: datetime) -> MailSyncResult:
    try:
        messages = _load_from_apple_mail(settings, now)
        priorities = [
            {
                "id": f"prio-mail-{message['id']}",
                "title": message["title"],
                "detail": message["snippet"],
                "priority": message["priority"],
                "source": "Dienstmail",
                "due": "neu",
            }
            for message in messages
            if message["priority"] in {"critical", "high"}
        ][:3]

        return MailSyncResult(
            source={
                "id": "mail",
                "name": "Dienstmail",
                "type": "Apple Mail",
                "status": "ok",
                "cadence": "lokal bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "Read-only Vorschau in Apple Mail spaeter um Filter fuer Schulleitung und Eltern erweitern",
                "detail": f"{len(messages)} lokale Nachrichten aus Apple Mail geladen.",
            },
            messages=messages,
            priorities=priorities,
            mode="live-mail",
            note=f"Apple-Mail-Vorschau ist lokal aktiv. Letzter Abruf: {now.strftime('%H:%M')}.",
        )
    except Exception as exc:
        detail = f"Apple-Mail-Vorschau konnte nicht geladen werden: {type(exc).__name__}."
        if isinstance(exc, subprocess.CalledProcessError):
            stderr_lines = [line.strip() for line in (exc.stderr or "").splitlines() if line.strip()]
            if stderr_lines:
                detail = f"Apple-Mail-Vorschau konnte nicht geladen werden: {stderr_lines[-1][:180]}"
        return MailSyncResult(
            source={
                "id": "mail",
                "name": "Dienstmail",
                "type": "Apple Mail",
                "status": "warning",
                "cadence": "lokal bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "Apple Mail oeffnen und Codex ggf. unter Systemeinstellungen > Datenschutz > Automation freigeben",
                "detail": detail,
            },
            messages=[],
            priorities=[],
            mode="demo",
            note="Apple Mail ist als lokale Quelle aktiviert, konnte aber gerade nicht ausgelesen werden.",
        )


def _load_from_apple_mail(settings: MailSettings, now: datetime) -> list[dict[str, Any]]:
    script = _build_apple_mail_script(settings.max_messages, settings.local_mailbox, settings.local_account)
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-"],
        input=script,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    messages = []
    for index, line in enumerate(lines, start=1):
        fields = line.split("\x1f")
        if len(fields) != 5:
            continue

        subject, sender, read_state, received_iso, snippet = fields
        received_at = _parse_local_date(received_iso, now)
        messages.append(
            {
                "id": f"apple-mail-{index}",
                "channel": "mail",
                "channelLabel": "Dienstmail",
                "sender": sender or "Apple Mail",
                "title": subject or "(ohne Betreff)",
                "snippet": snippet or "Keine Textvorschau verfuegbar.",
                "priority": _priority_for_message(subject, sender, snippet),
                "timestamp": received_at.strftime("%H:%M"),
                "sortKey": received_at.isoformat(),
                "unread": read_state.strip().lower() != "true",
                "_receivedAt": received_at.isoformat(),
            }
        )

    messages.sort(key=lambda item: item.get("_receivedAt", ""), reverse=True)
    messages = messages[: settings.max_messages]
    for message in messages:
        message.pop("_receivedAt", None)

    return messages


def _build_apple_mail_script(max_messages: int, mailbox_name: str, account_match: str) -> str:
    mailbox_name_json = json.dumps(mailbox_name or "")
    account_match_json = json.dumps((account_match or "").lower())
    scan_count = min(max(max_messages * 3, 12), 24)
    return f"""
const fieldSep = String.fromCharCode(31);
const maxCount = {scan_count};
const fallbackMailboxName = {mailbox_name_json};
const targetAccount = {account_match_json};

function normalizeText(value) {{
  return String(value || "").replace(/[\\r\\n\\t]+/g, " ").trim();
}}

function twoDigits(value) {{
  return String(value).padStart(2, "0");
}}

function isoDate(value) {{
  const date = new Date(value);
  return [
    date.getFullYear(),
    twoDigits(date.getMonth() + 1),
    twoDigits(date.getDate()),
  ].join("-") + "T" + [
    twoDigits(date.getHours()),
    twoDigits(date.getMinutes()),
    twoDigits(date.getSeconds()),
  ].join(":");
}}

function pickMailbox(mailApp) {{
  const accounts = mailApp.accounts();
  for (let index = 0; index < accounts.length; index += 1) {{
    const account = accounts[index];
    let accountName = "";
    try {{
      accountName = normalizeText(account.name()).toLowerCase();
    }} catch (error) {{}}
    if (targetAccount && accountName && !accountName.includes(targetAccount)) {{
      continue;
    }}
    let mailboxes = [];
    try {{
      mailboxes = account.mailboxes();
    }} catch (error) {{}}
    if (fallbackMailboxName) {{
      for (let mailboxIndex = 0; mailboxIndex < mailboxes.length; mailboxIndex += 1) {{
        const mailbox = mailboxes[mailboxIndex];
        try {{
          if (normalizeText(mailbox.name()) === fallbackMailboxName) return mailbox;
        }} catch (error) {{}}
      }}
    }}
    if (mailboxes.length) return mailboxes[0];
  }}

  const allMailboxes = mailApp.mailboxes();
  if (fallbackMailboxName) {{
    for (let mailboxIndex = 0; mailboxIndex < allMailboxes.length; mailboxIndex += 1) {{
      const mailbox = allMailboxes[mailboxIndex];
      try {{
        if (normalizeText(mailbox.name()) === fallbackMailboxName) return mailbox;
      }} catch (error) {{}}
    }}
  }}
  return allMailboxes.length ? allMailboxes[0] : null;
}}

const Mail = Application("com.apple.mail");
const mailbox = pickMailbox(Mail);
if (!mailbox) throw new Error("Kein Apple-Mail-Postfach gefunden");

const messages = mailbox.messages();
const limitCount = Math.min(messages.length, maxCount);
const lines = [];

for (let index = 0; index < limitCount; index += 1) {{
  const message = messages[index];
  let subject = "";
  let sender = "";
  let readValue = "false";
  let receivedValue = "";
  try {{ subject = normalizeText(message.subject()); }} catch (error) {{}}
  try {{ sender = normalizeText(message.sender()); }} catch (error) {{}}
  try {{ readValue = String(message.readStatus()); }} catch (error) {{}}
  try {{ receivedValue = isoDate(message.dateReceived()); }} catch (error) {{}}
  lines.push([subject, sender, readValue, receivedValue, "Lokale Vorschau aus Apple Mail"].join(fieldSep));
}}

lines.join("\\n");
""".strip()


def _parse_local_date(raw_value: str, now: datetime) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw_value)
        return parsed.replace(tzinfo=now.tzinfo)
    except ValueError:
        return now


def _matches_local_account(target: str, account_name: str, mailbox_name: str, recipients: str) -> bool:
    needle = target.strip().lower()
    haystack = " ".join([account_name or "", mailbox_name or "", recipients or ""]).lower()
    return needle in haystack


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
