"""Tests for frontend file structure — verifies Phase 8d extraction worked correctly.

These are plain file-read tests (no DB, no Flask required).
"""
import os
import pytest


# ── File existence tests ───────────────────────────────────────────────────────

def test_api_client_js_exists():
    """src/api-client.js exists."""
    assert os.path.isfile("src/api-client.js"), "src/api-client.js not found"


def test_dashboard_manager_js_exists():
    """src/modules/dashboard-manager.js exists."""
    assert os.path.isfile("src/modules/dashboard-manager.js"), (
        "src/modules/dashboard-manager.js not found"
    )


def test_index_html_exists():
    """index.html exists."""
    assert os.path.isfile("index.html"), "index.html not found"


def test_app_js_exists():
    """src/app.js exists."""
    assert os.path.isfile("src/app.js"), "src/app.js not found"


# ── index.html script tag tests ───────────────────────────────────────────────

@pytest.fixture(scope="module")
def index_html_content():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


def test_index_html_contains_api_client_script(index_html_content):
    """index.html contains src/api-client.js in a <script> tag."""
    assert "src/api-client.js" in index_html_content, (
        "index.html does not contain a reference to src/api-client.js"
    )


def test_index_html_contains_dashboard_manager_script(index_html_content):
    """index.html contains src/modules/dashboard-manager.js in a <script> tag."""
    assert "src/modules/dashboard-manager.js" in index_html_content, (
        "index.html does not contain a reference to src/modules/dashboard-manager.js"
    )


def test_index_html_api_client_before_app_js(index_html_content):
    """index.html loads api-client.js before app.js (check string position in file)."""
    api_client_pos = index_html_content.find("src/api-client.js")
    app_js_pos = index_html_content.find("src/app.js")
    assert api_client_pos != -1, "src/api-client.js not found in index.html"
    assert app_js_pos != -1, "src/app.js not found in index.html"
    assert api_client_pos < app_js_pos, (
        f"api-client.js (pos {api_client_pos}) must appear before app.js (pos {app_js_pos}) "
        "in index.html"
    )


def test_index_html_dashboard_manager_before_app_js(index_html_content):
    """index.html loads dashboard-manager.js before app.js."""
    dm_pos = index_html_content.find("src/modules/dashboard-manager.js")
    app_js_pos = index_html_content.find("src/app.js")
    assert dm_pos != -1, "src/modules/dashboard-manager.js not found in index.html"
    assert app_js_pos != -1, "src/app.js not found in index.html"
    assert dm_pos < app_js_pos, (
        f"dashboard-manager.js (pos {dm_pos}) must appear before app.js (pos {app_js_pos}) "
        "in index.html"
    )


# ── app.js content tests ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app_js_content():
    with open("src/app.js", "r", encoding="utf-8") as f:
        return f.read()


def test_app_js_does_not_contain_dashboardmanager_iife_class(app_js_content):
    """src/app.js does NOT define the DashboardManager IIFE (extraction worked).

    The DashboardManager module is now in src/modules/dashboard-manager.js.
    app.js should reference window.DashboardManager instead of defining it.
    """
    # dashboard-manager.js defines: var DashboardManager = (function() { ... })();
    # If the extraction worked, app.js should NOT contain this definition.
    # We check that the IIFE assignment pattern is absent.
    assert "var DashboardManager = (function()" not in app_js_content, (
        "src/app.js still contains the DashboardManager IIFE definition. "
        "It should have been extracted to src/modules/dashboard-manager.js"
    )


def test_app_js_references_window_dashboardmanager(app_js_content):
    """src/app.js references window.DashboardManager (uses extracted module)."""
    assert "window.DashboardManager" in app_js_content, (
        "src/app.js does not reference window.DashboardManager. "
        "Expected: const DashboardManager = window.DashboardManager;"
    )


# ── dashboard-manager.js content tests ───────────────────────────────────────

@pytest.fixture(scope="module")
def dashboard_manager_content():
    with open("src/modules/dashboard-manager.js", "r", encoding="utf-8") as f:
        return f.read()


def test_dashboard_manager_exports_to_window(dashboard_manager_content):
    """src/modules/dashboard-manager.js exports DashboardManager to window."""
    assert "window.DashboardManager" in dashboard_manager_content, (
        "dashboard-manager.js does not assign to window.DashboardManager"
    )


# ── Phase 9 additions: grades.js and backfill script ─────────────────────────

def test_grades_js_exists():
    """src/features/grades.js exists (Phase 9 extraction)."""
    assert os.path.isfile("src/features/grades.js"), "src/features/grades.js not found"


def test_backfill_script_exists():
    """scripts/backfill_encryption.py exists."""
    assert os.path.isfile("scripts/backfill_encryption.py"), (
        "scripts/backfill_encryption.py not found"
    )


def test_backfill_script_contains_dry_run_flag():
    """scripts/backfill_encryption.py implements --dry-run flag."""
    with open("scripts/backfill_encryption.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "--dry-run" in content, (
        "scripts/backfill_encryption.py does not contain --dry-run flag"
    )


def test_index_html_contains_grades_js_script(index_html_content):
    """index.html contains src/features/grades.js in a <script> tag."""
    assert "src/features/grades.js" in index_html_content, (
        "index.html does not contain a reference to src/features/grades.js"
    )


def test_index_html_grades_js_before_app_js(index_html_content):
    """index.html loads grades.js before app.js (check string position)."""
    grades_pos = index_html_content.find("src/features/grades.js")
    app_js_pos = index_html_content.find("src/app.js")
    assert grades_pos != -1, "src/features/grades.js not found in index.html"
    assert app_js_pos != -1, "src/app.js not found in index.html"
    assert grades_pos < app_js_pos, (
        f"grades.js (pos {grades_pos}) must appear before app.js (pos {app_js_pos}) in index.html"
    )


def test_app_js_references_window_lehrerGrades(app_js_content):
    """src/app.js references window.LehrerGrades (extraction marker)."""
    assert "window.LehrerGrades" in app_js_content, (
        "src/app.js does not reference window.LehrerGrades. "
        "Expected: grades.js sets window.LehrerGrades and app.js references it."
    )


# ── admin.html audit-log tab ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_html_content():
    with open("admin.html", "r", encoding="utf-8") as f:
        return f.read()


def test_admin_html_contains_audit_log_element(admin_html_content):
    """admin.html contains 'audit-log' in an element id (audit tab present)."""
    assert "audit-log" in admin_html_content, (
        "admin.html does not contain an element with 'audit-log' — audit tab missing"
    )
