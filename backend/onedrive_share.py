"""Read files shared through public OneDrive links ("Jeder mit dem Link").

Classic direct-download tricks (…?download=1, api.onedrive.com/v1.0/shares)
stopped working for anonymous callers. This module uses the anonymous
"badger" token that the OneDrive web viewer itself uses:

  1. POST https://api-badgerp.svc.ms/v1.0/token {"appId": …}  → token (~7 days)
  2. GET  https://my.microsoftpersonalcontent.com/_api/v2.0/shares/u!{id}/driveitem
          Authorization: Badger <token>, Prefer: autoredeem
          → name, size, eTag, lastModifiedDateTime, @content.downloadUrl
  3. GET  @content.downloadUrl (pre-authenticated, no headers) → file bytes

A shared *folder* has no download address; then …/driveitem/children lists it
and the newest plan file inside is used, so a new school year's file is picked
up without a new link.

This is not a documented Microsoft API. Callers must keep the manual upload
as a fallback, and Microsoft may refuse datacenter IPs (see OneDriveBlocked).
The browser variant lives in src/features/onedrive-sync.js.
"""
from __future__ import annotations

import base64
import json
import re
import threading
import time as _time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .http_utils import tls_context

BADGER_APP_ID = "5cbed6ac-a083-4e14-b191-b4ba07653de2"
TOKEN_URL = "https://api-badgerp.svc.ms/v1.0/token"
API_BASE = "https://my.microsoftpersonalcontent.com/_api/v2.0"
ONEDRIVE_HOSTS = {"1drv.ms", "onedrive.live.com", "my.microsoftpersonalcontent.com"}
MAX_BYTES = 15 * 1024 * 1024
TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; Lehrercockpit/1.0; +https://lehrercockpit.com)"

_token_lock = threading.Lock()
_token_cache: dict[str, Any] = {}


class OneDriveError(Exception):
    """The shared file could not be read."""


class OneDriveBlocked(OneDriveError):
    """Microsoft refused this caller (typically a datacenter IP)."""


SHARING_HINT = ("In OneDrive die Datei oder den Ordner auswählen → „Teilen“ → „Jeder mit dem Link kann anzeigen“ "
                "→ „Link kopieren“. Der Link beginnt meist mit https://1drv.ms/.")


def is_onedrive_link(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ONEDRIVE_HOSTS


def link_problem(url: str) -> str | None:
    """Why a OneDrive address cannot work, or None.

    Addresses copied from the browser's address bar (…/edit?…, …/?id=…, _layouts)
    are not sharing links; the anonymous API only accepts real sharing links.
    """
    if not is_onedrive_link(url):
        return None
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    query = parsed.query.lower()
    if host == "onedrive.live.com" and (
        parsed.path.startswith("/edit") or "_layouts" in parsed.path
        or (("id=" in query or "cid=" in query) and "authkey=" not in query and "redeem=" not in query)
    ):
        return "Das ist die Adresse aus der Browserzeile, kein Freigabelink. " + SHARING_HINT
    return None


def share_id(url: str) -> str:
    """Encode a sharing URL for the /shares endpoint (u! + unpadded base64url)."""
    encoded = base64.urlsafe_b64encode(url.strip().encode("utf-8")).decode("ascii").rstrip("=")
    return "u!" + encoded


def _request_json(request: Request) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=TIMEOUT, context=tls_context()) as response:
            return json.loads(response.read(2_000_000).decode("utf-8") or "{}")
    except HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise OneDriveBlocked(f"Microsoft verweigert den Abruf (HTTP {exc.code}).") from exc
        if exc.code in (400, 404):
            raise OneDriveError("OneDrive findet zu diesem Link keine freigegebene Datei. " + SHARING_HINT) from exc
        raise OneDriveError(f"OneDrive antwortet mit HTTP {exc.code}.") from exc
    except OSError as exc:
        raise OneDriveError("OneDrive ist nicht erreichbar.") from exc


def get_token() -> str:
    """Anonymous badger token, cached until shortly before it expires."""
    with _token_lock:
        if _token_cache.get("token") and _token_cache.get("expires", 0) > _time.time() + 300:
            return str(_token_cache["token"])
    payload = _request_json(Request(
        TOKEN_URL,
        method="POST",
        data=json.dumps({"appId": BADGER_APP_ID}).encode("ascii"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    ))
    token = payload.get("token")
    if not token:
        raise OneDriveError("OneDrive hat kein Zugriffstoken geliefert.")
    with _token_lock:
        # Tokens live about seven days; refresh daily to stay well inside that.
        _token_cache.update({"token": token, "expires": _time.time() + 24 * 3600})
    return str(token)


PLAN_EXTENSIONS = (".xlsx", ".xlsm", ".xls", ".csv")
_SCHOOL_YEAR_IN_NAME = re.compile(r"(20\d{2})\s*[_/-]\s*(20\d{2}|\d{2})")


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Badger " + get_token(),
        "Prefer": "autoredeem",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }


