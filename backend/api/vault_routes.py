"""
Datentresor (Präfix /api/v2/vault): Klassenlisten, Einsammlungen, eigene Links
und Einstellungen liegen im Browser. Damit sie auf einem neuen Gerät wieder
da sind, legt der Browser eine Kopie hier ab – verschlüsselt mit einem
Schlüssel, der nur im Browser aus dem Zugangscode entsteht (AES-GCM,
PBKDF2). Der Server speichert nur den unlesbaren Block.

    GET  ""   → {"vault": {"iv", "ciphertext", "version", "updated_at"} | null}
    PUT  ""   {"iv", "ciphertext", "base_version"} → 409 mit dem aktuellen Stand,
              wenn ein anderes Gerät inzwischen gespeichert hat
"""
from __future__ import annotations

import re

from flask import Blueprint, g, request

from backend.api.auth_routes import limiter
from backend.api.helpers import error, require_auth, success
from backend.db import db_connection

vault_bp = Blueprint("vault", __name__)

MAX_CIPHERTEXT = 3_000_000  # base64 characters
_BASE64 = re.compile(r"^[A-Za-z0-9+/=_-]*$")


def _load(conn, user_id: int):
    row = conn.execute(
        "SELECT iv, ciphertext, version, updated_at FROM user_vault WHERE user_id = %s", (user_id,)
    ).fetchone()
    if not row:
        return None
    return {"iv": row[0], "ciphertext": row[1], "version": row[2], "updated_at": row[3].isoformat() if row[3] else None}


@vault_bp.route("", methods=["GET"])
@require_auth
def get_vault():
    try:
        with db_connection() as conn:
            vault = _load(conn, g.current_user.id)
    except Exception as exc:
        return error(f"Tresor konnte nicht geladen werden: {type(exc).__name__}", 500)
    return success({"vault": vault})


@vault_bp.route("", methods=["PUT"])
@require_auth
@limiter.limit("240 per hour")
def put_vault():
    body = request.get_json(silent=True) or {}
    iv = body.get("iv")
    ciphertext = body.get("ciphertext")
    base_version = body.get("base_version")
    if not isinstance(iv, str) or not isinstance(ciphertext, str) or not iv or not ciphertext:
        return error("Ungültiger Tresor-Inhalt.", 422)
    if len(iv) > 64 or len(ciphertext) > MAX_CIPHERTEXT or not _BASE64.match(iv) or not _BASE64.match(ciphertext):
        return error("Der Tresor ist zu groß oder beschädigt.", 422)
    if not isinstance(base_version, int) or base_version < 0:
        return error("Ungültige Version.", 422)
    try:
        with db_connection() as conn:
            current = conn.execute(
                "SELECT version FROM user_vault WHERE user_id = %s FOR UPDATE", (g.current_user.id,)
            ).fetchone()
            current_version = current[0] if current else 0
            if current_version != base_version:
                return {"error": "Ein anderes Gerät hat inzwischen gespeichert.",
                        "vault": _load(conn, g.current_user.id)}, 409
            conn.execute(
                """INSERT INTO user_vault (user_id, iv, ciphertext, version, updated_at)
                   VALUES (%s, %s, %s, %s, NOW())
                   ON CONFLICT (user_id) DO UPDATE SET iv = EXCLUDED.iv, ciphertext = EXCLUDED.ciphertext,
                       version = EXCLUDED.version, updated_at = NOW()""",
                (g.current_user.id, iv, ciphertext, current_version + 1),
            )
    except Exception as exc:
        return error(f"Tresor konnte nicht gespeichert werden: {type(exc).__name__}", 500)
    return success({"version": current_version + 1})
