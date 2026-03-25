"""
Modul-Daten-Endpunkte: liefert die eigentlichen Modul-Inhalte.
Enthält auch CRUD-Endpunkte für Modul-Konfigurationen und
öffentliche Registry-Metadaten (kein Auth erforderlich).
"""
from datetime import datetime, timezone
from flask import Blueprint, request, g

from backend.db import db_connection
from backend.modules.module_registry import (
    get_all_modules,
    get_user_module_config,
    save_user_module_config,
    get_module_by_id,
    get_default_module_set,
)
from backend.admin.admin_service import get_system_setting
from backend.api.helpers import require_auth, success, error, mask_config
from backend.users.user_service import (
    get_grades,
    upsert_grade,
    delete_grade,
    get_notes,
    upsert_note,
    delete_note,
)

module_bp = Blueprint("modules", __name__)


def _mask_config(config: dict) -> dict:
    """Alias for shared mask_config helper (backward compat)."""
    return mask_config(config)


# ── Public Module Registry (no auth required) ─────────────────────────────────

@module_bp.route("", methods=["GET"])
@module_bp.route("/", methods=["GET"])
def list_all_modules():
    """Alle verfügbaren Module abrufen (öffentlich, kein Auth).

    Response: {"ok": true, "modules": [...]}
    """
    try:
        with db_connection() as conn:
            modules = get_all_modules(conn)
        return success({"modules": [m.to_dict() for m in modules]})
    except Exception as exc:
        return error(f"Fehler beim Laden der Module: {type(exc).__name__}: {exc}", 500)


@module_bp.route("/defaults", methods=["GET"])
def list_default_modules():
    """Standard-aktivierte Module abrufen (öffentlich, kein Auth).

    Gibt Module zurück bei denen default_enabled=True (is_enabled AND default_visible),
    sortiert nach default_order.

    Response: {"ok": true, "modules": [...]}
    """
    try:
        with db_connection() as conn:
            modules = get_default_module_set(conn)
        return success({"modules": [m.to_dict() for m in modules]})
    except Exception as exc:
        return error(f"Fehler beim Laden der Default-Module: {type(exc).__name__}: {exc}", 500)


# ── Module Config CRUD ────────────────────────────────────────────────────────

@module_bp.route("/<module_id>/config", methods=["GET"])
@require_auth
def get_module_config_route(module_id: str):
    """Konfiguration eines Moduls abrufen (sensible Felder maskiert).

    Response: {"ok": true, "config": {...}}
    """
    try:
        with db_connection() as conn:
            config = get_user_module_config(conn, g.current_user.id, module_id)
        return success({"config": _mask_config(config)})
    except Exception as exc:
        return error(f"Fehler beim Laden der Konfiguration: {type(exc).__name__}: {exc}", 500)


@module_bp.route("/<module_id>/config", methods=["PUT"])
@require_auth
def put_module_config_route(module_id: str):
    """Konfiguration eines Moduls speichern.

    Nur für 'individual'-Module erlaubt (nicht für 'central' oder 'local').
    Body: {...} (beliebiges JSON-Objekt)
    Response: {"ok": true}
    """
    config_data = request.get_json(silent=True)
    if config_data is None:
        config_data = {}

    if not isinstance(config_data, dict):
        return error("Body muss ein JSON-Objekt sein", 422)

    try:
        with db_connection() as conn:
            module = get_module_by_id(conn, module_id)
            if module is None:
                return error("Modul nicht gefunden", 404)
            if module.module_type in ("central", "local"):
                return error(
                    f"Modul '{module_id}' ist ein {module.module_type}-Modul "
                    "und kann nicht vom User konfiguriert werden",
                    403,
                )
            save_user_module_config(conn, g.current_user.id, module_id, config_data)
        return success()
    except Exception as exc:
        return error(f"Fehler beim Speichern der Konfiguration: {type(exc).__name__}: {exc}", 500)


@module_bp.route("/<module_id>/config", methods=["DELETE"])
@require_auth
def delete_module_config_route(module_id: str):
    """Konfiguration eines Moduls zurücksetzen (leeres dict speichern).

    Response: {"ok": true}
    """
    try:
        with db_connection() as conn:
            # Reset to empty config and mark module as unconfigured
            save_user_module_config(conn, g.current_user.id, module_id, {})
            # Unmark as configured
            conn.execute(
                """
                UPDATE user_modules
                SET is_configured = FALSE, updated_at = NOW()
                WHERE user_id = %s AND module_id = %s
                """,
                (g.current_user.id, module_id),
            )
        return success()
    except Exception as exc:
        return error(f"Fehler beim Löschen der Konfiguration: {type(exc).__name__}: {exc}", 500)


