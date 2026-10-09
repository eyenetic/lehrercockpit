"""Changing requests from foreign websites are refused (CSRF), the app's own pass."""
import pytest


@pytest.fixture()
def client(monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, "CORS_ORIGIN", "https://app.lehrercockpit.com")
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_post_from_a_foreign_site_is_refused(client):
    resp = client.post("/api/v2/auth/logout", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403


def test_null_origin_is_refused(client):
    resp = client.post("/api/classwork/upload", data=b"x", headers={"Origin": "null"})
    assert resp.status_code == 403


def test_the_apps_own_origin_passes_the_check(client):
    resp = client.post("/api/v2/auth/logout", headers={"Origin": "https://app.lehrercockpit.com"})
    assert resp.status_code != 403


def test_requests_without_origin_and_reads_are_not_affected(client):
    assert client.post("/api/v2/auth/logout").status_code != 403
    assert client.get("/api/health", headers={"Origin": "https://evil.example"}).status_code == 200
