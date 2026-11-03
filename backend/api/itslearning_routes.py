"""itslearning: Anhänge von Kalendereinträgen mit dem eigenen Login der Lehrkraft.

GET /api/v2/itslearning/attachment?url=… → die Datei (Bilder inline, sonst als Download)

Der Browser kann itslearning-Anhänge nicht selbst laden (dort ist er nicht
angemeldet). Hat die Lehrkraft unter Verbindungen ihren itslearning-Login
hinterlegt, holt der Server die Datei damit ab. Nur itslearning-Adressen,
nur übliche Datei-Arten, nichts wird gespeichert.
"""
from __future__ import annotations

from flask import Blueprint, Response, g, request

from backend.api.auth_routes import limiter
from backend.api.helpers import error, require_auth
from backend.db import db_connection
from backend.http_utils import UnsafeUrlError, require_public_https_url
from backend.modules.module_registry import get_user_module_config

itslearning_bp = Blueprint("itslearning", __name__)


@itslearning_bp.route("/attachment", methods=["GET"])
@require_auth
@limiter.limit("120 per minute")
def attachment():
    from backend.config import ItslearningSettings
    from backend.itslearning_adapter import attachment_host_allowed, fetch_attachment
    from backend.itslearning_module import DEFAULT_BASE_URL, _origin

    url = (request.args.get("url") or "").strip()
    with db_connection() as conn:
        config = get_user_module_config(conn, g.current_user.id, "itslearning") or {}
    username = str(config.get("username") or "").strip()
    password = str(config.get("password") or "")
    if not (username and password):
        return error("Für Anhänge braucht das Cockpit deinen itslearning-Login (Verbindungen → itslearning).", 404)
    base_url = _origin(str(config.get("base_url") or config.get("server_url") or "")) or DEFAULT_BASE_URL
    if not attachment_host_allowed(url, base_url):
        return error("Kein itslearning-Anhang.", 422)
    try:
        require_public_https_url(url)
        content, ctype, inline = fetch_attachment(
            ItslearningSettings(base_url=base_url, username=username, password=password, max_updates=1), url)
    except (UnsafeUrlError, ValueError) as exc:
        return error(str(exc), 422)
    except Exception as exc:
        return error(f"Der Anhang konnte nicht geladen werden ({type(exc).__name__}).", 502)

    resp = Response(content, mimetype=ctype)
    resp.headers["Cache-Control"] = "private, max-age=3600"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    if not inline:
        resp.headers["Content-Disposition"] = "attachment"
    return resp
