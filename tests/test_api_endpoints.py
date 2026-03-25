"""Integration tests for the Flask API endpoints in app.py.

Uses Flask's built-in test client — no running server needed.
Heavy backend imports (dashboard, adapters) may fail without credentials;
tests are structured so they still verify HTTP behaviour using the mock fallback.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Return a Flask test client with isolated data paths."""
    # Point all data paths to tmp_path so tests don't touch real data/
    monkeypatch.setenv("PORT", "0")

    # Import app after env is patched
    import importlib
    import app as app_module

    # Override path constants to use tmp_path
    monkeypatch.setattr(app_module, "GRADES_LOCAL_PATH", tmp_path / "grades.json")
    monkeypatch.setattr(app_module, "NOTES_LOCAL_PATH", tmp_path / "notes.json")
    monkeypatch.setattr(app_module, "CLASSWORK_CACHE_PATH", tmp_path / "classwork.json")

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


# ── /api/health ───────────────────────────────────────────────────────────────

def test_health_ok(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"


# ── /api/grades ───────────────────────────────────────────────────────────────

def test_grades_empty(client) -> None:
    response = client.get("/api/grades")
    assert response.status_code == 200
    data = response.get_json()
    assert data["entries"] == []
    assert data["status"] == "empty"


def test_grades_post_and_get(client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module
    monkeypatch.setattr(app_module, "GRADES_LOCAL_PATH", tmp_path / "grades.json")

    payload = {
        "classLabel": "10A",
        "studentName": "Max",
        "title": "KA 1",
        "type": "Klassenarbeit",
        "gradeValue": "2",
        "date": "2026-03-15",
    }
    # POST requires local request — patch _is_local_request
    with app_module.app.test_request_context():
        pass

    # Simulate a local POST
    response = client.post(
        "/api/local-settings/grades",
        json=payload,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert response.status_code == 200
    result = response.get_json()
    assert result["status"] == "ok"

    # Now GET should return the entry
    response2 = client.get("/api/grades")
    assert response2.status_code == 200
    data = response2.get_json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["classLabel"] == "10A"


# ── /api/notes ────────────────────────────────────────────────────────────────

def test_notes_empty(client) -> None:
    response = client.get("/api/notes")
    assert response.status_code == 200
    data = response.get_json()
    assert data["notes"] == []


def test_notes_post_and_get(client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module
    monkeypatch.setattr(app_module, "NOTES_LOCAL_PATH", tmp_path / "notes.json")

    payload = {"classLabel": "9B", "text": "Hausaufgaben vergessen.", "mode": "upsert"}
    response = client.post(
        "/api/local-settings/notes",
        json=payload,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert response.status_code == 200

    response2 = client.get("/api/notes")
    data = response2.get_json()
    assert len(data["notes"]) == 1
    assert data["notes"][0]["classLabel"] == "9B"


# ── /api/classwork ────────────────────────────────────────────────────────────

def test_classwork_empty(client) -> None:
    response = client.get("/api/classwork")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "pending"


# ── CORS headers ──────────────────────────────────────────────────────────────

def test_cors_headers_present(client) -> None:
    response = client.get("/api/health")
    assert "Access-Control-Allow-Origin" in response.headers


# ── local-only guard ──────────────────────────────────────────────────────────

def test_grades_post_blocked_from_remote(client) -> None:
    """POST /api/local-settings/grades must be blocked from non-local IPs."""
    response = client.post(
        "/api/local-settings/grades",
        json={"classLabel": "10A", "studentName": "X", "title": "T"},
        environ_base={"REMOTE_ADDR": "1.2.3.4"},
    )
    assert response.status_code == 403


def test_notes_post_blocked_from_remote(client) -> None:
    response = client.post(
        "/api/local-settings/notes",
        json={"classLabel": "9B", "text": "test"},
        environ_base={"REMOTE_ADDR": "8.8.8.8"},
    )
    assert response.status_code == 403
