"""Playwright-based scraper for Klassenarbeitsplan from OneDrive Excel Online.

Uses Arrow key navigation to read cell values from the formula bar.
No login required — the file is publicly accessible via the school website link.

Features:
- Arrow-key cell iteration (formula bar reads each cell)
- All sheets scraped
- Diff detection
- Progress callback
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ProgressCallback = Callable[[int, str], None]


def _col_letter(n: int) -> str:
    """Convert 1-based column number to Excel column letter (A, B, ... Z, AA, ...)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _parse_col_num(col_str: str) -> int:
    """Convert column letter (A, B, ... AE) to 1-based number."""
    return sum((ord(c) - 64) * (26 ** i) for i, c in enumerate(reversed(col_str.upper())))


def scrape_classwork_plan(
    url: str,
    email: str = "",
    password: str = "",
    cookie_path: Path | None = None,
    previous_hash: str = "",
    on_progress: ProgressCallback | None = None,
    timeout_ms: int = 45000,
    scrape_all_sheets: bool = False,
) -> dict[str, Any]:
    """
    Scrape the OneDrive Klassenarbeitsplan via Excel Online.

    Works without Microsoft login if the file is publicly shared.
    Uses Arrow-key navigation + formula bar to extract cell values.
    """

    def progress(pct: int, msg: str) -> None:
        if on_progress:
            on_progress(pct, msg)
        print(f"[classwork] {pct}% — {msg}", flush=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return _error("Playwright not installed. Run: pip install playwright && playwright install chromium", url)

    if not url:
        return _error("Keine URL konfiguriert (CLASSWORK_PLAN_URL fehlt).", "")

    now = datetime.now()
    progress(5, "Browser wird gestartet…")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--no-zygote", "--single-process"],
            )
            context_opts: dict[str, Any] = {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "viewport": {"width": 1280, "height": 900},
                "locale": "de-DE",
            }
            context = browser.new_context(**context_opts)

            # Load saved session cookies if available
            if cookie_path and cookie_path.exists():
                try:
                    context.add_cookies(json.loads(cookie_path.read_text(encoding="utf-8")))
                    progress(8, "Gespeicherte Session geladen…")
                except Exception:
                    pass

            page = context.new_page()

            progress(10, f"Seite wird geladen…")
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_timeout(4000)

            # Handle login if needed
            current_url = page.url
            if any(d in current_url for d in ["login.microsoftonline.com", "login.live.com", "account.live.com"]):
                if email and password:
                    progress(15, "Microsoft-Login wird durchgeführt…")
                    ok = _do_login(page, email, password, timeout_ms, progress)
                    if not ok:
                        browser.close()
                        return _error("Microsoft-Login fehlgeschlagen. Credentials prüfen.", url, now)
                    if cookie_path:
                        _save_cookies(context, cookie_path)
                    page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                    page.wait_for_timeout(4000)
                else:
                    browser.close()
                    return _error(
                        "Microsoft-Login nötig. Bitte MS_LOGIN_EMAIL und MS_LOGIN_PASSWORD in .env.local setzen.",
                        url, now,
                    )

            # Wait for Excel Online to load
            progress(20, "Excel Online wird geladen…")
            excel_frame = _wait_for_excel_frame(page, timeout_ms)
            if not excel_frame:
                browser.close()
                return _warning("Excel Online Frame nicht gefunden. Seite reagiert unerwartet.", url, now)

            # Wait a bit more for full render
            page.wait_for_timeout(8000)
            progress(30, "Tabellendaten werden extrahiert…")

            # Activate the spreadsheet by clicking
            page.mouse.click(640, 400)
            page.wait_for_timeout(500)

            # Collect sheet names from workbook context
            sheet_names = _get_sheet_names(excel_frame)
            progress(35, f"{len(sheet_names)} Tabellenblätter gefunden…")

            # Decide which sheets to scrape
            sheets_to_scrape = sheet_names if scrape_all_sheets else sheet_names[:1]
            if not sheets_to_scrape:
                sheets_to_scrape = ["current"]

            all_structured: list[dict[str, Any]] = []
            preview_rows: list[str] = []

            for sheet_idx, sheet_name in enumerate(sheets_to_scrape):
                pct = 35 + int(55 * sheet_idx / len(sheets_to_scrape))
                progress(pct, f"Lese {sheet_name}…")

                # Navigate to sheet if needed
                if len(sheets_to_scrape) > 1 and sheet_idx > 0:
                    _switch_sheet(excel_frame, page, sheet_name)
                    page.wait_for_timeout(2000)

                rows = _read_sheet(page, excel_frame)
                if not rows:
                    continue

                # Build structured rows
                headers = [c.strip() for c in rows[0]] if rows else []
                for row in rows[1:]:
                    if not any(c.strip() for c in row):
                        continue
                    entry: dict[str, str] = {"_sheet": sheet_name}
                    for i, hdr in enumerate(headers):
                        entry[hdr if hdr else f"Col{i+1}"] = row[i].strip() if i < len(row) else ""
                    all_structured.append(entry)

                # Preview rows from first sheet
                if sheet_idx == 0:
                    preview_rows = [" | ".join(r[:6]) for r in rows[:9] if any(c.strip() for c in r)]

            if cookie_path:
                _save_cookies(context, cookie_path)

            browser.close()

        progress(95, "Daten werden aufbereitet…")

        if not all_structured and not preview_rows:
            return _warning("Keine Zelldaten gelesen. Excel Online hat möglicherweise die Ansicht verändert.", url, now)

        current_hash = _hash(all_structured)
        has_changes = bool(previous_hash) and current_hash != previous_hash
        no_changes = bool(previous_hash) and current_hash == previous_hash

        if no_changes:
            detail = f"Keine Änderungen. {len(all_structured)} Einträge unverändert."
        elif has_changes:
            detail = f"Aktualisierung erkannt! {len(all_structured)} Einträge neu geladen."
        else:
            detail = f"Erstmaliger Abruf. {len(all_structured)} Einträge geladen."

        progress(100, detail)

        return {
            "status": "ok",
            "title": "Klassenarbeitsplan",
            "detail": detail,
            "updatedAt": now.strftime("%H:%M"),
            "scrapedAt": now.isoformat(),
            "previewRows": preview_rows,
            "structuredRows": all_structured[:80],
            "sourceUrl": url,
            "scrapeMode": "playwright",
            "dataHash": current_hash,
            "hasChanges": has_changes,
            "noChanges": no_changes,
        }

    except Exception as exc:
        return _error(f"Scraping fehlgeschlagen: {type(exc).__name__}: {exc}", url, now)


