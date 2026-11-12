"""„Neu im Cockpit“ und Erinnerungen an offene Einladungen."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import backend.api.auth_routes as auth_routes
import backend.api.helpers
import backend.api.invitation_routes as invitation_routes
from backend import invitations, news

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(auth_routes.auth_bp, url_prefix="/api/v2/auth")
    app.register_blueprint(invitation_routes.invitation_admin_bp, url_prefix="/api/v2/admin/invitations")
    return app.test_client()


def _db():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _user(created_at=datetime(2026, 10, 18, tzinfo=timezone.utc), admin=False):
    user = MagicMock(id=7, is_active=True, is_admin=admin, role="admin" if admin else "teacher", created_at=created_at)
    user.to_dict.return_value = {"id": 7, "first_name": "Test"}
    return user


def test_frontend_and_backend_use_the_same_news_id():
    js = (ROOT / "src/features/news.js").read_text(encoding="utf-8")
    assert re.search(r"var ID = '([^']+)'", js).group(1) == news.NEWS_ID


def test_index_loads_news_before_the_auth_check():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert html.index("src/features/news.js") < html.index("async function checkAuth")
    assert "LehrerNews.maybeShow" in html
    assert html.count("data-open-news") == 2


def test_existing_accounts_see_the_news_once():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    assert news.seen(conn, 7, datetime(2026, 10, 18, tzinfo=timezone.utc)) is False
    conn.execute.return_value.fetchone.return_value = (1,)
    assert news.seen(conn, 7, datetime(2026, 10, 18, tzinfo=timezone.utc)) is True


def test_new_accounts_skip_the_news():
    conn = MagicMock()
    assert news.seen(conn, 7, news.SINCE + timedelta(hours=1)) is True
    assert news.seen(conn, 7, (news.SINCE + timedelta(days=1)).replace(tzinfo=None)) is True
    conn.execute.assert_not_called()


def test_me_reports_news_and_never_fails(client):
    with patch.object(backend.api.helpers, "get_current_user", return_value=_user()), \
            patch.object(auth_routes, "db_connection", return_value=_db()), \
            patch.object(auth_routes.terms, "accepted_at", return_value=None), \
            patch.object(news, "seen", return_value=False):
        data = client.get("/api/v2/auth/me").get_json()
    assert data["user"]["news"] == {"id": news.NEWS_ID, "seen": False}

    with patch.object(backend.api.helpers, "get_current_user", return_value=_user()), \
            patch.object(auth_routes, "db_connection", side_effect=RuntimeError("DB weg")):
        data = client.get("/api/v2/auth/me").get_json()
    assert data["user"]["news"]["seen"] is True


def test_marking_news_as_seen(client):
    with patch.object(backend.api.helpers, "get_current_user", return_value=_user()), \
            patch.object(auth_routes, "db_connection", return_value=_db()), \
            patch.object(news, "mark_seen") as mark:
        assert client.post("/api/v2/auth/me/news", json={"id": "alt"}).status_code == 422
        mark.assert_not_called()
        assert client.post("/api/v2/auth/me/news", json={"id": news.NEWS_ID}).status_code == 200
    assert mark.call_args.args[1] == 7


def _invite(**extra):
    base = {"id": 3, "kind": "personal", "name": "Erika Muster", "email": "erika@example.org", "token": "alt",
            "created_at": datetime(2026, 10, 18, tzinfo=timezone.utc),
            "expires_at": datetime(2026, 11, 1, tzinfo=timezone.utc), "revoked_at": None, "uses": 0,
            "last_used_at": None, "used_by": None, "access_request_id": None, "created_by": 1}
    base.update(extra)
    return base


def test_reminder_replaces_the_old_link_for_the_same_person(client):
    fresh = _invite(id=9, token="neu", created_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=14))
    with patch.object(backend.api.helpers, "get_current_user", return_value=_user(admin=True)), \
            patch.object(invitation_routes, "db_connection", return_value=_db()), \
            patch.object(invitation_routes, "log_audit_event"), \
            patch.object(invitations, "get", return_value=_invite()), \
            patch.object(invitations, "revoke") as revoke, \
            patch.object(invitations, "create", return_value=fresh) as create:
        response = client.post("/api/v2/admin/invitations/3/renew")
    assert response.status_code == 201
    revoke.assert_called_once()
    assert revoke.call_args.args[1] == 3
    assert create.call_args.kwargs["name"] == "Erika Muster"
    assert create.call_args.kwargs["email"] == "erika@example.org"
    assert response.get_json()["invitation"]["link"].endswith("#einladung=neu")


def test_no_reminder_for_accepted_invitations_or_non_admins(client):
    with patch.object(backend.api.helpers, "get_current_user", return_value=_user(admin=True)), \
            patch.object(invitation_routes, "db_connection", return_value=_db()), \
            patch.object(invitations, "get", return_value=_invite(uses=1)), \
            patch.object(invitations, "create") as create:
        assert client.post("/api/v2/admin/invitations/3/renew").status_code == 409
    create.assert_not_called()

    with patch.object(backend.api.helpers, "get_current_user", return_value=_user()):
        assert client.post("/api/v2/admin/invitations/3/renew").status_code == 403
