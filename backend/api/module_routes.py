"""
Modul-Daten-Endpunkte: liefert die eigentlichen Modul-Inhalte.
Enthält auch CRUD-Endpunkte für Modul-Konfigurationen und
öffentliche Registry-Metadaten (kein Auth erforderlich).
"""
import dataclasses
import json
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
from backend.admin.admin_service import get_system_setting, set_system_setting
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

    Returns {"ok": true, "data": null, "configured": false} when no credentials are set.
    Response: {"ok": true, "data": {...}}
    """
    try:
        with db_connection() as conn:
            config = get_user_module_config(conn, g.current_user.id, "itslearning")
    except Exception as exc:
        return error(f"Fehler beim Laden der Konfiguration: {type(exc).__name__}: {exc}", 500)

    try:
        from backend.itslearning_module import build_itslearning_payload

        result = build_itslearning_payload(config, datetime.now(timezone.utc))
    except Exception as exc:
        return success({"data": None, "error": f"{type(exc).__name__}: {exc}"})
    result.pop("ok", None)
    return success(result)


@module_bp.route("/webuntis/data", methods=["GET"])
@require_auth
def webuntis_data():
    """WebUntis-Daten abrufen.

    Response: {"ok": true, "data": {...}}

    If no ical_url is configured, returns {"ok": true, "data": null, "configured": false}
    with HTTP 200 rather than 500.
    """
    try:
        with db_connection() as conn:
            config = get_user_module_config(conn, g.current_user.id, "webuntis")
    except Exception as exc:
        return error(f"Fehler beim Laden der Konfiguration: {type(exc).__name__}: {exc}", 500)

    base_url = config.get("base_url", "") if config else ""
    ical_url = config.get("ical_url", "") if config else ""

    if not ical_url:
        return success({
            "data": None,
            "configured": False,
            "error": "WebUntis iCal-Link nicht konfiguriert",
        })

    try:
        from backend.webuntis_adapter import fetch_webuntis_sync

        now = datetime.now(timezone.utc)
        result = fetch_webuntis_sync(base_url, ical_url, now)
        # Convert dataclass to dict so Flask's jsonify can serialize it
        try:
            data_dict = dataclasses.asdict(result)
        except Exception as serial_exc:
            return success({"data": None, "error": f"Serialisierungsfehler: {type(serial_exc).__name__}: {serial_exc}"})
        return success({"data": data_dict})
    except Exception as exc:
        return success({"data": None, "error": f"{type(exc).__name__}: {exc}"})


@module_bp.route("/nextcloud/data", methods=["GET"])
@require_auth
def nextcloud_data():
    """Nextcloud-Daten abrufen.

    Returns {"ok": true, "data": null, "configured": false} when base_url not set.
    Response: {"ok": true, "data": {...}}
    """
    try:
        with db_connection() as conn:
            config = get_user_module_config(conn, g.current_user.id, "nextcloud")
    except Exception as exc:
        return error(f"Fehler beim Laden der Konfiguration: {type(exc).__name__}: {exc}", 500)

    from backend.nextcloud_module import build_nextcloud_payload, is_connected

    if is_connected(config):  # connected via Login Flow v2 (app password)
        result = build_nextcloud_payload(config, datetime.now(timezone.utc))
        result.pop("ok", None)
        return success(result)

    # Graceful: no base_url configured at all
    base_url = config.get("base_url", "") if config else ""
    workspace_url = config.get("workspace_url", "") if config else ""
    if not base_url and not workspace_url:
        return success({
            "data": None,
            "configured": False,
            "error": "Nextcloud nicht konfiguriert",
        })

    try:
        from backend.config import NextcloudSettings
        from backend.nextcloud_adapter import fetch_nextcloud_sync

        settings = NextcloudSettings(
            base_url=config.get("base_url", ""),
            username=config.get("username", ""),
            password=config.get("password", ""),
            workspace_url=config.get("workspace_url", ""),
            q1q2_url=config.get("q1q2_url", ""),
            q3q4_url=config.get("q3q4_url", ""),
            link_1_label=config.get("link_1_label", ""),
            link_1_url=config.get("link_1_url", ""),
            link_2_label=config.get("link_2_label", ""),
            link_2_url=config.get("link_2_url", ""),
            link_3_label=config.get("link_3_label", ""),
            link_3_url=config.get("link_3_url", ""),
        )
        now = datetime.now(timezone.utc)
        result = fetch_nextcloud_sync(settings, now)
        # Convert dataclass to dict so Flask's jsonify can serialize it
        try:
            data_dict = dataclasses.asdict(result)
        except Exception as serial_exc:
            return success({"data": None, "error": f"Serialisierungsfehler: {type(serial_exc).__name__}: {serial_exc}"})
        return success({"data": data_dict, "configured": True})
    except Exception as exc:
        return success({"data": None, "error": f"{type(exc).__name__}: {exc}"})


@module_bp.route("/orgaplan/data", methods=["GET"])
@require_auth
def orgaplan_data():
    """Orgaplan für die nächsten Wochen (neueste PDF der Schulwebseite oder feste PDF).

    Response: {"ok": true, "data": {"upcoming": [...], "today_entries": [...], ...}, "configured": true}
    """
    from backend.api.dashboard_routes import _fetch_orgaplan_data

    result = _fetch_orgaplan_data()
    if not result.get("ok"):
        return success({"data": None, "configured": True, "error": result.get("error", "Fehler beim Laden")})
    return success({"data": result["data"], "configured": True})


@module_bp.route("/orgaplan/refresh", methods=["POST"])
@require_auth
def orgaplan_refresh():
    """Orgaplan sofort neu suchen und einlesen (z. B. nach einer neuen PDF auf der Webseite)."""
    from backend import orgaplan

    try:
        with db_connection() as conn:
            source = orgaplan.load_source(conn)
    except Exception as exc:
        return error(f"Einstellungen konnten nicht geladen werden: {type(exc).__name__}", 500)
    digest = orgaplan.current(source, datetime.now(timezone.utc), wait=25.0, force=True)
    return success({"data": digest})


@module_bp.route("/klassenarbeitsplan/data", methods=["GET"])
@require_auth
def klassenarbeitsplan_data():
    """Klassenarbeitsplan ab heute plus Sync-Status (OneDrive).

    Response: {"ok": true, "data": {"entries": [...], "planStatus": {...}, ...}, "configured": bool, "sync": {...}}
    """
    from backend.api.dashboard_routes import _fetch_klassenarbeitsplan_data

    result = _fetch_klassenarbeitsplan_data()
    if not result.get("ok"):
        return success({"data": None, "error": result.get("error", "Fehler beim Laden")})
    return success({"data": result["data"], "configured": result.get("configured", False),
                    "sync": result.get("sync", {})})


def _classwork_url() -> str:
    from backend.school_sources import classwork_url

    with db_connection() as conn:
        return classwork_url(conn)


@module_bp.route("/klassenarbeitsplan/browser-sync", methods=["POST"])
@require_auth
def klassenarbeitsplan_browser_sync():
    """A teacher's browser fetched the plan from OneDrive (the server may be blocked).

    Body: the raw file (application/octet-stream).
    Headers: X-Source-ETag, X-Source-Modified, X-Source-Name (from OneDrive metadata).
    """
    from urllib.parse import unquote

    from backend.classwork_sync import record_browser_result, store_plan
    from backend.onedrive_share import MAX_BYTES, is_onedrive_link

    file_bytes = request.get_data(cache=False)
    if not file_bytes:
        return error("Keine Datei empfangen.", 400)
    if len(file_bytes) > MAX_BYTES:
        return error("Datei zu groß (max. 15 MB).", 413)
    try:
        url = _classwork_url()
    except Exception as exc:
        return error(f"Einstellungen konnten nicht geladen werden: {type(exc).__name__}", 500)
    if not is_onedrive_link(url):
        return error("Für den Klassenarbeitsplan ist kein OneDrive-Link hinterlegt.", 409)

    meta = {
        "etag": request.headers.get("X-Source-ETag", "")[:200],
        "modified": request.headers.get("X-Source-Modified", "")[:64],
        "name": unquote(request.headers.get("X-Source-Name", ""))[:200],  # sent URI-encoded
    }
    try:
        result = store_plan(file_bytes, source="onedrive-browser",
                            uploaded_by=g.current_user.full_name, meta=meta)
    except ValueError as exc:
        return error(f"Datei konnte nicht gelesen werden: {exc}", 422)
    record_browser_result(url, meta, changed=True)
    return success({"data": result})


@module_bp.route("/klassenarbeitsplan/sync-confirm", methods=["POST"])
@require_auth
def klassenarbeitsplan_sync_confirm():
    """A browser checked OneDrive and the plan is unchanged (same eTag)."""
    from backend.classwork_sync import load_state, record_browser_result, sync_info

    body = request.get_json(silent=True) or {}
    etag = str(body.get("etag", ""))[:200]
    try:
        url = _classwork_url()
    except Exception as exc:
        return error(f"Einstellungen konnten nicht geladen werden: {type(exc).__name__}", 500)
    state = load_state()
    if not etag or state.get("source_url") != url or state.get("etag") != etag:
        return error("Stand stimmt nicht überein – bitte die Datei übertragen.", 409)
    record_browser_result(url, {"etag": etag, "modified": state.get("modified", ""),
                                "name": state.get("name", "")}, changed=False)
    return success({"sync": sync_info(url)})


@module_bp.route("/klassenarbeitsplan/config", methods=["POST"])
@require_auth
def klassenarbeitsplan_save_config():
    """Speichert den OneDrive-Link (Datei oder Ordner) für den Klassenarbeitsplan (nur Admins, schulweit)."""
    from backend.school_sources import CLASSWORK_CANDIDATE_KEY, CLASSWORK_KEY

    if not g.current_user.is_admin:
        return error("Nur Admins können den schulweiten Link ändern.", 403)
    body = request.get_json(silent=True) or {}
    url = str(body.get("url", "")).strip()
    if url and not url.lower().startswith("https://"):
        return error("Bitte den vollständigen Link (https://…) einfügen.", 422)
    if len(url) > 2000:
        return error("Der Link ist zu lang.", 422)
    try:
        with db_connection() as conn:
            set_system_setting(conn, CLASSWORK_KEY, url)
            conn.execute("DELETE FROM system_settings WHERE key = %s", (CLASSWORK_CANDIDATE_KEY,))
        return success({"saved": True, "url": url})
    except Exception as exc:
        return error(f"Speichern fehlgeschlagen: {type(exc).__name__}", 500)


def _download_direct(url: str) -> bytes:
    """A plan file under a normal https address (not OneDrive). Raises ValueError."""
    from urllib.error import URLError
    from urllib.request import Request as UrlRequest, urlopen

    from backend.http_utils import UnsafeUrlError, require_public_https_url, tls_context

    try:
        safe = require_public_https_url(url)
    except UnsafeUrlError as exc:
        raise ValueError(str(exc)) from exc
    request_ = UrlRequest(safe, headers={"User-Agent": "Mozilla/5.0 (compatible; Lehrercockpit/1.0)"})
    try:
        with urlopen(request_, timeout=25, context=tls_context()) as resp:
            if "text/html" in resp.headers.get("Content-Type", "").lower():
                raise ValueError("Der Link führt zu einer Webseite statt zu einer Datei (evtl. Anmeldung nötig).")
            data = resp.read(20 * 1024 * 1024 + 1)
    except URLError as exc:
        raise ValueError(f"Datei konnte nicht geladen werden ({exc.reason}).") from exc
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("Datei zu groß (max. 20 MB).")
    return data


@module_bp.route("/klassenarbeitsplan/fetch", methods=["POST"])
@require_auth
def klassenarbeitsplan_fetch():
    """Klassenarbeitsplan jetzt vom hinterlegten Link holen.

    OneDrive: erst über den Server; blockt Microsoft ihn, lädt der Browser (sync.needs_browser).
    """
    from backend.classwork_cache import load_cache
    from backend.classwork_sync import CACHE_PATH, plan_view, store_plan, sync_from_server, sync_info
    from backend.onedrive_share import is_onedrive_link

    body = request.get_json(silent=True) or {}
    if str(body.get("url", "")).strip():
        return error("Den Link bitte unter „Verbindungen“ speichern.", 422)
    try:
        url = _classwork_url()
    except Exception as exc:
        return error(f"Einstellungen konnten nicht geladen werden: {type(exc).__name__}", 500)
    if not url:
        return error("Für den Klassenarbeitsplan ist noch kein Link hinterlegt.", 400)

    if is_onedrive_link(url):
        result_code = sync_from_server(url)
        sync = sync_info(url)
        if result_code in ("ok", "unchanged"):
            return success({"data": plan_view(load_cache(CACHE_PATH)), "result": result_code, "sync": sync})
        # Microsoft refused the server: the browser has to fetch the file.
        return success({"data": None, "result": result_code, "sync": {**sync, "needs_browser": True},
                        "error": sync.get("last_error") or "Abruf durch den Server nicht möglich."})

    try:
        result = store_plan(_download_direct(url), source="auto", uploaded_by=g.current_user.full_name)
    except ValueError as exc:
        return error(str(exc), 422)
    return success({"data": plan_view(result), "result": "ok"})


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


# ── Schulwebseite scannen / Custom Links ─────────────────────────────────────

@module_bp.route("/scrape-school-website", methods=["POST"])
@require_auth
def scrape_school_website():
    """Scrapt eine Schulwebseite und gibt kategorisierte Links zurück."""
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url or not url.startswith("http"):
        return error("Bitte eine gültige URL eingeben.", 422)
    try:
        from backend.school_scraper import scrape_school_links
        links = scrape_school_links(url)
        return success({"links": links})
    except Exception as exc:
        return error(f"Webseite konnte nicht geladen werden: {exc}", 502)


@module_bp.route("/save-custom-links", methods=["POST"])
@require_auth
def save_custom_links():
    """Speichert benutzerdefinierte Links in user_module_configs."""
    body = request.get_json(silent=True) or {}
    links = body.get("links", [])
    # Validierung: max 30 Links, jeder hat title + url
    if not isinstance(links, list):
        return error("Ungültige Links.", 422)
    links = [l for l in links if isinstance(l, dict) and l.get("title") and l.get("url")][:30]

    user_id = g.current_user.id

    with db_connection() as conn:
        conn.execute("""
            INSERT INTO user_module_configs (user_id, module_id, config_data)
            VALUES (%s, 'custom_links', %s)
            ON CONFLICT (user_id, module_id) DO UPDATE
                SET config_data = EXCLUDED.config_data, updated_at = NOW()
        """, (user_id, json.dumps({"links": links})))

    return success({"saved": len(links)})
