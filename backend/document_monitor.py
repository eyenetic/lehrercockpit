from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class MonitoredDocument:
    id: str
    title: str
    url: str
    type: str
    note: str


def build_document_monitor(
    documents: list[MonitoredDocument],
    state_path: Path,
    now: datetime,
) -> list[dict[str, Any]]:
    stored_state = _load_state(state_path)
    updated_state = dict(stored_state)
    results = []

    for document in documents:
        previous_entry = stored_state.get(document.id, {})
        current_probe = _probe_document(document.url)
        changed = _has_changed(previous_entry, current_probe)

        if current_probe["reachable"]:
            updated_state[document.id] = {
                "etag": current_probe["etag"],
                "last_modified": current_probe["last_modified"],
                "content_length": current_probe["content_length"],
                "status_code": current_probe["status_code"],
                "checked_at": now.isoformat(),
            }

        results.append(
            {
                "id": document.id,
                "title": document.title,
                "type": document.type,
                "status": _status_for_probe(current_probe, changed),
                "changed": changed,
                "checkedAt": now.strftime("%H:%M"),
                "detail": _detail_for_probe(document, current_probe, previous_entry, changed),
                "url": document.url,
            }
        )

    _write_state(state_path, updated_state)
    return results


def _probe_document(url: str) -> dict[str, Any]:
    request = Request(url, method="HEAD", headers={"User-Agent": "LehrerCockpit/1.0"})

    try:
        with _open_request(request) as response:
            headers = response.headers
            return {
                "reachable": True,
                "status_code": response.status,
                "etag": headers.get("ETag"),
                "last_modified": headers.get("Last-Modified"),
                "content_length": headers.get("Content-Length"),
            }
    except HTTPError as error:
        return {
            "reachable": False,
            "status_code": error.code,
            "etag": None,
            "last_modified": None,
            "content_length": None,
        }
    except URLError:
        return {
            "reachable": False,
            "status_code": None,
            "etag": None,
            "last_modified": None,
            "content_length": None,
        }


def _open_request(request: Request):
    try:
        return urlopen(request, timeout=12)
    except URLError as error:
        reason = getattr(error, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            insecure_context = ssl._create_unverified_context()
            return urlopen(request, timeout=12, context=insecure_context)
        raise


def _has_changed(previous_entry: dict[str, Any], current_probe: dict[str, Any]) -> bool:
    if not previous_entry or not current_probe["reachable"]:
        return False

    current_fingerprint = (
        current_probe["etag"],
        current_probe["last_modified"],
        current_probe["content_length"],
    )
    previous_fingerprint = (
        previous_entry.get("etag"),
        previous_entry.get("last_modified"),
        previous_entry.get("content_length"),
    )
    return current_fingerprint != previous_fingerprint


def _status_for_probe(current_probe: dict[str, Any], changed: bool) -> str:
    if changed:
        return "changed"
    if current_probe["reachable"]:
        return "tracked"
    if current_probe["status_code"]:
        return "warning"
    return "error"


def _detail_for_probe(
    document: MonitoredDocument,
    current_probe: dict[str, Any],
    previous_entry: dict[str, Any],
    changed: bool,
) -> str:
    if current_probe["reachable"] and changed:
        return (
            f"{document.note} Aenderung erkannt: "
            f"Last-Modified {current_probe['last_modified'] or 'unbekannt'}."
        )

    if current_probe["reachable"] and previous_entry:
        return (
            f"{document.note} Kein Unterschied zum letzten bekannten Stand. "
            f"Letzte Quelle: {current_probe['last_modified'] or 'ohne Last-Modified'}."
        )

    if current_probe["reachable"]:
        return (
            f"{document.note} Erstbeobachtung gespeichert. "
            f"Quelle meldet {current_probe['last_modified'] or 'keine Zeitangabe'}."
        )

    if current_probe["status_code"]:
        return (
            f"{document.note} Automatischer Abruf derzeit blockiert "
            f"(HTTP {current_probe['status_code']})."
        )

    return f"{document.note} Quelle war beim letzten Pruefen nicht erreichbar."


def _load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}

    try:
        with state_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        return {}


def _write_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, ensure_ascii=True)
