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

# Photos in an admin's answer (e.g. screenshots: „hier tippen“). Only the teacher who wrote
# the Rückmeldung and the admins can load them; deleting the Rückmeldung deletes them.
MAX_IMAGES = 4
MAX_IMAGE_BYTES = 2_500_000
_IMAGE_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"RIFF", "image/webp"),  # checked further below: "WEBP" at offset 8
)

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


def migrate_images(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_images (
            id          SERIAL PRIMARY KEY,
            feedback_id INTEGER NOT NULL REFERENCES feedback(id) ON DELETE CASCADE,
            mime        TEXT NOT NULL,
            data        BYTEA NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_images_feedback ON feedback_images(feedback_id)")


def image_type(data: bytes) -> str | None:
    """The image type judged by the file's first bytes (not by what the browser claims)."""
    for magic, mime in _IMAGE_MAGIC:
        if data.startswith(magic):
            if mime == "image/webp" and data[8:12] != b"WEBP":
                return None
            return mime
    return None


def add_image(conn, feedback_id: int, data: bytes, now: datetime | None = None) -> dict[str, Any] | str:
    """Stores a photo for the answer; returns {"id"} or an error message."""
    if not data:
        return "Kein Bild empfangen."
    if len(data) > MAX_IMAGE_BYTES:
        return "Das Bild ist zu groß."
    mime = image_type(data)
    if not mime:
        return "Bitte ein Foto oder einen Screenshot (JPG, PNG oder WebP) wählen."
    if not conn.execute("SELECT 1 FROM feedback WHERE id = %s", (feedback_id,)).fetchone():
        return "Rückmeldung nicht gefunden."
    count = conn.execute("SELECT COUNT(*) FROM feedback_images WHERE feedback_id = %s", (feedback_id,)).fetchone()[0]
    if int(count) >= MAX_IMAGES:
        return f"Höchstens {MAX_IMAGES} Fotos pro Antwort."
    row = conn.execute(
        "INSERT INTO feedback_images (feedback_id, mime, data) VALUES (%s, %s, %s) RETURNING id",
        (feedback_id, mime, data),
    ).fetchone()
    now = now or datetime.now(timezone.utc)
    conn.execute(
        "UPDATE feedback SET user_unread = TRUE, updated_at = %s, replied_at = COALESCE(replied_at, %s) WHERE id = %s",
        (now, now, feedback_id),
    )
    return {"id": row[0]}


def delete_image(conn, feedback_id: int, image_id: int) -> bool:
    return conn.execute("DELETE FROM feedback_images WHERE id = %s AND feedback_id = %s",
                        (image_id, feedback_id)).rowcount > 0


def load_image(conn, image_id: int) -> tuple[int | None, str, bytes] | None:
    """(owner user id, mime, bytes) of a photo, or None."""
    row = conn.execute(
        """SELECT f.user_id, i.mime, i.data FROM feedback_images i JOIN feedback f ON f.id = i.feedback_id
           WHERE i.id = %s""",
        (image_id,),
    ).fetchone()
    return (row[0], row[1], bytes(row[2])) if row else None


def _with_images(conn, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in items:
        item["images"] = []
    if not items:
        return items
    by_id = {item["id"]: item for item in items}
    try:
        rows = conn.execute(
            "SELECT feedback_id, id FROM feedback_images WHERE feedback_id = ANY(%s) ORDER BY id",
            (list(by_id),),
        ).fetchall()
    except Exception:
        return items  # table not there yet: answers without photos
    for feedback_id, image_id in rows:
        by_id[feedback_id]["images"].append(image_id)
    return items


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
    return _with_images(conn, [_item(row, for_admin=for_admin)])[0] if row else None


def list_for_user(conn, user_id: int, limit: int = 30) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""SELECT {_COLUMNS} FROM feedback f LEFT JOIN users u ON u.id = f.user_id
            WHERE f.user_id = %s ORDER BY f.created_at DESC LIMIT %s""",
        (user_id, limit),
    ).fetchall()
    return _with_images(conn, [_item(row, for_admin=False) for row in rows])


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
    return _with_images(conn, [_item(row, for_admin=True) for row in rows])


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


def admin_mailboxes(conn) -> list[tuple[str, str]]:
    """(address, app password) of every active admin who connected the Dienstmail."""
    from .dienstmail import is_configured
    from .modules.module_registry import get_user_module_config

    rows = conn.execute("SELECT id FROM users WHERE is_admin = TRUE AND is_active = TRUE").fetchall()
    boxes = []
    for (admin_id,) in rows:
        config = get_user_module_config(conn, admin_id, "mail") or {}
        if is_configured(config):
            boxes.append((str(config["address"]), str(config["app_password"])))
    return boxes


def mail_admins_in_background(kind: str, first_name: str, message: str, admin_url: str) -> None:
    """Puts the Rückmeldung into each admin's own Dienstmail inbox (IMAP APPEND, nothing is sent)."""
    from threading import Thread

    from . import dienstmail
    from .db import db_connection

    def run() -> None:
        try:
            with db_connection() as conn:
                boxes = admin_mailboxes(conn)
            label = KINDS.get(kind, "Rückmeldung")
            subject = f"Lehrercockpit: {label} von {first_name}"
            text = f"{label} von {first_name}:\n\n{message}\n\nIn der Verwaltung ansehen und antworten:\n{admin_url}\n"
            for address, app_password in boxes:
                try:
                    dienstmail.put_into_inbox(address, app_password, subject, text)
                except Exception as exc:
                    print(f"[feedback] Ablage im Posteingang fehlgeschlagen: {type(exc).__name__}", flush=True)
        except Exception as exc:  # never break feedback because of mail
            print(f"[feedback] Ablage im Posteingang fehlgeschlagen: {type(exc).__name__}", flush=True)

    Thread(target=run, daemon=True).start()
