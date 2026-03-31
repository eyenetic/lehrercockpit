"""
mail_adapter.py
───────────────
Liest die letzten Mails aus Apple Mail per AppleScript.
Nur lokal auf macOS. Read-only. Kein IMAP, kein Passwort.

Zusätzlich bleibt eine kleine Kompatibilitätsschicht erhalten, damit das
bestehende Dashboard weiter mit MailSyncResult/fetch_mail_sync arbeiten kann.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Any


logger = logging.getLogger(__name__)

APPLE_SCRIPT = """
tell application "Mail"
    set resultList to {}
    set theMessages to messages of inbox of first account
    set maxCount to 10
    if (count of theMessages) < maxCount then
        set maxCount to count of theMessages
    end if
    repeat with i from 1 to maxCount
        set m to item i of theMessages
        set msgDate to date string of (date received of m)
        set msgTime to time string of (date received of m)
        set resultList to resultList & ¬
            (sender of m) & "|||" & ¬
            (subject of m) & "|||" & ¬
            msgDate & " " & msgTime & "|||" & ¬
            ((read status of m) as string) & "|||SEP|||"
    end repeat
    return resultList as string
end tell
"""


def get_mail_preview(account: str = "", max_messages: int = 10) -> dict[str, Any]:
    """
    Gibt die letzten Mails aus Apple Mail zurück.
    account: optional – E-Mail-Adresse des gewünschten Kontos
    """
    try:
        script = APPLE_SCRIPT
        if account:
            script = APPLE_SCRIPT.replace(
                "first account",
                f'first account whose name contains "{account}"'
            )

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            logger.warning("AppleScript Fehler: %s", result.stderr)
            return _error("Apple Mail nicht erreichbar oder kein Zugriff erlaubt.")

        raw = result.stdout.strip()
        if not raw:
            return {"status": "ok", "messages": [], "detail": "Keine Mails gefunden.", "source": "apple_mail"}

        messages = []
        entries = [entry.strip() for entry in raw.split("|||SEP|||") if entry.strip()]

        for entry in entries[:max_messages]:
            parts = entry.split("|||")
            if len(parts) >= 4:
                messages.append(
                    {
                        "sender": parts[0].strip(),
                        "subject": parts[1].strip(),
                        "date": parts[2].strip(),
                        "unread": parts[3].strip().lower() == "false",
                    }
                )

        return {
            "status": "ok",
            "messages": messages,
            "detail": f"{len(messages)} Mails geladen",
            "source": "apple_mail",
        }

    except subprocess.TimeoutExpired:
        return _error("Apple Mail hat nicht geantwortet (Timeout).")
    except FileNotFoundError:
        return _error("osascript nicht gefunden – nur auf macOS verfügbar.")
    except Exception as exc:
        logger.exception("Unerwarteter Fehler in mail_adapter")
        return _error(str(exc))


def _error(msg: str) -> dict[str, Any]:
    return {
        "status": "error",
        "messages": [],
        "detail": msg,
        "source": "apple_mail",
    }


@dataclass
class MailSyncResult:
    source: dict[str, Any]
    messages: list[dict[str, Any]]
    priorities: list[dict[str, Any]]
    mode: str
    note: str


def fetch_mail_sync(settings: Any, now: datetime) -> MailSyncResult:
    """
    Kompatibilitätsschicht für das bestehende Dashboard.
    Nutzt lokal Apple Mail und mappt das Ergebnis auf das frühere Format.
    """
    if not getattr(settings, "configured", False):
        return MailSyncResult(
            source={
                "id": "mail",
                "name": "Dienstmail",
                "type": "Apple Mail",
                "status": "warning",
                "cadence": "lokal bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "MAIL_LOCAL_SOURCE=apple_mail setzen und lokalen Zugriff erlauben",
                "detail": "Mail-Vorschau ist vorbereitet, aber noch nicht konfiguriert.",
            },
            messages=[],
            priorities=[],
            mode="demo",
            note="Dienstmail ist noch nicht lokal angebunden.",
        )

    result = get_mail_preview(
        getattr(settings, "local_account", "") or "",
        int(getattr(settings, "max_messages", 10) or 10),
    )

    if result.get("status") != "ok":
        return MailSyncResult(
            source={
                "id": "mail",
                "name": "Dienstmail",
                "type": "Apple Mail",
                "status": "warning",
                "cadence": "lokal bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "Apple Mail öffnen und Zugriff für Automatisierung erlauben",
                "detail": result.get("detail", "Apple Mail nicht erreichbar."),
            },
            messages=[],
            priorities=[],
            mode="demo",
            note="Apple Mail ist lokal eingerichtet, konnte aber gerade nicht ausgelesen werden.",
        )

    normalized_messages = []
    priorities = []
    for index, item in enumerate(result.get("messages", []), start=1):
        timestamp = str(item.get("date", "")).strip()
        subject = str(item.get("subject", "")).strip() or "(ohne Betreff)"
        sender = str(item.get("sender", "")).strip() or "Apple Mail"
        unread = bool(item.get("unread"))
        normalized = {
            "id": f"apple-mail-{index}",
            "channel": "mail",
            "channelLabel": "Dienstmail",
            "sender": sender,
            "title": subject,
            "snippet": sender,
            "priority": "high" if unread else "low",
            "timestamp": timestamp,
            "sortKey": f"{index:04d}",
            "unread": unread,
        }
        normalized_messages.append(normalized)
        if unread and len(priorities) < 3:
            priorities.append(
                {
                    "id": f"prio-mail-{index}",
                    "title": subject,
                    "detail": sender,
                    "priority": "high",
                    "source": "Dienstmail",
                    "due": "neu",
                }
            )

    return MailSyncResult(
        source={
            "id": "mail",
            "name": "Dienstmail",
            "type": "Apple Mail",
            "status": "ok",
            "cadence": "lokal bei Reload",
            "lastSync": now.strftime("%H:%M"),
            "nextStep": "Read-only Vorschau in Apple Mail aktiv",
            "detail": result.get("detail", f"{len(normalized_messages)} Mails geladen"),
        },
        messages=normalized_messages,
        priorities=priorities,
        mode="live-mail",
        note=f"Apple-Mail-Vorschau ist lokal aktiv. Letzter Abruf: {now.strftime('%H:%M')}.",
    )
