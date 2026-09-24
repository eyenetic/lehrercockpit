"""Tests für /api/v2/ai (Opt-in, Tageslimit, Zwischenspeicher)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import backend.api.ai_routes as routes
import backend.api.helpers

NOW = datetime(2026, 9, 23, 5, 30, tzinfo=timezone.utc)


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(routes.ai_bp, url_prefix="/api/v2/ai")
    return app.test_client()


def _teacher():
    user = MagicMock()
    user.id = 9
    user.is_active = True
    return user


def _db():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _call(client, method, path, *, prefs=None, usage=None, cached=None, available=True, **kwargs):
    with patch.object(backend.api.helpers, "get_current_user", return_value=_teacher()), \
            patch.object(routes, "db_connection", return_value=_db()), \
            patch.object(routes, "load_prefs", return_value=dict(prefs or {})), \
            patch.object(routes, "save_prefs") as save, \
            patch.object(routes.ai, "available", return_value=available), \
            patch.object(routes.ai, "usage_today", return_value=usage or {"briefings": 0, "questions": 0}), \
            patch.object(routes.ai, "cached_briefing", return_value=cached), \
            patch.object(routes.ai, "store_briefing"), patch.object(routes.ai, "record_usage"), \
            patch.object(routes, "_context", return_value="KONTEXT"), \
            patch.object(routes, "_now", return_value=NOW):
        response = getattr(client, method)(path, **kwargs)
    return response, save


def test_status_reports_opt_in(client):
    response, _ = _call(client, "get", "/api/v2/ai/status", prefs={"ai_enabled": True})
    body = response.get_json()
    assert body["available"] is True and body["enabled"] is True
    assert body["limits"] == {"briefings": 8, "questions": 30}


def test_settings_store_opt_in(client):
    response, save = _call(client, "put", "/api/v2/ai/settings", json={"enabled": True})
    assert response.status_code == 200
    assert save.call_args.args[2] == {"ai_enabled": True}


def test_features_require_server_key_and_opt_in(client):
    assert _call(client, "post", "/api/v2/ai/briefing", json={}, available=False)[0].status_code == 503
    assert _call(client, "post", "/api/v2/ai/briefing", json={})[0].status_code == 403
    assert _call(client, "post", "/api/v2/ai/chat", json={"question": "x"})[0].status_code == 403


def test_briefing_is_generated_once_and_then_reused(client):
    with patch.object(routes.ai, "generate_briefing", return_value=(["Punkt"], {"input": 1, "output": 1})) as gen:
        fresh, _ = _call(client, "post", "/api/v2/ai/briefing", json={}, prefs={"ai_enabled": True})
        digest = routes.ai.context_hash("KONTEXT")
        cached = {"day": NOW.date(), "context_hash": digest, "lines": ["Alt"], "created_at": NOW}
        reused, _ = _call(client, "post", "/api/v2/ai/briefing", json={}, prefs={"ai_enabled": True}, cached=cached)
    assert fresh.get_json()["lines"] == ["Punkt"] and fresh.get_json()["cached"] is False
    assert reused.get_json() == {"ok": True, "lines": ["Alt"], "cached": True, "generated_at": NOW.isoformat()}
    assert gen.call_count == 1


def test_daily_limits(client):
    response, _ = _call(client, "post", "/api/v2/ai/chat", json={"question": "Wann?"},
                        prefs={"ai_enabled": True}, usage={"briefings": 0, "questions": 30})
    assert response.status_code == 429
    response, _ = _call(client, "post", "/api/v2/ai/briefing", json={"refresh": True},
                        prefs={"ai_enabled": True}, usage={"briefings": 8, "questions": 0})
    assert response.status_code == 429


def test_chat_answers_and_maps_errors(client):
    with patch.object(routes.ai, "answer_question", return_value=("Am Fr.", {"input": 1, "output": 1})):
        ok, _ = _call(client, "post", "/api/v2/ai/chat", json={"question": "Wann?"}, prefs={"ai_enabled": True})
    assert ok.get_json()["answer"] == "Am Fr."
    with patch.object(routes.ai, "answer_question", side_effect=routes.ai.AIError("ausgelastet", 429)):
        busy, _ = _call(client, "post", "/api/v2/ai/chat", json={"question": "Wann?"}, prefs={"ai_enabled": True})
    assert busy.status_code == 429 and busy.get_json()["error"] == "ausgelastet"
    empty, _ = _call(client, "post", "/api/v2/ai/chat", json={"question": "  "}, prefs={"ai_enabled": True})
    assert empty.status_code == 422
