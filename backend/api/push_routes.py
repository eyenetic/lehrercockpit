"""
Web-Push: Geräte anmelden, testen und den zeitgesteuerten Versand anstoßen.

GET    /api/v2/push/config      → {"enabled": bool, "public_key": str}  (öffentlich)
GET    /api/v2/push/devices     → Anzahl angemeldeter Geräte der Lehrkraft
POST   /api/v2/push/subscribe   {"subscription": {...}, "prefs": {"morning": bool, "weekly": bool}}
DELETE /api/v2/push/subscribe   {"endpoint": "..."}
POST   /api/v2/push/test        → Test-Nachricht an alle eigenen Geräte
POST   /api/v2/push/dispatch    → Versand fälliger Zusammenfassungen (Header X-Cron-Secret)
"""
from __future__ import annotations

import hmac
import os
from urllib.parse import urlparse

from flask import Blueprint, g, request

from backend.api.helpers import error, require_auth, success
from backend.db import db_connection
from backend.push_service import delete_subscription, dispatch, save_subscription, send_test, user_subscriptions
from backend.webpush import vapid_config

push_bp = Blueprint("push", __name__)


@push_bp.route("/config", methods=["GET"])
def push_config():
    config = vapid_config()
    return success({"enabled": config is not None, "public_key": config.public_key if config else ""})


@push_bp.route("/devices", methods=["GET"])
@require_auth
def push_devices():
    try:
        with db_connection() as conn:
            subs = user_subscriptions(conn, g.current_user.id)
    except Exception as exc:
        return error(f"Geräte konnten nicht geladen werden: {type(exc).__name__}", 500)
    return success({"devices": len(subs)})


@push_bp.route("/subscribe", methods=["POST"])
@require_auth
def push_subscribe():
    if vapid_config() is None:
        return error("Push-Nachrichten sind auf diesem Server nicht eingerichtet.", 503)
    body = request.get_json(silent=True) or {}
    sub = body.get("subscription") or {}
    keys = sub.get("keys") or {}
    endpoint = str(sub.get("endpoint") or "")
    p256dh = str(keys.get("p256dh") or "")
    auth = str(keys.get("auth") or "")
    if urlparse(endpoint).scheme != "https" or not p256dh or not auth or len(endpoint) > 2000:
        return error("Ungültige Push-Anmeldung.", 422)
    raw_prefs = body.get("prefs") or {}
    prefs = {"morning": bool(raw_prefs.get("morning", True)), "weekly": bool(raw_prefs.get("weekly", True))}
    try:
        with db_connection() as conn:
            save_subscription(conn, g.current_user.id, endpoint, p256dh, auth,
                              request.headers.get("User-Agent", ""), prefs)
    except Exception as exc:
        return error(f"Anmeldung fehlgeschlagen: {type(exc).__name__}", 500)
    return success({"prefs": prefs})


@push_bp.route("/subscribe", methods=["DELETE"])
@require_auth
def push_unsubscribe():
    body = request.get_json(silent=True) or {}
    endpoint = str(body.get("endpoint") or "")
    if not endpoint:
        return error("endpoint fehlt.", 422)
    try:
        with db_connection() as conn:
            removed = delete_subscription(conn, g.current_user.id, endpoint)
    except Exception as exc:
        return error(f"Abmeldung fehlgeschlagen: {type(exc).__name__}", 500)
    return success({"removed": removed})


@push_bp.route("/test", methods=["POST"])
@require_auth
def push_test():
    config = vapid_config()
    if config is None:
        return error("Push-Nachrichten sind auf diesem Server nicht eingerichtet.", 503)
    try:
        with db_connection() as conn:
            delivered = send_test(conn, g.current_user.id, config)
    except Exception as exc:
        return error(f"Test fehlgeschlagen: {type(exc).__name__}", 500)
    if not delivered:
        return error("Kein Gerät hat die Nachricht angenommen. Bitte Push auf diesem Gerät neu aktivieren.", 409)
    return success({"delivered": delivered})


@push_bp.route("/dispatch", methods=["POST"])
def push_dispatch():
    """Called by the scheduler. Requires PUSH_CRON_SECRET."""
    secret = os.environ.get("PUSH_CRON_SECRET", "").strip()
    given = request.headers.get("X-Cron-Secret", "")
    if not secret or not hmac.compare_digest(secret, given):
        return error("Nicht erlaubt.", 403)
    try:
        summary = dispatch()
    except Exception as exc:
        return error(f"Versand fehlgeschlagen: {type(exc).__name__}", 500)
    return success({"summary": summary})
