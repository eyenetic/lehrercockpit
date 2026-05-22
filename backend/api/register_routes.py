"""
Registrierungsanfragen (Waitlist) – öffentlicher Endpunkt.

POST /api/v2/register-interest  – Anfrage stellen
"""
from flask import Blueprint, request

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from backend.db import db_connection
from backend.api.helpers import success, error

register_bp = Blueprint("register", __name__)

_limiter = Limiter(key_func=get_remote_address, default_limits=[])


@register_bp.route("/register-interest", methods=["POST"])
@_limiter.limit("3 per hour")
def register_interest():
    """Interesse / Zugangswunsch registrieren.

    Body: {"name": "...", "email": "..."}

    Response 200: {"ok": true, "message": "Danke! ..."}
    Response 409: {"error": "E-Mail bereits vorhanden"} – wenn doppelt
    Response 422: {"error": "..."} – bei Validierungsfehlern
    """
    body = request.get_json(silent=True) or {}
    name  = str(body.get("name", "")).strip()
    email = str(body.get("email", "")).strip().lower()

    if not name:
        return error("Name ist erforderlich", 422)
    if not email or "@" not in email:
        return error("Gültige E-Mail-Adresse ist erforderlich", 422)

    try:
        with db_connection() as conn:
            # Bereits in access_requests (pending oder approved)?
            existing_req = conn.execute(
                """
                SELECT id, status FROM access_requests
                WHERE LOWER(email) = %s AND status IN ('pending', 'approved')
                LIMIT 1
                """,
                (email,),
            ).fetchone()

            if existing_req:
                status = existing_req[1]
                if status == "approved":
                    return error(
                        "Diese E-Mail wurde bereits freigeschaltet. "
                        "Bitte prüfe deinen Posteingang nach deinem Zugangscode.",
                        409,
                    )
                return error(
                    "Für diese E-Mail besteht bereits eine offene Anfrage. "
                    "Wir melden uns in Kürze!",
                    409,
                )

            # Bereits in users-Tabelle?
            existing_user = conn.execute(
                "SELECT id FROM users WHERE LOWER(email) = %s LIMIT 1",
                (email,),
            ).fetchone()

            if existing_user:
                return error(
                    "Diese E-Mail ist bereits als Konto registriert. "
                    "Bitte melde dich direkt an.",
                    409,
                )

            # Eintrag anlegen
            conn.execute(
                "INSERT INTO access_requests (name, email) VALUES (%s, %s)",
                (name, email),
            )

        # Bestätigungsmail senden (nur wenn SMTP konfiguriert)
        try:
            from backend import mailer
            if mailer.is_configured():
                _send_confirmation_mail(email, name)
        except Exception as _mail_exc:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "[register] Bestätigungsmail fehlgeschlagen: %s", _mail_exc
            )

        return success({
            "message": (
                "Danke! Wir haben deine Anfrage erhalten und schalten "
                "dich in Kürze frei. Du bekommst dann eine E-Mail mit "
                "deinem persönlichen Zugangscode."
            )
        })

    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).error("[register] Fehler: %s", exc)
        return error(f"Fehler beim Speichern der Anfrage: {type(exc).__name__}", 500)


def _send_confirmation_mail(to: str, name: str) -> None:
    """Sendet die Bestätigungsmail an den Interessenten."""
    from backend.mailer import send_mail

    subject = "Willkommen bei Lehrer-Cockpit 👋"

    body_html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;color:#1a1a1a;max-width:480px;margin:0 auto;padding:24px;">
  <h2 style="color:#4f46e5;margin-bottom:8px;">Willkommen bei Lehrer-Cockpit!</h2>
  <p>Hallo {name},</p>
  <p>schön, dass du dabei sein willst!</p>
  <p>
    Wir haben deine Anfrage erhalten und schalten dich in Kürze frei.
    Du bekommst dann eine E-Mail mit deinem persönlichen Zugangscode.
  </p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;">
  <p style="color:#999;font-size:0.75rem;">Dein Lehrer-Cockpit Team</p>
</body>
</html>"""

    body_text = (
        f"Hallo {name},\n\n"
        "schön, dass du dabei sein willst!\n\n"
        "Wir haben deine Anfrage erhalten und schalten dich in Kürze frei.\n"
        "Du bekommst dann eine E-Mail mit deinem persönlichen Zugangscode.\n\n"
        "Dein Lehrer-Cockpit Team"
    )

    send_mail(to, subject, body_html, body_text)