# ── Excel sheet reading ───────────────────────────────────────────────────────

def _read_sheet(page: Any, excel_frame: Any) -> list[list[str]]:
    """Read all cells in the current sheet using Arrow key navigation."""

    def get_fb() -> str:
        try:
            return excel_frame.evaluate(
                '() => { const fb = document.getElementById("formulaBarTextDivId_textElement"); return fb ? fb.innerText.trim() : ""; }'
            )
        except Exception:
            return ""

    def get_nb() -> str:
        try:
            return excel_frame.evaluate(
                '() => { const nb = document.getElementById("FormulaBar-NameBox-input"); return nb ? nb.value : ""; }'
            )
        except Exception:
            return ""

    # Find last used cell
    page.keyboard.press("Control+Home")
    page.wait_for_timeout(300)
    page.keyboard.press("Control+End")
    page.wait_for_timeout(300)
    last_cell = get_nb()

    m = re.match(r"([A-Z]+)(\d+)", last_cell)
    if not m:
        return []

    max_row = int(m.group(2))
    max_col = _parse_col_num(m.group(1))

    # Cap at reasonable size
    max_row = min(max_row, 50)
    max_col = min(max_col, 40)

    if max_row < 1 or max_col < 1:
        return []

    # Read row by row
    all_rows: list[list[str]] = []

    for row in range(1, max_row + 1):
        # Navigate to start of this row
        page.keyboard.press("Control+Home")
        page.wait_for_timeout(80)
        for _ in range(row - 1):
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(40)

        # Read each column
        row_values: list[str] = []
        for col in range(1, max_col + 1):
            val = get_fb()
            row_values.append(val)
            if col < max_col:
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(40)

        all_rows.append(row_values)

    return all_rows


