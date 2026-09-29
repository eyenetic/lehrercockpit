"""
Einladungslinks: Kolleg:innen legen ihr Konto mit einem Link selbst an.

Öffentlich (Präfix /api/v2/auth):
    POST /invitation          {"token"}                      → wofür der Link gilt
    POST /invitation/accept   {"token", "first_name", "last_name", "email"?, "code"}
                                                             → Konto anlegen und anmelden
Admins (Präfix /api/v2/admin/invitations):
    GET    ""                 → letzte Einladungen und der aktive Kollegiums-Link
    POST   ""                 {"kind": "personal"|"team", "name"?, "email"?, "send_mail"?}
    DELETE /<id>              → Link abschalten
"""
from __future__ import annotations

import logging
import os
from html import escape

from flask import Blueprint, g, request

from backend import invitations
from backend.admin.admin_service import get_system_setting
from backend.api.auth_routes import limiter
from backend.api.helpers import error, require_admin, set_session_cookie, success
from backend.auth.access_code import chosen_code_problem, get_code_prefix, hash_code
from backend.auth.session import create_session
from backend.db import db_connection
from backend.migrations import log_audit_event
from backend.modules.module_registry import initialize_user_modules
from backend.users.user_service import code_taken
from backend.users.user_store import create_user, set_access_code

log = logging.getLogger(__name__)

invitation_public_bp = Blueprint("invitation_public", __name__)
invitation_admin_bp = Blueprint("invitation_admin", __name__)

EXPIRED = "Dieser Einladungslink ist abgelaufen oder wurde schon benutzt. Bitte frag nach einem neuen Link."


def frontend_base() -> str:
    url = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")
    return url if url.startswith("https://") else "https://app.lehrercockpit.com"


def school_name(conn) -> str:
    for key in ("school_name", "schulname"):
        value = get_system_setting(conn, key, "")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return os.environ.get("SCHOOL_NAME", "").strip()


