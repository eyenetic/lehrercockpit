"""
Admin-Funktionen für das Lehrer-Cockpit.

Enthält sowohl Low-Level-Helpers (system_settings, module defaults) als auch
High-Level-Wrapper für User-Management, die von Admin-Routen und Bootstrap
verwendet werden können.
"""
from typing import List, Dict, Any, Optional, Tuple
import psycopg.types.json as _pjson


# ── System-Settings ────────────────────────────────────────────────────────────

def get_system_setting(conn, key: str, default: Any = None) -> Any:
    """Lädt eine globale System-Einstellung.

    Args:
        conn: psycopg3 DB-Verbindung.
        key: Einstellungsschlüssel.
        default: Rückgabewert wenn Einstellung nicht vorhanden.

    Returns:
        Einstellungswert oder default.
    """
    row = conn.execute(
        "SELECT value FROM system_settings WHERE key = %s",
        (key,),
    ).fetchone()
    return row[0] if row else default


def set_system_setting(conn, key: str, value: Any) -> bool:
    """Speichert eine globale System-Einstellung (upsert).

    Args:
        conn: psycopg3 DB-Verbindung.
        key: Einstellungsschlüssel.
        value: Einstellungswert (muss JSON-serialisierbar sein).

    Returns:
        True bei Erfolg.
    """
    conn.execute(
        """
        INSERT INTO system_settings (key, value, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
        """,
        (key, _pjson.Jsonb(value)),
    )
    return True


