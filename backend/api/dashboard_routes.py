"""
Dashboard-Endpunkte für Lehrkräfte: Modules-Layout, Daten.
"""
import dataclasses
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
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


_MANDATORY_MODULE_IDS = ['tagesbriefing', 'zugaenge']
_MANDATORY_MODULE_DEFAULTS = {
    'tagesbriefing': {
        'module_id': 'tagesbriefing',
        'display_name': 'Tagesbriefing',
        'module_type': 'central',
        'is_visible': True,
        'sort_order': 1,
        'is_configured': False,
        'requires_config': False,
    },
    'zugaenge': {
        'module_id': 'zugaenge',
        'display_name': 'Zugänge',
        'module_type': 'central',
        'is_visible': True,
        'sort_order': 2,
        'is_configured': False,
        'requires_config': False,
    },
}


def _inject_mandatory_modules(result: list) -> list:
    """Ensure tagesbriefing and zugaenge are always present and first/second."""
    result_map = {m['module_id']: m for m in result}
    mandatory_entries = []
    for mid in _MANDATORY_MODULE_IDS:
        if mid in result_map:
            entry = dict(result_map[mid])
            entry['is_visible'] = True  # mandatory modules always visible
            mandatory_entries.append(entry)
        else:
            mandatory_entries.append(dict(_MANDATORY_MODULE_DEFAULTS[mid]))
    # optional: all non-mandatory modules in their original order
    optional_entries = [m for m in result if m['module_id'] not in _MANDATORY_MODULE_IDS]
    return mandatory_entries + optional_entries


def _update_heute_layout(conn, user_id: int, module_updates: list) -> None:
    """Upsert user_modules rows for heute-layout updates.

    Args:
        conn: psycopg3 DB-Verbindung.
        user_id: ID des Users.
        module_updates: List of {'id': str, 'is_visible': bool, 'sort_order': int}
    """
    from backend.modules.module_registry import update_user_module as _update_module
    for item in module_updates:
        module_id = item.get('id') or item.get('module_id')
        if not module_id or module_id in _MANDATORY_MODULE_IDS:
            continue
        is_visible = item.get('is_visible')
        sort_order = item.get('sort_order')
        kwargs = {}
        if is_visible is not None:
            kwargs['is_visible'] = bool(is_visible)
        if sort_order is not None:
            kwargs['sort_order'] = int(sort_order)
        if kwargs:
            _update_module(conn, user_id, module_id, **kwargs)


