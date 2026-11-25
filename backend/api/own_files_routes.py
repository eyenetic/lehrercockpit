"""Anhänge an eigenen Terminen und Aufgaben (nur verschlüsselte Bytes, siehe backend/own_files.py).

POST   /api/v2/files            Body: die verschlüsselte Datei → {id, size, used, quota}
GET    /api/v2/files/usage      → {used, quota}
GET    /api/v2/files/<id>       → die verschlüsselten Bytes (nur für die eigene Lehrkraft)
DELETE /api/v2/files/<id>
"""
from __future__ import annotations

import re

from flask import Blueprint, Response, g, request

from backend import own_files
from backend.api.auth_routes import limiter
from backend.api.helpers import error, require_auth, success
from backend.db import db_connection

own_files_bp = Blueprint("own_files", __name__)
_ID = re.compile(r"^[A-Za-z0-9_-]{10,40}$")


@own_files_bp.route("", methods=["POST"])
@require_auth
@limiter.limit("60 per hour")
def upload():
    if (request.content_length or 0) > own_files.MAX_FILE_BYTES:
        return error("Die Datei ist zu groß (höchstens 10 MB).", 413)
    data = request.get_data(cache=False)
    with db_connection() as conn:
        result = own_files.add(conn, g.current_user.id, data)
    if isinstance(result, str):
        return error(result, 413 if "groß" in result or "voll" in result else 422)
    return success(result, 201)


@own_files_bp.route("/usage", methods=["GET"])
@require_auth
def usage():
    with db_connection() as conn:
        used = own_files.used(conn, g.current_user.id)
    return success({"used": used, "quota": own_files.QUOTA_BYTES})


@own_files_bp.route("/<file_id>", methods=["GET"])
@require_auth
@limiter.limit("300 per hour")
def download(file_id: str):
    if not _ID.match(file_id):
        return error("Nicht gefunden.", 404)
    with db_connection() as conn:
        data = own_files.load(conn, g.current_user.id, file_id)
    if data is None:
        return error("Nicht gefunden.", 404)
    resp = Response(data, mimetype="application/octet-stream")
    resp.headers["Cache-Control"] = "private, max-age=86400"   # unreadable without the key in the entry
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@own_files_bp.route("/<file_id>", methods=["DELETE"])
@require_auth
def remove(file_id: str):
    if not _ID.match(file_id):
        return error("Nicht gefunden.", 404)
    with db_connection() as conn:
        own_files.delete(conn, g.current_user.id, file_id)
        used = own_files.used(conn, g.current_user.id)
    return success({"used": used, "quota": own_files.QUOTA_BYTES})
