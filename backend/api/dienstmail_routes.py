"""Dienstmail: Text einer einzelnen Mail auf Klick (nur lesen, nichts gespeichert).

GET /api/v2/dienstmail/messages/<uid> → {text, truncated, attachments}
"""
from __future__ import annotations

from flask import Blueprint, g

from backend import dienstmail
from backend.api.auth_routes import limiter
from backend.api.helpers import error, require_auth, success
from backend.db import db_connection
from backend.modules.module_registry import get_user_module_config

dienstmail_bp = Blueprint("dienstmail", __name__)


@dienstmail_bp.route("/messages/<uid>", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def read_message(uid: str):
    with db_connection() as conn:
        config = get_user_module_config(conn, g.current_user.id, "mail")
    if not dienstmail.is_configured(config):
        return error("Die Dienstmail ist nicht verbunden.", 404)
    try:
        message = dienstmail.fetch_message(str(config["address"]), str(config["app_password"]), uid)
    except dienstmail.DienstmailError as exc:
        return error(str(exc), 422)
    except Exception as exc:
        return error(f"Die Mail konnte nicht gelesen werden ({type(exc).__name__}).", 502)
    resp, status = success({"message": message})
    resp.headers["Cache-Control"] = "no-store"
    return resp, status
