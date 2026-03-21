"""Playwright-based scraper to extract Klassenarbeitsplan from OneDrive Excel Online viewer."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def scrape_classwork_plan(url: str, timeout_ms: int = 30000) -> dict[str, Any]:
    """Open the OneDrive Excel Online viewer with Playwright and extract table data."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return _error_result("Playwright not installed. Run: pip install playwright && playwright install chromium", url)

    if not url:
        return _error_result("Keine URL konfiguriert (CLASSWORK_PLAN_URL fehlt).", "")

    now = datetime.now()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-zygote",
                    "--single-process",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="de-DE",
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                # Wait for Excel Online to render the spreadsheet
                try:
                    page.wait_for_selector(
                        "div[role='gridcell'], td.ms-spreadsheet-cell, .od-spreadsheet-cell, table td",
                        timeout=timeout_ms,
                    )
                except Exception:
                    # Try waiting for any table
                    page.wait_for_timeout(5000)

                rows = _extract_rows_from_page(page)

                if not rows:
                    # Try extracting from page title + raw text as fallback
                    text = page.inner_text("body")
                    rows = _parse_text_as_rows(text)

                browser.close()

                if not rows:
                    return _warning_result(
                        "Seite geladen, aber keine Tabellendaten erkannt. "
                        "Moeglicherweise erfordert die Datei einen Microsoft-Login.",
                        url,
                        now,
                    )

                headers = rows[0] if rows else []
                data_rows = rows[1:] if len(rows) > 1 else []

                structured: list[dict[str, str]] = []
                for row in data_rows:
                    if not any(cell.strip() for cell in row):
                        continue
                    entry: dict[str, str] = {}
                    for i, header in enumerate(headers):
                        entry[header] = row[i].strip() if i < len(row) else ""
                    structured.append(entry)

                preview_rows = [" | ".join(r[:6]) for r in rows[:9] if any(c.strip() for c in r)]

                return {
                    "status": "ok",
                    "title": "Klassenarbeitsplan",
                    "detail": f"Live gescraped. {len(structured)} Eintraege gefunden.",
                    "updatedAt": now.strftime("%H:%M"),
                    "scrapedAt": now.isoformat(),
                    "previewRows": preview_rows,
                    "structuredRows": structured[:60],
                    "sourceUrl": url,
                    "scrapeMode": "playwright",
                }

            except Exception as exc:
                browser.close()
                raise exc

    except Exception as exc:
        return _error_result(f"Scraping fehlgeschlagen: {type(exc).__name__}: {exc}", url, now)


def _extract_rows_from_page(page: Any) -> list[list[str]]:
    """Try multiple strategies to extract table rows from Excel Online."""

    # Strategy 1: Standard HTML table
    rows = page.evaluate("""
        () => {
            const tables = document.querySelectorAll('table');
            for (const table of tables) {
                const rows = [];
                for (const tr of table.querySelectorAll('tr')) {
                    const cells = Array.from(tr.querySelectorAll('th, td')).map(c => c.innerText.trim());
                    if (cells.some(c => c)) rows.push(cells);
                }
                if (rows.length > 1) return rows;
            }
            return [];
        }
    """)
    if rows and len(rows) > 1:
        return rows

    # Strategy 2: Excel Online grid cells
    rows = page.evaluate("""
        () => {
            const grid = document.querySelector('[role="grid"], [role="table"]');
            if (!grid) return [];
            const rows = [];
            for (const row of grid.querySelectorAll('[role="row"]')) {
                const cells = Array.from(row.querySelectorAll('[role="gridcell"], [role="columnheader"]'))
                    .map(c => c.innerText.trim());
                if (cells.some(c => c)) rows.push(cells);
            }
            return rows;
        }
    """)
    if rows and len(rows) > 1:
        return rows

    # Strategy 3: Any element with spreadsheet-like class names
    rows = page.evaluate("""
        () => {
            const cells = document.querySelectorAll('[class*="cell"], [class*="Cell"]');
            if (!cells.length) return [];
            const rowMap = new Map();
            cells.forEach(cell => {
                const rect = cell.getBoundingClientRect();
                const y = Math.round(rect.top / 20) * 20;
                if (!rowMap.has(y)) rowMap.set(y, []);
                rowMap.get(y).push({ x: rect.left, text: cell.innerText.trim() });
            });
            return Array.from(rowMap.entries())
                .sort(([a], [b]) => a - b)
                .map(([, cells]) => cells.sort((a, b) => a.x - b.x).map(c => c.text));
        }
    """)
    if rows and len(rows) > 1:
        return rows

    return []


def _parse_text_as_rows(text: str) -> list[list[str]]:
    """Last-resort: try to parse raw text as tab/newline-separated data."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rows = []
    for line in lines[:50]:
        if "\t" in line:
            rows.append(line.split("\t"))
        elif "  " in line:
            rows.append([part.strip() for part in re.split(r" {2,}", line) if part.strip()])
    return rows if len(rows) > 1 else []


def _error_result(detail: str, url: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    return {
        "status": "error",
        "title": "Klassenarbeitsplan",
        "detail": detail,
        "updatedAt": now.strftime("%H:%M"),
        "scrapedAt": now.isoformat(),
        "previewRows": [],
        "structuredRows": [],
        "sourceUrl": url,
        "scrapeMode": "playwright",
    }


def _warning_result(detail: str, url: str, now: datetime) -> dict[str, Any]:
    return {
        "status": "warning",
        "title": "Klassenarbeitsplan",
        "detail": detail,
        "updatedAt": now.strftime("%H:%M"),
        "scrapedAt": now.isoformat(),
        "previewRows": [],
        "structuredRows": [],
        "sourceUrl": url,
        "scrapeMode": "playwright",
    }
