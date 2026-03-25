"""
Business-Logik für User-Management.
Kombiniert user_store, access_code und module_registry Operationen.
"""
from typing import Tuple, Optional, List, Dict, Any

from .user_store import User, create_user, set_access_code, get_access_code_hash, get_all_users
from ..auth.access_code import generate_code, hash_code, verify_code, get_code_prefix


def create_teacher(
    conn, first_name: str, last_name: str, role: str = "teacher"
) -> Tuple[User, str]:
    """Erstellt eine neue Lehrkraft mit einem generierten Zugangscode.

    Der Plain-Code wird NUR einmalig zurückgegeben und danach nicht mehr
    zugänglich (nur der Hash wird gespeichert).

    Args:
        conn: psycopg3 DB-Verbindung.
        first_name: Vorname der Lehrkraft.
        last_name: Nachname der Lehrkraft.
        role: 'teacher' (Standard) oder 'admin'.

    Returns:
        Tuple aus (User, plain_code) – plain_code nur einmalig verfügbar.
    """
    user = create_user(conn, first_name, last_name, role)
    plain_code = generate_code()
    code_hash = hash_code(plain_code)
    prefix = get_code_prefix(plain_code)
    set_access_code(conn, user.id, code_hash, code_prefix=prefix)
    return user, plain_code


def regenerate_access_code(conn, user_id: int) -> Optional[str]:
    """Generiert einen neuen Zugangscode für einen bestehenden User.

    Der alte Code wird überschrieben und ist danach ungültig.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.

    Returns:
        Neuer Plain-Code (nur einmalig) oder None wenn User nicht gefunden.
    """
    from .user_store import get_user_by_id
    user = get_user_by_id(conn, user_id)
    if user is None:
        return None

    plain_code = generate_code()
    code_hash = hash_code(plain_code)
    prefix = get_code_prefix(plain_code)
    set_access_code(conn, user_id, code_hash, code_prefix=prefix)
    return plain_code


def authenticate_by_code(conn, plain_code: str) -> Optional[User]:
    """Authentifiziert einen User anhand seines Zugangscodes.

    Nutzt code_prefix für O(1) DB-Vorfilterung: nur Users mit passendem Präfix
    (oder ohne Präfix für Rückwärtskompatibilität) werden mit argon2 verifiziert.

    Args:
        conn: psycopg3 DB-Verbindung.
        plain_code: Eingegeben Zugangscode im Klartext.

    Returns:
        Aktiver User wenn Authentifizierung erfolgreich, sonst None.
    """
    prefix = get_code_prefix(plain_code)

    rows = conn.execute(
        """
        SELECT u.id, u.first_name, u.last_name, u.role, u.is_active,
               u.created_at, u.updated_at, uac.code_hash
        FROM users u
        INNER JOIN user_access_codes uac ON uac.user_id = u.id
        WHERE u.is_active = TRUE
          AND (uac.code_prefix = %s OR uac.code_prefix IS NULL)
        """,
        (prefix,),
    ).fetchall()

    for row in rows:
        stored_hash = row[7]
        if verify_code(plain_code, stored_hash):
            from .user_store import User as U
            user = U(
                id=row[0],
                first_name=row[1],
                last_name=row[2],
                role=row[3],
                is_active=row[4],
                created_at=row[5],
                updated_at=row[6],
            )
            return user

    return None


# ── Grades service functions (Phase 9b) ───────────────────────────────────────

def get_grades(conn, user_id: int) -> List[Dict[str, Any]]:
    """Lädt alle Noten-Einträge für einen User.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.

    Returns:
        Liste von dicts mit id, user_id, class_name, subject, grade_value,
        grade_date, note, created_at, updated_at.
    """
    rows = conn.execute(
        """
        SELECT id, user_id, class_name, subject, grade_value, grade_date,
               note, created_at, updated_at
        FROM grades
        WHERE user_id = %s
        ORDER BY class_name, grade_date DESC
        """,
        (user_id,),
    ).fetchall()

    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "user_id": row[1],
            "class_name": row[2],
            "subject": row[3],
            "grade_value": row[4],
            "grade_date": row[5].isoformat() if row[5] else None,
            "note": row[6] or "",
            "created_at": row[7].isoformat() if row[7] else None,
            "updated_at": row[8].isoformat() if row[8] else None,
        })
    return result