def _split_name(name: str) -> tuple[str, str]:
    parts = name.strip().rsplit(" ", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (name.strip(), "")


def _mail_enabled() -> bool:
    try:
        from backend import mailer
        return mailer.is_configured()
    except Exception:
        return False


def send_invitation_mail(to: str, name: str, link: str, school: str) -> bool:
    """Mail with the personal link. Returns True if it was sent."""
    if not to or not _mail_enabled():
        return False
    from backend.mailer import send_mail

    greeting = f"Hallo {name}," if name else "Hallo,"
    where = f" der {school}" if school else ""
    body_html = f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;color:#111;max-width:480px;margin:0 auto;padding:24px;">
  <p>{escape(greeting)}</p>
  <p>du bist ins Lehrercockpit{escape(where)} eingeladen: Stundenplan, Orgaplan, Klassenarbeiten
     und Nachrichten auf einen Blick.</p>
  <p style="margin:28px 0;">
    <a href="{escape(link)}" style="background:#1a56db;color:#fff;padding:12px 22px;border-radius:8px;
       text-decoration:none;font-weight:600;">Konto anlegen</a>
  </p>
  <p style="color:#666;font-size:0.85rem;">Der Link gilt {invitations.VALID_DAYS['personal']} Tage und nur für dich.</p>
</body></html>"""
    body_text = (f"{greeting}\n\ndu bist ins Lehrercockpit{where} eingeladen.\n\n"
                 f"Konto anlegen: {link}\n\nDer Link gilt {invitations.VALID_DAYS['personal']} Tage und nur für dich.\n")
    try:
        send_mail(to, "Deine Einladung ins Lehrercockpit", body_html, body_text)
        return True
    except Exception as exc:
        log.warning("[invitations] Einladungsmail fehlgeschlagen: %s", exc)
        return False


# ── Öffentlich ────────────────────────────────────────────────────────────────

@invitation_public_bp.route("/invitation", methods=["POST"])
@limiter.limit("30 per hour")
def invitation_info():
    token = str((request.get_json(silent=True) or {}).get("token") or "").strip()
    try:
        with db_connection() as conn:
            invite = invitations.find_usable(conn, token)
            if not invite:
                return error(EXPIRED, 410)
            school = school_name(conn)
            inviter = ""
            if invite.get("created_by"):
                row = conn.execute("SELECT first_name FROM users WHERE id = %s", (invite["created_by"],)).fetchone()
                inviter = row[0] if row else ""
    except Exception as exc:
        return error(f"Einladung konnte nicht geprüft werden: {type(exc).__name__}", 500)
    first, last = _split_name(invite.get("name") or "") if invite["kind"] == "personal" else ("", "")
    return success({"invitation": {
        "kind": invite["kind"],
        "first_name": first,
        "last_name": last,
        "email": invite.get("email") or "",
        "school_name": school,
        "inviter": inviter,
        "mail_reset": _mail_enabled(),
    }})


@invitation_public_bp.route("/invitation/accept", methods=["POST"])
@limiter.limit("10 per hour")
def accept_invitation():
    body = request.get_json(silent=True) or {}
    token = str(body.get("token") or "").strip()
    first = str(body.get("first_name") or "").strip()[:80]
    last = str(body.get("last_name") or "").strip()[:80]
    email = str(body.get("email") or "").strip().lower()[:200]
    code = str(body.get("code") or "").strip()

    if not first or not last:
        return error("Bitte gib Vor- und Nachnamen ein.", 422)
    if email and ("@" not in email or " " in email or "." not in email.split("@")[-1]):
        return error("Die E-Mail-Adresse sieht nicht vollständig aus.", 422)
    problem = chosen_code_problem(code)
    if problem:
        return error(problem, 422)

    try:
        with db_connection() as conn:
            invite = invitations.find_usable(conn, token, lock=True)
            if not invite:
                return error(EXPIRED, 410)
            if code_taken(conn, code):
                return error("Diesen Code kannst du nicht verwenden. Bitte wähle einen anderen.", 409)
            if email and conn.execute("SELECT 1 FROM users WHERE LOWER(email) = %s", (email,)).fetchone():
                return error("Zu dieser E-Mail gibt es schon ein Konto. Melde dich einfach mit deinem Code an.", 409)

            user = create_user(conn, first, last, "teacher", is_admin=False)
            set_access_code(conn, user.id, hash_code(code), code_prefix=get_code_prefix(code))
            if email:
                conn.execute("UPDATE users SET email = %s WHERE id = %s", (email, user.id))
            initialize_user_modules(conn, user.id)
            invitations.mark_used(conn, invite["id"], user.id)
            log_audit_event(conn, "invitation_accepted", user_id=user.id, ip_address=request.remote_addr,
                            details={"invitation_id": invite["id"], "kind": invite["kind"]})
            session = create_session(conn, user.id)
    except Exception as exc:
        return error(f"Konto konnte nicht angelegt werden: {type(exc).__name__}", 500)

    try:
        from backend.push_service import notify_in_background
        via = "den Kollegiums-Link" if invite["kind"] == "team" else "eine persönliche Einladung"
        notify_in_background({"title": "Neu im Lehrercockpit", "body": f"{first} {last} ist über {via} dazugekommen.",
                              "url": "/admin.html#nutzer", "tag": "new-user"}, admins=True)
    except Exception:
        pass

    resp, status = success({"user": user.to_dict()}, 201)
    set_session_cookie(resp, session.id)
    return resp, status


# ── Admins ────────────────────────────────────────────────────────────────────

@invitation_admin_bp.route("", methods=["GET"])
@require_admin
def list_invitations():
    try:
        with db_connection() as conn:
            items = invitations.list_recent(conn)
    except Exception as exc:
        return error(f"Einladungen konnten nicht geladen werden: {type(exc).__name__}", 500)
    base = frontend_base()
    views = [invitations.public_view(item, base) for item in items]
    team = next((view for view in views if view["kind"] == "team" and view["usable"]), None)
    return success({
        "invitations": [view for view in views if view["kind"] == "personal"],
        "team": team,
        "mail_enabled": _mail_enabled(),
        "valid_days": invitations.VALID_DAYS,
    })


@invitation_admin_bp.route("", methods=["POST"])
@require_admin
def create_invitation():
    body = request.get_json(silent=True) or {}
    kind = str(body.get("kind") or "personal")
    name = str(body.get("name") or "").strip()[:120]
    email = str(body.get("email") or "").strip().lower()[:200]
    if kind not in invitations.KINDS:
        return error("Unbekannte Art der Einladung.", 422)
    if email and "@" not in email:
        return error("Die E-Mail-Adresse sieht nicht vollständig aus.", 422)
    try:
        with db_connection() as conn:
            invite = invitations.create(conn, kind=kind, name=name if kind == "personal" else "",
                                        email=email if kind == "personal" else "", created_by=g.current_user.id)
            school = school_name(conn)
            log_audit_event(conn, "invitation_created", user_id=g.current_user.id, ip_address=request.remote_addr,
                            details={"invitation_id": invite["id"], "kind": kind})
    except Exception as exc:
        return error(f"Einladung konnte nicht erstellt werden: {type(exc).__name__}", 500)
    view = invitations.public_view(invite, frontend_base())
    mailed = bool(body.get("send_mail")) and kind == "personal" and send_invitation_mail(email, name, view["link"], school)
    return success({"invitation": view, "mailed": mailed}, 201)


@invitation_admin_bp.route("/<int:invite_id>", methods=["DELETE"])
@require_admin
def revoke_invitation(invite_id: int):
    try:
        with db_connection() as conn:
            if not invitations.revoke(conn, invite_id):
                return error("Einladung nicht gefunden oder schon abgeschaltet.", 404)
            log_audit_event(conn, "invitation_revoked", user_id=g.current_user.id, ip_address=request.remote_addr,
                            details={"invitation_id": invite_id})
    except Exception as exc:
        return error(f"Einladung konnte nicht abgeschaltet werden: {type(exc).__name__}", 500)
    return success()