@module_bp.route("/itslearning/data", methods=["GET"])
@require_auth
def itslearning_data():
    """itslearning-Daten abrufen.

    Response: {"ok": true, "data": {...}}
    """
    try:
        with db_connection() as conn:
            config = get_user_module_config(conn, g.current_user.id, "itslearning")
    except Exception as exc:
        return error(f"Fehler beim Laden der Konfiguration: {type(exc).__name__}: {exc}", 500)

    try:
        from backend.config import ItslearningSettings
        from backend.itslearning_adapter import fetch_itslearning_sync

        settings = ItslearningSettings(
            base_url=config.get("base_url", "https://berlin.itslearning.com"),
            username=config.get("username", ""),
            password=config.get("password", ""),
            max_updates=int(config.get("max_updates", 6)),
        )
        now = datetime.now(timezone.utc)
        data = fetch_itslearning_sync(settings, now)
        return success({"data": data})
    except Exception as exc:
        return success({"data": None, "error": f"{type(exc).__name__}: {exc}"})


@module_bp.route("/webuntis/data", methods=["GET"])
@require_auth
def webuntis_data():
    """WebUntis-Daten abrufen.

    Response: {"ok": true, "data": {...}}
    """
    try:
        with db_connection() as conn:
            config = get_user_module_config(conn, g.current_user.id, "webuntis")
    except Exception as exc:
        return error(f"Fehler beim Laden der Konfiguration: {type(exc).__name__}: {exc}", 500)

    try:
        from backend.webuntis_adapter import fetch_webuntis_sync

        base_url = config.get("base_url", "")
        ical_url = config.get("ical_url", "")
        now = datetime.now(timezone.utc)
        data = fetch_webuntis_sync(base_url, ical_url, now)
        return success({"data": data})
    except Exception as exc:
        return success({"data": None, "error": f"{type(exc).__name__}: {exc}"})


@module_bp.route("/nextcloud/data", methods=["GET"])
@require_auth
def nextcloud_data():
    """Nextcloud-Daten abrufen.

    Response: {"ok": true, "data": {...}}
    """
    try:
        with db_connection() as conn:
            config = get_user_module_config(conn, g.current_user.id, "nextcloud")
    except Exception as exc:
        return error(f"Fehler beim Laden der Konfiguration: {type(exc).__name__}: {exc}", 500)

    try:
        from backend.nextcloud_adapter import fetch_nextcloud_sync

        data = fetch_nextcloud_sync(config)
        return success({"data": data})
    except Exception as exc:
        return success({"data": None, "error": f"{type(exc).__name__}: {exc}"})


@module_bp.route("/orgaplan/data", methods=["GET"])
@require_auth
def orgaplan_data():
    """Orgaplan-Daten aus System-Settings abrufen.

    Response: {"ok": true, "data": {"url": ..., "pdf_url": ...}}
    """
    try:
        with db_connection() as conn:
            orgaplan_url = get_system_setting(conn, "orgaplan_url", None)
            pdf_url = get_system_setting(conn, "orgaplan_pdf_url", None)

        return success({"data": {
            "url": orgaplan_url,
            "pdf_url": pdf_url,
        }})
    except Exception as exc:
        return success({"data": None, "error": f"{type(exc).__name__}: {exc}"})


@module_bp.route("/klassenarbeitsplan/data", methods=["GET"])
@require_auth
def klassenarbeitsplan_data():
    """Klassenarbeitsplan-Daten abrufen.

    Response: {"ok": true, "data": {"url": ..., "structured_rows": [...]}}
    """
    try:
        with db_connection() as conn:
            url = get_system_setting(conn, "klassenarbeitsplan_url", None)

        structured_rows = []
        try:
            from backend.plan_digest import load_classwork_plan
            from pathlib import Path
            import os

            local_path = Path(__file__).resolve().parent.parent.parent / "data" / "classwork-plan-local.xlsx"
            if local_path.exists():
                structured_rows = load_classwork_plan(str(local_path))
        except Exception:
            pass

        return success({"data": {
            "url": url,
            "structured_rows": structured_rows,
        }})
    except Exception as exc:
        return success({"data": None, "error": f"{type(exc).__name__}: {exc}"})


# ── Noten / Grades v2 (Phase 9b) ─────────────────────────────────────────────

