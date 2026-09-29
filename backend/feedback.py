"""Rückmeldungen: teachers tell the admins about problems, ideas and questions.

Admins set a status and can answer; the teacher sees the answer in the cockpit
(user_unread marks answers the teacher has not opened yet).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

KINDS = {"problem": "Problem", "idee": "Idee", "frage": "Frage", "lob": "Lob"}
STATUSES = {"neu": "Neu", "in_arbeit": "In Arbeit", "erledigt": "Erledigt"}
MAX_MESSAGE = 4000
MAX_REPLY = 4000

_COLUMNS = "f.id, f.user_id, f.kind, f.message, f.context, f.status, f.reply, f.replied_at, " \
           "f.user_unread, f.created_at, f.updated_at, u.first_name, u.last_name, u.email"


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _item(row, *, for_admin: bool) -> dict[str, Any]:
    (fid, user_id, kind, message, context, status, reply, replied_at, unread,
     created_at, updated_at, first_name, last_name, email) = row
    item = {
        "id": fid,
        "kind": kind,
        "kind_label": KINDS.get(kind, kind),
        "message": message,
        "status": status,
        "status_label": STATUSES.get(status, status),
        "reply": reply or "",
        "replied_at": _iso(replied_at),
        "unread": bool(unread),
        "created_at": _iso(created_at),
        "updated_at": _iso(updated_at),
    }
    if for_admin:
        item.update({
            "user_id": user_id,
            "user_name": " ".join(part for part in (first_name, last_name) if part) or "gelöschtes Konto",
            "user_email": email or "",
            "context": context if isinstance(context, dict) else {},
        })
    return item


def validate(kind: Any, message: Any) -> str | None:
    if kind not in KINDS:
        return "Bitte wähle, worum es geht."
    text = message.strip() if isinstance(message, str) else ""
    if len(text) < 3:
        return "Bitte beschreibe kurz, worum es geht."
    if len(text) > MAX_MESSAGE:
        return f"Bitte fasse dich kürzer (höchstens {MAX_MESSAGE} Zeichen)."
    return None


def create(conn, user_id: int, kind: str, message: str, context: dict[str, Any]) -> dict[str, Any]:
    import psycopg.types.json as _pjson

    row = conn.execute(
        "INSERT INTO feedback (user_id, kind, message, context) VALUES (%s, %s, %s, %s) RETURNING id",
        (user_id, kind, message.strip(), _pjson.Jsonb(context)),
    ).fetchone()
    return get(conn, row[0], for_admin=False)


def get(conn, feedback_id: int, *, for_admin: bool) -> dict[str, Any] | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM feedback f LEFT JOIN users u ON u.id = f.user_id WHERE f.id = %s",
        (feedback_id,),
    ).fetchone()
    return _item(row, for_admin=for_admin) if row else None


def list_for_user(conn, user_id: int, limit: int = 30) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""SELECT {_COLUMNS} FROM feedback f LEFT JOIN users u ON u.id = f.user_id
            WHERE f.user_id = %s ORDER BY f.created_at DESC LIMIT %s""",
        (user_id, limit),
    ).fetchall()
    return [_item(row, for_admin=False) for row in rows]


def unread_for_user(conn, user_id: int) -> int:
    row = conn.execute("SELECT COUNT(*) FROM feedback WHERE user_id = %s AND user_unread", (user_id,)).fetchone()
    return int(row[0]) if row else 0


def mark_seen(conn, user_id: int) -> None:
    conn.execute("UPDATE feedback SET user_unread = FALSE WHERE user_id = %s AND user_unread", (user_id,))


def list_all(conn, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""SELECT {_COLUMNS} FROM feedback f LEFT JOIN users u ON u.id = f.user_id
            ORDER BY (f.status = 'erledigt'), f.created_at DESC LIMIT %s""",
        (limit,),
    ).fetchall()
    return [_item(row, for_admin=True) for row in rows]


def counts(conn) -> dict[str, int]:
    result = {status: 0 for status in STATUSES}
    for status, count in conn.execute("SELECT status, COUNT(*) FROM feedback GROUP BY status").fetchall():
        result[status] = int(count)
    return result


def update(conn, feedback_id: int, *, status: str | None = None, reply: str | None = None,
           now: datetime | None = None) -> dict[str, Any] | None:
    """Admin changes status and/or answer. The teacher is told about a new answer."""
    current = get(conn, feedback_id, for_admin=True)
    if current is None:
        return None
    now = now or datetime.now(timezone.utc)
    new_status = status if status in STATUSES else current["status"]
    new_reply = current["reply"] if reply is None else reply.strip()[:MAX_REPLY]
    reply_changed = new_reply != current["reply"]
    conn.execute(
        """UPDATE feedback SET status = %s, reply = %s, updated_at = %s,
               replied_at = CASE WHEN %s THEN %s ELSE replied_at END,
               user_unread = user_unread OR %s
           WHERE id = %s""",
        (new_status, new_reply, now, reply_changed and bool(new_reply), now,
         (reply_changed and bool(new_reply)) or new_status != current["status"], feedback_id),
    )
    return get(conn, feedback_id, for_admin=True)


def delete(conn, feedback_id: int) -> bool:
    return conn.execute("DELETE FROM feedback WHERE id = %s", (feedback_id,)).rowcount > 0
