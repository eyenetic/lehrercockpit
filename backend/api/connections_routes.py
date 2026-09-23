"""
Verbindungen: Status und Einstellungen aller persönlichen Quellen an einem Ort.

GET    /api/v2/connections                   → Status je Quelle (ohne Geheimnisse)
PATCH  /api/v2/connections/<module_id>       → einzelne Felder zusammenführen statt
                                               die ganze Modul-Konfiguration zu ersetzen
POST   /api/v2/connections/nextcloud/start   → Nextcloud Login Flow v2 starten
POST   /api/v2/connections/nextcloud/poll    → prüfen, ob die Anmeldung abgeschlossen ist
DELETE /api/v2/connections/nextcloud         → App-Passwort widerrufen und trennen
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, g, request

from backend import nextcloud_module
from backend.admin.admin_service import get_system_setting
from backend.api.helpers import error, require_auth, success
from backend.db import db_connection
from backend.http_utils import UnsafeUrlError
from backend.migrations import log_audit_event
from backend.modules.module_registry import get_user_module_config, save_user_module_config
from backend.nextcloud_client import NextcloudError, poll_login_flow, revoke_app_password, start_login_flow

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


_STATUS_MODULES = ("webuntis", "itslearning", "nextcloud")
_NEXTCLOUD_SETTING_KEYS = ("nextcloud_url", "nextcloud_workspace_url", "fehlzeiten_11_url", "fehlzeiten_12_url")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _school_settings(conn) -> dict:
    settings = {}
    for key in _NEXTCLOUD_SETTING_KEYS:
        try:
            settings[key] = get_system_setting(conn, key, "")
        except Exception:
            settings[key] = ""
    if not any(isinstance(v, str) and v for v in settings.values()):
        try:  # local single-school setup (.env.local)
            from backend.config import load_settings
            local = load_settings().nextcloud
            settings["nextcloud_url"] = local.base_url or local.workspace_url
        except Exception:
            pass
    return settings


def _status_payload(configs: dict[str, dict], settings: dict | None = None) -> dict:
    webuntis = configs.get("webuntis") or {}
    itslearning = configs.get("itslearning") or {}
    return {
        "webuntis": {"configured": bool(webuntis.get("ical_url"))},
        "itslearning": {
            "calendar": bool(itslearning.get("calendar_url")),
            "login": bool(itslearning.get("username") and itslearning.get("password")),
            "username": itslearning.get("username", ""),
        },
        "nextcloud": nextcloud_module.status(configs.get("nextcloud"), settings or {}, _now()),
    }


def _classwork_link(conn) -> str:
    try:
        url = get_system_setting(conn, "klassenarbeitsplan_url", "") or get_system_setting(conn, "classwork_url", "")
    except Exception:
        return ""
    return url if isinstance(url, str) else ""


def _classwork_status(url: str, is_admin: bool) -> dict:
    """School-wide Klassenarbeitsplan: OneDrive link, last update, sync health.

    Reads the plan cache and sync state through the persistence store (its own
    connections), so call it outside of an open db_connection() transaction.
    """
    try:
        from backend.classwork_cache import load_cache
        from backend.classwork_sync import CACHE_PATH, sync_info
        from backend.onedrive_share import is_onedrive_link

        cached = load_cache(CACHE_PATH)
        return {
            "url": url,
            "onedrive": is_onedrive_link(url),
            "sync": sync_info(url),
            "uploaded_at": cached.get("uploadedAt", ""),
            "upload_source": cached.get("uploadSource", ""),
            "uploaded_by": cached.get("uploadedBy", ""),
            "can_edit": bool(is_admin),
        }
    except Exception:
        return {"url": "", "onedrive": False, "sync": {}, "can_edit": bool(is_admin)}


def _load_status(conn, user_id: int) -> tuple[dict, str]:
    """Per-user connection status plus the school's Klassenarbeitsplan link."""
    configs = {mid: get_user_module_config(conn, user_id, mid) for mid in _STATUS_MODULES}
    return _status_payload(configs, _school_settings(conn)), _classwork_link(conn)


def _with_classwork(loaded: tuple[dict, str], is_admin: bool) -> dict:
    status, classwork_url = loaded
    status["klassenarbeitsplan"] = _classwork_status(classwork_url, is_admin)
    return status


def _store_config(conn, user_id: int, module_id: str, config: dict, *, configured: bool) -> None:
    """Save a module config and set is_configured explicitly (save_user_module_config always sets it)."""
    save_user_module_config(conn, user_id, module_id, config)
    if not configured:
        conn.execute(
            "UPDATE user_modules SET is_configured = FALSE, updated_at = NOW() "
            "WHERE user_id = %s AND module_id = %s",
            (user_id, module_id),
        )


@connections_bp.route("", methods=["GET"])
@require_auth
def get_connections():
    user_id = g.current_user.id
    try:
        with db_connection() as conn:
            loaded = _load_status(conn, user_id)
    except Exception as exc:
        return error(f"Verbindungen konnten nicht geladen werden: {type(exc).__name__}", 500)
    return success({"connections": _with_classwork(loaded, g.current_user.is_admin)})


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
            _store_config(conn, user_id, module_id, config, configured=bool(config))
            loaded = _load_status(conn, user_id)
    except Exception as exc:
        return error(f"Speichern fehlgeschlagen: {type(exc).__name__}", 500)
    return success({"connections": _with_classwork(loaded, g.current_user.is_admin)})


