"""Nutzungsbedingungen: Zustimmung bei der Einrichtung und für bestehende Konten."""
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import backend.api.auth_routes as auth_routes
import backend.api.helpers
import backend.api.invitation_routes as invitation_routes
from backend import terms

ROOT = Path(__file__).resolve().parents[1]
WHEN = datetime(2026, 11, 10, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(auth_routes.auth_bp, url_prefix="/api/v2/auth")
    app.register_blueprint(invitation_routes.invitation_public_bp, url_prefix="/api/v2/auth")
    return app.test_client()


def _db():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _user():
    user = MagicMock(id=7, is_active=True, is_admin=False)
    user.to_dict.return_value = {"id": 7, "first_name": "Test"}
    return user


def test_frontend_and_backend_use_the_same_version():
    js = (ROOT / "src/features/terms.js").read_text(encoding="utf-8")
    assert re.search(r"var VERSION = '([^']+)'", js).group(1) == terms.VERSION


def test_me_reports_whether_the_current_version_was_accepted(client):
    with patch.object(backend.api.helpers, "get_current_user", return_value=_user()), \
            patch.object(auth_routes, "db_connection", return_value=_db()), \
            patch.object(terms, "accepted_at", return_value=None):
        data = client.get("/api/v2/auth/me").get_json()
    assert data["user"]["terms"] == {"version": terms.VERSION, "accepted": False, "accepted_at": None}


def test_me_never_locks_out_when_the_check_fails(client):
    with patch.object(backend.api.helpers, "get_current_user", return_value=_user()), \
            patch.object(auth_routes, "db_connection", side_effect=RuntimeError("DB weg")):
        data = client.get("/api/v2/auth/me").get_json()
    assert data["user"]["terms"]["accepted"] is True


def test_accepting_needs_the_current_version_and_is_recorded(client):
    with patch.object(backend.api.helpers, "get_current_user", return_value=_user()), \
            patch.object(auth_routes, "db_connection", return_value=_db()), \
            patch.object(auth_routes, "log_audit_event") as audit, \
            patch.object(terms, "accept") as accept, \
            patch.object(terms, "accepted_at", return_value=WHEN):
        assert client.post("/api/v2/auth/me/terms", json={"accept": True, "version": "alt"}).status_code == 422
        assert client.post("/api/v2/auth/me/terms", json={"version": terms.VERSION}).status_code == 422
        accept.assert_not_called()

        response = client.post("/api/v2/auth/me/terms", json={"accept": True, "version": terms.VERSION})
    assert response.status_code == 200
    assert response.get_json()["terms"]["accepted_at"] == WHEN.isoformat()
    accept.assert_called_once()
    assert accept.call_args.args[1] == 7
    assert audit.call_args.args[1] == "terms_accepted"
    assert "ip_address" not in audit.call_args.kwargs


def test_accepting_requires_login(client):
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        assert client.post("/api/v2/auth/me/terms", json={"accept": True, "version": terms.VERSION}).status_code == 401


def test_setting_up_an_account_without_agreeing_is_refused(client):
    body = {"token": "t", "first_name": "A", "last_name": "B", "code": "ein-guter-code-123"}
    with patch.object(invitation_routes, "db_connection") as db:
        assert client.post("/api/v2/auth/invitation/accept", json=body).status_code == 422
        body.update(accept_terms=True, terms_version="alt")
        assert client.post("/api/v2/auth/invitation/accept", json=body).status_code == 422
    db.assert_not_called()


def test_record_is_idempotent_sql():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (WHEN,)
    assert terms.accept(conn, 7) == WHEN
    sql = conn.execute.call_args_list[0].args[0]
    assert "ON CONFLICT (user_id, version) DO NOTHING" in sql
    assert conn.execute.call_args_list[0].args[1] == (7, terms.VERSION)
