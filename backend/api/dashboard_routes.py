"""
Dashboard-Endpunkte für Lehrkräfte: Modules-Layout, Daten.
"""
from flask import Blueprint, request, g

from backend.db import db_connection
from backend.modules.module_registry import (
    get_user_modules,
    get_module_by_id,
    update_user_module_visibility,
    update_user_module_order,
    get_user_module_config,
    save_user_module_config,
)
from backend.admin.admin_service import get_all_system_settings, get_system_setting, set_system_setting
from backend.api.helpers import require_auth, success, error, mask_config

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("", methods=["GET"])
@require_auth
def get_dashboard():
    """Aggregiertes Dashboard-Payload: User-Info + Module-Layout + System-Settings.

    Response: {"ok": true, "user": {...}, "modules": [...], "onboarding_complete": bool}
    """
    try:
        with db_connection() as conn:
            user_modules = get_user_modules(conn, g.current_user.id)
            user_modules.sort(key=lambda um: um.sort_order)

            modules_out = []
            for um in user_modules:
                module = get_module_by_id(conn, um.module_id)
                if module and module.is_enabled:
                    modules_out.append({
                        "module_id": um.module_id,
                        "name": module.display_name,
                        "display_name": module.display_name,
                        "module_type": module.module_type,
                        "enabled": um.is_visible,
                        "is_visible": um.is_visible,
                        "order": um.sort_order,
                        "sort_order": um.sort_order,
                        "configured": um.is_configured,
                        "is_configured": um.is_configured,
                        "requires_config": module.requires_config,
                    })

            onboarding_flag = get_system_setting(
                conn, f"onboarding_done_{g.current_user.id}", None
            )
            onboarding_complete = bool(onboarding_flag and onboarding_flag.get("done"))

        user_dict = g.current_user.to_dict()
        # Expose display_name as alias for full_name for frontend convenience
        user_dict["display_name"] = user_dict.get("full_name", "")

        return success({
            "user": user_dict,
            "modules": modules_out,
            "onboarding_complete": onboarding_complete,
        })
    except Exception as exc:
        return error(f"Fehler beim Laden des Dashboards: {type(exc).__name__}: {exc}", 500)


@dashboard_bp.route("/layout", methods=["GET"])
@require_auth
def get_layout():
    """User's Dashboard-Layout abrufen.

    Response: {"ok": true, "modules": [...]}
    """
    try:
        with db_connection() as conn:
            user_modules = get_user_modules(conn, g.current_user.id)
            # Sortiere nach sort_order
            user_modules.sort(key=lambda um: um.sort_order)

            result = []
            for um in user_modules:
                module = get_module_by_id(conn, um.module_id)
                if module:
                    result.append({
                        "module_id": um.module_id,
                        "is_visible": um.is_visible,
                        "sort_order": um.sort_order,
                        "is_configured": um.is_configured,
                        "display_name": module.display_name,
                        "module_type": module.module_type,
                        "requires_config": module.requires_config,
                    })

        return success({"modules": result})
    except Exception as exc:
        return error(f"Fehler beim Laden des Layouts: {type(exc).__name__}: {exc}", 500)


@dashboard_bp.route("/layout", methods=["PUT"])
@require_auth
def update_layout():
    """Reihenfolge und Sichtbarkeit der Module anpassen.

    Body: {"modules": [{"module_id": "itslearning", "sort_order": 1, "order": 1, "enabled": true}, ...]}
    Felder 'sort_order' und 'order' sind Aliase; 'enabled' und 'is_visible' ebenfalls.
    Response: {"ok": true}
    """
    from backend.modules.module_registry import update_user_module as _update_module

    body = request.get_json(silent=True) or {}
    modules = body.get("modules", [])

    if not isinstance(modules, list):
        return error("modules muss eine Liste sein", 422)

    module_orders = []
    visibility_updates = []

    for item in modules:
        if not isinstance(item, dict):
            continue
        module_id = item.get("module_id")
        if not module_id:
            continue
        module_id = str(module_id)

        # Accept both sort_order and order as aliases
        sort_order = item.get("sort_order") if item.get("sort_order") is not None else item.get("order")
        if sort_order is not None:
            module_orders.append({"module_id": module_id, "sort_order": int(sort_order)})

        # Accept both enabled and is_visible as aliases
        enabled = item.get("enabled") if item.get("enabled") is not None else item.get("is_visible")
        if enabled is not None:
            visibility_updates.append({"module_id": module_id, "is_visible": bool(enabled)})

    if not module_orders and not visibility_updates:
        return error("Keine gültigen Modul-Einträge angegeben", 422)

    try:
        with db_connection() as conn:
            if module_orders:
                update_user_module_order(conn, g.current_user.id, module_orders)
            for vu in visibility_updates:
                _update_module(conn, g.current_user.id, vu["module_id"], is_visible=vu["is_visible"])
        return success()
    except Exception as exc:
        return error(f"Fehler beim Aktualisieren der Reihenfolge: {type(exc).__name__}: {exc}", 500)