@dashboard_bp.route("/layout", methods=["GET"])
@require_auth
def get_layout():
    """User's Dashboard-Layout abrufen.

    Mandatory modules (tagesbriefing, zugaenge) are always first and always visible.

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

        return success({"modules": _inject_mandatory_modules(result)})
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


@dashboard_bp.route("/heute-layout", methods=["PUT"])
@require_auth
def update_heute_layout():
    """Sichtbarkeit und Reihenfolge der optionalen Heute-Module persistieren.

    Mandatory modules (tagesbriefing, zugaenge) werden im Body silently ignoriert.

    Body: {"modules": [{"id": "itslearning", "is_visible": true, "sort_order": 10}, ...]}
    Response: {"ok": true}
    """
    body = request.get_json(silent=True) or {}
    modules = body.get("modules", [])

    if not isinstance(modules, list):
        return error("modules muss eine Liste sein", 422)

    # Filter out mandatory modules silently
    optional_updates = [
        m for m in modules
        if isinstance(m, dict) and m.get('id') not in _MANDATORY_MODULE_IDS
        and m.get('module_id') not in _MANDATORY_MODULE_IDS
    ]

    try:
        with db_connection() as conn:
            _update_heute_layout(conn, g.current_user.id, optional_updates)
        return success()
    except Exception as exc:
        return error(f"Fehler beim Speichern des Heute-Layouts: {type(exc).__name__}: {exc}", 500)


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


# ── Dashboard Composition Endpoint (Phase 11c / Phase 12) ────────────────────

_MODULE_FETCH_TIMEOUT = 5  # seconds per module fetch

from backend.wichtige_termine_adapter import fetch_wichtige_termine, WichtigeTermineResult


def _build_base_quick_links(
    schoolportal_url: str = "",
    orgaplan_pdf_url: str = "",
    itslearning_base_url: str = "",
) -> list:
    """Build quick_links list for the v2 base dashboard section."""
    links: list = [
        {
            "id": "schoolportal",
            "title": "Berliner Schulportal",
            "url": schoolportal_url or "https://portal.berlin.de",
            "kind": "Portal",
            "note": "Zentraler Einstieg fuer Berliner Schuldienste",
        }
    ]
    if itslearning_base_url:
        links.append({
            "id": "itslearning",
            "title": "itslearning",
            "url": itslearning_base_url,
            "kind": "Lernen",
            "note": "Updates und Kursmeldungen",
        })
    if orgaplan_pdf_url:
        links.append({
            "id": "orgaplan",
            "title": "Orgaplan",
            "url": orgaplan_pdf_url,
            "kind": "PDF",
            "note": "Aktueller Orgaplan fuer eure Schule",
        })
    return links


def _fetch_base_data() -> dict:
    """Fetch base dashboard sections: quick_links, workspace, berlin_focus.

    Reads system_settings from DB first; falls back to load_settings() (local
    config) for any missing URL fields. Each sub-section is wrapped in its own
    try/except so a single failure does not block the others.

    documents is DEFERRED in Phase 12 — requires document_monitor state and
    the full mock-dashboard enrichment pipeline. Returns None for that field.

    Response shape:
        {"ok": True, "data": {"quick_links": [...], "workspace": {...},
                               "berlin_focus": [...], "documents": None,
                               "schoolportal_url": str, "itslearning_base_url": str,
                               "orgaplan_pdf_url": str, "fehlzeiten_11_url": str,
                               "fehlzeiten_12_url": str, "klassenarbeitsplan_url": str,
                               "webuntis_url": str}}
    """
    schoolportal_url = ""
    orgaplan_pdf_url = ""
    itslearning_base_url = ""
    school_name = ""
    fehlzeiten_11_url = ""
    fehlzeiten_12_url = ""
    klassenarbeitsplan_url = ""
    webuntis_url = ""
    app_title = ""

    # 1. Read system_settings from DB
    def _safe_str(val: object) -> str:
        """Return val as str only if it is a real str; otherwise empty string."""
        return val if isinstance(val, str) else ""

    try:
        with db_connection() as conn:
            schoolportal_url = _safe_str(get_system_setting(conn, "schoolportal_url", ""))
            orgaplan_pdf_url = _safe_str(get_system_setting(conn, "orgaplan_pdf_url", ""))
            itslearning_base_url = _safe_str(get_system_setting(conn, "itslearning_base_url", ""))
            school_name = _safe_str(get_system_setting(conn, "school_name", ""))
            fehlzeiten_11_url = _safe_str(get_system_setting(conn, "fehlzeiten_11_url", ""))
            fehlzeiten_12_url = _safe_str(get_system_setting(conn, "fehlzeiten_12_url", ""))
            klassenarbeitsplan_url = _safe_str(get_system_setting(conn, "klassenarbeitsplan_url", ""))
            webuntis_url = _safe_str(get_system_setting(conn, "webuntis_url", ""))
            app_title = _safe_str(get_system_setting(conn, "app_title", ""))
    except Exception:
        pass  # Fall back to local settings below

    # 2. Supplement with local settings (load_settings reads .env.local)
    try:
        from backend.config import load_settings as _load_settings
        _settings = _load_settings()
        if not schoolportal_url:
            schoolportal_url = _safe_str(getattr(_settings, "schoolportal_url", ""))
        if not orgaplan_pdf_url:
            orgaplan_pdf_url = _safe_str(getattr(_settings, "orgaplan_pdf_url", ""))
        if not itslearning_base_url:
            itslearning_base_url = _safe_str(getattr(_settings, "itslearning_base_url", ""))
        if not school_name:
            school_name = _safe_str(getattr(_settings, "school_name", ""))
    except Exception:
        pass

    if not school_name:
        school_name = "Ihre Schule"

    # 3. Build each sub-section independently
    quick_links: list = []
    try:
        quick_links = _build_base_quick_links(
            schoolportal_url=schoolportal_url,
            orgaplan_pdf_url=orgaplan_pdf_url,
            itslearning_base_url=itslearning_base_url,
        )
    except Exception:
        quick_links = []

    workspace: dict = {}
    try:
        workspace = {
            "eyebrow": "Berlin Lehrer-Cockpit",
            "title": f"Dein Tagesstart fuer {school_name}",
            "description": (
                "Ein persoenliches Dashboard fuer Berliner Schulportal-Dienste, WebUntis, "
                "itslearning und eure wichtigsten Schul-Dokumente."
            ),
            "app_title": app_title or "Lehrercockpit",
        }
    except Exception:
        workspace = {"eyebrow": "Berlin Lehrer-Cockpit", "title": "Dein Tagesstart", "description": ""}

    berlin_focus: list = []
    try:
        berlin_focus = [
            {
                "title": "SSO-Dienste zuerst",
                "detail": "WebUntis und itslearning sind bereits als echte Einstiegsquellen im Cockpit hinterlegt.",
            },
            {
                "title": "Dokumente bringen den Mehrwert",
                "detail": (
                    "Der konkrete Orgaplan ist schon hinterlegt, sodass wir als Naechstes Aenderungen automatisch vergleichen koennen."
                    if orgaplan_pdf_url else
                    "Orgaplan und Klassenarbeitsplan bleiben besonders wichtig, weil PDFs und Share-Links im Alltag schnell verstreut sind."
                ),
            },
            {
                "title": "Mail vorerst nur Portal-Logik",
                "detail": "Die Berliner Dienstmail bleibt ohne klassischen IMAP-Weg zunaechst ein Portal-/Hinweis-Modul.",
            },
        ]
    except Exception:
        berlin_focus = []

    return {
        "ok": True,
        "data": {
            "quick_links": quick_links,
            "workspace": workspace,
            "berlin_focus": berlin_focus,
            "documents": None,  # Deferred: requires document_monitor pipeline
            # URL fields for Zugaenge module card (Slice 2)
            "schoolportal_url": schoolportal_url,
            "itslearning_base_url": itslearning_base_url,
            "orgaplan_pdf_url": orgaplan_pdf_url,
            "fehlzeiten_11_url": fehlzeiten_11_url,
            "fehlzeiten_12_url": fehlzeiten_12_url,
            "klassenarbeitsplan_url": klassenarbeitsplan_url,
            "webuntis_url": webuntis_url,
            # Slice 4: configurable app title
            "app_title": app_title or "Lehrercockpit",
        },
    }


def _fetch_wichtige_termine_data(user_id: int) -> dict:
    """Fetch school calendar events from iCal feed (system-wide, not per-user).

    Reads wichtige_termine_ical_url from system_settings; falls back to the
    default HES URL. Returns the parsed result as a dict.
    """
    from datetime import datetime
    try:
        with db_connection() as conn:
            ical_url = get_system_setting(conn, 'wichtige_termine_ical_url', None)
        if not ical_url or not isinstance(ical_url, str) or not ical_url.strip():
            ical_url = 'https://hermann-ehlers-schule.de/events/liste/?ical=1'

        result = fetch_wichtige_termine(ical_url, datetime.now())
        import dataclasses
        return {'ok': result.ok, 'data': dataclasses.asdict(result)}
    except Exception as e:
        return {'ok': False, 'data': {'mode': 'error', 'error': str(e), 'today_events': [], 'upcoming_events': []}}


def _fetch_webuntis_data(user_id: int) -> dict:
    """Fetch WebUntis data for the given user. Returns module result dict."""
    try:
        with db_connection() as conn:
            config = get_user_module_config(conn, user_id, "webuntis")
        ical_url = config.get("ical_url", "") if config else ""
        base_url = config.get("base_url", "") if config else ""
        if not ical_url:
            return {"ok": True, "data": None, "configured": False, "error": "WebUntis iCal-Link nicht konfiguriert"}
        from backend.webuntis_adapter import fetch_webuntis_sync
        now = datetime.now(timezone.utc)
        result = fetch_webuntis_sync(base_url, ical_url, now)
        data_dict = dataclasses.asdict(result)
        return {"ok": True, "data": data_dict, "configured": True}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _fetch_itslearning_data(user_id: int) -> dict:
    """Fetch itslearning data for the given user. Returns module result dict."""
    try:
        with db_connection() as conn:
            config = get_user_module_config(conn, user_id, "itslearning")
        username = config.get("username", "") if config else ""
        password = config.get("password", "") if config else ""
        if not username or not password:
            return {"ok": True, "data": None, "configured": False, "error": "itslearning nicht konfiguriert"}
        from backend.config import ItslearningSettings
        from backend.itslearning_adapter import fetch_itslearning_sync
        settings = ItslearningSettings(
            base_url=config.get("base_url", "https://berlin.itslearning.com"),
            username=username,
            password=password,
            max_updates=int(config.get("max_updates", 6)),
        )
        now = datetime.now(timezone.utc)
        result = fetch_itslearning_sync(settings, now)
        data_dict = dataclasses.asdict(result)
        return {"ok": True, "data": data_dict, "configured": True}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _fetch_orgaplan_data() -> dict:
    """Fetch orgaplan data from cache or parse fresh. Returns module result dict."""
    try:
        with db_connection() as conn:
            orgaplan_url = get_system_setting(conn, "orgaplan_url", None)
            pdf_url = get_system_setting(conn, "orgaplan_pdf_url", None)
            cached_raw = get_system_setting(conn, "orgaplan_cache", None)
            cached_ts_raw = get_system_setting(conn, "orgaplan_cache_ts", None)
            cached_url = get_system_setting(conn, "orgaplan_cache_url", None)

        effective_url = pdf_url or orgaplan_url
        if not effective_url:
            return {"ok": True, "data": None, "configured": False}

        # Check cache validity
        now = datetime.now(timezone.utc)
        cache_valid = False
        if cached_raw and cached_ts_raw:
            try:
                ts = datetime.fromisoformat(cached_ts_raw) if isinstance(cached_ts_raw, str) else None
                if ts:
                    ts_aware = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
                    age_minutes = (now - ts_aware).total_seconds() / 60
                    if age_minutes < 60 and cached_url == effective_url:
                        cache_valid = True
            except Exception:
                cache_valid = False

        if cache_valid and isinstance(cached_raw, dict):
            digest = cached_raw
            return {"ok": True, "data": {
                "url": orgaplan_url, "pdf_url": pdf_url,
                "highlights": digest.get("highlights", []),
                "upcoming": digest.get("upcoming", []),
                "entries": digest.get("upcoming", []),
                "classes": [],
                "status": digest.get("status", "ok"),
                "detail": digest.get("detail", ""),
                "monthLabel": digest.get("monthLabel", ""),
                "cached_at": cached_ts_raw,
            }, "configured": True}

        from backend.plan_digest import build_plan_digest
        full_digest = build_plan_digest(effective_url, None, None, now)
        orgaplan_digest = full_digest.get("orgaplan", {})
        ts_str = now.isoformat()
        try:
            with db_connection() as conn:
                set_system_setting(conn, "orgaplan_cache", orgaplan_digest)
                set_system_setting(conn, "orgaplan_cache_ts", ts_str)
                set_system_setting(conn, "orgaplan_cache_url", effective_url)
        except Exception:
            pass
        return {"ok": True, "data": {
            "url": orgaplan_url, "pdf_url": pdf_url,
            "highlights": orgaplan_digest.get("highlights", []),
            "upcoming": orgaplan_digest.get("upcoming", []),
            "entries": orgaplan_digest.get("upcoming", []),
            "classes": [],
            "status": orgaplan_digest.get("status", "ok"),
            "detail": orgaplan_digest.get("detail", ""),
            "monthLabel": orgaplan_digest.get("monthLabel", ""),
            "cached_at": ts_str,
        }, "configured": True}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _fetch_klassenarbeitsplan_data() -> dict:
    """Fetch klassenarbeitsplan from classwork cache or plan_digest. Returns module result dict."""
    try:
        with db_connection() as conn:
            url = get_system_setting(conn, "klassenarbeitsplan_url", None)

        from pathlib import Path
        from backend.classwork_cache import load_cache
        cache_path = Path(__file__).resolve().parent.parent.parent / "data" / "classwork-cache.json"
        cached = load_cache(cache_path)
        if cached.get("status") == "ok" and (
            cached.get("previewRows") or cached.get("structuredRows") or cached.get("entries")
        ):
            return {"ok": True, "data": {"url": url, **cached}, "configured": True}

        # Fallback: plan_digest
        now = datetime.now(timezone.utc)
        local_xlsx = Path(__file__).resolve().parent.parent.parent / "data" / "classwork-plan-local.xlsx"
        local_path_str = str(local_xlsx) if local_xlsx.exists() else None
        from backend.plan_digest import build_plan_digest
        full_digest = build_plan_digest(None, url, local_path_str, now)
        classwork_digest = full_digest.get("classwork", {})
        return {"ok": True, "data": {
            "url": url,
            "status": classwork_digest.get("status", "warning"),
            "title": classwork_digest.get("title", "Klassenarbeitsplan"),
            "detail": classwork_digest.get("detail", ""),
            "updatedAt": classwork_digest.get("updatedAt", "--:--"),
            "previewRows": classwork_digest.get("previewRows", []),
            "classes": classwork_digest.get("classes", []),
            "entries": classwork_digest.get("entries", []),
            "defaultClass": classwork_digest.get("defaultClass", ""),
            "sourceUrl": classwork_digest.get("sourceUrl", url or ""),
        }, "configured": bool(url or local_path_str)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _fetch_noten_data(user_id: int) -> dict:
    """Fetch grades and notes for user. Returns module result dict."""
    try:
        from backend.users.user_service import get_grades, get_notes
        with db_connection() as conn:
            grades = get_grades(conn, user_id)
            notes = get_notes(conn, user_id)
        return {"ok": True, "data": {"grades": grades, "notes": notes}}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


@dashboard_bp.route("/data", methods=["GET"])
@require_auth
def get_dashboard_data():
    """Aggregiertes Modul-Daten-Payload für alle aktiven Module des Users.

    Ruft Daten für alle sichtbaren Module parallel ab. Jedes Modul schlägt
    unabhängig fehl — ein Fehler blockiert keine anderen Module.

    Phase 12: Enthält jetzt eine 'base'-Sektion mit quickLinks, workspace und
    berlinFocus, die unabhängig von den Modul-Daten geladen wird.

    Response:
    {
      "ok": true,
      "base": {
        "quick_links":  [{label, url, icon}],
        "workspace":    {"eyebrow": "...", "title": "...", "description": "..."},
        "berlin_focus": [{"title": "...", "detail": "..."}],
        "documents":    null  (deferred — requires document_monitor pipeline)
      },
      "modules": {
        "webuntis":          {"ok": true,  "data": {...}, "configured": true},
        "itslearning":       {"ok": true,  "data": null,  "configured": false, "error": "..."},
        "orgaplan":          {"ok": true,  "data": {...}, "configured": true},
        "klassenarbeitsplan":{"ok": true,  "data": {...}, "configured": true},
        "noten":             {"ok": true,  "data": {"grades": [...], "notes": [...]}}
      },
      "user": {"id": 1, "display_name": "..."},
      "generated_at": "ISO timestamp"
    }
    """
    user_id = g.current_user.id

    # Determine which modules are active/visible for this user
    try:
        with db_connection() as conn:
            user_module_list = get_user_modules(conn, user_id)
        active_module_ids = {
            um.module_id
            for um in user_module_list
            if um.is_visible
        }
    except Exception:
        # Fallback: fetch all known data modules
        active_module_ids = {"webuntis", "itslearning", "orgaplan", "klassenarbeitsplan", "noten"}

    # Define which fetchers to run (only for active modules)
    module_fetchers = {}
    if "webuntis" in active_module_ids:
        module_fetchers["webuntis"] = lambda: _fetch_webuntis_data(user_id)
    if "itslearning" in active_module_ids:
        module_fetchers["itslearning"] = lambda: _fetch_itslearning_data(user_id)
    if "orgaplan" in active_module_ids:
        module_fetchers["orgaplan"] = _fetch_orgaplan_data
    if "klassenarbeitsplan" in active_module_ids:
        module_fetchers["klassenarbeitsplan"] = _fetch_klassenarbeitsplan_data
    if "noten" in active_module_ids:
        module_fetchers["noten"] = lambda: _fetch_noten_data(user_id)
    if "wichtige-termine" in active_module_ids:
        module_fetchers["wichtige-termine"] = lambda: _fetch_wichtige_termine_data(user_id)

    modules_result = {}
    base_result: dict = {}

    # Collect all fetchers: module fetchers + base fetcher (Phase 12)
    all_fetchers: dict = dict(module_fetchers)
    all_fetchers["__base__"] = _fetch_base_data

    # Execute fetchers in parallel with per-module timeout
    with ThreadPoolExecutor(max_workers=len(all_fetchers) or 1) as executor:
        future_map = {
            executor.submit(fetcher): fetch_id
            for fetch_id, fetcher in all_fetchers.items()
        }
        for future, fetch_id in future_map.items():
            try:
                result = future.result(timeout=_MODULE_FETCH_TIMEOUT)
                if fetch_id == "__base__":
                    base_result = result
                else:
                    modules_result[fetch_id] = result
            except FuturesTimeoutError:
                if fetch_id == "__base__":
                    base_result = {"ok": False, "error": "timeout"}
                else:
                    modules_result[fetch_id] = {"ok": False, "error": "timeout"}
            except Exception as exc:
                err_val = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                if fetch_id == "__base__":
                    base_result = err_val
                else:
                    modules_result[fetch_id] = err_val

    user_dict = g.current_user.to_dict()
    user_dict["display_name"] = user_dict.get("full_name", "")

    # Build the base section from base_result.data (Phase 12)
    base_data = base_result.get("data", {}) if base_result.get("ok") else {}
    base_section = {
        "quick_links": base_data.get("quick_links", []),
        "workspace": base_data.get("workspace", {}),
        "berlin_focus": base_data.get("berlin_focus", []),
        "documents": base_data.get("documents", None),  # None = deferred
        # URL fields for Zugaenge module card
        "schoolportal_url": base_data.get("schoolportal_url", ""),
        "itslearning_base_url": base_data.get("itslearning_base_url", ""),
        "orgaplan_pdf_url": base_data.get("orgaplan_pdf_url", ""),
        "fehlzeiten_11_url": base_data.get("fehlzeiten_11_url", ""),
        "fehlzeiten_12_url": base_data.get("fehlzeiten_12_url", ""),
        "klassenarbeitsplan_url": base_data.get("klassenarbeitsplan_url", ""),
        "webuntis_url": base_data.get("webuntis_url", ""),
        # Slice 4: configurable app title
        "app_title": base_data.get("app_title", "Lehrercockpit"),
    }

    return success({
        "base": base_section,
        "modules": modules_result,
        "user": {
            "id": user_dict.get("id"),
            "display_name": user_dict.get("display_name", ""),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
