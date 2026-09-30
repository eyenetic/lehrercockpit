"""Links for the whole staff, managed by admins – e.g. the Klassenarbeitsplan
edit link that only teachers may get (not public on the school website).

A teacher's own links stay in the browser and travel between devices in the
encrypted vault (src/features/vault.js); user_id is always NULL here for now.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

MAX_SCHOOL = 40


def clean(title: Any, url: Any) -> tuple[str, str] | str:
    """(title, url) or an error message."""
    address = url.strip() if isinstance(url, str) else ""
    parsed = urlparse(address)
    if parsed.scheme not in ("https", "http") or not parsed.netloc or len(address) > 2000:
        return "Bitte eine vollständige Adresse eingeben (beginnt mit https://)."
    name = title.strip() if isinstance(title, str) else ""
    if not name:
        name = parsed.netloc.removeprefix("www.")
    return name[:80], address


def _row(row) -> dict[str, Any]:
    return {"id": row[0], "title": row[1], "url": row[2]}


def school_links(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, title, url FROM user_links WHERE user_id IS NULL ORDER BY sort_order, id"
    ).fetchall()
    return [_row(row) for row in rows]


def add_school_link(conn, *, title: str, url: str) -> dict[str, Any] | str:
    """New link at the end of the list, or an error message when the list is full."""
    count = conn.execute("SELECT COUNT(*) FROM user_links WHERE user_id IS NULL").fetchone()[0]
    if count >= MAX_SCHOOL:
        return f"Höchstens {MAX_SCHOOL} Links – bitte zuerst einen entfernen."
    row = conn.execute(
        "INSERT INTO user_links (user_id, title, url, sort_order) VALUES (NULL, %s, %s, %s) RETURNING id, title, url",
        (title, url, int(count)),
    ).fetchone()
    return _row(row)


def remove_school_link(conn, link_id: int) -> bool:
    return conn.execute("DELETE FROM user_links WHERE id = %s AND user_id IS NULL", (link_id,)).rowcount > 0
