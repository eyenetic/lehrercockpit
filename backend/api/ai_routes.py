"""
KI-Assistent: Tageszusammenfassung und Fragen an das Cockpit.

GET  /api/v2/ai/status     → verfügbar? eingeschaltet? Nutzung heute
PUT  /api/v2/ai/settings   {"enabled": bool}  (Opt-in je Lehrkraft)
POST /api/v2/ai/briefing   {"refresh": bool}  → {"lines": [...], "cached": bool}
POST /api/v2/ai/chat       {"question": "...", "history": [{"role", "content"}]} → {"answer": "..."}
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, g, request

from backend import ai_assistant as ai
from backend.api.helpers import error, require_auth, success
from backend.db import db_connection
from backend.ical_utils import BERLIN
from backend.signal_store import load_prefs, save_prefs

ai_bp = Blueprint("ai", __name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _modules(user_id: int) -> dict:
    from backend.api.dashboard_routes import recent_modules
    from backend.push_service import _collect_modules

    return recent_modules(user_id) or _collect_modules(user_id)


def _context(user_id: int, prefs: dict, now: datetime) -> str:
    from backend.signals import build_signals

    modules = _modules(user_id)
    signals, classes = build_signals(modules, now, prefs.get("classes") or [])
    return ai.build_context(modules, signals, classes, now)


def _guard(prefs: dict):
    if not ai.available():
        return error("Der KI-Assistent ist auf diesem Server nicht eingerichtet.", 503)
    if not prefs.get("ai_enabled"):
        return error("Der KI-Assistent ist für dich noch nicht eingeschaltet (unter „Verbindungen“).", 403)
    return None


@ai_bp.route("/status", methods=["GET"])
@require_auth
def ai_status():
    today = _now().astimezone(BERLIN).date()
    try:
        with db_connection() as conn:
            prefs = load_prefs(conn, g.current_user.id)
            usage = ai.usage_today(conn, g.current_user.id, today) if ai.available() else {}
    except Exception as exc:
        return error(f"Status konnte nicht geladen werden: {type(exc).__name__}", 500)
    return success({
        "available": ai.available(),
        "enabled": bool(prefs.get("ai_enabled")),
        "model": ai.MODEL,
        "usage": usage,
        "limits": {"briefings": ai.MAX_BRIEFINGS_PER_DAY, "questions": ai.MAX_QUESTIONS_PER_DAY},
    })


@ai_bp.route("/settings", methods=["PUT"])
@require_auth
def ai_settings():
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("enabled"), bool):
        return error("enabled muss true oder false sein.", 422)
    try:
        with db_connection() as conn:
            prefs = load_prefs(conn, g.current_user.id)
            prefs["ai_enabled"] = body["enabled"]
            save_prefs(conn, g.current_user.id, prefs)
    except Exception as exc:
        return error(f"Speichern fehlgeschlagen: {type(exc).__name__}", 500)
    return success({"enabled": body["enabled"]})


@ai_bp.route("/briefing", methods=["POST"])
@require_auth
def ai_briefing():
    user_id = g.current_user.id
    body = request.get_json(silent=True) or {}
    now = _now()
    today = now.astimezone(BERLIN).date()
    try:
        with db_connection() as conn:
            prefs = load_prefs(conn, user_id)
            cached = ai.cached_briefing(conn, user_id)
            usage = ai.usage_today(conn, user_id, today) if ai.available() else {}
    except Exception as exc:
        return error(f"Status konnte nicht geladen werden: {type(exc).__name__}", 500)
    blocked = _guard(prefs)
    if blocked:
        return blocked

    context = _context(user_id, prefs, now)
    digest = ai.context_hash(context)
    if not body.get("refresh") and ai.briefing_is_fresh(cached, today, digest, now):
        return success({"lines": cached["lines"], "cached": True, "generated_at": cached["created_at"].isoformat()})
    if usage.get("briefings", 0) >= ai.MAX_BRIEFINGS_PER_DAY:
        if cached and cached["day"] == today:
            return success({"lines": cached["lines"], "cached": True, "limited": True,
                            "generated_at": cached["created_at"].isoformat()})
        return error("Das Tageslimit für Zusammenfassungen ist erreicht.", 429)

    try:
        lines, tokens = ai.generate_briefing(context)
    except ai.AIError as exc:
        return error(str(exc), exc.status)
    try:
        with db_connection() as conn:
            ai.store_briefing(conn, user_id, today, digest, lines, now)
            ai.record_usage(conn, user_id, today, "briefing", tokens)
    except Exception:
        pass  # the briefing itself succeeded; caching/usage are best effort
    return success({"lines": lines, "cached": False, "generated_at": now.isoformat()})


@ai_bp.route("/chat", methods=["POST"])
@require_auth
def ai_chat():
    user_id = g.current_user.id
    body = request.get_json(silent=True) or {}
    question = str(body.get("question") or "").strip()
    if not question:
        return error("Bitte eine Frage eingeben.", 422)
    now = _now()
    today = now.astimezone(BERLIN).date()
    try:
        with db_connection() as conn:
            prefs = load_prefs(conn, user_id)
            usage = ai.usage_today(conn, user_id, today) if ai.available() else {}
    except Exception as exc:
        return error(f"Status konnte nicht geladen werden: {type(exc).__name__}", 500)
    blocked = _guard(prefs)
    if blocked:
        return blocked
    if usage.get("questions", 0) >= ai.MAX_QUESTIONS_PER_DAY:
        return error("Das Tageslimit für Fragen ist erreicht. Morgen geht es weiter.", 429)

    try:
        answer, tokens = ai.answer_question(_context(user_id, prefs, now), body.get("history"), question)
    except ai.AIError as exc:
        return error(str(exc), exc.status)
    try:
        with db_connection() as conn:
            ai.record_usage(conn, user_id, today, "question", tokens)
    except Exception:
        pass
    return success({"answer": answer})
