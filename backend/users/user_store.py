"""
User CRUD-Operationen. Direkte DB-Zugriffe.

Authorization model (Phase 13):
  - `role` field: identity/display (values: 'teacher', 'admin') — retained for backward compat
  - `is_admin` field: persisted BOOLEAN authorization flag — used for all admin access decisions
  - Compatibility: passing role='admin' anywhere automatically sets is_admin=True and
    normalizes role to 'teacher'. Both role='admin' (legacy) and role='teacher'+is_admin=True
    (canonical) are accepted inputs and produce identical DB state.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from datetime import datetime


@dataclass
class User:
    """Repräsentiert eine Lehrkraft oder einen Admin im System.

    Attributes:
        id: Primärschlüssel.
        first_name: Vorname.
        last_name: Nachname.
        role: Identity role ('teacher' or 'admin' for legacy compat). NOT used for authorization.
        is_active: Gibt an ob der Account aktiv ist.
        created_at: Erstellungszeitpunkt.
        updated_at: Letzter Änderungszeitpunkt.
        is_admin: Persisted authorization flag. Used by require_admin for all access decisions.
                  A user can be role='teacher' AND is_admin=True simultaneously.
    """
    id: int
    first_name: str
    last_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # is_admin is a persisted DB column (Phase 13). Default False for backward compat
    # when constructed without the column (e.g. legacy code paths).
    is_admin: bool = False

    @property
    def full_name(self) -> str:
        """Vollständiger Name des Users."""
        return f"{self.first_name} {self.last_name}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert den User als dict (ohne Passwort/sensible Daten).

        Returns:
            Dictionary mit sicheren User-Feldern.
            is_admin reflects the persisted DB flag (not derived from role).
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


def _normalize_role_and_admin(role: str, is_admin: bool = False):
    """Normalizes role + is_admin for the compatibility layer.

    Compatibility rule (Phase 13):
      - role='admin'  → returns ('teacher', True)   — legacy callers still work
      - role='teacher', is_admin=True  → ('teacher', True)   — canonical new form
      - role='teacher', is_admin=False → ('teacher', False)  — standard teacher

    Args:
        role: Raw role string from caller.
        is_admin: Raw is_admin flag from caller.

    Returns:
        Tuple (normalized_role: str, normalized_is_admin: bool)
    """
    if role == "admin":
        # Legacy compatibility: treat role='admin' as is_admin=True + normalize role
        return ("teacher", True)
    return (role, is_admin)


def _row_to_user(row) -> User:
    """Konvertiert eine DB-Zeile in ein User-Objekt.

    Expects columns: id, first_name, last_name, role, is_active, created_at, updated_at, is_admin
    Falls back gracefully if is_admin column is missing (row has only 7 columns).
    """
    is_admin = bool(row[7]) if len(row) > 7 else False
    return User(
        id=row[0],
        first_name=row[1],
        last_name=row[2],
        role=row[3],
        is_active=row[4],
        created_at=row[5],
        updated_at=row[6],
        is_admin=is_admin,
    )


def create_user(
    conn,
    first_name: str,
    last_name: str,
    role: str = "teacher",
    is_admin: bool = False,
) -> "User":
    """Erstellt einen neuen User in der Datenbank.

    Args:
        conn: psycopg3 DB-Verbindung.
        first_name: Vorname der Lehrkraft.
        last_name: Nachname der Lehrkraft.
        role: 'teacher' (Standard) oder 'admin' (legacy — normalized to 'teacher' + is_admin=True).
        is_admin: Admin-Berechtigung (separate from role). Defaults to False.
                  Automatically set to True if role='admin' is passed (compatibility layer).

    Returns:
        Neu erstelltes User-Objekt.
    """
    # Compatibility layer: role='admin' → role='teacher', is_admin=True
    normalized_role, normalized_is_admin = _normalize_role_and_admin(role, is_admin)

    row = conn.execute(
        """
        INSERT INTO users (first_name, last_name, role, is_admin)
        VALUES (%s, %s, %s, %s)
        RETURNING id, first_name, last_name, role, is_active, created_at, updated_at, is_admin
        """,
        (first_name, last_name, normalized_role, normalized_is_admin),
    ).fetchone()
    return _row_to_user(row)


def get_user_by_id(conn, user_id: int) -> Optional["User"]:
    """Lädt einen User anhand seiner ID.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: Primärschlüssel des Users.

    Returns:
        User-Objekt oder None wenn nicht gefunden.
    """
    row = conn.execute(
        """
        SELECT id, first_name, last_name, role, is_active, created_at, updated_at, is_admin
        FROM users
        WHERE id = %s
        """,
        (user_id,),
    ).fetchone()
    return _row_to_user(row) if row else None


def get_all_users(conn) -> List["User"]:
    """Lädt alle User aus der Datenbank.

    Args:
        conn: psycopg3 DB-Verbindung.

    Returns:
        Liste aller User-Objekte.
    """
    rows = conn.execute(
        """
        SELECT id, first_name, last_name, role, is_active, created_at, updated_at, is_admin
        FROM users
        ORDER BY last_name, first_name
        """
    ).fetchall()
    return [_row_to_user(row) for row in rows]


_ALLOWED_UPDATE_FIELDS = {"first_name", "last_name", "role", "is_active", "is_admin"}


def update_user(conn, user_id: int, **kwargs) -> Optional["User"]:
    """Aktualisiert User-Felder.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des zu aktualisierenden Users.
        **kwargs: Zu aktualisierende Felder (erlaubt: first_name, last_name, role, is_active,
                  is_admin).
                  Compatibility: passing role='admin' is interpreted as is_admin=True, role='teacher'.

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

    # Compatibility layer: if role='admin' in updates, normalize to role='teacher'+is_admin=True
    if "role" in kwargs and kwargs["role"] == "admin":
        kwargs["role"] = "teacher"
        kwargs.setdefault("is_admin", True)

    set_clauses = ", ".join(f"{field} = %s" for field in kwargs)
    values = list(kwargs.values()) + [user_id]

    row = conn.execute(
        f"""
        UPDATE users
        SET {set_clauses}, updated_at = NOW()
        WHERE id = %s
        RETURNING id, first_name, last_name, role, is_active, created_at, updated_at, is_admin
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
