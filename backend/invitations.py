"""Invitation links for colleagues.

An admin creates a link, sends it (mail, messenger …), the colleague opens it,
enters name and a self-chosen access code and is logged in right away.

  personal  one colleague, works once, 14 days
  team      the whole staff ("Kollegiums-Link"), works for many, 30 days,
            admins can switch it off at any time

Only the SHA-256 of the token is used for lookups; the token itself is kept
(encrypted when ENCRYPTION_KEY is set) so admins can copy the link again.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from .crypto import decrypt_config, encrypt_config

KINDS = ("personal", "team")
VALID_DAYS = {"personal": 14, "team": 30}

_COLUMNS = ("id, kind, name, email, token_enc, created_by, created_at, expires_at, "
            "revoked_at, uses, last_used_at, used_by, access_request_id")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _row(row) -> dict[str, Any]:
    keys = [c.strip() for c in _COLUMNS.split(",")]
    item = dict(zip(keys, row))
    item["token"] = decrypt_config({"token": item.pop("token_enc") or ""})["token"]
    return item


def create(conn, *, kind: str = "personal", name: str = "", email: str = "",
           created_by: int | None = None, access_request_id: int | None = None,
           now: datetime | None = None) -> dict[str, Any]:
    """New invitation; returns the stored row including the plain token."""
    if kind not in KINDS:
        raise ValueError("Unbekannte Art der Einladung")
    now = now or _now()
    token = secrets.token_urlsafe(24)
    if kind == "team":
        # One staff link at a time: a new one replaces the old one.
        conn.execute("UPDATE invitations SET revoked_at = %s WHERE kind = 'team' AND revoked_at IS NULL", (now,))
    row = conn.execute(
        f"""
        INSERT INTO invitations (token_hash, token_enc, kind, name, email, created_by,
                                 access_request_id, created_at, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING {_COLUMNS}
        """,
        (token_hash(token), encrypt_config({"token": token})["token"], kind, name.strip()[:120],
         email.strip().lower()[:200], created_by, access_request_id, now,
         now + timedelta(days=VALID_DAYS[kind])),
    ).fetchone()
    return _row(row)


def is_usable(invite: dict[str, Any], now: datetime | None = None) -> bool:
    now = now or _now()
    if invite.get("revoked_at") or invite["expires_at"] <= now:
        return False
    return invite["kind"] == "team" or not invite.get("uses")


def find_usable(conn, token: str, now: datetime | None = None, *, lock: bool = False) -> dict[str, Any] | None:
    """The invitation behind a token if it can still be used. `lock` holds the
    row until the transaction ends, so a personal link cannot be used twice."""
    if not token or len(token) > 200:
        return None
    row = conn.execute(f"SELECT {_COLUMNS} FROM invitations WHERE token_hash = %s"
                       + (" FOR UPDATE" if lock else ""), (token_hash(token),)).fetchone()
    if not row:
        return None
    invite = _row(row)
    return invite if is_usable(invite, now) else None


def mark_used(conn, invite_id: int, user_id: int, now: datetime | None = None) -> None:
    conn.execute(
        "UPDATE invitations SET uses = uses + 1, last_used_at = %s, used_by = %s WHERE id = %s",
        (now or _now(), user_id, invite_id),
    )


def revoke(conn, invite_id: int, now: datetime | None = None) -> bool:
    result = conn.execute(
        "UPDATE invitations SET revoked_at = %s WHERE id = %s AND revoked_at IS NULL",
        (now or _now(), invite_id),
    )
    return result.rowcount > 0


def list_recent(conn, now: datetime | None = None, days: int = 60) -> list[dict[str, Any]]:
    """Invitations of the last `days` days, newest first, with who joined."""
    now = now or _now()
    rows = conn.execute(
        f"""
        SELECT {", ".join("i." + c.strip() for c in _COLUMNS.split(","))},
               u.first_name, u.last_name
        FROM invitations i LEFT JOIN users u ON u.id = i.used_by
        WHERE i.created_at >= %s
        ORDER BY i.created_at DESC
        """,
        (now - timedelta(days=days),),
    ).fetchall()
    result = []
    for row in rows:
        invite = _row(row[:-2])
        invite["used_by_name"] = " ".join(part for part in row[-2:] if part)
        invite["usable"] = is_usable(invite, now)
        result.append(invite)
    return result


def link(token: str, frontend_url: str) -> str:
    """The URL colleagues open. The token sits in the fragment, so it never
    reaches web server logs or Referer headers."""
    return f"{frontend_url.rstrip('/')}/login.html#einladung={token}"


def public_view(invite: dict[str, Any], frontend_url: str, now: datetime | None = None) -> dict[str, Any]:
    """What the admin page shows about an invitation."""
    def iso(value):
        return value.isoformat() if value else None

    usable = is_usable(invite, now)
    token = invite.get("token") if usable else ""
    return {
        "id": invite["id"],
        "kind": invite["kind"],
        "name": invite.get("name") or "",
        "email": invite.get("email") or "",
        "token": token or "",
        "link": link(token, frontend_url) if token else "",
        "created_at": iso(invite.get("created_at")),
        "expires_at": iso(invite.get("expires_at")),
        "revoked_at": iso(invite.get("revoked_at")),
        "uses": invite.get("uses") or 0,
        "last_used_at": iso(invite.get("last_used_at")),
        "used_by_name": invite.get("used_by_name", ""),
        "usable": usable,
    }
