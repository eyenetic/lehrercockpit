"""
TEMPORÄRER Notfall-Reset. Wird nach Nutzung sofort entfernt.
"""
from flask import Blueprint, request, jsonify
from backend.db import db_connection
from backend.auth.access_code import hash_code, get_code_prefix

emergency_bp = Blueprint("emergency", __name__)

_SECRET = "O5FU8vFtgrytFUOwwBl85eJ3TKtPQTdF"
_NEW_CODE = "Heg16042"


@emergency_bp.route("/api/emergency-reset", methods=["POST"])
def emergency_reset():
    body = request.get_json(silent=True) or {}
    if body.get("secret") != _SECRET:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    try:
        with db_connection() as conn:
            code_hash = hash_code(_NEW_CODE)
            prefix = get_code_prefix(_NEW_CODE)
            conn.execute(
                """INSERT INTO user_access_codes (user_id, code_hash, code_prefix)
                   VALUES (1, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE
                       SET code_hash = EXCLUDED.code_hash,
                           code_prefix = EXCLUDED.code_prefix""",
                (code_hash, prefix),
            )
            conn.execute("DELETE FROM sessions WHERE user_id = 1")
        return jsonify({"ok": True, "message": "Code zurückgesetzt auf: " + _NEW_CODE})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