def _download_url(item: dict[str, Any]) -> str:
    return str(item.get("@content.downloadUrl") or item.get("@microsoft.graph.downloadUrl") or "")


def _meta(item: dict[str, Any], download_url: str, folder: str = "") -> dict[str, Any]:
    return {
        "name": str(item.get("name") or ""),
        "size": int(item.get("size") or 0),
        "etag": str(item.get("eTag") or ""),
        "modified": str(item.get("lastModifiedDateTime") or ""),
        "download_url": download_url,
        "folder": folder,
    }


def plan_file_rank(item: dict[str, Any]) -> tuple:
    """Newest plan first: school year in the name, then last change."""
    name = str(item.get("name") or "")
    year = _SCHOOL_YEAR_IN_NAME.search(name)
    return (
        "klassenarbeit" in name.lower(),
        int(year.group(1)) if year else 0,
        str(item.get("lastModifiedDateTime") or ""),
    )


def pick_plan_file(children: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The current plan in a shared folder: a spreadsheet, newest school year first."""
    files = [c for c in children if isinstance(c, dict) and str(c.get("name") or "").lower().endswith(PLAN_EXTENSIONS)]
    return max(files, key=plan_file_rank) if files else None


def _folder_children(url: str) -> list[dict[str, Any]]:
    """Items of a shared folder: …/driveitem?$expand=children, else …/driveitem/children."""
    try:
        item = _request_json(Request(f"{API_BASE}/shares/{share_id(url)}/driveitem?$expand=children",
                                     headers=_headers()))
        if isinstance(item.get("children"), list):
            return item["children"]
    except OneDriveBlocked:
        raise
    except OneDriveError:
        pass
    listing = _request_json(Request(f"{API_BASE}/shares/{share_id(url)}/driveitem/children?$top=200",
                                    headers=_headers()))
    return listing.get("value") or []


def _resolve_folder(url: str, folder: dict[str, Any]) -> dict[str, Any]:
    """A shared folder: take the newest plan inside, so next school year's file is found automatically."""
    chosen = pick_plan_file(_folder_children(url))
    if chosen is None:
        raise OneDriveError("Im freigegebenen Ordner liegt keine Excel-Datei.")
    download_url = _download_url(chosen)
    if not download_url and chosen.get("id"):
        drive = (chosen.get("parentReference") or {}).get("driveId") or (folder.get("parentReference") or {}).get("driveId")
        if drive:
            detail = _request_json(Request(
                f"{API_BASE}/drives/{drive}/items/{chosen['id']}"
                "?$select=name,size,eTag,lastModifiedDateTime,@content.downloadUrl",
                headers=_headers(),
            ))
            download_url = _download_url(detail)
    if not download_url:
        raise OneDriveError("OneDrive liefert für die Datei im Ordner keine Download-Adresse.")
    return _meta(chosen, download_url, folder=str(folder.get("name") or ""))


def resolve(url: str) -> dict[str, Any]:
    """Metadata of a shared file: name, size, eTag, modified, download_url.

    For a shared folder the newest plan file inside is used (meta["folder"] is set).
    """
    if not is_onedrive_link(url):
        raise OneDriveError("Das ist kein OneDrive-Freigabelink.")
    problem = link_problem(url)
    if problem:
        raise OneDriveError(problem)
    item = _request_json(Request(
        f"{API_BASE}/shares/{share_id(url)}/driveitem"
        "?$select=name,size,eTag,lastModifiedDateTime,@content.downloadUrl",
        headers=_headers(),
    ))
    download_url = _download_url(item)
    if download_url:
        return _meta(item, download_url)
    return _resolve_folder(url, item)  # no download address: a folder link


def download(url: str) -> tuple[bytes, dict[str, Any]]:
    """Download a shared file. Returns (bytes, metadata without download_url)."""
    meta = resolve(url)
    if meta["size"] > MAX_BYTES:
        raise OneDriveError("Die Datei ist zu groß (max. 15 MB).")
    try:
        request = Request(meta.pop("download_url"), headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=TIMEOUT, context=tls_context()) as response:
            data = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise OneDriveBlocked(f"Microsoft verweigert den Download (HTTP {exc.code}).") from exc
        raise OneDriveError(f"Download fehlgeschlagen (HTTP {exc.code}).") from exc
    except OSError as exc:
        raise OneDriveError("Download von OneDrive fehlgeschlagen.") from exc
    if len(data) > MAX_BYTES:
        raise OneDriveError("Die Datei ist zu groß (max. 15 MB).")
    return data, meta
