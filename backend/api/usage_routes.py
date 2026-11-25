"""Nutzung zählen (Tagessummen, ohne IP und ohne Personenbezug) und für Admins anzeigen.

POST /api/v2/usage/event  {"event": "open", "device": "phone|desktop|app"}   – angemeldet
                          {"event": "invite"}                                 – Einladungsseite
                          {"event": "video", "video": "<id>", "ended": bool}
GET  /api/v2/usage/admin?days=28  → Tageszahlen und Wochensummen (nur Admins)
"""
from __future__ import annotations

import logging

from flask import Blueprint, request

from backend import usage
from backend.api.auth_routes import limiter
from backend.api import helpers
from backend.api.helpers import error, require_admin, success
from backend.db import db_connection

usage_bp = Blueprint("usage", __name__)
log = logging.getLogger(__name__)


@usage_bp.route("/event", methods=["POST"])
@limiter.limit("120 per hour")
def record_event():
    body = request.get_json(silent=True) or {}
    event = str(body.get("event") or "")
    try:
        if event == "open":
            user = helpers.get_current_user()
            if not user or not user.is_active:
                return error("Nicht angemeldet", 401)
            with db_connection() as conn:
                usage.record_open(conn, user.id, str(body.get("device") or ""))
        elif event == "invite":
            with db_connection() as conn:
                usage.bump(conn, "invite")
        elif event == "video":
            with db_connection() as conn:
                if not usage.record_video(conn, str(body.get("video") or ""), bool(body.get("ended"))):
                    return error("Unbekanntes Video.", 400)
        else:
            return error("Unbekanntes Ereignis.", 400)
    except Exception as exc:  # counting must never bother anyone
        log.warning("usage event %s not counted: %s", event, exc)
    return "", 204


@usage_bp.route("/admin", methods=["GET"])
@require_admin
def admin_summary():
    try:
        days = int(request.args.get("days", 28))
    except ValueError:
        days = 28
    with db_connection() as conn:
        data = usage.summary(conn, days)
    resp, status = success(data)
    resp.headers["Cache-Control"] = "no-store"
    return resp, status
