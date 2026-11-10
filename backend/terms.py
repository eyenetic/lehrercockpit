"""Nutzungsbedingungen: welche Fassung gilt und wer ihr wann zugestimmt hat.

Der Text selbst steht in src/features/terms.js. Wird er inhaltlich geändert,
VERSION hier und dort gleich hochsetzen – dann fragt das Cockpit alle erneut.
Jede Zustimmung bleibt als eigene Zeile erhalten (Nachweis), ohne IP-Adresse.
"""
from __future__ import annotations

VERSION = "2026-11-10"


def migrate(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS terms_acceptances (
            id           SERIAL PRIMARY KEY,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            version      TEXT NOT NULL,
            accepted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, version)
        )
        """
    )


def accepted_at(conn, user_id: int, version: str = VERSION):
    row = conn.execute(
        "SELECT accepted_at FROM terms_acceptances WHERE user_id = %s AND version = %s",
        (user_id, version),
    ).fetchone()
    return row[0] if row else None


def accept(conn, user_id: int, version: str = VERSION):
    """Records the acceptance (idempotent) and returns its time."""
    conn.execute(
        "INSERT INTO terms_acceptances (user_id, version) VALUES (%s, %s) "
        "ON CONFLICT (user_id, version) DO NOTHING",
        (user_id, version),
    )
    return accepted_at(conn, user_id, version)


def status(conn, user_id: int) -> dict:
    when = accepted_at(conn, user_id)
    return {"version": VERSION, "accepted": when is not None,
            "accepted_at": when.isoformat() if when else None}
