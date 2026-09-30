"""Einladungslinks und Rückmeldungen gegen eine echte Datenbank (Flask-Test-Client)."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.db


@pytest.fixture
def db_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        pytest.skip("DATABASE_URL nicht gesetzt")
    return url


@pytest.fixture
def app(db_url):
    import psycopg
    from flask import Flask

    import backend.api.auth_routes as auth_module
    from backend.api import register_blueprints
    from backend.migrations import _migrate_invitations_and_feedback, _migrate_signals_and_push, run_migrations

    with psycopg.connect(db_url) as conn:
        run_migrations(conn)
        _migrate_signals_and_push(conn)
        _migrate_invitations_and_feedback(conn)
        conn.commit()

    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    auth_module.limiter.init_app(flask_app)
    auth_module.limiter.reset()
    register_blueprints(flask_app)
    return flask_app


@pytest.fixture
def people(db_url):
    """An admin and a teacher with sessions; everything they create is removed afterwards."""
    import psycopg
    from backend.auth.session import create_session
    from backend.users.user_store import create_user

    created = {}
    with psycopg.connect(db_url) as conn:
        admin = create_user(conn, "Ada", "Admin", "teacher", is_admin=True)
        teacher = create_user(conn, "Tim", "Lehrer")
        created = {
            "admin": admin.id, "admin_session": create_session(conn, admin.id).id,
            "teacher": teacher.id, "teacher_session": create_session(conn, teacher.id).id,
        }
        conn.commit()
    yield created
    with psycopg.connect(db_url) as conn:
        conn.execute("DELETE FROM invitations WHERE created_by = %s", (created["admin"],))
        conn.execute("DELETE FROM users WHERE id IN (%s, %s) OR last_name LIKE 'Eingeladen%%'",
                     (created["admin"], created["teacher"]))
        conn.execute("DELETE FROM access_requests WHERE email LIKE '%%@einladung.test'")
        conn.execute("DELETE FROM user_links WHERE user_id IS NULL AND url LIKE 'https://1drv.ms/x/%%'")
        conn.commit()


def _client(app, session_id=None):
    client = app.test_client()
    if session_id:
        client.set_cookie("lc_session", session_id)
    return client


def _new_invite(app, people, **body):
    response = _client(app, people["admin_session"]).post("/api/v2/admin/invitations", json=body)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["invitation"]


# ── Einladungen ──────────────────────────────────────────────────────────────

def test_personal_invitation_creates_account_and_logs_in(app, people):
    invite = _new_invite(app, people, kind="personal", name="Clara Eingeladen-Eins")
    assert invite["token"] and invite["link"].endswith(invite["token"])
    assert "#einladung=" in invite["link"]

    guest = _client(app)
    info = guest.post("/api/v2/auth/invitation", json={"token": invite["token"]}).get_json()["invitation"]
    assert info["first_name"] == "Clara" and info["last_name"] == "Eingeladen-Eins"

    accepted = guest.post("/api/v2/auth/invitation/accept", json={
        "token": invite["token"], "first_name": "Clara", "last_name": "Eingeladen-Eins", "code": "Clara2026neu"})
    assert accepted.status_code == 201, accepted.get_json()
    assert "lc_session" in accepted.headers.get("Set-Cookie", "")
    me = guest.get("/api/v2/auth/me").get_json()["user"]
    assert me["full_name"] == "Clara Eingeladen-Eins" and me["is_admin"] is False

    # The new code works for login …
    login = _client(app).post("/api/v2/auth/login", json={"code": "Clara2026neu"})
    assert login.status_code == 200
    # … and a personal link works only once.
    again = _client(app).post("/api/v2/auth/invitation/accept", json={
        "token": invite["token"], "first_name": "X", "last_name": "Eingeladen-Zwei", "code": "Anderer2026x"})
    assert again.status_code == 410


def test_team_link_works_for_several_and_replaces_older_one(app, people):
    first = _new_invite(app, people, kind="team")
    second = _new_invite(app, people, kind="team")
    assert _client(app).post("/api/v2/auth/invitation", json={"token": first["token"]}).status_code == 410

    for index, code in enumerate(["TeamCode2026a", "TeamCode2026b"]):
        response = _client(app).post("/api/v2/auth/invitation/accept", json={
            "token": second["token"], "first_name": f"Team{index}", "last_name": "Eingeladen-Team", "code": code})
        assert response.status_code == 201, response.get_json()

    listing = _client(app, people["admin_session"]).get("/api/v2/admin/invitations").get_json()
    assert listing["team"]["id"] == second["id"] and listing["team"]["uses"] == 2


def test_accept_rejects_taken_and_weak_codes(app, people):
    invite = _new_invite(app, people, kind="personal", name="Doris Eingeladen-Drei")
    base = {"token": invite["token"], "first_name": "Doris", "last_name": "Eingeladen-Drei"}
    weak = _client(app).post("/api/v2/auth/invitation/accept", json={**base, "code": "kurz"})
    assert weak.status_code == 422

    _client(app).post("/api/v2/auth/invitation/accept", json={
        **base, "token": _new_invite(app, people, kind="personal")["token"], "code": "Doppelt2026"})
    taken = _client(app).post("/api/v2/auth/invitation/accept", json={**base, "code": "Doppelt2026"})
    assert taken.status_code == 409
    # the invitation is still usable after the rejected attempt
    assert _client(app).post("/api/v2/auth/invitation", json={"token": invite["token"]}).status_code == 200


def test_revoked_and_expired_links_do_not_work(app, people, db_url):
    import psycopg

    revoked = _new_invite(app, people, kind="personal")
    assert _client(app, people["admin_session"]).delete(f"/api/v2/admin/invitations/{revoked['id']}").status_code == 200
    assert _client(app).post("/api/v2/auth/invitation", json={"token": revoked["token"]}).status_code == 410

    expired = _new_invite(app, people, kind="personal")
    with psycopg.connect(db_url) as conn:
        conn.execute("UPDATE invitations SET expires_at = %s WHERE id = %s",
                     (datetime.now(timezone.utc) - timedelta(minutes=1), expired["id"]))
        conn.commit()
    assert _client(app).post("/api/v2/auth/invitation", json={"token": expired["token"]}).status_code == 410
    assert _client(app).post("/api/v2/auth/invitation", json={"token": "gibt-es-nicht"}).status_code == 410


def test_only_admins_manage_invitations(app, people):
    teacher = _client(app, people["teacher_session"])
    assert teacher.get("/api/v2/admin/invitations").status_code == 403
    assert teacher.post("/api/v2/admin/invitations", json={"kind": "team"}).status_code == 403
    assert _client(app).get("/api/v2/admin/invitations").status_code == 401


def test_approving_access_request_creates_personal_invitation(app, people, db_url):
    import psycopg

    with psycopg.connect(db_url) as conn:
        req_id = conn.execute(
            "INSERT INTO access_requests (name, email) VALUES ('Emil Eingeladen-Vier', 'emil@einladung.test') RETURNING id"
        ).fetchone()[0]
        conn.commit()
    with patch("backend.api.invitation_routes._mail_enabled", return_value=False):
        response = _client(app, people["admin_session"]).post(f"/api/v2/admin/access-requests/{req_id}/approve")
    body = response.get_json()
    assert response.status_code == 200, body
    assert body["mailed"] is False and body["invitation"]["email"] == "emil@einladung.test"

    info = _client(app).post("/api/v2/auth/invitation", json={"token": body["invitation"]["token"]}).get_json()
    assert info["invitation"]["email"] == "emil@einladung.test"
    assert _client(app, people["admin_session"]).post(
        f"/api/v2/admin/access-requests/{req_id}/approve").status_code == 409


# ── Rückmeldungen ────────────────────────────────────────────────────────────

def test_feedback_round_trip(app, people):
    teacher = _client(app, people["teacher_session"])
    admin = _client(app, people["admin_session"])

    assert teacher.post("/api/v2/feedback", json={"kind": "wunsch", "message": "Hallo"}).status_code == 422
    assert teacher.post("/api/v2/feedback", json={"kind": "idee", "message": " "}).status_code == 422

    created = teacher.post("/api/v2/feedback", json={
        "kind": "problem", "message": "Der Orgaplan lädt nicht.", "context": {"section": "documents", "evil": "x"}})
    assert created.status_code == 201
    item_id = created.get_json()["item"]["id"]

    listing = admin.get("/api/v2/feedback/admin").get_json()
    mine = next(item for item in listing["items"] if item["id"] == item_id)
    assert mine["user_name"] == "Tim Lehrer" and mine["status"] == "neu"
    assert mine["context"]["section"] == "documents" and "evil" not in mine["context"]
    assert listing["counts"]["neu"] >= 1

    assert teacher.get("/api/v2/feedback/admin").status_code == 403
    assert teacher.patch(f"/api/v2/feedback/admin/{item_id}", json={"status": "erledigt"}).status_code == 403

    replied = admin.patch(f"/api/v2/feedback/admin/{item_id}",
                          json={"status": "erledigt", "reply": "Behoben, danke!"}).get_json()["item"]
    assert replied["status"] == "erledigt" and replied["reply"] == "Behoben, danke!" and replied["replied_at"]

    own = teacher.get("/api/v2/feedback").get_json()
    assert own["unread"] == 1 and own["items"][0]["reply"] == "Behoben, danke!"
    assert "user_email" not in own["items"][0] and "context" not in own["items"][0]
    teacher.post("/api/v2/feedback/seen")
    assert teacher.get("/api/v2/feedback").get_json()["unread"] == 0

    assert admin.delete(f"/api/v2/feedback/admin/{item_id}").status_code == 200
    assert teacher.get("/api/v2/feedback").get_json()["items"] == []


# ── Links, Tresor, Konto ─────────────────────────────────────────────────────

def test_school_links_only_admins_edit(app, people):
    teacher = _client(app, people["teacher_session"])
    admin = _client(app, people["admin_session"])
    assert teacher.post("/api/v2/links", json={"title": "X", "url": "https://x.de"}).status_code == 403
    assert admin.post("/api/v2/links", json={"url": "javascript:alert(1)"}).status_code == 422
    created = admin.post("/api/v2/links", json={"title": "KA-Plan bearbeiten", "url": "https://1drv.ms/x/edit"})
    assert created.status_code == 201
    link = created.get_json()["link"]
    listing = teacher.get("/api/v2/links").get_json()
    assert any(item["id"] == link["id"] for item in listing["school"]) and listing["can_edit_school"] is False
    assert teacher.delete(f"/api/v2/links/{link['id']}").status_code == 403
    assert admin.delete(f"/api/v2/links/{link['id']}").status_code == 200


def test_vault_stores_only_ciphertext_and_detects_conflicts(app, people):
    teacher = _client(app, people["teacher_session"])
    assert teacher.get("/api/v2/vault").get_json()["vault"] is None
    first = teacher.put("/api/v2/vault", json={"iv": "aXY=", "ciphertext": "Y2lwaGVy", "base_version": 0})
    assert first.status_code == 200 and first.get_json()["version"] == 1
    stale = teacher.put("/api/v2/vault", json={"iv": "aXY=", "ciphertext": "b3RoZXI=", "base_version": 0})
    assert stale.status_code == 409 and stale.get_json()["vault"]["version"] == 1
    assert teacher.put("/api/v2/vault", json={"iv": "<script>", "ciphertext": "x", "base_version": 1}).status_code == 422
    vault = teacher.get("/api/v2/vault").get_json()["vault"]
    assert vault["ciphertext"] == "Y2lwaGVy" and vault["version"] == 1
    # other accounts never see it
    assert _client(app, people["admin_session"]).get("/api/v2/vault").get_json()["vault"] is None


def test_change_code_requires_current_code(app, people, db_url):
    import psycopg
    from backend.auth.access_code import get_code_prefix, hash_code
    from backend.users.user_store import set_access_code

    with psycopg.connect(db_url) as conn:
        set_access_code(conn, people["teacher"], hash_code("AlterCode2026"), code_prefix=get_code_prefix("AlterCode2026"))
        conn.commit()
    teacher = _client(app, people["teacher_session"])
    wrong = teacher.post("/api/v2/auth/me/change-code", json={"current_code": "Falsch123", "new_code": "NeuerCode2026"})
    assert wrong.status_code == 403
    assert teacher.post("/api/v2/auth/me/verify-code", json={"code": "AlterCode2026"}).status_code == 200
    ok = teacher.post("/api/v2/auth/me/change-code", json={"current_code": "AlterCode2026", "new_code": "NeuerCode2026"})
    assert ok.status_code == 200
    assert _client(app).post("/api/v2/auth/login", json={"code": "NeuerCode2026"}).status_code == 200
    assert teacher.put("/api/v2/auth/me/email", json={"email": "tim@einladung.test"}).get_json()["email"] == "tim@einladung.test"
    assert teacher.get("/api/v2/auth/me/account").get_json()["account"]["email"] == "tim@einladung.test"


def test_admin_reset_link_lets_teacher_choose_new_code(app, people):
    admin = _client(app, people["admin_session"])
    data = admin.post(f"/api/v2/admin/users/{people['teacher']}/reset-link").get_json()
    assert data["valid_days"] == 3 and "login.html?reset_token=" in data["link"]
    assert _client(app, people["teacher_session"]).post(
        f"/api/v2/admin/users/{people['admin']}/reset-link").status_code == 403
    info = _client(app).get(f"/api/v2/auth/reset-info?token={data['token']}")
    assert info.status_code == 200 and info.get_json()["first_name"] == "Tim"
    done = _client(app).post("/api/v2/auth/reset-code", json={"token": data["token"], "new_code": "ResetCode2026"})
    assert done.status_code == 200
    assert _client(app).post("/api/v2/auth/login", json={"code": "ResetCode2026"}).status_code == 200
