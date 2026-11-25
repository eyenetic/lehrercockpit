"""Anhänge an eigenen Terminen und Aufgaben – nur verschlüsselt, der Server kann sie nicht lesen.

Der Browser verschlüsselt jede Datei mit einem eigenen, zufälligen AES-GCM-Schlüssel.
Dieser Schlüssel steht nur im Eintrag selbst (lehrerCockpit.ownEntries), und der reist
verschlüsselt im Tresor. Der Server speichert hier nur die unlesbaren Bytes, wem sie
gehören und wie groß sie sind – keinen Namen, keinen Dateityp.

Kontingent: QUOTA_BYTES pro Lehrkraft, eine Datei höchstens MAX_FILE_BYTES.
"""
from __future__ import annotations

import secrets

MAX_FILE_BYTES = 10 * 1024 * 1024 + 64   # 10 MB plus the AES-GCM tag
QUOTA_BYTES = 25 * 1024 * 1024


def migrate(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS own_files (
            id          TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            size        INTEGER NOT NULL,
            data        BYTEA NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS own_files_user ON own_files (user_id)")


def used(conn, user_id: int) -> int:
    row = conn.execute("SELECT COALESCE(SUM(size), 0) FROM own_files WHERE user_id = %s", (user_id,)).fetchone()
    return int(row[0] or 0)


def add(conn, user_id: int, data: bytes) -> dict | str:
    """Stores the encrypted bytes. Returns {id, size, used} or a message for the teacher."""
    if not data or len(data) < 28:  # IV is separate; at least the 16-byte tag plus some content
        return "Die Datei ist leer."
    if len(data) > MAX_FILE_BYTES:
        return "Die Datei ist zu groß (höchstens 10 MB)."
    now_used = used(conn, user_id)
    if now_used + len(data) > QUOTA_BYTES:
        free = max(0, QUOTA_BYTES - now_used) / 1024 / 1024
        return f"Dein Speicher für Anhänge ist fast voll (noch {free:.1f} MB frei). Lösch alte Anhänge, dann geht es wieder."
    file_id = secrets.token_urlsafe(18)
    conn.execute(
        "INSERT INTO own_files (id, user_id, size, data) VALUES (%s, %s, %s, %s)",
        (file_id, user_id, len(data), data),
    )
    return {"id": file_id, "size": len(data), "used": now_used + len(data), "quota": QUOTA_BYTES}


def load(conn, user_id: int, file_id: str) -> bytes | None:
    row = conn.execute("SELECT data FROM own_files WHERE id = %s AND user_id = %s", (file_id, user_id)).fetchone()
    return bytes(row[0]) if row else None


def delete(conn, user_id: int, file_id: str) -> bool:
    row = conn.execute("DELETE FROM own_files WHERE id = %s AND user_id = %s RETURNING id", (file_id, user_id)).fetchone()
    return row is not None
