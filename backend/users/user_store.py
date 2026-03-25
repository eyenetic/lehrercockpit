"""
User CRUD-Operationen. Direkte DB-Zugriffe.
"""
from dataclasses import dataclass
from typing import Optional, List, Any, Dict
from datetime import datetime


@dataclass
class User:
    """Repräsentiert eine Lehrkraft oder einen Admin im System.

    Attributes:
        id: Primärschlüssel.
        first_name: Vorname.
        last_name: Nachname.
        role: 'teacher' oder 'admin'.
        is_active: Gibt an ob der Account aktiv ist.
        created_at: Erstellungszeitpunkt.
        updated_at: Letzter Änderungszeitpunkt.
    """
    id: int
    first_name: str
    last_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        """Vollständiger Name des Users."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_admin(self) -> bool:
        """True wenn der User Admin-Rechte hat."""
        return self.role == "admin"

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert den User als dict (ohne Passwort/sensible Daten).

        Returns:
            Dictionary mit sicheren User-Feldern.
        """
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def _row_to_user(row) -> User:
    """Konvertiert eine DB-Zeile in ein User-Objekt."""
    return User(
        id=row[0],
        first_name=row[1],
        last_name=row[2],
        role=row[3],
        is_active=row[4],
        created_at=row[5],
        updated_at=row[6],
    )


def create_user(conn, first_name: str, last_name: str, role: str = "teacher") -> User:
    """Erstellt einen neuen User in der Datenbank.

    Args:
        conn: psycopg3 DB-Verbindung.
        first_name: Vorname der Lehrkraft.
        last_name: Nachname der Lehrkraft.
        role: 'teacher' (Standard) oder 'admin'.

    Returns:
        Neu erstelltes User-Objekt.
    """
    row = conn.execute(
        """
        INSERT INTO users (first_name, last_name, role)
        VALUES (%s, %s, %s)
        RETURNING id, first_name, last_name, role, is_active, created_at, updated_at
        """,
        (first_name, last_name, role),
    ).fetchone()
    return _row_to_user(row)


def get_user_by_id(conn, user_id: int) -> Optional[User]:
    """Lädt einen User anhand seiner ID.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: Primärschlüssel des Users.

    Returns:
        User-Objekt oder None wenn nicht gefunden.
    """
    row = conn.execute(
        """
        SELECT id, first_name, last_name, role, is_active, created_at, updated_at
        FROM users
        WHERE id = %s
        """,
        (user_id,),
    ).fetchone()
    return _row_to_user(row) if row else None


def get_all_users(conn) -> List[User]:
    """Lädt alle User aus der Datenbank.

    Args:
        conn: psycopg3 DB-Verbindung.

    Returns:
        Liste aller User-Objekte.
    """
    rows = conn.execute(
        """
        SELECT id, first_name, last_name, role, is_active, created_at, updated_at
        FROM users
        ORDER BY last_name, first_name
        """
    ).fetchall()
    return [_row_to_user(row) for row in rows]


_ALLOWED_UPDATE_FIELDS = {"first_name", "last_name", "role", "is_active"}


def update_user(conn, user_id: int, **kwargs) -> Optional[User]:
    """Aktualisiert User-Felder.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des zu aktualisierenden Users.
        **kwargs: Zu aktualisierende Felder (erlaubt: first_name, last_name, role, is_active).

    Returns:
        Aktualisiertes User-Objekt oder None wenn nicht gefunden.

    Raises:
        ValueError: Bei unerlaubten Feldnamen.
    """
    invalid_fields = set(kwargs.keys()) - _ALLOWED_UPDATE_FIELDS
    if invalid_fields:
        raise ValueError(f"Unerlaubte Felder: {invalid_fields}")

    if not kwargs:
        return get_user_by_id(conn, user_id)

    set_clauses = ", ".join(f"{field} = %s" for field in kwargs)
    values = list(kwargs.values()) + [user_id]

    row = conn.execute(
        f"""
        UPDATE users
        SET {set_clauses}, updated_at = NOW()
        WHERE id = %s
        RETURNING id, first_name, last_name, role, is_active, created_at, updated_at
        """,
        values,
    ).fetchone()
    return _row_to_user(row) if row else None


def delete_user(conn, user_id: int) -> bool:
    """Löscht einen User (und alle zugehörigen Daten via CASCADE).

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des zu löschenden Users.

    Returns:
        True wenn gelöscht, False wenn nicht gefunden.
    """
    result = conn.execute(
        "DELETE FROM users WHERE id = %s",
        (user_id,),
    )
    return result.rowcount > 0


# ── Access Code Operationen ────────────────────────────────────────────────────

def set_access_code(conn, user_id: int, code_hash: str, code_prefix: str = "") -> None:
    """Speichert oder überschreibt den Zugangscode-Hash eines Users (upsert).

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        code_hash: argon2id-Hash des neuen Zugangscodes.
        code_prefix: Erste 8 Zeichen des Klartextcodes für O(1)-Lookup (optional).
    """
    conn.execute(
        """
        INSERT INTO user_access_codes (user_id, code_hash, code_prefix)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
            SET code_hash = EXCLUDED.code_hash,
                code_prefix = EXCLUDED.code_prefix,
                created_at = NOW()
        """,
        (user_id, code_hash, code_prefix),
    )


def get_access_code_hash(conn, user_id: int) -> Optional[str]:
    """Lädt den Zugangscode-Hash eines Users.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.

    Returns:
        argon2id-Hash-String oder None wenn kein Code gesetzt.
    """
    row = conn.execute(
        "SELECT code_hash FROM user_access_codes WHERE user_id = %s",
        (user_id,),
    ).fetchone()
    return row[0] if row else None
