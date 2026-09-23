from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import base64
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import NextcloudSettings
from .http_utils import tls_context


@dataclass
class NextcloudSyncResult:
    source: dict[str, Any]
    note: str


def fetch_nextcloud_sync(settings: NextcloudSettings, now: datetime) -> NextcloudSyncResult:
    if not settings.configured:
        return NextcloudSyncResult(
            source={
                "id": "nextcloud",
                "name": "Nextcloud",
                "type": "Fehlzeiten",
                "status": "warning",
                "cadence": "lokal vorbereiten",
                "lastSync": "nicht verbunden",
                "nextStep": "Arbeitsbereich lokal vorbereiten",
                "detail": "Nextcloud ist als Arbeitsbereich noch nicht eingerichtet.",
            },
            note="",
        )

    if not settings.login_configured:
        return NextcloudSyncResult(
            source={
                "id": "nextcloud",
                "name": "Nextcloud",
                "type": "Fehlzeiten",
                "status": "ok",
                "cadence": "im Browser",
                "lastSync": "bereit",
                "nextStep": "Arbeitslinks nutzen oder später optional einen lokalen Verbindungscheck hinterlegen",
                "detail": "Nextcloud ist als Arbeitsbereich hinterlegt. Die Dateien lassen sich direkt im Browser öffnen.",
            },
            note="",
        )

    try:
        _probe_nextcloud_webdav(settings)
        return NextcloudSyncResult(
            source={
                "id": "nextcloud",
                "name": "Nextcloud",
                "type": "Fehlzeiten",
                "status": "ok",
                "cadence": "lokal bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "Als Nächstes können wir Metadaten oder später direkte Datei-Leselogik prüfen",
                "detail": (
                    "Nextcloud-Arbeitsbereich lokal verbunden. "
                    "Die Fehlzeiten-Dateien können jetzt direkt aus dem Cockpit geöffnet werden."
                ),
            },
            note=f"Nextcloud-Fehlzeiten sind lokal verbunden. Letzter Abruf: {now.strftime('%H:%M')}.",
        )
    except Exception as exc:
        if settings.workspace_url or settings.q1q2_url or settings.q3q4_url:
            return NextcloudSyncResult(
                source={
                    "id": "nextcloud",
                    "name": "Nextcloud",
                    "type": "Fehlzeiten",
                    "status": "ok",
                    "cadence": "im Browser",
                    "lastSync": now.strftime("%H:%M"),
                    "nextStep": "Arbeitslinks weiter nutzen. Den technischen Direktcheck können wir später noch verfeinern.",
                    "detail": (
                        "Nextcloud ist als Arbeitsbereich nutzbar. "
                        f"Der technische Verbindungscheck war gerade nicht stabil ({_nextcloud_error_detail(exc)})."
                    ),
                },
                note="Nextcloud bleibt als Arbeitsbereich verfügbar.",
            )
        return NextcloudSyncResult(
            source={
                "id": "nextcloud",
                "name": "Nextcloud",
                "type": "Fehlzeiten",
                "status": "warning",
                "cadence": "lokal bei Reload",
                "lastSync": now.strftime("%H:%M"),
                "nextStep": "Zugang prüfen oder später mit der Schul-IT App-Passwoerter/WebDAV klaeren",
                "detail": _nextcloud_error_detail(exc),
            },
            note="Nextcloud konnte gerade nicht technisch geprüft werden.",
        )


def _probe_nextcloud_webdav(settings: NextcloudSettings) -> dict[str, Any]:
    auth_token = base64.b64encode(f"{settings.username}:{settings.password}".encode("utf-8")).decode("ascii")
    dav_root = settings.base_url.rstrip("/") + f"/remote.php/dav/files/{quote(settings.username)}/"
    request = Request(
        dav_root,
        method="PROPFIND",
        headers={
            "Authorization": f"Basic {auth_token}",
            "Depth": "0",
            "User-Agent": "LehrerCockpit/1.0",
        },
    )
    with urlopen(request, timeout=12, context=tls_context()) as response:
        status = getattr(response, "status", 200)
        if status not in {200, 207}:
            raise RuntimeError(f"Unerwarteter Nextcloud-Status {status}")
        return {"status": status}


def _nextcloud_error_detail(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        if exc.code in {401, 403}:
            return "Nextcloud-Zugang abgelehnt. Bitte Benutzername/Passwort prüfen."
        return f"Nextcloud antwortet mit HTTP {exc.code}."
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            return "Das Zertifikat des Nextcloud-Servers konnte nicht bestätigt werden."
        return "Nextcloud konnte lokal nicht erreicht werden."
    return f"Nextcloud-Test fehlgeschlagen: {type(exc).__name__}: {exc}"
