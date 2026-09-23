"""
Verbindungen: Status und Einstellungen aller persönlichen Quellen an einem Ort.

GET   /api/v2/connections              → Status je Quelle (ohne Geheimnisse)
PATCH /api/v2/connections/<module_id>  → einzelne Felder zusammenführen statt
                                          die ganze Modul-Konfiguration zu ersetzen
"""
from __future__ import annotations

from flask import Blueprint, g, request

from backend.api.helpers import error, require_auth, success
from backend.db import db_connection
from backend.modules.module_registry import get_user_module_config, save_user_module_config

connections_bp = Blueprint("connections", __name__)

# Fields a teacher may set per module through this endpoint.
_EDITABLE_FIELDS = {
    "webuntis": {"ical_url"},
    "itslearning": {"calendar_url", "username", "password"},
}
_URL_FIELDS = {"ical_url", "calendar_url"}


def _normalize_feed_url(value: str) -> str:
    """Accept webcal:// links (what calendar 'subscribe' buttons hand out) as https://."""
    value = value.strip()
    if value.lower().startswith("webcal://"):
        value = "https://" + value[len("webcal://"):]
    return value


def _validate_field(field: str, value: str) -> str | None:
    if field in _URL_FIELDS:
        if not value.lower().startswith("https://"):
            return "Bitte den vollständigen Link (https://…) einfügen."
        if len(value) > 2000:
            return "Der Link ist zu lang."
    elif len(value) > 300:
        return "Eingabe ist zu lang."
    return None


def _status_payload(configs: dict[str, dict]) -> dict:
    webuntis = configs.get("webuntis") or {}
    itslearning = configs.get("itslearning") or {}
    return {
        "webuntis": {"configured": bool(webuntis.get("ical_url"))},
        "itslearning": {
            "calendar": bool(itslearning.get("calendar_url")),
            "login": bool(itslearning.get("username") and itslearning.get("password")),
            "username": itslearning.get("username", ""),
        },
    }


@connections_bp.route("", methods=["GET"])
@require_auth
def get_connections():
    user_id = g.current_user.id
    try:
        with db_connection() as conn:
            configs = {mid: get_user_module_config(conn, user_id, mid) for mid in _EDITABLE_FIELDS}
    except Exception as exc:
        return error(f"Verbindungen konnten nicht geladen werden: {type(exc).__name__}", 500)
    return success({"connections": _status_payload(configs)})


@connections_bp.route("/<module_id>", methods=["PATCH"])
@require_auth
def patch_connection(module_id: str):
    allowed = _EDITABLE_FIELDS.get(module_id)
    if allowed is None:
        return error("Diese Verbindung kann hier nicht bearbeitet werden.", 404)

    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body:
        return error("Keine Änderungen übermittelt.", 422)
    unknown = set(body) - allowed
    if unknown:
        return error(f"Unbekannte Felder: {', '.join(sorted(unknown))}", 422)

    updates: dict[str, str | None] = {}
    for field, raw in body.items():
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            updates[field] = None  # remove the field
            continue
        if not isinstance(raw, str):
            return error(f"{field} muss ein Text sein.", 422)
        if field in _URL_FIELDS:
            value = _normalize_feed_url(raw)
        else:
            value = raw if field == "password" else raw.strip()
        problem = _validate_field(field, value)
        if problem:
            return error(problem, 422)
        updates[field] = value

    user_id = g.current_user.id
    try:
        with db_connection() as conn:
            config = dict(get_user_module_config(conn, user_id, module_id))
            for field, value in updates.items():
                if value is None:
                    config.pop(field, None)
                else:
                    config[field] = value
            save_user_module_config(conn, user_id, module_id, config)
            if not config:
                conn.execute(
                    "UPDATE user_modules SET is_configured = FALSE, updated_at = NOW() "
                    "WHERE user_id = %s AND module_id = %s",
                    (user_id, module_id),
                )
            configs = {mid: get_user_module_config(conn, user_id, mid) for mid in _EDITABLE_FIELDS}
    except Exception as exc:
        return error(f"Speichern fehlgeschlagen: {type(exc).__name__}", 500)
    return success({"connections": _status_payload(configs)})
