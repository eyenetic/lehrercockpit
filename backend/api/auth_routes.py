"""
Auth-Endpunkte: Login, Logout, aktueller User.
"""
from flask import Blueprint, request, g

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from backend.db import db_connection
from backend.auth.session import create_session, delete_session
from backend.users.user_service import authenticate_by_code, code_taken
from backend.users.user_store import set_access_code
from backend.auth.access_code import chosen_code_problem, hash_code, get_code_prefix
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

    if not code or not isinstance(code, str) or len(code.strip()) < 6:
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

    Sends Clear-Site-Data: "cache", "cookies", "storage" so the browser
    discards all cached assets, session cookies and localStorage on logout.

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
    # Tell the browser to wipe cache, cookies and storage for this origin on logout.
    # Supported in Chrome/Edge/Firefox; Safari ignores the header gracefully.
    resp.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
    return resp, resp_tuple[1]


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    """Gibt den aktuell eingeloggten User zurück.

    Response 200: {"ok": true, "user": {...}}
    """
    return success({"user": g.current_user.to_dict()})


@auth_bp.route("/me/change-code", methods=["POST"])
@require_auth
@limiter.limit("10 per hour")
def change_my_code():
    """Zugangscode für den eingeloggten User ändern.

    Body: {"current_code": "...", "new_code": "..."}
    Der aktuelle Code wird geprüft (eine offen gelassene Sitzung reicht nicht).
    Regeln: mind. 8 Zeichen, nur Buchstaben und Ziffern, von keinem anderen Konto benutzt.
    Andere Sitzungen des Kontos werden abgemeldet.
    """
    from backend.auth.access_code import verify_code
    from backend.users.user_store import get_access_code_hash

    body = request.get_json(silent=True) or {}
    current_code = str(body.get("current_code") or "").strip()
    new_code = str(body.get("new_code") or "").strip()

    if not new_code:
        return error("Neuer Code erforderlich", 422)
    problem = chosen_code_problem(new_code)
    if problem:
        return error(problem, 422)

    try:
        with db_connection() as conn:
            stored = get_access_code_hash(conn, g.current_user.id)
            if not stored or not current_code or not verify_code(current_code, stored):
                log_audit_event(conn, "code_change_failed", user_id=g.current_user.id,
                                ip_address=request.remote_addr)
                return error("Der aktuelle Code stimmt nicht.", 403)
            if new_code == current_code:
                return error("Der neue Code ist derselbe wie der alte.", 422)
            if code_taken(conn, new_code, g.current_user.id):
                return error("Diesen Code kannst du nicht verwenden. Bitte wähle einen anderen.", 409)
            set_access_code(conn, g.current_user.id, hash_code(new_code), code_prefix=get_code_prefix(new_code))
            conn.execute("DELETE FROM sessions WHERE user_id = %s AND id <> %s",
                         (g.current_user.id, request.cookies.get(SESSION_COOKIE_NAME, "")))
            log_audit_event(
                conn,
                "code_rotated",
                user_id=g.current_user.id,
                ip_address=request.remote_addr,
                details={"self_service": True},
            )
        return success()
    except Exception as exc:
        return error(f"Fehler beim Ändern des Codes: {type(exc).__name__}", 500)


@auth_bp.route("/me/verify-code", methods=["POST"])
@require_auth
@limiter.limit("10 per hour")
def verify_my_code():
    """Prüft den eigenen Zugangscode (z. B. bevor der Browser daraus den Tresor-Schlüssel ableitet)."""
    from backend.auth.access_code import verify_code
    from backend.users.user_store import get_access_code_hash

    code = str((request.get_json(silent=True) or {}).get("code") or "").strip()
    try:
        with db_connection() as conn:
            stored = get_access_code_hash(conn, g.current_user.id)
    except Exception as exc:
        return error(f"Prüfung fehlgeschlagen: {type(exc).__name__}", 500)
    if not code or not stored or not verify_code(code, stored):
        return error("Der Code stimmt nicht.", 403)
    return success()


@auth_bp.route("/me/account", methods=["GET"])
@require_auth
def my_account():
    """Eigene Kontodaten inkl. E-Mail (für „Code vergessen“)."""
    from backend import mailer

    return success({"account": {
        "full_name": g.current_user.full_name,
        "email": g.current_user.email or "",
        "mail_reset": mailer.is_configured(),
    }})


@auth_bp.route("/me/email", methods=["PUT"])
@require_auth
@limiter.limit("20 per hour")
def change_my_email():
    """E-Mail für „Code vergessen“ hinterlegen oder entfernen. Body: {"email": "..."}"""
    email = str((request.get_json(silent=True) or {}).get("email") or "").strip().lower()[:200]
    if email and ("@" not in email or " " in email or "." not in email.split("@")[-1]):
        return error("Die E-Mail-Adresse sieht nicht vollständig aus.", 422)
    try:
        with db_connection() as conn:
            if email and conn.execute("SELECT 1 FROM users WHERE LOWER(email) = %s AND id <> %s",
                                      (email, g.current_user.id)).fetchone():
                return error("Diese E-Mail gehört schon zu einem anderen Konto.", 409)
            conn.execute("UPDATE users SET email = %s, updated_at = NOW() WHERE id = %s",
                         (email or None, g.current_user.id))
    except Exception as exc:
        return error(f"Konnte nicht gespeichert werden: {type(exc).__name__}", 500)
    return success({"email": email})
