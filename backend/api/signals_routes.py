"""
Neu & geändert: Aktionen auf Einträgen und Klassenwahl.

Die Einträge selbst kommen mit GET /api/v2/dashboard/data (Abschnitt "signals").

POST /api/v2/signals/state       {"id": "...", "action": "seen|done|hide|snooze|reopen"}
POST /api/v2/signals/seen        {"ids": [...]}   → alle als gelesen markieren
GET  /api/v2/signals/preferences
PUT  /api/v2/signals/preferences {"classes": ["10B", "Q1"]}
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from flask import Blueprint, g, request

from backend.api.helpers import error, require_auth, success
from backend.db import db_connection
from backend.signal_store import ACTIONS, MAX_PREFERRED_CLASSES, apply_action, load_prefs, mark_seen, save_prefs

signals_bp = Blueprint("signals", __name__)

_CLASS_LABEL = re.compile(r"^[0-9A-Za-zÄÖÜäöü/\-]{1,12}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@signals_bp.route("/state", methods=["POST"])
@require_auth
def set_state():
    body = request.get_json(silent=True) or {}
    signal_id = str(body.get("id") or "")[:300]
    action = str(body.get("action") or "")
    if not signal_id or action not in ACTIONS:
        return error("id und eine gültige action sind erforderlich.", 422)
    try:
        with db_connection() as conn:
            found = apply_action(conn, g.current_user.id, signal_id, action, _now())
    except Exception as exc:
        return error(f"Speichern fehlgeschlagen: {type(exc).__name__}", 500)
    if not found:
        return error("Eintrag nicht gefunden.", 404)
    return success()


@signals_bp.route("/seen", methods=["POST"])
@require_auth
def set_seen():
    body = request.get_json(silent=True) or {}
    ids = body.get("ids")
    if not isinstance(ids, list):
        return error("ids muss eine Liste sein.", 422)
    ids = [str(i)[:300] for i in ids if i][:500]
    try:
        with db_connection() as conn:
            count = mark_seen(conn, g.current_user.id, ids, _now())
    except Exception as exc:
        return error(f"Speichern fehlgeschlagen: {type(exc).__name__}", 500)
    return success({"updated": count})


@signals_bp.route("/preferences", methods=["GET"])
@require_auth
def get_preferences():
    try:
        with db_connection() as conn:
            prefs = load_prefs(conn, g.current_user.id)
    except Exception as exc:
        return error(f"Einstellungen konnten nicht geladen werden: {type(exc).__name__}", 500)
    return success({"preferences": prefs})


@signals_bp.route("/preferences", methods=["PUT"])
@require_auth
def put_preferences():
    body = request.get_json(silent=True) or {}
    classes = body.get("classes")
    if not isinstance(classes, list):
        return error("classes muss eine Liste sein.", 422)
    cleaned = sorted({str(c).strip() for c in classes if isinstance(c, str) and _CLASS_LABEL.match(str(c).strip())})
    try:
        with db_connection() as conn:
            prefs = load_prefs(conn, g.current_user.id)
            prefs["classes"] = cleaned[:MAX_PREFERRED_CLASSES]
            save_prefs(conn, g.current_user.id, prefs)
    except Exception as exc:
        return error(f"Speichern fehlgeschlagen: {type(exc).__name__}", 500)
    return success({"preferences": prefs})
