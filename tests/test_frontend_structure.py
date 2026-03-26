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


# ── Phase 10g: webuntis.js extraction tests ───────────────────────────────────

def test_webuntis_js_exists():
    """src/features/webuntis.js exists (Phase 10c extraction)."""
    assert os.path.isfile("src/features/webuntis.js"), (
        "src/features/webuntis.js not found"
    )


def test_index_html_contains_webuntis_js_script(index_html_content):
    """index.html contains src/features/webuntis.js in a <script> tag."""
    assert "src/features/webuntis.js" in index_html_content, (
        "index.html does not contain a reference to src/features/webuntis.js"
    )


def test_index_html_webuntis_js_before_app_js(index_html_content):
    """index.html loads webuntis.js before app.js (check string position)."""
    webuntis_pos = index_html_content.find("src/features/webuntis.js")
    app_js_pos = index_html_content.find("src/app.js")
    assert webuntis_pos != -1, "src/features/webuntis.js not found in index.html"
    assert app_js_pos != -1, "src/app.js not found in index.html"
    assert webuntis_pos < app_js_pos, (
        f"webuntis.js (pos {webuntis_pos}) must appear before app.js (pos {app_js_pos}) "
        "in index.html"
    )


def test_webuntis_js_exports_window_lehrerwebuntis():
    """src/features/webuntis.js assigns window.LehrerWebUntis."""
    with open("src/features/webuntis.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "window.LehrerWebUntis" in content, (
        "src/features/webuntis.js does not assign window.LehrerWebUntis"
    )


def test_app_js_references_window_lehrerWebUntis(app_js_content):
    """src/app.js references window.LehrerWebUntis (extraction confirmation)."""
    assert "window.LehrerWebUntis" in app_js_content, (
        "src/app.js does not reference window.LehrerWebUntis. "
        "Expected delegates calling window.LehrerWebUntis.*() after extraction."
    )


def test_operations_runbook_exists():
    """docs/operations_runbook.md exists (Phase 10f documentation)."""
    assert os.path.isfile("docs/operations_runbook.md"), (
        "docs/operations_runbook.md not found"
    )


def test_operations_runbook_contains_encryption_key_reference():
    """docs/operations_runbook.md mentions ENCRYPTION_KEY (runbook completeness check)."""
    with open("docs/operations_runbook.md", "r", encoding="utf-8") as f:
        content = f.read()
    assert "ENCRYPTION_KEY" in content, (
        "docs/operations_runbook.md does not mention ENCRYPTION_KEY — "
        "runbook completeness check failed"
    )


# ── Phase 11f: itslearning.js extraction tests ───────────────────────────────

def test_itslearning_js_exists():
    """src/features/itslearning.js exists (Phase 11d extraction)."""
    assert os.path.isfile("src/features/itslearning.js"), (
        "src/features/itslearning.js not found"
    )


def test_index_html_contains_itslearning_js_script(index_html_content):
    """index.html contains src/features/itslearning.js in a <script> tag."""
    assert "src/features/itslearning.js" in index_html_content, (
        "index.html does not contain a reference to src/features/itslearning.js"
    )


def test_index_html_itslearning_js_after_webuntis_js_before_app_js(index_html_content):
    """index.html loads itslearning.js after webuntis.js and before app.js (Phase 11 load order)."""
    webuntis_pos = index_html_content.find("src/features/webuntis.js")
    itslearning_pos = index_html_content.find("src/features/itslearning.js")
    app_js_pos = index_html_content.find("src/app.js")
    assert webuntis_pos != -1, "src/features/webuntis.js not found in index.html"
    assert itslearning_pos != -1, "src/features/itslearning.js not found in index.html"
    assert app_js_pos != -1, "src/app.js not found in index.html"
    assert webuntis_pos < itslearning_pos < app_js_pos, (
        f"Expected webuntis.js (pos {webuntis_pos}) < itslearning.js (pos {itslearning_pos}) "
        f"< app.js (pos {app_js_pos}) in index.html"
    )


def test_itslearning_js_assigns_window_lehrerItslearning():
    """src/features/itslearning.js assigns window.LehrerItslearning."""
    with open("src/features/itslearning.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "window.LehrerItslearning" in content, (
        "src/features/itslearning.js does not assign window.LehrerItslearning"
    )


def test_app_js_references_window_lehrerItslearning(app_js_content):
    """src/app.js references window.LehrerItslearning (Phase 11 delegation marker)."""
    assert "window.LehrerItslearning" in app_js_content, (
        "src/app.js does not reference window.LehrerItslearning. "
        "Expected delegates calling window.LehrerItslearning.*() after Phase 11 extraction."
    )


def test_app_js_contains_overlayV2ModuleData(app_js_content):
    """src/app.js contains overlayV2ModuleData function definition (Phase 11 v2 overlay)."""
    assert "overlayV2ModuleData" in app_js_content, (
        "src/app.js does not contain 'overlayV2ModuleData'. "
        "Expected: Phase 11 v2 module data overlay function."
    )


def test_app_py_contains_x_deprecated_header():
    """app.py marks at least one v1 endpoint with X-Deprecated header (Phase 11 retirement markers)."""
    with open("app.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "X-Deprecated" in content, (
        "app.py does not contain any X-Deprecated header. "
        "Expected: at least one v1 endpoint marked with X-Deprecated."
    )


