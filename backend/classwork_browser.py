from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from pathlib import Path
import tempfile
import time
from typing import Any

from .classwork_cache import save_cache
from .plan_digest import _read_classwork_workbook


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = PROJECT_ROOT / "data" / "classwork-cache.json"
PROFILE_DIR = PROJECT_ROOT / "data" / "playwright-classwork-profile"
DOWNLOAD_DIR = PROJECT_ROOT / "data" / "playwright-downloads"


def fetch_classwork_from_browser(onedrive_url: str) -> dict[str, Any]:
    if not onedrive_url:
        return {
            "status": "error",
            "detail": "Kein OneDrive-Link fuer den Browser-Abruf vorhanden.",
        }

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {
            "status": "error",
            "detail": f"Playwright ist lokal nicht installiert oder nicht verfuegbar: {exc}",
        }

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()

    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=False,
                accept_downloads=True,
                downloads_path=str(DOWNLOAD_DIR),
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(onedrive_url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)

                if _looks_like_login(page):
                    return {
                        "status": "login_required",
                        "detail": "Microsoft-Login erforderlich. Bitte zuerst im Browser anmelden.",
                    }

                workbook_bytes = _download_workbook_via_ui(page)
                if not workbook_bytes:
                    return {
                        "status": "error",
                        "detail": (
                            "Die Office-Webansicht konnte geoeffnet werden, aber der Download der Excel-Datei "
                            "liess sich nicht automatisch ausloesen."
                        ),
                    }

                result = _read_classwork_workbook(
                    workbook_bytes,
                    now,
                    detail="Online im Browser abgerufen und lokal als Beta-Komfortfunktion eingelesen.",
                    source_url=onedrive_url,
                )
                result["scrapedAt"] = now.isoformat()
                result["scrapeMode"] = "browser-fetch"
                return result
            finally:
                with suppress(Exception):
                    context.close()
    except PlaywrightTimeoutError:
        return {
            "status": "error",
            "detail": "Zeitueberschreitung beim Oeffnen der Office-Webansicht.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "detail": f"Browser-Abruf fehlgeschlagen: {type(exc).__name__}: {exc}",
        }


def write_to_cache(result: dict[str, Any]) -> bool:
    if result.get("status") != "ok":
        return False

    save_cache(CACHE_PATH, result)
    return True


def _looks_like_login(page: Any) -> bool:
    login_markers = (
        "anmelden",
        "sign in",
        "microsoft account",
        "passwort",
        "email, phone, or skype",
    )

    with suppress(Exception):
        page_text = (page.locator("body").inner_text(timeout=3000) or "").lower()
        if any(marker in page_text for marker in login_markers):
            return True

    selectors = (
        "input[type='password']",
        "input[name='loginfmt']",
        "input[type='email']",
    )
    for selector in selectors:
        with suppress(Exception):
            if page.locator(selector).first.is_visible():
                return True
    return False


def _download_workbook_via_ui(page: Any) -> bytes | None:
    file_labels = ("Datei", "File")
    download_labels = (
        "Herunterladen einer Kopie",
        "Kopie herunterladen",
        "Download a Copy",
        "Download a copy",
        "Download",
    )

    for file_label in file_labels:
        if not _click_label(page, file_label):
            continue

        for download_label in download_labels:
            with suppress(Exception):
                with page.expect_download(timeout=15000) as download_info:
                    if _click_label(page, download_label):
                        download = download_info.value
                        temp_path = Path(tempfile.mktemp(suffix=".xlsx"))
                        download.save_as(str(temp_path))
                        data = temp_path.read_bytes()
                        with suppress(Exception):
                            temp_path.unlink()
                        if data:
                            return data
            page.wait_for_timeout(600)

    return None


def _click_label(page: Any, label: str) -> bool:
    candidates = (
        page.get_by_role("button", name=label, exact=True),
        page.get_by_role("link", name=label, exact=True),
        page.get_by_role("menuitem", name=label, exact=True),
        page.get_by_text(label, exact=True),
    )

    for locator in candidates:
        with suppress(Exception):
            locator.first.click(timeout=5000)
            page.wait_for_timeout(500)
            return True
    return False
