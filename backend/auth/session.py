"""
Session-Management. Sessions werden in der DB gespeichert.
"""
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

SESSION_DURATION_DAYS = 30


@dataclass
class Session:
    """Repräsentiert eine aktive Benutzer-Session.

    Attributes:
        id: UUID der Session (Primary Key in DB).
        user_id: ID des zugehörigen Users.
        created_at: Zeitpunkt der Session-Erstellung.
        expires_at: Ablaufzeitpunkt der Session.
        last_seen: Letzter Aktivitätszeitpunkt.
    """
    id: str
    user_id: int
    created_at: datetime
    expires_at: datetime
    last_seen: datetime


def create_session(conn, user_id: int) -> Session:
    """Erstellt eine neue Session in der Datenbank.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users für den die Session erstellt wird.

    Returns:
        Neu erstelltes Session-Objekt.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=SESSION_DURATION_DAYS)

    conn.execute(
        """
        INSERT INTO sessions (id, user_id, created_at, expires_at, last_seen)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (session_id, user_id, now, expires_at, now),
    )

    return Session(
        id=session_id,
        user_id=user_id,
        created_at=now,
        expires_at=expires_at,
        last_seen=now,
    )


def get_session(conn, session_id: str) -> Optional[Session]:
    """Lädt eine Session aus der DB. Gibt None zurück wenn abgelaufen oder nicht gefunden.

    Args:
        conn: psycopg3 DB-Verbindung.
        session_id: UUID der Session.

    Returns:
        Session-Objekt oder None wenn nicht gefunden / abgelaufen.
    """
    now = datetime.now(timezone.utc)
    row = conn.execute(
        """
        SELECT id, user_id, created_at, expires_at, last_seen
        FROM sessions
        WHERE id = %s AND expires_at > %s
        """,
        (session_id, now),
    ).fetchone()

    if row is None:
        return None

    return Session(
        id=row[0],
        user_id=row[1],
        created_at=row[2],
        expires_at=row[3],
        last_seen=row[4],
    )


def refresh_session(conn, session_id: str) -> bool:
    """Aktualisiert den last_seen-Zeitstempel einer Session.

    Args:
        conn: psycopg3 DB-Verbindung.
        session_id: UUID der Session.

    Returns:
        True wenn die Session gefunden und aktualisiert wurde, sonst False.
    """
    now = datetime.now(timezone.utc)
    result = conn.execute(
        """
        UPDATE sessions
        SET last_seen = %s
        WHERE id = %s AND expires_at > %s
        """,
        (now, session_id, now),
    )
    return result.rowcount > 0


def delete_session(conn, session_id: str) -> None:
    """Löscht eine Session aus der Datenbank (Logout).

    Args:
        conn: psycopg3 DB-Verbindung.
        session_id: UUID der zu löschenden Session.
    """
    conn.execute(
        "DELETE FROM sessions WHERE id = %s",
        (session_id,),
    )


def cleanup_expired_sessions(conn) -> int:
    """Löscht alle abgelaufenen Sessions.

    Args:
        conn: psycopg3 DB-Verbindung.

    Returns:
        Anzahl der gelöschten Sessions.
    """
    now = datetime.now(timezone.utc)
    result = conn.execute(
        "DELETE FROM sessions WHERE expires_at <= %s",
        (now,),
    )
    return result.rowcount