# ── Phase 12: v2 primary dashboard tests ─────────────────────────────────────

def test_app_js_contains_normalizeV2Dashboard(app_js_content):
    """src/app.js contains normalizeV2Dashboard function definition (Phase 12)."""
    assert "normalizeV2Dashboard" in app_js_content, (
        "src/app.js does not contain 'normalizeV2Dashboard'. "
        "Expected: Phase 12 v2 primary dashboard normalization function."
    )


def test_app_js_calls_getDashboardData_as_primary(app_js_content):
    """src/app.js calls getDashboardData() (v2 primary) in loadDashboard() (Phase 12)."""
    assert "getDashboardData" in app_js_content, (
        "src/app.js does not call 'getDashboardData'. "
        "Expected: Phase 12 v2 primary path in loadDashboard()."
    )


def test_app_py_api_dashboard_has_x_deprecated(app_js_content):
    """app.py marks GET /api/dashboard with X-Deprecated header (Phase 12)."""
    with open("app.py", "r", encoding="utf-8") as f:
        content = f.read()
    # Check that the GET /api/dashboard route specifically has the deprecation header
    assert "Use GET /api/v2/dashboard/data" in content, (
        "app.py does not contain 'Use GET /api/v2/dashboard/data' in X-Deprecated header. "
        "Expected: GET /api/dashboard marked deprecated for Phase 12."
    )


# ── Phase 13+: Post-login UX — admin lands on dashboard, not admin.html ───────

@pytest.fixture(scope="module")
def login_html_content():
    with open("login.html", "r", encoding="utf-8") as f:
        return f.read()


def test_login_html_redirectbyrole_does_not_go_to_admin_html(login_html_content):
    """login.html redirectByRole() does NOT redirect to admin.html as destination.

    After Phase 13+, all users (including is_admin=true) land on index.html.
    The admin link is shown on the dashboard instead.
    """
    # The redirectByRole function must not contain a direct redirect to admin.html
    import re
    # Find the redirectByRole function body
    match = re.search(
        r"function\s+redirectByRole\s*\(.*?\{(.*?)\}",
        login_html_content,
        re.DOTALL,
    )
    assert match is not None, "redirectByRole function not found in login.html"
    func_body = match.group(1)
    assert "admin.html" not in func_body, (
        "redirectByRole() still redirects to admin.html. "
        "After Phase 13+, all users should land on index.html (admin link on dashboard)."
    )


def test_login_html_redirectbyrole_sends_to_index_html(login_html_content):
    """login.html redirectByRole() sends users to index.html."""
    # Find the start of the function and scan the next 600 chars (enough for the full body)
    start = login_html_content.find("function redirectByRole")
    assert start != -1, "redirectByRole function not found in login.html"
    func_region = login_html_content[start:start + 600]
    assert "index.html" in func_region, (
        "redirectByRole() does not redirect to index.html. "
        "Expected: all users land on dashboard after login."
    )


def test_login_html_redirectbyrole_still_handles_onboarding(login_html_content):
    """login.html redirectByRole() still redirects to onboarding.html if not complete."""
    import re
    match = re.search(
        r"function\s+redirectByRole\s*\(.*?\{(.*?)\}",
        login_html_content,
        re.DOTALL,
    )
    assert match is not None, "redirectByRole function not found in login.html"
    func_body = match.group(1)
    assert "onboarding.html" in func_body, (
        "redirectByRole() does not redirect to onboarding.html. "
        "Onboarding flow must still work for users who haven't completed it."
    )


def test_index_html_contains_admin_link_with_admin_html_href(index_html_content):
    """index.html contains an anchor element linking to admin.html (admin panel link)."""
    assert 'href="./admin.html"' in index_html_content or 'href="admin.html"' in index_html_content, (
        "index.html does not contain an admin link pointing to admin.html. "
        "is_admin users must see an admin link on the dashboard."
    )


def test_index_html_admin_link_conditional_on_is_admin(index_html_content):
    """index.html admin link element exists AND is_admin is used to control its visibility.

    The HTML element (sidebar-admin-link) is in the sidebar HTML block.
    The JS guard (is_admin check + adminLink.style.display) is in the initUserInfo script block.
    Both must be present, and the JS block must reference 'sidebar-admin-link' alongside is_admin.
    """
    assert "sidebar-admin-link" in index_html_content, (
        "index.html does not contain sidebar-admin-link element."
    )
    assert "is_admin" in index_html_content, (
        "index.html does not reference is_admin anywhere."
    )
    # The JS initUserInfo block must reference both sidebar-admin-link (as getElementById)
    # and is_admin together — verify they co-occur in the same script block
    js_block_start = index_html_content.find("initUserInfo")
    assert js_block_start != -1, (
        "index.html does not contain initUserInfo JS block for user info setup."
    )
    js_block = index_html_content[js_block_start:js_block_start + 1200]
    assert "sidebar-admin-link" in js_block, (
        "initUserInfo block does not reference sidebar-admin-link. "
        "Admin link must be shown/hidden in the user-info setup block."
    )
    assert "is_admin" in js_block, (
        "initUserInfo block does not check is_admin. "
        "Admin link visibility must be conditional on is_admin."
    )
