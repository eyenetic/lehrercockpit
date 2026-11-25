"""Anhänge an eigenen Einträgen: nur verschlüsselte Bytes, nur für die eigene Lehrkraft, mit Kontingent."""
from unittest.mock import MagicMock, patch

import pytest

import backend.api.helpers
import backend.api.own_files_routes as routes
from backend import own_files


@pytest.fixture
def client():
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(routes.own_files_bp, url_prefix="/api/v2/files")
    return app.test_client()


def _db(conn):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=conn)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _user(uid=7):
    return MagicMock(id=uid, is_active=True, is_admin=False)


def test_quota_and_size_are_checked_before_storing():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (own_files.QUOTA_BYTES - 100,)
    assert "voll" in own_files.add(conn, 7, b"x" * 500)
    assert "leer" in own_files.add(conn, 7, b"")
    assert "groß" in own_files.add(conn, 7, b"x" * (own_files.MAX_FILE_BYTES + 1))
    assert not any("INSERT" in c.args[0] for c in conn.execute.call_args_list)

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (1000,)
    result = own_files.add(conn, 7, b"x" * 500)
    assert result["size"] == 500 and result["used"] == 1500 and len(result["id"]) >= 20
    insert = next(c for c in conn.execute.call_args_list if "INSERT" in c.args[0])
    assert insert.args[1][1] == 7


def test_only_the_owner_gets_the_bytes():
    conn = MagicMock()
    own_files.load(conn, 7, "abc")
    sql, params = conn.execute.call_args.args
    assert "user_id = %s" in sql and params == ("abc", 7)
    own_files.delete(conn, 7, "abc")
    sql, params = conn.execute.call_args.args
    assert sql.startswith("DELETE") and "user_id = %s" in sql and params == ("abc", 7)


def test_routes(client):
    conn = MagicMock()
    with patch.object(backend.api.helpers, "get_current_user", return_value=None):
        assert client.post("/api/v2/files", data=b"x" * 100).status_code == 401
        assert client.get("/api/v2/files/abcdefghijkl").status_code == 401
    with patch.object(backend.api.helpers, "get_current_user", return_value=_user()), \
            patch.object(routes, "db_connection", return_value=_db(conn)):
        with patch.object(own_files, "add", return_value={"id": "f" * 24, "size": 100, "used": 100, "quota": 1}) as add:
            resp = client.post("/api/v2/files", data=b"x" * 100, content_type="application/octet-stream")
        assert resp.status_code == 201 and add.call_args.args[1:] == (7, b"x" * 100)
        with patch.object(own_files, "add", return_value="Dein Speicher für Anhänge ist fast voll"):
            assert client.post("/api/v2/files", data=b"x" * 100).status_code == 413
        with patch.object(own_files, "load", return_value=None):
            assert client.get("/api/v2/files/abcdefghijkl").status_code == 404
        assert client.get("/api/v2/files/../etc").status_code == 404
        with patch.object(own_files, "load", return_value=b"\x01\x02") as load:
            resp = client.get("/api/v2/files/abcdefghijkl")
        assert resp.data == b"\x01\x02" and resp.mimetype == "application/octet-stream"
        assert load.call_args.args[1:] == (7, "abcdefghijkl")
