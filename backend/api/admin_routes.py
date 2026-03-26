"""
Admin-Endpunkte: User-Verwaltung, System-Einstellungen, Modul-Defaults.

Alle Routen erfordern Admin-Rolle (via @require_admin).
"""
import csv
import io
from datetime import date as _date
from flask import Blueprint, request, g, Response

from backend.db import db_connection
from backend.users.user_store import get_user_by_id, update_user, delete_user
from backend.users.user_service import create_teacher, regenerate_access_code
from backend.migrations import log_audit_event
from backend.modules.module_registry import (
    get_all_modules,
    initialize_user_modules,
    get_module_by_id,
    get_user_modules,
)
from backend.admin.admin_service import (
    get_user_overview,
    get_all_system_settings,
    set_system_setting,
    set_default_module_config,
    get_default_module_order,
    set_default_module_order,
    get_default_enabled_modules,
    set_default_enabled_modules,
    deactivate_user,
)
from backend.api.helpers import require_admin, success, error

admin_bp = Blueprint("admin", __name__)


# ── User Management ────────────────────────────────────────────────────────────

@admin_bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    """Alle User abrufen.

    Response: {"ok": true, "users": [...]}
    """
    try:
        with db_connection() as conn:
            users = get_user_overview(conn)
        return success({"users": users})
    except Exception as exc:
        return error(f"Fehler beim Laden der User: {type(exc).__name__}: {exc}", 500)


def _normalize_role_and_admin_request(role: str, is_admin_raw) -> tuple:
    """Normalizes role + is_admin from API request body (Phase 13 compatibility layer).

    Handles both legacy and new canonical form:
      - {"role": "admin"}                          → role='teacher', is_admin=True
      - {"role": "teacher", "is_admin": True}      → role='teacher', is_admin=True  (canonical)
      - {"role": "teacher", "is_admin": False}     → role='teacher', is_admin=False
      - {"role": "teacher"}                        → role='teacher', is_admin=False

    Args:
        role: Raw role string from request body.
        is_admin_raw: Raw is_admin value from request body (may be None if not sent).

    Returns:
        Tuple (normalized_role: str, normalized_is_admin: bool)
    """
    if role == "admin":
        # Legacy compatibility: treat role='admin' as is_admin=True, role='teacher'
        return ("teacher", True)
    is_admin = bool(is_admin_raw) if is_admin_raw is not None else False
    return (role, is_admin)


@admin_bp.route("/users", methods=["POST"])
@require_admin
def create_user():
    """User anlegen.

    Body: {"first_name": "...", "last_name": "...", "role": "teacher",
           "is_admin": false, "display_name": "..."}

    Legacy compat: role='admin' is normalized to role='teacher' + is_admin=True.
    Canonical new form: role='teacher' + is_admin=true/false.

    Response 201: {"ok": true, "user": {...}, "access_code": "..."}
    """
    body = request.get_json(silent=True) or {}
    first_name = str(body.get("first_name", "")).strip()
    last_name = str(body.get("last_name", "")).strip()
    # display_name is optional — if only display_name given, split it
    display_name = str(body.get("display_name", "")).strip()
    role_raw = str(body.get("role", "teacher")).strip() or "teacher"
    is_admin_raw = body.get("is_admin", None)

    # If first_name/last_name not given but display_name is, split display_name
    if not first_name and not last_name and display_name:
        parts = display_name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else parts[0]

    if not first_name:
        return error("Vorname ist erforderlich (first_name oder display_name)", 422)
    if not last_name:
        return error("Nachname ist erforderlich (last_name oder display_name)", 422)
    if role_raw not in ("teacher", "admin"):
        return error("Ungültige Rolle (teacher oder admin)", 422)

    # Normalize: role='admin' → role='teacher' + is_admin=True (Phase 13 compat)
    role, is_admin = _normalize_role_and_admin_request(role_raw, is_admin_raw)

    try:
        with db_connection() as conn:
            user, plain_code = create_teacher(conn, first_name, last_name, role, is_admin=is_admin)
            initialize_user_modules(conn, user.id)
            try:
                log_audit_event(
                    conn,
                    "teacher_created",
                    user_id=user.id,
                    ip_address=request.remote_addr,
                    details={"created_by": g.current_user.id},
                )
            except Exception:
                pass
        return success({"user": user.to_dict(), "access_code": plain_code}, 201)
    except Exception as exc:
        return error(f"Fehler beim Anlegen des Users: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/users/<int:user_id>", methods=["GET"])
