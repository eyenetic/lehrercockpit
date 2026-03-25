"""
Modul-Registry und User-Modul-Verwaltung.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class Module:
    """Repräsentiert ein registriertes Cockpit-Modul.

    Attributes:
        id: Eindeutiger Bezeichner (z.B. 'itslearning').
        display_name: Anzeigename im UI.
        description: Kurzbeschreibung des Moduls.
        module_type: 'individual', 'central' oder 'local'.
        is_enabled: Ob das Modul global aktiv ist.
        default_visible: Standard-Sichtbarkeit für neue User.
        default_order: Standard-Reihenfolge im Dashboard.
        requires_config: Ob der User Credentials eingeben muss.
    """
    id: str
    display_name: str
    description: str
    module_type: str
    is_enabled: bool
    default_visible: bool
    default_order: int
    requires_config: bool

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert das Modul als dict.

        Returns:
            Dictionary mit allen Modul-Feldern.
        """
        return {
            "id": self.id,
            "display_name": self.display_name,
            "description": self.description,
            "module_type": self.module_type,
            "is_enabled": self.is_enabled,
            "default_visible": self.default_visible,
            "default_order": self.default_order,
            "requires_config": self.requires_config,
        }


@dataclass
class UserModule:
    """Repräsentiert die User-spezifischen Einstellungen für ein Modul.

    Attributes:
        id: Primärschlüssel.
        user_id: ID des zugehörigen Users.
        module_id: ID des Moduls.
        is_visible: Ob das Modul im Dashboard angezeigt wird.
        sort_order: Reihenfolge im Dashboard.
        is_configured: Ob der User das Modul konfiguriert hat.
    """
    id: int
    user_id: int
    module_id: str
    is_visible: bool
    sort_order: int
    is_configured: bool

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert das UserModule als dict.

        Returns:
            Dictionary mit allen UserModule-Feldern.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "module_id": self.module_id,
            "is_visible": self.is_visible,
            "sort_order": self.sort_order,
            "is_configured": self.is_configured,
        }


def _row_to_module(row) -> Module:
    """Konvertiert eine DB-Zeile in ein Module-Objekt."""
    return Module(
        id=row[0],
        display_name=row[1],
        description=row[2],
        module_type=row[3],
        is_enabled=row[4],
        default_visible=row[5],
        default_order=row[6],
        requires_config=row[7],
    )


def _row_to_user_module(row) -> UserModule:
    """Konvertiert eine DB-Zeile in ein UserModule-Objekt."""
    return UserModule(
        id=row[0],
        user_id=row[1],
        module_id=row[2],
        is_visible=row[3],
        sort_order=row[4],
        is_configured=row[5],
    )


def get_all_modules(conn) -> List[Module]:
    """Lädt alle registrierten Module aus der Datenbank.

    Args:
        conn: psycopg3 DB-Verbindung.

    Returns:
        Liste aller Module, sortiert nach default_order.
    """
    rows = conn.execute(
        """
        SELECT id, display_name, description, module_type, is_enabled,
               default_visible, default_order, requires_config
        FROM modules
        ORDER BY default_order
        """
    ).fetchall()
    return [_row_to_module(row) for row in rows]


def get_modules_by_type(conn, module_type: str) -> List[Module]:
    """Lädt alle Module eines bestimmten Typs.

    Args:
        conn: psycopg3 DB-Verbindung.
        module_type: Typ-Filter ('individual', 'central' oder 'local').

    Returns:
        Liste der gefilterten Module, sortiert nach default_order.
    """
    rows = conn.execute(
        """
        SELECT id, display_name, description, module_type, is_enabled,
               default_visible, default_order, requires_config
        FROM modules
        WHERE module_type = %s
        ORDER BY default_order
        """,
        (module_type,),
    ).fetchall()
    return [_row_to_module(row) for row in rows]


def get_default_module_set(conn) -> List[Module]:
    """Gibt alle standardmäßig aktivierten Module zurück.

    Returns Module where is_enabled=TRUE and default_visible=TRUE,
    sorted by default_order.

    Args:
        conn: psycopg3 DB-Verbindung.

    Returns:
        Liste der Standard-Module, sortiert nach default_order.
    """
    rows = conn.execute(
        """
        SELECT id, display_name, description, module_type, is_enabled,
               default_visible, default_order, requires_config
        FROM modules
        WHERE is_enabled = TRUE AND default_visible = TRUE
        ORDER BY default_order
        """
    ).fetchall()
    return [_row_to_module(row) for row in rows]


def is_valid_module(conn, module_id: str) -> bool:
    """Prüft ob ein Modul mit der gegebenen ID existiert.

    Args:
        conn: psycopg3 DB-Verbindung.
        module_id: ID des Moduls.

    Returns:
        True wenn das Modul existiert, sonst False.
    """
    row = conn.execute(
        "SELECT 1 FROM modules WHERE id = %s",
        (module_id,),
    ).fetchone()
    return row is not None


def get_module_by_id(conn, module_id: str) -> Optional[Module]:
    """Lädt ein Modul anhand seiner ID.

    Args:
        conn: psycopg3 DB-Verbindung.
        module_id: ID des Moduls.

    Returns:
        Module-Objekt oder None wenn nicht gefunden.
    """
    row = conn.execute(
        """
        SELECT id, display_name, description, module_type, is_enabled,
               default_visible, default_order, requires_config
        FROM modules
        WHERE id = %s
        """,
        (module_id,),
    ).fetchone()
    return _row_to_module(row) if row else None


