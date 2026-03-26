"""
Auth-Endpunkte: Login, Logout, aktueller User.
"""
from flask import Blueprint, request, g

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from backend.db import db_connection
from backend.auth.session import create_session, delete_session
from backend.users.user_service import authenticate_by_code
from backend.migrations import log_audit_event
from backend.api.helpers import (
    require_auth,
    set_session_cookie,
    clear_session_cookie,
    success,
    error,
    SESSION_COOKIE_NAME,
)
from backend.config import (
    LOGIN_RATE_LIMIT_MAX_PER_MINUTE,
    LOGIN_RATE_LIMIT_MAX,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS,
)

auth_bp = Blueprint("auth", __name__)

limiter = Limiter(key_func=get_remote_address, default_limits=[])


def _login_limit_string() -> str:
    """Builds a Flask-Limiter limit string from environment config.

    Returns e.g. "5 per minute;10 per 900 seconds".
    Evaluated at request time so changes to ENV vars take effect on restart.
    """
    return (
        f"{LOGIN_RATE_LIMIT_MAX_PER_MINUTE} per minute;"
        f"{LOGIN_RATE_LIMIT_MAX} per {LOGIN_RATE_LIMIT_WINDOW_SECONDS} seconds"
    )


@auth_bp.route("/login", methods=["POST"])
@limiter.limit(_login_limit_string)  # callable — evaluated at request time
def login():
    """Login mit Zugangscode.

    Body: {"code": "..."}
    Response 200: {"ok": true, "user": {...}}
    Response 401: {"error": "Ungültiger Zugangscode"}
    Response 422: {"error": "Code erforderlich"}
    """
    body = request.get_json(silent=True) or {}
    code = body.get("code", "")

    if not code or not isinstance(code, str) or len(code.strip()) < 8:
        return error("Code erforderlich", 422)

    code = code.strip()

    try:
        with db_connection() as conn:
            user = authenticate_by_code(conn, code)
            if not user or not user.is_active:
                log_audit_event(
                    conn,
                    "login_failure",
                    ip_address=request.remote_addr,
                    details={"reason": "invalid_code"},
                )
                return error("Ungültiger Zugangscode", 401)

            session = create_session(conn, user.id)
            log_audit_event(
                conn,
                "login_success",
                user_id=user.id,
                ip_address=request.remote_addr,
            )

        response_data = success({"user": user.to_dict()})
        # response_data is a tuple (response, status_code)
        resp = response_data[0]
        set_session_cookie(resp, session.id)
        return resp, response_data[1]
    except Exception as exc:
        return error(f"Login fehlgeschlagen: {type(exc).__name__}", 500)


@auth_bp.route("/logout", methods=["POST"])
@require_auth
def logout():
    """Logout: Session löschen und Cookie entfernen.

    Response 200: {"ok": true}
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    try:
        if session_id:
            with db_connection() as conn:
                delete_session(conn, session_id)
    except Exception:
        pass  # Immer ausloggen, auch wenn DB-Fehler

    resp_tuple = success()
    resp = resp_tuple[0]
    clear_session_cookie(resp)
    return resp, resp_tuple[1]


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    """Gibt den aktuell eingeloggten User zurück.

    Response 200: {"ok": true, "user": {...}}
    """
    return success({"user": g.current_user.to_dict()})