@require_admin
def get_user(user_id: int):
    """Einzelnen User abrufen.

    Response: {"ok": true, "user": {...}}
    """
    try:
        with db_connection() as conn:
            user = get_user_by_id(conn, user_id)
        if not user:
            return error("User nicht gefunden", 404)
        return success({"user": user.to_dict()})
    except Exception as exc:
        return error(f"Fehler beim Laden des Users: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/users/<int:user_id>", methods=["PUT", "PATCH"])
@require_admin
def update_user_route(user_id: int):
    """User aktualisieren.

    Body: {"first_name"?: "...", "last_name"?: "...", "role"?: "...",
           "is_active"?: bool, "is_admin"?: bool}

    Legacy compat: passing role='admin' is normalized to role='teacher' + is_admin=True.
    Canonical new form: pass role='teacher' and is_admin=true/false independently.

    Response: {"ok": true, "user": {...}}
    """
    body = request.get_json(silent=True) or {}
    allowed_fields = {"first_name", "last_name", "role", "is_active", "is_admin"}
    updates = {}

    for field in allowed_fields:
        if field in body:
            val = body[field]
            if field in ("first_name", "last_name", "role"):
                val = str(val).strip()
            elif field in ("is_active", "is_admin"):
                val = bool(val)
            updates[field] = val

    if "role" in updates and updates["role"] not in ("teacher", "admin"):
        return error("Ungültige Rolle (teacher oder admin)", 422)

    # Compatibility: role='admin' in update → role='teacher' + is_admin=True
    # (handled in update_user store-layer, but also apply here for clarity)
    if "role" in updates and updates["role"] == "admin":
        updates["role"] = "teacher"
        updates.setdefault("is_admin", True)

    try:
        with db_connection() as conn:
            user = update_user(conn, user_id, **updates)
        if not user:
            return error("User nicht gefunden", 404)
        return success({"user": user.to_dict()})
    except Exception as exc:
        return error(f"Fehler beim Aktualisieren des Users: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@require_admin
def deactivate_user_route(user_id: int):
    """User deaktivieren (Soft-Delete).

    Setzt is_active=False und invalidiert Sessions.
    Response: {"ok": true}
    """
    if g.current_user.id == user_id:
        return error("Eigenes Konto kann nicht deaktiviert werden", 400)
    try:
        with db_connection() as conn:
            deactivated = deactivate_user(conn, user_id)
            if deactivated:
                try:
                    log_audit_event(
                        conn,
                        "teacher_deactivated",
                        user_id=user_id,
                        ip_address=request.remote_addr,
                        details={"deactivated_by": g.current_user.id},
                    )
                except Exception:
                    pass
        if not deactivated:
            return error("User nicht gefunden", 404)
        return success()
    except Exception as exc:
        return error(f"Fehler beim Deaktivieren des Users: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/users/<int:user_id>/rotate-code", methods=["POST"])
@admin_bp.route("/users/<int:user_id>/regenerate-code", methods=["POST"])
@require_admin
def regenerate_code(user_id: int):
    """Zugangscode neu generieren.

    Routen-Aliases:
      POST /api/v2/admin/users/<id>/rotate-code  (dokumentierter Name)
      POST /api/v2/admin/users/<id>/regenerate-code  (Legacy-Alias)

    Response: {"ok": true, "access_code": "..."}
    """
    try:
        with db_connection() as conn:
            plain_code = regenerate_access_code(conn, user_id)
            if plain_code is not None:
                try:
                    log_audit_event(
                        conn,
                        "code_rotated",
                        user_id=user_id,
                        ip_address=request.remote_addr,
                        details={"rotated_by": g.current_user.id},
                    )
                except Exception:
                    pass
        if plain_code is None:
            return error("User nicht gefunden", 404)
        return success({"access_code": plain_code})
    except Exception as exc:
        return error(f"Fehler beim Generieren des Codes: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_admin
def delete_user_route(user_id: int):
    """User löschen (hard-delete).

    Für Soft-Delete: POST /users/<id>/deactivate verwenden.
    Response: {"ok": true}
    """
    if g.current_user.id == user_id:
        return error("Eigenes Konto kann nicht gelöscht werden", 400)
    try:
        with db_connection() as conn:
            deleted = delete_user(conn, user_id)
        if not deleted:
            return error("User nicht gefunden", 404)
        return success()
    except Exception as exc:
        return error(f"Fehler beim Löschen des Users: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/users/<int:user_id>/modules", methods=["GET"])
@require_admin
def get_user_modules_route(user_id: int):
    """Modul-Status eines Users abrufen.

    Response: {"ok": true, "modules": [{module_id, enabled, order, configured, ...}]}
    """
    try:
        with db_connection() as conn:
            user = get_user_by_id(conn, user_id)
            if not user:
                return error("User nicht gefunden", 404)
            user_modules = get_user_modules(conn, user_id)
            result = []
            for um in sorted(user_modules, key=lambda m: m.sort_order):
                module = get_module_by_id(conn, um.module_id)
                result.append({
                    "module_id": um.module_id,
                    "display_name": module.display_name if module else um.module_id,
                    "module_type": module.module_type if module else "unknown",
                    "enabled": um.is_visible,
                    "is_visible": um.is_visible,
                    "order": um.sort_order,
                    "sort_order": um.sort_order,
                    "configured": um.is_configured,
                    "is_configured": um.is_configured,
                    "requires_config": module.requires_config if module else False,
                })
        return success({"modules": result})
    except Exception as exc:
        return error(f"Fehler beim Laden der User-Module: {type(exc).__name__}: {exc}", 500)


# ── Module Defaults ────────────────────────────────────────────────────────────

@admin_bp.route("/modules/defaults", methods=["GET"])
@require_admin
def get_module_defaults():
    """Standard-Modul-Konfiguration abrufen.

    Response: {"ok": true, "default_order": [...], "default_enabled": [...]}
    """
    try:
        with db_connection() as conn:
            default_order = get_default_module_order(conn)
            default_enabled = get_default_enabled_modules(conn)
        return success({
            "default_order": default_order,
            "default_enabled": default_enabled,
        })
    except Exception as exc:
        return error(f"Fehler beim Laden der Modul-Defaults: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/modules/defaults", methods=["PUT"])
@require_admin
def put_module_defaults():
    """Standard-Modul-Konfiguration setzen.

    Body: {"default_order": ["webuntis", ...], "default_enabled": ["webuntis", ...]}
    Response: {"ok": true}
    """
    body = request.get_json(silent=True) or {}
    default_order = body.get("default_order")
    default_enabled = body.get("default_enabled")

    if default_order is None and default_enabled is None:
        return error("default_order oder default_enabled erforderlich", 422)

    try:
        with db_connection() as conn:
            if default_order is not None:
                if not isinstance(default_order, list):
                    return error("default_order muss eine Liste sein", 422)
                set_default_module_order(conn, [str(m) for m in default_order])
            if default_enabled is not None:
                if not isinstance(default_enabled, list):
                    return error("default_enabled muss eine Liste sein", 422)
                set_default_enabled_modules(conn, [str(m) for m in default_enabled])
        return success()
    except Exception as exc:
        return error(f"Fehler beim Setzen der Modul-Defaults: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/modules", methods=["GET"])
@require_admin
def list_modules():
    """Alle Module + default config abrufen.

    Response: {"ok": true, "modules": [...]}
    """
    try:
        with db_connection() as conn:
            modules = get_all_modules(conn)
        return success({"modules": [m.to_dict() for m in modules]})
    except Exception as exc:
        return error(f"Fehler beim Laden der Module: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/modules/<module_id>", methods=["PUT"])
@require_admin
def update_module(module_id: str):
    """Modul-Defaults anpassen.

    Body: {"default_visible"?: bool, "default_order"?: int, "is_enabled"?: bool}
    Response: {"ok": true}
    """
    body = request.get_json(silent=True) or {}

    default_visible = body.get("default_visible")
    default_order = body.get("default_order")
    is_enabled = body.get("is_enabled")

    try:
        with db_connection() as conn:
            # Handle is_enabled separately (not in set_default_module_config)
            if is_enabled is not None:
                conn.execute(
                    "UPDATE modules SET is_enabled = %s WHERE id = %s",
                    (bool(is_enabled), module_id),
                )

            # Handle default_visible and default_order
            kwargs = {}
            if default_visible is not None:
                kwargs["default_visible"] = bool(default_visible)
            if default_order is not None:
                kwargs["default_order"] = int(default_order)

            if kwargs or is_enabled is not None:
                if kwargs:
                    found = set_default_module_config(conn, module_id, **kwargs)
                    if not found:
                        return error("Modul nicht gefunden", 404)
                else:
                    row = conn.execute(
                        "SELECT 1 FROM modules WHERE id = %s", (module_id,)
                    ).fetchone()
                    if not row:
                        return error("Modul nicht gefunden", 404)
            else:
                return error("Keine Felder zum Aktualisieren angegeben", 422)

        return success()
    except Exception as exc:
        return error(f"Fehler beim Aktualisieren des Moduls: {type(exc).__name__}: {exc}", 500)


# ── System Settings ────────────────────────────────────────────────────────────

@admin_bp.route("/settings", methods=["GET"])
@require_admin
def get_settings():
    """Alle System-Settings abrufen.

    Response: {"ok": true, "settings": {...}}
    """
    try:
        with db_connection() as conn:
            settings = get_all_system_settings(conn)
        return success({"settings": settings})
    except Exception as exc:
        return error(f"Fehler beim Laden der Einstellungen: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/settings", methods=["PUT"])
@require_admin
def put_settings():
    """System-Setting setzen (Body mit key+value).

    Body: {"key": "...", "value": ...}
    Response: {"ok": true}
    """
    body = request.get_json(silent=True) or {}
    key = body.get("key")
    if not key or not isinstance(key, str) or not key.strip():
        return error("key ist erforderlich", 422)
    if "value" not in body:
        return error("value ist erforderlich", 422)

    key = key.strip()
    value = body["value"]

    try:
        with db_connection() as conn:
            set_system_setting(conn, key, value)
        return success()
    except Exception as exc:
        return error(f"Fehler beim Speichern der Einstellung: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/settings/<key>", methods=["PUT"])
@require_admin
def put_setting_by_key(key: str):
    """Einzelne System-Einstellung per URL-Key setzen.

    Body: {"value": ...}
    Response: {"ok": true}
    """
    body = request.get_json(silent=True) or {}
    if "value" not in body:
        return error("value ist erforderlich", 422)
    value = body["value"]

    try:
        with db_connection() as conn:
            set_system_setting(conn, key, value)
        return success()
    except Exception as exc:
        return error(f"Fehler beim Speichern der Einstellung: {type(exc).__name__}: {exc}", 500)


# ── Audit Log ─────────────────────────────────────────────────────────────────

def _build_audit_query(event_type, date_from, date_to):
    """Helper: build WHERE clause + params for audit_log queries.

    Returns (where_clause, params_list).
    """
    conditions = []
    params = []
    if event_type:
        conditions.append("al.event_type = %s")
        params.append(event_type)
    if date_from:
        conditions.append("al.created_at >= %s::date")
        params.append(date_from)
    if date_to:
        conditions.append("al.created_at < (%s::date + INTERVAL '1 day')")
        params.append(date_to)
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where_clause, params


@admin_bp.route("/audit-log", methods=["GET"])
@require_admin
def get_audit_log():
    """Audit-Log-Ereignisse abrufen (paginiert, filterbar).

    Query-Parameter:
      limit      (int, default 50, max 200)
      offset     (int, default 0)
      event_type (str, optional)
      date_from  (ISO date string, e.g. 2024-03-01, optional)
      date_to    (ISO date string, e.g. 2024-03-31, optional)

    Response: {"ok": true, "events": [...], "total": int, "limit": int, "offset": int}
    """
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = int(request.args.get("offset", 0))
    except (ValueError, TypeError):
        return error("limit und offset müssen Ganzzahlen sein", 422)

    event_type = request.args.get("event_type", "").strip() or None
    date_from = request.args.get("date_from", "").strip() or None
    date_to = request.args.get("date_to", "").strip() or None

    where_clause, base_params = _build_audit_query(event_type, date_from, date_to)

    try:
        with db_connection() as conn:
            count_sql = f"SELECT COUNT(*) FROM audit_log al {where_clause}"
            total_row = conn.execute(count_sql, base_params).fetchone()

            rows_sql = f"""
                SELECT al.id, al.event_type, al.user_id,
                       u.first_name || ' ' || u.last_name AS user_name,
                       al.ip_address, al.details, al.created_at
                FROM audit_log al
                LEFT JOIN users u ON al.user_id = u.id
                {where_clause}
                ORDER BY al.created_at DESC
                LIMIT %s OFFSET %s
            """
            rows = conn.execute(rows_sql, base_params + [limit, offset]).fetchall()

        total = total_row[0] if total_row else 0
        events = []
        for row in rows:
            events.append({
                "id": row[0],
                "event_type": row[1],
                "user_id": row[2],
                "user_name": row[3],
                "ip_address": row[4],
                "details": row[5] or {},
                "created_at": row[6].isoformat() if row[6] else None,
            })

        return success({
            "events": events,
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    except Exception as exc:
        return error(f"Fehler beim Laden des Audit-Logs: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/audit-log/export.csv", methods=["GET"])
@require_admin
def export_audit_log_csv():
    """Audit-Log als CSV exportieren.

    Query-Parameter: dieselben wie GET /audit-log (limit bis 5000, date_from, date_to, event_type).

    Response: CSV-Datei mit Content-Disposition: attachment.
    """
    try:
        limit = min(int(request.args.get("limit", 5000)), 5000)
        offset = int(request.args.get("offset", 0))
    except (ValueError, TypeError):
        limit = 5000
        offset = 0

    event_type = request.args.get("event_type", "").strip() or None
    date_from = request.args.get("date_from", "").strip() or None
    date_to = request.args.get("date_to", "").strip() or None

    where_clause, base_params = _build_audit_query(event_type, date_from, date_to)

    try:
        with db_connection() as conn:
            rows_sql = f"""
                SELECT al.id, al.event_type, al.user_id,
                       u.first_name || ' ' || u.last_name AS user_name,
                       al.ip_address, al.details, al.created_at
                FROM audit_log al
                LEFT JOIN users u ON al.user_id = u.id
                {where_clause}
                ORDER BY al.created_at DESC
                LIMIT %s OFFSET %s
            """
            rows = conn.execute(rows_sql, base_params + [limit, offset]).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Zeitpunkt", "Ereignis", "Benutzer", "IP", "Details"])
        for row in rows:
            created_at = row[6].isoformat() if row[6] else ""
            details_str = str(row[5] or {})
            writer.writerow([
                created_at,
                row[1] or "",
                row[3] or "",
                row[4] or "",
                details_str,
            ])

        today = _date.today().isoformat()
        filename = f"audit-log-{today}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        return error(f"Fehler beim Exportieren des Audit-Logs: {type(exc).__name__}: {exc}", 500)


# ── Maintenance ────────────────────────────────────────────────────────────────

@admin_bp.route("/maintenance/null-prefix-users", methods=["GET"])
@require_admin
def get_null_prefix_users():
    """Benutzer mit fehlendem code_prefix abrufen.

    Diese Benutzer wurden vor Phase 9c angelegt und nutzen den langsameren
    Authentifizierungspfad (vollständiger Tabellen-Scan + argon2 für alle User).
    code_prefix kann nicht rückwirkend berechnet werden — nur Code-Rotation hilft.

    Response: {"ok": true, "users": [...], "count": int}
    """
    try:
        with db_connection() as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.first_name || ' ' || u.last_name AS display_name,
                       u.role, u.created_at
                FROM users u
                JOIN user_access_codes uac ON u.id = uac.user_id
                WHERE uac.code_prefix IS NULL
                  AND u.is_active = TRUE
                ORDER BY u.last_name, u.first_name
                """
            ).fetchall()

        users = [
            {
                "user_id": row[0],
                "display_name": row[1],
                "role": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
            }
            for row in rows
        ]
        return success({"users": users, "count": len(users)})
    except Exception as exc:
        return error(f"Fehler beim Laden der Benutzer ohne code_prefix: {type(exc).__name__}: {exc}", 500)


@admin_bp.route("/maintenance/cleanup-sessions", methods=["POST"])
@require_admin
def cleanup_sessions():
    """Abgelaufene Sessions löschen.

    Response: {"ok": true, "deleted": int}
    """
    try:
        with db_connection() as conn:
            from backend.auth.session import cleanup_expired_sessions
            count = cleanup_expired_sessions(conn)
        return success({"deleted": count})
    except Exception as exc:
        return error(f"Fehler beim Bereinigen der Sessions: {type(exc).__name__}: {exc}", 500)