@module_bp.route("/noten/data", methods=["GET"])
@require_auth
def get_noten_data():
    """Noten und Klassen-Notizen für den aktuellen User abrufen.

    Response: {"ok": true, "grades": [...], "notes": [...]}
    """
    user_id = g.current_user.id
    try:
        with db_connection() as conn:
            grades = get_grades(conn, user_id)
            notes = get_notes(conn, user_id)
        return success({"grades": grades, "notes": notes})
    except Exception as exc:
        return error(f"Fehler beim Laden der Noten-Daten: {type(exc).__name__}: {exc}", 500)


@module_bp.route("/noten/grades", methods=["POST"])
@require_auth
def create_or_update_grade():
    """Noten-Eintrag erstellen oder aktualisieren.

    Body: {"class_name": "5a", "subject": "Mathe", "grade_value": "2+",
           "grade_date": "2024-03-01", "note": "", "id": null}
    Response: {"ok": true, "grade": {...}}
    """
    user_id = g.current_user.id
    body = request.get_json(silent=True) or {}

    class_name = str(body.get("class_name", "")).strip()
    subject = str(body.get("subject", "")).strip()
    grade_value = str(body.get("grade_value", "")).strip()
    grade_date = body.get("grade_date") or None
    note = str(body.get("note", "")).strip()
    grade_id = body.get("id") or None

    if not class_name:
        return error("class_name ist erforderlich", 422)
    if not grade_value:
        return error("grade_value ist erforderlich", 422)

    try:
        with db_connection() as conn:
            grade = upsert_grade(
                conn,
                user_id=user_id,
                class_name=class_name,
                subject=subject,
                grade_value=grade_value,
                grade_date=grade_date,
                note=note,
                grade_id=int(grade_id) if grade_id is not None else None,
            )
        if not grade:
            return error("Noten-Eintrag nicht gefunden oder keine Berechtigung", 404)
        return success({"grade": grade})
    except Exception as exc:
        return error(f"Fehler beim Speichern des Noten-Eintrags: {type(exc).__name__}: {exc}", 500)


@module_bp.route("/noten/grades/<int:grade_id>", methods=["DELETE"])
@require_auth
def delete_grade_entry(grade_id: int):
    """Noten-Eintrag löschen.

    Response: {"ok": true}
    """
    user_id = g.current_user.id
    try:
        with db_connection() as conn:
            deleted = delete_grade(conn, user_id=user_id, grade_id=grade_id)
        if not deleted:
            return error("Noten-Eintrag nicht gefunden oder keine Berechtigung", 404)
        return success()
    except Exception as exc:
        return error(f"Fehler beim Löschen des Noten-Eintrags: {type(exc).__name__}: {exc}", 500)


@module_bp.route("/noten/notes", methods=["GET"])
@require_auth
def get_notes_data():
    """Klassen-Notizen für den aktuellen User abrufen.

    Response: {"ok": true, "notes": [...]}
    """
    user_id = g.current_user.id
    try:
        with db_connection() as conn:
            notes = get_notes(conn, user_id)
        return success({"notes": notes})
    except Exception as exc:
        return error(f"Fehler beim Laden der Notizen: {type(exc).__name__}: {exc}", 500)


@module_bp.route("/noten/notes", methods=["POST"])
@require_auth
def upsert_note_entry():
    """Klassen-Notiz erstellen oder aktualisieren.

    Body: {"class_name": "5a", "note_text": "..."}
    Response: {"ok": true, "note": {...}}
    """
    user_id = g.current_user.id
    body = request.get_json(silent=True) or {}

    class_name = str(body.get("class_name", "")).strip()
    note_text = str(body.get("note_text", "")).strip()

    if not class_name:
        return error("class_name ist erforderlich", 422)

    try:
        with db_connection() as conn:
            note = upsert_note(conn, user_id=user_id, class_name=class_name, note_text=note_text)
        return success({"note": note})
    except Exception as exc:
        return error(f"Fehler beim Speichern der Notiz: {type(exc).__name__}: {exc}", 500)


@module_bp.route("/noten/notes/<path:class_name>", methods=["DELETE"])
@require_auth
def delete_note_entry(class_name: str):
    """Klassen-Notiz löschen.

    Response: {"ok": true}
    """
    user_id = g.current_user.id
    try:
        with db_connection() as conn:
            deleted = delete_note(conn, user_id=user_id, class_name=class_name)
        if not deleted:
            return error("Notiz nicht gefunden", 404)
        return success()
    except Exception as exc:
        return error(f"Fehler beim Löschen der Notiz: {type(exc).__name__}: {exc}", 500)
