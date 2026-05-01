"""
backend/mailer.py — SMTP-E-Mail-Versand für Lehrercockpit.

Konfiguration via Umgebungsvariablen:
    SMTP_HOST       z.B. smtp.gmail.com oder smtp.office365.com
    SMTP_PORT       Standard: 587 (STARTTLS)
    SMTP_USER       Benutzername / Absender-Adresse
    SMTP_PASSWORD   Passwort oder App-Passwort
    SMTP_FROM       Absender-Adresse (optional, fällt auf SMTP_USER zurück)
    SMTP_USE_TLS    true/false (Standard: true → STARTTLS auf Port 587)

Unterstützte Provider (Beispiele):
    Gmail:          smtp.gmail.com:587, App-Passwort erforderlich
    Outlook/Office: smtp.office365.com:587
    Hotmail:        smtp-mail.outlook.com:587
    Ionos/1&1:      smtp.ionos.de:587
    eigener Server: beliebig
"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from backend.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_TLS


class MailerNotConfiguredError(Exception):
    """Wird geworfen wenn SMTP nicht konfiguriert ist."""


def is_configured() -> bool:
    """Gibt True zurück wenn SMTP vollständig konfiguriert ist."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_mail(
    to: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
) -> None:
    """Sendet eine E-Mail via SMTP.

    Args:
        to:         Empfänger-Adresse.
        subject:    Betreff.
        body_html:  HTML-Body.
        body_text:  Plaintext-Fallback (optional, wird aus HTML abgeleitet wenn leer).

    Raises:
        MailerNotConfiguredError: Wenn SMTP_HOST/USER/PASSWORD fehlen.
        smtplib.SMTPException:    Bei Verbindungs- oder Authentifizierungsfehlern.
    """
    if not is_configured():
        raise MailerNotConfiguredError(
            "SMTP nicht konfiguriert. Bitte SMTP_HOST, SMTP_USER und SMTP_PASSWORD setzen."
        )

    from_addr = SMTP_FROM or SMTP_USER

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Lehrercockpit <{from_addr}>"
    msg["To"]      = to

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    if SMTP_USE_TLS:
        # STARTTLS (Port 587, empfohlen)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(from_addr, [to], msg.as_bytes())
    else:
        # SSL direkt (Port 465)
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(from_addr, [to], msg.as_bytes())


def send_reset_mail(to: str, reset_url: str, user_name: str) -> None:
    """Sendet die Passwort-Reset-E-Mail.

    Args:
        to:         Empfänger-Adresse.
        reset_url:  Vollständige Reset-URL mit Token.
        user_name:  Vorname des Users für die Anrede.
    """
    subject = "Lehrercockpit – Zugangscode zurücksetzen"

    body_html = f"""
<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;color:#1a1a1a;max-width:480px;margin:0 auto;padding:24px;">
  <h2 style="color:#4f46e5;margin-bottom:8px;">Zugangscode zurücksetzen</h2>
  <p>Hallo {user_name},</p>
  <p>du hast angefordert, deinen Zugangscode zurückzusetzen. Klicke auf den Button, um einen neuen Code zu vergeben:</p>
  <p style="text-align:center;margin:28px 0;">
    <a href="{reset_url}"
       style="background:#4f46e5;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:1rem;">
      Neuen Code vergeben
    </a>
  </p>
  <p style="color:#666;font-size:0.85rem;">
    Dieser Link ist <strong>15 Minuten</strong> gültig und kann nur einmal verwendet werden.<br>
    Wenn du keinen Reset angefordert hast, kannst du diese E-Mail ignorieren.
  </p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;">
  <p style="color:#999;font-size:0.75rem;">Lehrercockpit – Dein digitales Lehrerbuch</p>
</body>
</html>
"""

    body_text = (
        f"Hallo {user_name},\n\n"
        f"du hast angefordert, deinen Zugangscode zurückzusetzen.\n\n"
        f"Klicke auf diesen Link (gültig 15 Minuten):\n{reset_url}\n\n"
        f"Wenn du keinen Reset angefordert hast, ignoriere diese E-Mail.\n\n"
        f"Lehrercockpit"
    )

    send_mail(to, subject, body_html, body_text)