def get_all_system_settings(conn) -> Dict[str, Any]:
    """Lädt alle globalen System-Einstellungen.

    Args:
        conn: psycopg3 DB-Verbindung.

    Returns:
        Dictionary mit allen key → value Paaren.
    """
    rows = conn.execute(
        "SELECT key, value FROM system_settings ORDER BY key"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


# ── Module Defaults ────────────────────────────────────────────────────────────

def get_default_module_order(conn) -> List[str]:
    """Gibt die Standard-Modul-Reihenfolge zurück.

    Lädt den Wert aus system_settings unter dem Schlüssel 'default_module_order'.
    Falls nicht gesetzt, wird die DB-Reihenfolge aus der modules-Tabelle verwendet.

    Args:
        conn: psycopg3 DB-Verbindung.

    Returns:
        Liste von Modul-IDs in der Standard-Reihenfolge.
    """
    value = get_system_setting(conn, "default_module_order", None)
    if isinstance(value, list):
        return value
    # Fallback: Reihenfolge aus DB
    rows = conn.execute(
        "SELECT id FROM modules WHERE is_enabled = TRUE ORDER BY default_order"
    ).fetchall()
    return [row[0] for row in rows]


def set_default_module_order(conn, module_ids: List[str]) -> bool:
    """Speichert die Standard-Modul-Reihenfolge.

    Args:
        conn: psycopg3 DB-Verbindung.
        module_ids: Liste von Modul-IDs in der gewünschten Reihenfolge.

    Returns:
        True bei Erfolg.
    """
    return set_system_setting(conn, "default_module_order", module_ids)


def get_default_enabled_modules(conn) -> List[str]:
    """Gibt die Standard-Liste aktivierter Module zurück.

    Lädt den Wert aus system_settings unter dem Schlüssel 'default_enabled_modules'.
    Falls nicht gesetzt, werden alle Module mit default_visible=TRUE zurückgegeben.

    Args:
        conn: psycopg3 DB-Verbindung.

    Returns:
        Liste von Modul-IDs die standardmäßig aktiviert sind.
    """
    value = get_system_setting(conn, "default_enabled_modules", None)
    if isinstance(value, list):
        return value
    # Fallback: Module mit default_visible=TRUE
    rows = conn.execute(
        "SELECT id FROM modules WHERE is_enabled = TRUE AND default_visible = TRUE ORDER BY default_order"
    ).fetchall()
    return [row[0] for row in rows]


def set_default_enabled_modules(conn, module_ids: List[str]) -> bool:
    """Speichert die Standard-Liste aktivierter Module.

    Args:
        conn: psycopg3 DB-Verbindung.
        module_ids: Liste von Modul-IDs die standardmäßig aktiviert sein sollen.

    Returns:
        True bei Erfolg.
    """
    return set_system_setting(conn, "default_enabled_modules", module_ids)


# ── Module Registry Management ─────────────────────────────────────────────────

def set_default_module_config(
    conn,
    module_id: str,
    default_order: Optional[int] = None,
    default_visible: Optional[bool] = None,
) -> bool:
    """Aktualisiert die Standard-Konfiguration eines Moduls in der Registry.

    Args:
        conn: psycopg3 DB-Verbindung.
        module_id: ID des Moduls.
        default_order: Neuer Standard-Sortierindex (optional).
        default_visible: Neue Standard-Sichtbarkeit (optional).

    Returns:
        True wenn das Modul gefunden und aktualisiert wurde, sonst False.
    """
    updates: Dict[str, Any] = {}
    if default_order is not None:
        updates["default_order"] = default_order
    if default_visible is not None:
        updates["default_visible"] = default_visible

    if not updates:
        # Prüfe nur ob das Modul existiert
        row = conn.execute(
            "SELECT 1 FROM modules WHERE id = %s", (module_id,)
        ).fetchone()
        return row is not None

    set_clauses = ", ".join(f"{field} = %s" for field in updates)
    values = list(updates.values()) + [module_id]

    result = conn.execute(
        f"UPDATE modules SET {set_clauses} WHERE id = %s",
        values,
    )
    return result.rowcount > 0


# ── User Management ────────────────────────────────────────────────────────────

def get_all_users(conn) -> List[Dict[str, Any]]:
    """Gibt alle User zurück (für Admin-Verwaltung).

    Enthält nur sichere Felder — keine Access-Codes oder Hashes.

    Args:
        conn: psycopg3 DB-Verbindung.

    Returns:
        Liste von User-Dicts mit id, display_name, first_name, last_name,
        role, is_active, created_at.
    """
    rows = conn.execute(
        """
        SELECT id, first_name, last_name, role, is_active, created_at, updated_at
        FROM users
        ORDER BY last_name, first_name
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "display_name": f"{row[1]} {row[2]}",
            "role": row[3],
            "is_active": row[4],
            "created_at": row[5].isoformat(),
            "updated_at": row[6].isoformat(),
        }
        for row in rows
    ]


def get_user(conn, user_id: int) -> Optional[Dict[str, Any]]:
    """Gibt einen einzelnen User zurück.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.

    Returns:
        User-Dict oder None wenn nicht gefunden.
    """
    row = conn.execute(
        """
        SELECT id, first_name, last_name, role, is_active, created_at, updated_at
        FROM users
        WHERE id = %s
        """,
        (user_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "first_name": row[1],
        "last_name": row[2],
        "display_name": f"{row[1]} {row[2]}",
        "role": row[3],
        "is_active": row[4],
        "created_at": row[5].isoformat(),
        "updated_at": row[6].isoformat(),
    }


def deactivate_user(conn, user_id: int) -> bool:
    """Deaktiviert einen User (Soft-Delete).

    Setzt is_active=False und invalidiert alle Sessions.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.

    Returns:
        True wenn User gefunden und deaktiviert, False wenn nicht gefunden.
    """
    result = conn.execute(
        """
        UPDATE users SET is_active = FALSE, updated_at = NOW()
        WHERE id = %s
        RETURNING id
        """,
        (user_id,),
    )
    if result.rowcount == 0:
        return False
    # Alle Sessions des Users invalidieren
    conn.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
    return True


def rotate_access_code(conn, user_id: int) -> Optional[str]:
    """Generiert einen neuen Zugangscode für einen User.

    Ersetzt den alten Hash in der access_codes-Tabelle.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.

    Returns:
        Neuer Plaintext-Code (nur einmalig) oder None wenn User nicht gefunden.
    """
    from backend.users.user_service import regenerate_access_code
    return regenerate_access_code(conn, user_id)


def create_teacher(
    conn,
    first_name: str,
    last_name: str,
    role: str = "teacher",
    display_name: Optional[str] = None,
) -> Tuple[Any, str]:
    """Erstellt eine neue Lehrkraft mit Zugangscode und initialisiert Module.

    Wrapper um user_service.create_teacher + initialize_user_modules.

    Args:
        conn: psycopg3 DB-Verbindung.
        first_name: Vorname.
        last_name: Nachname.
        role: 'teacher' oder 'admin'.
        display_name: Ignoriert (nur für API-Kompatibilität; full_name wird aus first+last gebaut).

    Returns:
        Tuple aus (User, plain_code) — plain_code nur einmalig.
    """
    from backend.users.user_service import create_teacher as _create_teacher
    from backend.modules.module_registry import initialize_user_modules
    user, plain_code = _create_teacher(conn, first_name, last_name, role)
    initialize_user_modules(conn, user.id)
    return user, plain_code


# ── User Overview (Admin Dashboard) ───────────────────────────────────────────

def get_user_overview(conn) -> List[Dict[str, Any]]:
    """Gibt eine Übersicht aller User zurück (für Admin-Dashboard).

    Enthält User-Felder plus:
    - module_count: Anzahl konfigurierter Module
    - has_access_code: Ob ein Zugangscode gesetzt ist

    Args:
        conn: psycopg3 DB-Verbindung.

    Returns:
        Liste von User-Dicts mit erweiterten Admin-Infos.
    """
    rows = conn.execute(
        """
        SELECT
            u.id,
            u.first_name,
            u.last_name,
            u.role,
            u.is_active,
            u.created_at,
            u.updated_at,
            COUNT(um.id) FILTER (WHERE um.is_configured = TRUE) AS module_count,
            (uac.user_id IS NOT NULL) AS has_access_code
        FROM users u
        LEFT JOIN user_modules um ON um.user_id = u.id
        LEFT JOIN user_access_codes uac ON uac.user_id = u.id
        GROUP BY u.id, u.first_name, u.last_name, u.role, u.is_active,
                 u.created_at, u.updated_at, uac.user_id
        ORDER BY u.last_name, u.first_name
        """
    ).fetchall()

    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "display_name": f"{row[1]} {row[2]}",
            "full_name": f"{row[1]} {row[2]}",
            "role": row[3],
            "is_active": row[4],
            "is_admin": row[3] == "admin",
            "created_at": row[5].isoformat(),
            "updated_at": row[6].isoformat(),
            "module_count": row[7],
            "has_access_code": row[8],
        })
    return result