# ── Nextcloud (Login Flow v2) ────────────────────────────────────────────────

@connections_bp.route("/nextcloud/start", methods=["POST"])
@require_auth
def nextcloud_start():
    """Start the login flow; the browser opens login_url, the frontend polls /poll."""
    body = request.get_json(silent=True) or {}
    user_id = g.current_user.id
    try:
        with db_connection() as conn:
            config = dict(get_user_module_config(conn, user_id, "nextcloud"))
            settings = _school_settings(conn)
    except Exception as exc:
        return error(f"Verbindung konnte nicht vorbereitet werden: {type(exc).__name__}", 500)

    requested = body.get("base_url") if isinstance(body.get("base_url"), str) else ""
    base_url = nextcloud_module.origin(requested) or nextcloud_module.status(config, settings, _now())["suggested_server"]
    if not base_url:
        return error("Bitte die Adresse eurer Nextcloud eintragen (https://…).", 422)

    try:
        flow = start_login_flow(base_url)
    except UnsafeUrlError as exc:
        return error(str(exc), 422)
    except NextcloudError as exc:
        return error(str(exc), 502)

    config.update({
        "base_url": flow["base_url"] if not nextcloud_module.is_connected(config) else config["base_url"],
        "pending_base_url": flow["base_url"],
        "pending_poll_endpoint": flow["poll_endpoint"],
        "pending_poll_token": flow["poll_token"],
        "pending_started_at": _now().isoformat(),
    })
    try:
        with db_connection() as conn:
            _store_config(conn, user_id, "nextcloud", config, configured=nextcloud_module.is_connected(config))
    except Exception as exc:
        return error(f"Verbindung konnte nicht vorbereitet werden: {type(exc).__name__}", 500)
    return success({"login_url": flow["login_url"]})


@connections_bp.route("/nextcloud/poll", methods=["POST"])
@require_auth
def nextcloud_poll():
    user_id = g.current_user.id
    now = _now()
    try:
        with db_connection() as conn:
            config = dict(get_user_module_config(conn, user_id, "nextcloud"))
    except Exception as exc:
        return error(f"Status konnte nicht geladen werden: {type(exc).__name__}", 500)

    pending = nextcloud_module.pending_flow(config, now)
    if pending is None:
        if nextcloud_module.is_connected(config):
            return success({"status": "connected"})
        return success({"status": "expired"})

    try:
        credentials = poll_login_flow(pending["poll_endpoint"], pending["poll_token"])
    except (NextcloudError, UnsafeUrlError) as exc:
        return error(str(exc), 502)
    if credentials is None:
        return success({"status": "pending"})

    previous = None
    if nextcloud_module.is_connected(config):
        previous = (config["base_url"], config["login_name"], config["app_password"])
    for key in nextcloud_module.PENDING_KEYS:
        config.pop(key, None)
    config.update({
        "base_url": nextcloud_module.origin(credentials["server"]) or config.get("base_url", ""),
        "login_name": credentials["login_name"],
        "app_password": credentials["app_password"],
        "connected_at": now.isoformat(),
    })
    try:
        with db_connection() as conn:
            _store_config(conn, user_id, "nextcloud", config, configured=True)
            log_audit_event(conn, "nextcloud_connected", user_id=user_id,
                            details={"server": config["base_url"]})
            loaded = _load_status(conn, user_id)
    except Exception as exc:
        return error(f"Verbindung konnte nicht gespeichert werden: {type(exc).__name__}", 500)

    if previous and previous[2] != credentials["app_password"]:
        revoke_app_password(*previous)  # replace the old app password, best effort
    nextcloud_module.forget_cached(config)
    return success({"status": "connected", "connections": _with_classwork(loaded, g.current_user.is_admin)})


@connections_bp.route("/nextcloud", methods=["DELETE"])
@require_auth
def nextcloud_disconnect():
    user_id = g.current_user.id
    try:
        with db_connection() as conn:
            config = dict(get_user_module_config(conn, user_id, "nextcloud"))
    except Exception as exc:
        return error(f"Status konnte nicht geladen werden: {type(exc).__name__}", 500)

    revoked = True
    if nextcloud_module.is_connected(config):
        revoked = revoke_app_password(config["base_url"], config["login_name"], config["app_password"])
        nextcloud_module.forget_cached(config)
    for key in nextcloud_module.CREDENTIAL_KEYS + nextcloud_module.PENDING_KEYS:
        config.pop(key, None)
    try:
        with db_connection() as conn:
            _store_config(conn, user_id, "nextcloud", config, configured=False)
            log_audit_event(conn, "nextcloud_disconnected", user_id=user_id, details={"revoked": revoked})
            loaded = _load_status(conn, user_id)
    except Exception as exc:
        return error(f"Trennen fehlgeschlagen: {type(exc).__name__}", 500)
    return success({"revoked": revoked, "connections": _with_classwork(loaded, g.current_user.is_admin)})
