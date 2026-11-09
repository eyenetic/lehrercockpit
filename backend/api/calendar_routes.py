"""
Kalender-Abo (Präfix /api/v2/calendar) – die Termine des Cockpits im eigenen
Kalender (Apple, Outlook, Google), siehe backend/calendar_feed.py.

    GET    ""                  → {"active", "url", "webcal", "level"}
    POST   ""     {"level"}    → neuer geheimer Link (der alte gilt nicht mehr)
    PATCH  ""     {"level"}    → Stufe für den Orgaplan ändern
    DELETE ""                  → Abo beenden
    GET    /feed/<token>.ics   → die Kalenderdatei (ohne Anmeldung, der Link ist der Schlüssel)
"""
from __future__ import annotations

from flask import Blueprint, Response, g, request

from backend import calendar_feed
from backend.api.auth_routes import limiter
from backend.api.helpers import error, require_auth, success
from backend.db import db_connection

calendar_bp = Blueprint("calendar", __name__)


def _links(token: str) -> dict[str, str]:
    url = f"{request.host_url.rstrip('/')}/api/v2/calendar/feed/{token}.ics"
    if request.headers.get("X-Forwarded-Proto", "") == "https" and url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return {"url": url, "webcal": "webcal://" + url.split("://", 1)[1]}


@calendar_bp.route("", methods=["GET"])
@require_auth
def feed_status():
    try:
        with db_connection() as conn:
            feed = calendar_feed.load(conn, g.current_user.id)
    except Exception as exc:
        return error(f"Kalender-Abo konnte nicht geladen werden: {type(exc).__name__}", 500)
    if not feed or not feed["token"]:
        return success({"active": False})
    return success({"active": True, "level": feed["level"],
                    "last_fetch_at": feed["last_fetch_at"].isoformat() if feed["last_fetch_at"] else None,
                    **_links(feed["token"])})


@calendar_bp.route("", methods=["POST"])
@require_auth
@limiter.limit("20 per hour")
def feed_create():
    level = calendar_feed.clean_level((request.get_json(silent=True) or {}).get("level"))
    with db_connection() as conn:
        token = calendar_feed.create(conn, g.current_user.id, level)
    return success({"active": True, "level": level, "last_fetch_at": None, **_links(token)})


@calendar_bp.route("", methods=["PATCH"])
@require_auth
def feed_level():
    level = calendar_feed.clean_level((request.get_json(silent=True) or {}).get("level"))
    with db_connection() as conn:
        if not calendar_feed.set_level(conn, g.current_user.id, level):
            return error("Noch kein Kalender-Abo eingerichtet.", 404)
    return success({"level": level})


@calendar_bp.route("", methods=["DELETE"])
@require_auth
def feed_delete():
    with db_connection() as conn:
        calendar_feed.delete(conn, g.current_user.id)
    return success({"active": False})


@calendar_bp.route("/feed/<token>.ics", methods=["GET"])
@limiter.limit("600 per hour")  # iCloud fetches many subscriptions from shared addresses
def feed_ics(token: str):
    with db_connection() as conn:
        owner = calendar_feed.owner_of(conn, token)
        if not owner:
            return Response("Dieser Kalender-Link gilt nicht (mehr).\n", status=404, mimetype="text/plain")
        events = calendar_feed.collect(conn, owner[0], owner[1])
    resp = Response(calendar_feed.build_ics(events), mimetype="text/calendar")
    resp.headers["Content-Disposition"] = 'inline; filename="lehrercockpit.ics"'
    resp.headers["Cache-Control"] = "private, max-age=900"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp
