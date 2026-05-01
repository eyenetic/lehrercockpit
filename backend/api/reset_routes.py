"""
backend/api/reset_routes.py — Passwort-Reset via E-Mail.

Endpunkte:
    POST /api/request-reset   { "email": "..." }
        → Generiert Token, schickt E-Mail (immer 200, auch wenn E-Mail unbekannt)
    GET  /api/reset-info?token=...
        → Prüft Token, gibt user_name zurück (für Frontend-Anzeige)
    POST /api/reset-code      { "token": "...", "new_code": "..." }
        → Setzt neuen Code, invalidiert Token

Rate-Limiting: 3 Requests/Minute pro IP auf /request-reset.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from backend.db import db_connection
from backend.auth.access_code import hash_code, get_code_prefix
from backend.users.user_store import set_access_code
from backend.migrations import log_audit_event
from backend.mailer import send_reset_mail, is_configured as smtp_configured
from backend.api.helpers import success, error
from backend.config import FRONTEND_URL

reset_bp = Blueprint("reset", __name__)
limiter  = Limiter(key_func=get_remote_address, default_limits=[])

TOKEN_TTL_MINUTES = 15


# ── Helper ─────────────────────────────────────────────────────────────────────

def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _get_user_by_email(conn, email: str):
    """Sucht aktiven User mit dieser E-Mail (case-insensitive)."""
    row = conn.execute(
        """
        SELECT id, first_name, last_name, email
        FROM users
        WHERE LOWER(email) = LOWER(%s) AND is_active = TRUE
        LIMIT 1
        """,
        (email,),
    ).fetchone()
    return row  # (id, first_name, last_name, email) or None


def _create_reset_token(conn, user_id: int) -> str:
    """Erstellt einen neuen Reset-Token (invalidiert alte für diesen User)."""
    # Alte Token für diesen User löschen
    conn.execute(
        "DELETE FROM password_reset_tokens WHERE user_id = %s",
        (user_id,),
    )
    token = _generate_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES)
    conn.execute(
        """
        INSERT INTO password_reset_tokens (user_id, token, expires_at)
        VALUES (%s, %s, %s)
        """,
        (user_id, token, expires_at),
    )
    return token


def _get_valid_token_row(conn, token: str):
    """Gibt Token-Row zurück wenn gültig (nicht abgelaufen, nicht genutzt)."""
    row = conn.execute(
        """
        SELECT prt.user_id, prt.expires_at, prt.used,
               u.first_name, u.last_name, u.email
        FROM password_reset_tokens prt
        JOIN users u ON u.id = prt.user_id
        WHERE prt.token = %s
        """,
        (token,),
    ).fetchone()
    if not row:
        return None
    user_id, expires_at, used, first_name, last_name, email = row
    if used:
        return None
    if expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None
    return {"user_id": user_id, "first_name": first_name, "last_name": last_name, "email": email}


# ── Endpunkte ──────────────────────────────────────────────────────────────────

@reset_bp.route("/request-reset", methods=["POST"])
@limiter.limit("3 per minute")
def request_reset():
    """Startet den Reset-Prozess.

    Antwortet immer mit 200 (kein User-Enumeration-Risiko).
    Wenn SMTP nicht konfiguriert: 503.
    """
    if not smtp_configured():
        return error("E-Mail-Versand nicht konfiguriert. Bitte Administrator kontaktieren.", 503)

    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()

    if not email or "@" not in email:
        return error("Bitte eine gültige E-Mail-Adresse eingeben.", 422)

    try:
        with db_connection() as conn:
            user_row = _get_user_by_email(conn, email)
            if user_row:
                user_id, first_name, last_name, user_email = user_row
                token = _create_reset_token(conn, user_id)
                reset_url = f"{FRONTEND_URL}/?reset_token={token}"
                try:
                    send_reset_mail(user_email, reset_url, first_name)
                    log_audit_event(conn, "password_reset_requested", user_id=user_id,
                                    ip_address=request.remote_addr)
                except Exception as mail_exc:
                    # Token wurde erstellt, Mail-Fehler loggen aber User nicht informieren
                    print(f"[reset] Mail-Fehler: {mail_exc}", flush=True)
                    return error("E-Mail konnte nicht versendet werden. Bitte Administrator kontaktieren.", 503)
        # Immer gleiche Antwort (kein User-Enumeration)
        return success({"message": "Falls ein Account mit dieser E-Mail existiert, wurde ein Reset-Link versendet."})
    except Exception as exc:
        return error(f"Fehler: {type(exc).__name__}", 500)


@reset_bp.route("/reset-info", methods=["GET"])
def reset_info():
    """Prüft Token und gibt Vorname zurück (für Frontend-Anzeige).

    Query: ?token=...
    Response: { ok: true, first_name: "..." } oder 400/404
    """
    token = (request.args.get("token") or "").strip()
    if not token:
        return error("Token fehlt.", 400)

    try:
        with db_connection() as conn:
            row = _get_valid_token_row(conn, token)
            if not row:
                return error("Ungültiger oder abgelaufener Reset-Link.", 404)
            return success({"first_name": row["first_name"]})
    except Exception as exc:
        return error(f"Fehler: {type(exc).__name__}", 500)


@reset_bp.route("/reset-code", methods=["POST"])
@limiter.limit("5 per minute")
def reset_code():
    """Setzt neuen Code anhand eines gültigen Tokens.

    Body: { "token": "...", "new_code": "..." }
    Regeln: mind. 8 Zeichen, nur Buchstaben und Ziffern.
    """
    body = request.get_json(silent=True) or {}
    token    = (body.get("token") or "").strip()
    new_code = (body.get("new_code") or "").strip()

    if not token:
        return error("Token fehlt.", 400)
    if not new_code or len(new_code) < 8:
        return error("Der Code muss mindestens 8 Zeichen haben.", 422)
    if not new_code.isalnum():
        return error("Der Code darf nur Buchstaben und Ziffern enthalten.", 422)

    try:
        with db_connection() as conn:
            row = _get_valid_token_row(conn, token)
            if not row:
                return error("Ungültiger oder abgelaufener Reset-Link.", 404)

            user_id = row["user_id"]

            # Neuen Code setzen
            code_hash = hash_code(new_code)
            prefix    = get_code_prefix(new_code)
            set_access_code(conn, user_id, code_hash, code_prefix=prefix)

            # Token als genutzt markieren
            conn.execute(
                "UPDATE password_reset_tokens SET used = TRUE WHERE token = %s",
                (token,),
            )

            # Alle Sessions invalidieren (Sicherheit)
            conn.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))

            log_audit_event(conn, "password_reset_completed", user_id=user_id,
                            ip_address=request.remote_addr)

        return success({"message": "Zugangscode erfolgreich geändert."})
    except Exception as exc:
        return error(f"Fehler: {type(exc).__name__}", 500)