def upsert_grade(
    conn,
    user_id: int,
    class_name: str,
    subject: str,
    grade_value: str,
    grade_date=None,
    note: str = "",
    grade_id: int = None,
) -> Dict[str, Any]:
    """Erstellt oder aktualisiert einen Noten-Eintrag.

    Wenn grade_id angegeben: UPDATE (mit user_id-Eigentumscheck).
    Sonst: INSERT.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users (Eigentümer-Check bei Update).
        class_name: Klassenbezeichnung.
        subject: Fach.
        grade_value: Notenwert (z.B. '2+').
        grade_date: Datum der Note (optional).
        note: Anmerkung (optional).
        grade_id: Wenn gesetzt: Update des Eintrags mit dieser ID.

    Returns:
        Gespeicherter Noten-Eintrag als dict.
    """
    if grade_id is not None:
        row = conn.execute(
            """
            UPDATE grades
            SET class_name = %s, subject = %s, grade_value = %s,
                grade_date = %s, note = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING id, user_id, class_name, subject, grade_value, grade_date,
                      note, created_at, updated_at
            """,
            (class_name, subject, grade_value, grade_date, note, grade_id, user_id),
        ).fetchone()
    else:
        row = conn.execute(
            """
            INSERT INTO grades (user_id, class_name, subject, grade_value, grade_date, note)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, user_id, class_name, subject, grade_value, grade_date,
                      note, created_at, updated_at
            """,
            (user_id, class_name, subject, grade_value, grade_date, note),
        ).fetchone()

    if row is None:
        return {}

    return {
        "id": row[0],
        "user_id": row[1],
        "class_name": row[2],
        "subject": row[3],
        "grade_value": row[4],
        "grade_date": row[5].isoformat() if row[5] else None,
        "note": row[6] or "",
        "created_at": row[7].isoformat() if row[7] else None,
        "updated_at": row[8].isoformat() if row[8] else None,
    }


def delete_grade(conn, user_id: int, grade_id: int) -> bool:
    """Löscht einen Noten-Eintrag (nur wenn er dem User gehört).

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users (Eigentümer-Check).
        grade_id: ID des zu löschenden Eintrags.

    Returns:
        True wenn gelöscht, False wenn nicht gefunden oder nicht Eigentümer.
    """
    result = conn.execute(
        "DELETE FROM grades WHERE id = %s AND user_id = %s",
        (grade_id, user_id),
    )
    return result.rowcount > 0


# ── Notes service functions (Phase 9b) ────────────────────────────────────────

def get_notes(conn, user_id: int) -> List[Dict[str, Any]]:
    """Lädt alle Klassen-Notizen für einen User.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.

    Returns:
        Liste von dicts mit id, user_id, class_name, note_text, created_at, updated_at.
    """
    rows = conn.execute(
        """
        SELECT id, user_id, class_name, note_text, created_at, updated_at
        FROM class_notes
        WHERE user_id = %s
        ORDER BY class_name
        """,
        (user_id,),
    ).fetchall()

    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "user_id": row[1],
            "class_name": row[2],
            "note_text": row[3] or "",
            "created_at": row[4].isoformat() if row[4] else None,
            "updated_at": row[5].isoformat() if row[5] else None,
        })
    return result


def upsert_note(conn, user_id: int, class_name: str, note_text: str) -> Dict[str, Any]:
    """Erstellt oder aktualisiert eine Klassen-Notiz (Upsert per user_id + class_name).

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        class_name: Klassenbezeichnung.
        note_text: Notiztext.

    Returns:
        Gespeicherte Notiz als dict.
    """
    row = conn.execute(
        """
        INSERT INTO class_notes (user_id, class_name, note_text)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, class_name) DO UPDATE
            SET note_text = EXCLUDED.note_text,
                updated_at = NOW()
        RETURNING id, user_id, class_name, note_text, created_at, updated_at
        """,
        (user_id, class_name, note_text),
    ).fetchone()

    if row is None:
        return {}

    return {
        "id": row[0],
        "user_id": row[1],
        "class_name": row[2],
        "note_text": row[3] or "",
        "created_at": row[4].isoformat() if row[4] else None,
        "updated_at": row[5].isoformat() if row[5] else None,
    }


