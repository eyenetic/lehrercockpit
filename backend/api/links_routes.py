"""
Links für das ganze Kollegium (Präfix /api/v2/links) – z. B. der Bearbeitungs-
link zum Klassenarbeitsplan, der nicht öffentlich auf der Webseite steht.
Eigene Links der Lehrkräfte liegen im Browser (verschlüsselter Tresor).

    GET    ""        → {"school": [...], "can_edit_school": bool}
    POST   ""        {"title", "url"}   (nur Admins)
    DELETE /<id>                        (nur Admins)
"""
from __future__ import annotations

from flask import Blueprint, g, request

from backend import links
from backend.api.helpers import error, require_admin, require_auth, success
from backend.db import db_connection

links_bp = Blueprint("links", __name__)


@links_bp.route("", methods=["GET"])
@require_auth
def list_links():
    try:
        with db_connection() as conn:
            school = links.school_links(conn)
    except Exception as exc:
        return error(f"Links konnten nicht geladen werden: {type(exc).__name__}", 500)
    return success({"school": school, "can_edit_school": bool(g.current_user.is_admin)})


@links_bp.route("", methods=["POST"])
@require_admin
def add_link():
    body = request.get_json(silent=True) or {}
    cleaned = links.clean(body.get("title"), body.get("url"))
    if isinstance(cleaned, str):
        return error(cleaned, 422)
    try:
        with db_connection() as conn:
            result = links.add_school_link(conn, title=cleaned[0], url=cleaned[1])
    except Exception as exc:
        return error(f"Link konnte nicht gespeichert werden: {type(exc).__name__}", 500)
    if isinstance(result, str):
        return error(result, 409)
    return success({"link": result}, 201)


@links_bp.route("/<int:link_id>", methods=["DELETE"])
@require_admin
def delete_link(link_id: int):
    try:
        with db_connection() as conn:
            removed = links.remove_school_link(conn, link_id)
    except Exception as exc:
        return error(f"Link konnte nicht entfernt werden: {type(exc).__name__}", 500)
    if not removed:
        return error("Link nicht gefunden.", 404)
    return success()
