#!/usr/bin/env python3
"""Cockpit Mail Agent.

Small local HTTP agent for Lehrercockpit mail previews.
Runs on localhost and exposes:
  GET /health
  GET /mail

Mac mode reads Apple Mail via AppleScript.
Windows mode reads Outlook via PowerShell COM.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


HOST = "127.0.0.1"
PORT = int(os.environ.get("COCKPIT_AGENT_PORT", "8765"))
MAX_MESSAGES = int(os.environ.get("COCKPIT_AGENT_MAX_MESSAGES", "12"))


APPLE_SCRIPT = r"""
tell application "Mail"
    set resultList to {}
    set theMessages to messages of inbox of first account
    set maxCount to %MAX_MESSAGES%
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


POWERSHELL_SCRIPT = r"""
$ErrorActionPreference = "Stop"
$maxCount = %MAX_MESSAGES%
$outlook = New-Object -ComObject Outlook.Application
$namespace = $outlook.GetNamespace("MAPI")
$inbox = $namespace.GetDefaultFolder(6)
$items = $inbox.Items
$items.Sort("[ReceivedTime]", $true)
$result = @()
$count = [Math]::Min($items.Count, $maxCount)
for ($i = 1; $i -le $count; $i++) {
  $m = $items.Item($i)
  if ($null -eq $m) { continue }
  $sender = ""
  try { $sender = [string]$m.SenderName } catch {}
  $subject = ""
  try { $subject = [string]$m.Subject } catch {}
  $date = ""
  try { $date = ([datetime]$m.ReceivedTime).ToString("yyyy-MM-dd HH:mm") } catch {}
  $unread = $false
  try { $unread = [bool]$m.UnRead } catch {}
  $result += [pscustomobject]@{
    sender = $sender
    subject = $subject
    date = $date
    unread = $unread
  }
}
$result | ConvertTo-Json -Depth 3
"""


def detect_mode(explicit_mode: str) -> str:
    if explicit_mode in {"mac", "windows"}:
        return explicit_mode
    system = platform.system().lower()
    if "darwin" in system:
        return "mac"
    if "windows" in system:
        return "windows"
    return "unsupported"


def read_apple_mail(max_messages: int) -> dict[str, Any]:
    script = APPLE_SCRIPT.replace("%MAX_MESSAGES%", str(max_messages))
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return error_payload("osascript wurde nicht gefunden.", "apple_mail", "mac")
    except subprocess.TimeoutExpired:
        return error_payload("Apple Mail hat nicht rechtzeitig geantwortet.", "apple_mail", "mac")

    if result.returncode != 0:
        return error_payload(
            "Apple Mail ist nicht erreichbar oder der Zugriff wurde noch nicht erlaubt.",
            "apple_mail",
            "mac",
        )

    raw = result.stdout.strip()
    if not raw:
        return success_payload([], "apple_mail", "mac", "Keine Mails gefunden.")

    messages: list[dict[str, Any]] = []
    entries = [entry.strip() for entry in raw.split("|||SEP|||") if entry.strip()]
    for entry in entries[:max_messages]:
        parts = entry.split("|||")
        if len(parts) < 4:
            continue
        messages.append(
            {
                "sender": parts[0].strip() or "Apple Mail",
                "subject": parts[1].strip() or "(ohne Betreff)",
                "date": parts[2].strip(),
                "unread": parts[3].strip().lower() == "false",
            }
        )
    return success_payload(messages, "apple_mail", "mac", f"{len(messages)} Mails geladen.")


def read_windows_outlook(max_messages: int) -> dict[str, Any]:
    script = POWERSHELL_SCRIPT.replace("%MAX_MESSAGES%", str(max_messages))
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except FileNotFoundError:
        return error_payload("PowerShell wurde nicht gefunden.", "outlook", "windows")
    except subprocess.TimeoutExpired:
        return error_payload("Outlook hat nicht rechtzeitig geantwortet.", "outlook", "windows")

    if result.returncode != 0:
        return error_payload(
            "Outlook ist nicht erreichbar. Bitte Outlook geoeffnet lassen und den Agenten erneut starten.",
            "outlook",
            "windows",
        )

    try:
        parsed = json.loads(result.stdout or "[]")
        if isinstance(parsed, dict):
            parsed = [parsed]
    except Exception:
        return error_payload("Outlook-Daten konnten nicht gelesen werden.", "outlook", "windows")

    messages: list[dict[str, Any]] = []
    for item in parsed[:max_messages]:
        if not isinstance(item, dict):
            continue
        messages.append(
            {
                "sender": str(item.get("sender") or "Outlook").strip(),
                "subject": str(item.get("subject") or "(ohne Betreff)").strip(),
                "date": str(item.get("date") or "").strip(),
                "unread": bool(item.get("unread")),
            }
        )
    return success_payload(messages, "outlook", "windows", f"{len(messages)} Mails geladen.")


def success_payload(messages: list[dict[str, Any]], source: str, platform_name: str, detail: str) -> dict[str, Any]:
    return {
        "status": "ok",
        "messages": messages,
        "detail": detail,
        "source": source,
        "platform": platform_name,
        "fetchedAt": datetime.now().isoformat(),
    }


def error_payload(detail: str, source: str, platform_name: str) -> dict[str, Any]:
    return {
        "status": "error",
        "messages": [],
        "detail": detail,
        "source": source,
        "platform": platform_name,
        "fetchedAt": datetime.now().isoformat(),
    }


class AgentHandler(BaseHTTPRequestHandler):
    mode = "unsupported"

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            payload = {
                "status": "ok",
                "agent": "cockpit-mail-agent",
                "mode": self.mode,
                "port": PORT,
            }
            self._json(payload)
            return

        if self.path == "/mail":
            payload = self._mail_payload()
            self._json(payload)
            return

        self._json({"status": "error", "detail": "not_found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _mail_payload(self) -> dict[str, Any]:
        if self.mode == "mac":
            return read_apple_mail(MAX_MESSAGES)
        if self.mode == "windows":
            return read_windows_outlook(MAX_MESSAGES)
        return error_payload("Dieses System wird vom Mini-Agenten noch nicht unterstuetzt.", "unsupported", self.mode)

    def _json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cockpit Mail Agent")
    parser.add_argument("--mode", choices=["auto", "mac", "windows"], default="auto")
    args = parser.parse_args()

    mode = detect_mode(args.mode)
    AgentHandler.mode = mode
    server = ThreadingHTTPServer((HOST, PORT), AgentHandler)
    print(f"[cockpit-agent] gestartet auf http://{HOST}:{PORT} ({mode})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