@dashboard_bp.route("/layout/<module_id>/visibility", methods=["PUT"])
@require_auth
def update_visibility(module_id: str):
    """Sichtbarkeit eines Moduls umschalten.

    Body: {"is_visible": bool}
    Response: {"ok": true}
    """
    body = request.get_json(silent=True) or {}
    if "is_visible" not in body:
        return error("is_visible ist erforderlich", 422)

    is_visible = bool(body["is_visible"])

    try:
        with db_connection() as conn:
            updated = update_user_module_visibility(conn, g.current_user.id, module_id, is_visible)
        if not updated:
            return error("Modul nicht gefunden", 404)
        return success()
    except Exception as exc:
        return error(f"Fehler beim Aktualisieren der Sichtbarkeit: {type(exc).__name__}: {exc}", 500)


@dashboard_bp.route("/module-config/<module_id>", methods=["GET"])
@require_auth
def get_module_config(module_id: str):
    """Konfiguration eines Moduls abrufen (sensible Felder maskiert).

    Response: {"ok": true, "config": {...}}
    """
    try:
        with db_connection() as conn:
            config = get_user_module_config(conn, g.current_user.id, module_id)
        return success({"config": mask_config(config)})
    except Exception as exc:
        return error(f"Fehler beim Laden der Konfiguration: {type(exc).__name__}: {exc}", 500)


@dashboard_bp.route("/module-config/<module_id>", methods=["PUT"])
@require_auth
def save_module_config(module_id: str):
    """Konfiguration eines Moduls speichern.

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
            save_user_module_config(conn, g.current_user.id, module_id, config_data)
        return success()
    except Exception as exc:
        return error(f"Fehler beim Speichern der Konfiguration: {type(exc).__name__}: {exc}", 500)


@dashboard_bp.route("/onboarding-status", methods=["GET"])
@require_auth
def onboarding_status():
    """Prüft ob Onboarding nötig ist.

    Response: {"ok": true, "needs_onboarding": bool, "unconfigured_modules": [...]}
    """
    try:
        with db_connection() as conn:
            user_modules = get_user_modules(conn, g.current_user.id)
            unconfigured = []
            for um in user_modules:
                module = get_module_by_id(conn, um.module_id)
                if module and module.requires_config and not um.is_configured:
                    unconfigured.append(um.module_id)

            onboarding_flag = get_system_setting(
                conn, f"onboarding_done_{g.current_user.id}", None
            )
            already_completed = bool(onboarding_flag and onboarding_flag.get("done"))

        needs_onboarding = len(unconfigured) > 0 and not already_completed
        return success({
            "needs_onboarding": needs_onboarding,
            "unconfigured_modules": unconfigured,
            "onboarding_complete": already_completed,
        })
    except Exception as exc:
        return error(f"Fehler beim Laden des Onboarding-Status: {type(exc).__name__}: {exc}", 500)


@dashboard_bp.route("/onboarding/complete", methods=["POST"])
@require_auth
def complete_onboarding():
    """Markiert das Onboarding als abgeschlossen.

    Response: {"ok": true}
    """
    try:
        with db_connection() as conn:
            set_system_setting(
                conn,
                f"onboarding_done_{g.current_user.id}",
                {"done": True},
            )
        return success()
    except Exception as exc:
        return error(f"Fehler beim Abschließen des Onboardings: {type(exc).__name__}: {exc}", 500)
