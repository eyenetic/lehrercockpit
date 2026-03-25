"""
Gemeinsame Helpers für API-Routen: Auth-Decorators, Response-Helpers.
"""
import functools
import os as _os
from typing import Optional, Dict, Any

from flask import request, jsonify, g

from backend.db import db_connection
from backend.auth.session import get_session, refresh_session
from backend.users.user_store import get_user_by_id

SESSION_COOKIE_NAME = "lc_session"

# True when DATABASE_URL is set (= production / Render deployment)
_IS_PROD = bool(_os.environ.get("DATABASE_URL", "").strip())


def get_current_user():
    """Gibt den aktuell eingeloggten User zurück oder None."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None
    try:
        with db_connection() as conn:
            session = get_session(conn, session_id)
            if not session:
                return None
            refresh_session(conn, session_id)
            return get_user_by_id(conn, session.user_id)
    except Exception:
        return None


def require_auth(f):
    """Decorator: gibt 401 zurück wenn kein gültiger eingeloggter User vorhanden."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "Nicht angemeldet"}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    """Decorator: gibt 403 zurück wenn kein Admin, 401 wenn nicht eingeloggt."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "Nicht angemeldet"}), 401
        if not user.is_admin:
            return jsonify({"error": "Keine Berechtigung"}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper


def set_session_cookie(response, session_id: str):
    """Setzt HttpOnly Session-Cookie.

    In Produktion (DATABASE_URL gesetzt): Secure=True, SameSite=None
    (erforderlich für Cross-Origin-Requests Netlify → Render).
    In Entwicklung: Secure=False, SameSite=Lax.
    """
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        max_age=30 * 24 * 3600,  # 30 Tage
        httponly=True,
        secure=_IS_PROD,
        samesite="None" if _IS_PROD else "Lax",
        path="/",
    )
    return response


def clear_session_cookie(response):
    """Löscht den Session-Cookie."""
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


def success(data: Optional[Dict[str, Any]] = None, status: int = 200):
    """Erstellt eine Erfolgs-Response mit {"ok": true, ...data}."""
    payload: Dict[str, Any] = {"ok": True}
    if data:
        payload.update(data)
    return jsonify(payload), status


def error(message: str, status: int = 400):
    """Erstellt eine Fehler-Response mit {"error": message}."""
    return jsonify({"error": message}), status


# ── Shared config masking ─────────────────────────────────────────────────────

# Sensitive field name patterns — values are masked in GET responses
_SENSITIVE_PATTERNS = {"password", "secret", "token", "credential"}


def mask_config(config: dict) -> dict:
    """Gibt eine Kopie des config-dicts zurück, in der sensible Felder durch '***' ersetzt sind.

    Ein Feld gilt als sensibel wenn sein Name (lowercase) einen der _SENSITIVE_PATTERNS enthält.
    Felder mit 'enc:'-Präfix (verschlüsselt) werden ebenfalls maskiert.
    """
    masked = {}
    for key, value in config.items():
        key_lower = key.lower()
        is_sensitive = any(pattern in key_lower for pattern in _SENSITIVE_PATTERNS)
        # Also mask encrypted values (enc: prefix) to avoid leaking ciphertext
        is_encrypted = isinstance(value, str) and value.startswith("enc:")
        masked[key] = "***" if ((is_sensitive or is_encrypted) and value) else value
    return masked
