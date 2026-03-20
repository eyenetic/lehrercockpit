from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
import html
import imaplib
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
        return MailSyncResult(
            source={
                "id": "mail",
                "name": "Dienstmail",
                "type": "Apple Mail",
                "status": "warning",
                "cadence": "lokal bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "Apple Mail oeffnen und Codex ggf. unter Systemeinstellungen > Datenschutz > Automation freigeben",
                "detail": f"Apple-Mail-Vorschau konnte nicht geladen werden: {type(exc).__name__}.",
            },
            messages=[],
            priorities=[],
            mode="demo",
            note="Apple Mail ist als lokale Quelle aktiviert, konnte aber gerade nicht ausgelesen werden.",
        )


def _load_from_apple_mail(settings: MailSettings, now: datetime) -> list[dict[str, Any]]:
    script = _build_apple_mail_script(settings.max_messages, settings.local_mailbox, settings.local_account)
    result = subprocess.run(
        ["osascript", "-"],
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
        if len(fields) != 8:
            continue

        subject, sender, read_state, received_iso, snippet, account_name, mailbox_name, recipients = fields
        received_at = _parse_local_date(received_iso, now)
        if settings.local_account and not _matches_local_account(settings.local_account, account_name, mailbox_name, recipients):
            continue
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
    mailbox_name = mailbox_name.replace('"', "")
    account_match = account_match.replace('"', "")
    scan_count = min(max(max_messages * 3, 12), 24)
    return f"""
set fieldSep to ASCII character 31
set outputLines to {{}}
set maxCount to {scan_count}
set fallbackMailboxName to "{mailbox_name}"
set targetAccount to "{account_match}"

on twoDigits(valueNumber)
  if valueNumber < 10 then
    return "0" & valueNumber
  end if
  return valueNumber as text
end twoDigits

on monthNumber(monthValue)
  if monthValue is January then return "01"
  if monthValue is February then return "02"
  if monthValue is March then return "03"
  if monthValue is April then return "04"
  if monthValue is May then return "05"
  if monthValue is June then return "06"
  if monthValue is July then return "07"
  if monthValue is August then return "08"
  if monthValue is September then return "09"
  if monthValue is October then return "10"
  if monthValue is November then return "11"
  return "12"
end monthNumber

on normalizeText(rawText)
  set cleanText to rawText as text
  set cleanText to my replaceText(return, " ", cleanText)
  set cleanText to my replaceText(linefeed, " ", cleanText)
  set cleanText to my replaceText(tab, " ", cleanText)
  return cleanText
end normalizeText

on replaceText(findText, replaceText, sourceText)
  set oldDelimiters to AppleScript's text item delimiters
  set AppleScript's text item delimiters to findText
  set textItems to every text item of sourceText
  set AppleScript's text item delimiters to replaceText
  set sourceText to textItems as text
  set AppleScript's text item delimiters to oldDelimiters
  return sourceText
end replaceText

on containsText(sourceText, queryText)
  if queryText is "" then return true
  set sourceLower to do shell script "printf %s " & quoted form of sourceText & " | tr '[:upper:]' '[:lower:]'"
  set queryLower to do shell script "printf %s " & quoted form of queryText & " | tr '[:upper:]' '[:lower:]'"
  return sourceLower contains queryLower
end containsText

tell application "Mail"
  set targetAccountRef to missing value
  repeat with oneAccount in every account
    set accountNameValue to ""
    set addressValue to ""
    try
      set accountNameValue to my normalizeText(name of oneAccount as text)
    end try
    try
      set AppleScript's text item delimiters to ", "
      set addressValue to (email addresses of oneAccount as text)
      set AppleScript's text item delimiters to linefeed
      set addressValue to my normalizeText(addressValue)
    end try
    if my containsText(accountNameValue, targetAccount) or my containsText(addressValue, targetAccount) then
      set targetAccountRef to oneAccount
      exit repeat
    end if
  end repeat

  set mailboxRef to missing value
  if targetAccount is not "" and targetAccountRef is missing value then
    error "Target Apple Mail account not found"
  end if

  if targetAccountRef is not missing value then
    try
      set mailboxRef to first mailbox of targetAccountRef whose name is fallbackMailboxName
    end try
    if mailboxRef is missing value then
      try
        set mailboxRef to first mailbox of targetAccountRef
      end try
    end if
  end if
  if mailboxRef is missing value then
    try
      set mailboxRef to inbox
    end try
  end if
  if mailboxRef is missing value then
    set mailboxRef to first mailbox whose name is fallbackMailboxName
  end if

  set mailMessages to messages of mailboxRef
  set limitCount to count of mailMessages
  if limitCount > maxCount then set limitCount to maxCount

  repeat with indexNumber from 1 to limitCount
    set theMessage to item indexNumber of mailMessages
    set receivedDate to date received of theMessage
    set receivedValue to (year of receivedDate as text) & "-" & my monthNumber(month of receivedDate) & "-" & my twoDigits(day of receivedDate) & "T" & my twoDigits(hours of receivedDate) & ":" & my twoDigits(minutes of receivedDate) & ":" & my twoDigits(seconds of receivedDate)
    set subjectValue to my normalizeText(subject of theMessage as text)
    set senderValue to my normalizeText(sender of theMessage as text)
    set snippetValue to "Lokale Vorschau aus Apple Mail"
    set readValue to (read status of theMessage) as text
    set mailboxNameValue to ""
    set accountNameValue to ""
    try
      set mailboxNameValue to my normalizeText(name of mailbox of theMessage as text)
    end try
    try
      set accountNameValue to my normalizeText(name of account of mailbox of theMessage as text)
    end try
    copy (subjectValue & fieldSep & senderValue & fieldSep & readValue & fieldSep & receivedValue & fieldSep & snippetValue & fieldSep & accountNameValue & fieldSep & mailboxNameValue & fieldSep & "") to end of outputLines
  end repeat
end tell

set AppleScript's text item delimiters to linefeed
return outputLines as text
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