def delete_note(conn, user_id: int, class_name: str) -> bool:
    """Löscht eine Klassen-Notiz.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        class_name: Klassenbezeichnung.

    Returns:
        True wenn gelöscht, False wenn nicht gefunden.
    """
    result = conn.execute(
        "DELETE FROM class_notes WHERE user_id = %s AND class_name = %s",
        (user_id, class_name),
    )
    return result.rowcount > 0


# ── User Module State Management ───────────────────────────────────────────────

def get_user_modules(conn, user_id: int) -> List[Dict[str, Any]]:
    """Gibt den Modul-Status eines Users zurück.

    Kombiniert UserModule-Einträge mit Modul-Metadaten aus der Registry.
    Module ohne eigenen Eintrag werden mit Registry-Defaults gefüllt.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.

    Returns:
        Liste von dicts mit module_id, enabled, sort_order, is_visible,
        is_configured pro Modul.
    """
    from ..modules.module_registry import (
        get_all_modules,
        get_user_modules as _get_user_modules,
    )
    all_modules = get_all_modules(conn)
    user_module_list = _get_user_modules(conn, user_id)
    user_module_map = {um.module_id: um for um in user_module_list}

    result = []
    for module in all_modules:
        if not module.is_enabled:
            continue
        um = user_module_map.get(module.id)
        if um:
            result.append({
                "module_id": module.id,
                "enabled": um.is_visible,
                "is_visible": um.is_visible,
                "sort_order": um.sort_order,
                "order": um.sort_order,
                "is_configured": um.is_configured,
                "configured": um.is_configured,
            })
        else:
            # Use registry defaults
            result.append({
                "module_id": module.id,
                "enabled": module.default_visible,
                "is_visible": module.default_visible,
                "sort_order": module.default_order,
                "order": module.default_order,
                "is_configured": False,
                "configured": False,
            })

    result.sort(key=lambda m: m["sort_order"])
    return result


def update_user_module(conn, user_id: int, module_id: str, **fields) -> bool:
    """Aktualisiert einzelne Felder eines User-Modul-Eintrags.

    Erlaubte Felder: enabled (bool), sort_order (int), is_visible (bool).
    Führt einen Upsert durch wenn der Eintrag noch nicht existiert.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        module_id: ID des Moduls.
        **fields: Zu aktualisierende Felder.

    Returns:
        True bei Erfolg.
    """
    from ..modules.module_registry import update_user_module as _update_user_module
    return _update_user_module(conn, user_id, module_id, **fields)


def update_user_module_order(conn, user_id: int, ordered_module_ids: List[str]) -> bool:
    """Aktualisiert die Reihenfolge der Module für einen User.

    Weist jedem Modul einen sort_order-Wert basierend auf der Listenposition zu.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        ordered_module_ids: Liste von Modul-IDs in der gewünschten Reihenfolge.

    Returns:
        True bei Erfolg.
    """
    from ..modules.module_registry import update_user_module_order as _update_order
    module_orders = [
        {"module_id": module_id, "sort_order": (idx + 1) * 10}
        for idx, module_id in enumerate(ordered_module_ids)
    ]
    _update_order(conn, user_id, module_orders)
    return True


def initialize_user_modules(conn, user_id: int) -> bool:
    """Initialisiert UserModule-Einträge für alle aktivierten Module.

    Wird nach der User-Erstellung aufgerufen. Nutzt die default-Werte
    aus der modules-Tabelle.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.

    Returns:
        True bei Erfolg.
    """
    from ..modules.module_registry import initialize_user_modules as _init
    _init(conn, user_id)
    return True
