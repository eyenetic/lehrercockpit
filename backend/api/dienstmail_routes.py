"""Dienstmail: Text einer einzelnen Mail auf Klick (nur lesen, nichts gespeichert).

GET /api/v2/dienstmail/messages/<uid> → {text, truncated, attachments}
GET /api/v2/dienstmail/messages/<uid>/attachments/<n> → the n-th attachment (opened, not stored)
"""
from __future__ import annotations

from urllib.parse import quote

from flask import Blueprint, Response, g

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


@dienstmail_bp.route("/messages/<uid>/attachments/<int:index>", methods=["GET"])
@require_auth
@limiter.limit("30 per minute")
def read_attachment(uid: str, index: int):
    with db_connection() as conn:
        config = get_user_module_config(conn, g.current_user.id, "mail")
    if not dienstmail.is_configured(config):
        return error("Die Dienstmail ist nicht verbunden.", 404)
    try:
        name, ctype, data = dienstmail.fetch_attachment(str(config["address"]), str(config["app_password"]), uid, index)
    except dienstmail.DienstmailError as exc:
        return error(str(exc), 422)
    except Exception as exc:
        return error(f"Der Anhang konnte nicht geladen werden ({type(exc).__name__}).", 502)
    inline = ctype in dienstmail.INLINE_TYPES
    resp = Response(data, mimetype=ctype if inline else "application/octet-stream")
    resp.headers["Content-Disposition"] = f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(name)}"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    if ctype != "application/pdf":  # browsers refuse to show PDFs under a sandbox policy
        resp.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"
    return resp
