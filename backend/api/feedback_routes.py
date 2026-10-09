"""
Rückmeldungen an die Admins (Probleme, Ideen, Fragen, Lob).

Lehrkräfte (Präfix /api/v2/feedback):
    GET  ""        → eigene Rückmeldungen mit Status und Antwort
    POST ""        {"kind", "message", "context"?}
    POST /seen     → Antworten als gelesen markieren
Admins:
    GET    /admin          → alle Rückmeldungen und Zähler je Status
    PATCH  /admin/<id>     {"status"?, "reply"?}
    DELETE /admin/<id>
"""
from __future__ import annotations

from flask import Blueprint, g, request

from backend import feedback
from backend.api.auth_routes import limiter
from backend.api.helpers import error, require_admin, require_auth, success
from backend.db import db_connection

feedback_bp = Blueprint("feedback", __name__)

_CONTEXT_KEYS = ("section", "version", "viewport", "theme")


def _context() -> dict:
    raw = (request.get_json(silent=True) or {}).get("context") or {}
    context = {key: str(raw[key])[:60] for key in _CONTEXT_KEYS if isinstance(raw, dict) and raw.get(key)}
    context["browser"] = (request.headers.get("User-Agent") or "")[:200]
    return context


@feedback_bp.route("", methods=["GET"])
@require_auth
def my_feedback():
    try:
        with db_connection() as conn:
            items = feedback.list_for_user(conn, g.current_user.id)
    except Exception as exc:
        return error(f"Rückmeldungen konnten nicht geladen werden: {type(exc).__name__}", 500)
    return success({"items": items, "unread": sum(1 for item in items if item["unread"])})


@feedback_bp.route("", methods=["POST"])
@require_auth
@limiter.limit("20 per hour")
def send_feedback():
    body = request.get_json(silent=True) or {}
    kind, message = body.get("kind"), body.get("message")
    problem = feedback.validate(kind, message)
    if problem:
        return error(problem, 422)
    try:
        with db_connection() as conn:
            item = feedback.create(conn, g.current_user.id, kind, message, _context())
    except Exception as exc:
        return error(f"Rückmeldung konnte nicht gespeichert werden: {type(exc).__name__}", 500)

    try:
        from backend.push_service import notify_in_background
        text = " ".join(message.split())
        notify_in_background({
            "title": f"{feedback.KINDS[kind]} von {g.current_user.first_name}",
            "body": text[:140] + ("…" if len(text) > 140 else ""),
            "url": "/admin.html#rueckmeldungen", "tag": f"feedback-{item['id']}",
        }, admins=True)
    except Exception:
        pass
    try:
        from backend.api.invitation_routes import frontend_base
        feedback.mail_admins_in_background(kind, g.current_user.first_name or "einer Lehrkraft", message,
                                           frontend_base() + "/admin.html#rueckmeldungen")
    except Exception:
        pass
    return success({"item": item}, 201)


@feedback_bp.route("/seen", methods=["POST"])
@require_auth
def feedback_seen():
    try:
        with db_connection() as conn:
            feedback.mark_seen(conn, g.current_user.id)
    except Exception as exc:
        return error(f"Konnte nicht gespeichert werden: {type(exc).__name__}", 500)
    return success()


@feedback_bp.route("/admin", methods=["GET"])
@require_admin
def all_feedback():
    try:
        with db_connection() as conn:
            items = feedback.list_all(conn)
            counts = feedback.counts(conn)
    except Exception as exc:
        return error(f"Rückmeldungen konnten nicht geladen werden: {type(exc).__name__}", 500)
    return success({"items": items, "counts": counts, "kinds": feedback.KINDS, "statuses": feedback.STATUSES})


@feedback_bp.route("/admin/<int:feedback_id>", methods=["PATCH"])
@require_admin
def update_feedback(feedback_id: int):
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    reply = body.get("reply")
    if status is not None and status not in feedback.STATUSES:
        return error("Unbekannter Status.", 422)
    if reply is not None and not isinstance(reply, str):
        return error("Ungültige Antwort.", 422)
    try:
        with db_connection() as conn:
            before = feedback.get(conn, feedback_id, for_admin=True)
            item = feedback.update(conn, feedback_id, status=status, reply=reply)
    except Exception as exc:
        return error(f"Konnte nicht gespeichert werden: {type(exc).__name__}", 500)
    if item is None:
        return error("Rückmeldung nicht gefunden.", 404)

    if item["reply"] and item["reply"] != (before or {}).get("reply") and item.get("user_id"):
        try:
            from backend.push_service import notify_in_background
            notify_in_background({"title": "Antwort auf deine Rückmeldung",
                                  "body": item["reply"][:140] + ("…" if len(item["reply"]) > 140 else ""),
                                  "url": "/#rueckmeldung", "tag": f"feedback-reply-{item['id']}"},
                                 user_id=item["user_id"])
        except Exception:
            pass
    return success({"item": item})


@feedback_bp.route("/admin/<int:feedback_id>", methods=["DELETE"])
@require_admin
def delete_feedback(feedback_id: int):
    try:
        with db_connection() as conn:
            deleted = feedback.delete(conn, feedback_id)
    except Exception as exc:
        return error(f"Konnte nicht gelöscht werden: {type(exc).__name__}", 500)
    if not deleted:
        return error("Rückmeldung nicht gefunden.", 404)
    return success()