def _wait_for_excel_frame(page: Any, timeout_ms: int) -> Any | None:
    """Wait for and return the Excel Online iframe."""
    deadline = timeout_ms / 1000
    waited = 0
    while waited < deadline:
        for frame in page.frames:
            if "excel.officeapps.live.com" in frame.url:
                return frame
        page.wait_for_timeout(1000)
        waited += 1
    return None


def _get_sheet_names(excel_frame: Any) -> list[str]:
    """Extract sheet names from workbook context JSON."""
    try:
        ctx_str = excel_frame.evaluate(
            '() => { const inp = document.getElementById("m_excelWebRenderer_ewaCtl_m_workbookContextJson"); return inp ? inp.value : "{}"; }'
        )
        ctx = json.loads(ctx_str)
        tabs = ctx.get("SheetTabs", [])
        if isinstance(tabs, list):
            return [t.get("SheetName", "") for t in tabs if t.get("SheetName")]
        return [ctx.get("ActiveSheetName", "")]
    except Exception:
        return []


def _switch_sheet(excel_frame: Any, page: Any, sheet_name: str) -> None:
    """Click on a sheet tab by name."""
    try:
        excel_frame.evaluate(f'''() => {{
            const tabs = document.querySelectorAll("li.ewa-sheetTab, [class*=sheetTab], [role=tab]");
            for (const tab of tabs) {{
                if (tab.innerText.trim() === "{sheet_name}") {{ tab.click(); return; }}
            }}
        }}''')
    except Exception:
        pass


# ── Microsoft Login ───────────────────────────────────────────────────────────

def _do_login(page: Any, email: str, password: str, timeout_ms: int, progress: Callable) -> bool:
    """Perform Microsoft login flow."""
    try:
        progress(18, "E-Mail wird eingegeben…")
        for sel in ["input[type='email']", "input[name='loginfmt']", "#i0116"]:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.fill(sel, email)
                page.keyboard.press("Enter")
                break
            except Exception:
                continue

        page.wait_for_timeout(2000)

        progress(22, "Passwort wird eingegeben…")
        for sel in ["input[type='password']", "input[name='passwd']", "#i0118"]:
            try:
                page.wait_for_selector(sel, timeout=8000)
                page.fill(sel, password)
                page.keyboard.press("Enter")
                break
            except Exception:
                continue

        page.wait_for_timeout(3000)

        # Handle "Stay signed in?"
        try:
            yes_btn = page.query_selector("#idSIButton9, [value='Yes'], [value='Ja']")
            if yes_btn:
                yes_btn.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

        current = page.url.lower()
        return not any(d in current for d in ["login.microsoftonline", "login.live", "account.live"])
    except Exception as exc:
        print(f"[classwork] Login error: {exc}", flush=True)
        return False


def _save_cookies(context: Any, cookie_path: Path) -> None:
    try:
        cookies = context.cookies()
        cookie_path.parent.mkdir(parents=True, exist_ok=True)
        cookie_path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[classwork] Failed to save cookies: {exc}", flush=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(data: list[dict]) -> str:
    content = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _error(detail: str, url: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    return {
        "status": "error", "title": "Klassenarbeitsplan", "detail": detail,
        "updatedAt": now.strftime("%H:%M"), "scrapedAt": now.isoformat(),
        "previewRows": [], "structuredRows": [], "sourceUrl": url,
        "scrapeMode": "playwright", "dataHash": "", "hasChanges": False, "noChanges": False,
    }


def _warning(detail: str, url: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    return {
        "status": "warning", "title": "Klassenarbeitsplan", "detail": detail,
        "updatedAt": now.strftime("%H:%M"), "scrapedAt": now.isoformat(),
        "previewRows": [], "structuredRows": [], "sourceUrl": url,
        "scrapeMode": "playwright", "dataHash": "", "hasChanges": False, "noChanges": False,
    }