def get_user_modules(conn, user_id: int) -> List[UserModule]:
    """Lädt alle User-Modul-Einstellungen für einen User.

    Inkludiert Modul-Infos. Gibt nur Einträge zurück wo das Modul noch
    global aktiviert ist.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.

    Returns:
        Liste der UserModule-Objekte, sortiert nach sort_order.
    """
    rows = conn.execute(
        """
        SELECT um.id, um.user_id, um.module_id, um.is_visible, um.sort_order, um.is_configured
        FROM user_modules um
        INNER JOIN modules m ON m.id = um.module_id
        WHERE um.user_id = %s AND m.is_enabled = TRUE
        ORDER BY um.sort_order
        """,
        (user_id,),
    ).fetchall()
    return [_row_to_user_module(row) for row in rows]


def initialize_user_modules(conn, user_id: int) -> None:
    """Erstellt UserModule-Einträge für alle aktivierten Module (falls noch nicht vorhanden).

    Nutzt die default-Werte aus der modules-Tabelle.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users für den die Module initialisiert werden sollen.
    """
    conn.execute(
        """
        INSERT INTO user_modules (user_id, module_id, is_visible, sort_order)
        SELECT %s, m.id, m.default_visible, m.default_order
        FROM modules m
        WHERE m.is_enabled = TRUE
        ON CONFLICT (user_id, module_id) DO NOTHING
        """,
        (user_id,),
    )


def update_user_module_visibility(
    conn, user_id: int, module_id: str, is_visible: bool
) -> bool:
    """Aktualisiert die Sichtbarkeit eines Moduls für einen User.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        module_id: ID des Moduls.
        is_visible: Neue Sichtbarkeit.

    Returns:
        True wenn erfolgreich aktualisiert, False wenn Eintrag nicht gefunden.
    """
    result = conn.execute(
        """
        UPDATE user_modules
        SET is_visible = %s, updated_at = NOW()
        WHERE user_id = %s AND module_id = %s
        """,
        (is_visible, user_id, module_id),
    )
    return result.rowcount > 0


def update_user_module_order(
    conn, user_id: int, module_orders: List[Dict[str, Any]]
) -> None:
    """Aktualisiert die Reihenfolge mehrerer Module für einen User.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        module_orders: Liste von {"module_id": str, "sort_order": int}.
    """
    for item in module_orders:
        conn.execute(
            """
            UPDATE user_modules
            SET sort_order = %s, updated_at = NOW()
            WHERE user_id = %s AND module_id = %s
            """,
            (item["sort_order"], user_id, item["module_id"]),
        )


def get_user_module_config(conn, user_id: int, module_id: str) -> Dict[str, Any]:
    """Lädt die User-spezifische Konfiguration für ein Modul.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        module_id: ID des Moduls.

    Returns:
        Konfigurationsdaten als dict (leer wenn keine Konfiguration vorhanden).
        Sensible Felder werden automatisch entschlüsselt (falls Verschlüsselung aktiv).
    """
    from backend.crypto import decrypt_config

    row = conn.execute(
        """
        SELECT config_data
        FROM user_module_configs
        WHERE user_id = %s AND module_id = %s
        """,
        (user_id, module_id),
    ).fetchone()
    raw = row[0] if row else {}
    return decrypt_config(raw)


def save_user_module_config(
    conn, user_id: int, module_id: str, config_data: Dict[str, Any]
) -> None:
    """Speichert User-spezifische Modul-Konfiguration (upsert).

    Sensible Felder werden automatisch verschlüsselt (falls ENCRYPTION_KEY gesetzt).
    Markiert das Modul außerdem als konfiguriert in user_modules.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        module_id: ID des Moduls.
        config_data: Konfigurationsdaten (z.B. Credentials).
    """
    import psycopg.types.json as _pjson
    from backend.crypto import encrypt_config

    config_data = encrypt_config(config_data)

    conn.execute(
        """
        INSERT INTO user_module_configs (user_id, module_id, config_data, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (user_id, module_id) DO UPDATE
            SET config_data = EXCLUDED.config_data,
                updated_at = EXCLUDED.updated_at
        """,
        (user_id, module_id, _pjson.Jsonb(config_data)),
    )

    # Modul als konfiguriert markieren
    conn.execute(
        """
        UPDATE user_modules
        SET is_configured = TRUE, updated_at = NOW()
        WHERE user_id = %s AND module_id = %s
        """,
        (user_id, module_id),
    )


def update_user_module(
    conn, user_id: int, module_id: str, **fields
) -> bool:
    """Aktualisiert einzelne Felder eines User-Modul-Eintrags (Upsert).

    Erlaubte Felder: enabled/is_visible (bool), sort_order (int), is_visible (bool).

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        module_id: ID des Moduls.
        **fields: Zu aktualisierende Felder.

    Returns:
        True wenn erfolgreich, False wenn Eintrag nicht gefunden.
    """
    _ALLOWED = {"enabled", "is_visible", "sort_order"}
    updates: Dict[str, Any] = {}

    for key, val in fields.items():
        if key == "enabled":
            updates["is_visible"] = bool(val)
        elif key == "is_visible":
            updates["is_visible"] = bool(val)
        elif key == "sort_order":
            updates["sort_order"] = int(val)

    if not updates:
        row = conn.execute(
            "SELECT 1 FROM user_modules WHERE user_id = %s AND module_id = %s",
            (user_id, module_id),
        ).fetchone()
        return row is not None

    set_clauses = ", ".join(f"{field} = %s" for field in updates)
    values = list(updates.values()) + [user_id, module_id]

    result = conn.execute(
        f"""
        UPDATE user_modules
        SET {set_clauses}, updated_at = NOW()
        WHERE user_id = %s AND module_id = %s
        """,
        values,
    )
    return result.rowcount > 0
