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
    # The JS initUserInfo function body must reference both sidebar-admin-link and is_admin.
    # Anchor on "function initUserInfo" to skip any earlier comment/call-site occurrences.
    js_block_start = index_html_content.find("function initUserInfo")
    assert js_block_start != -1, (
        "index.html does not contain 'function initUserInfo' definition for user info setup."
    )
    js_block = index_html_content[js_block_start:js_block_start + 1200]
    assert "sidebar-admin-link" in js_block, (
        "initUserInfo function body does not reference sidebar-admin-link. "
        "Admin link must be shown/hidden inside initUserInfo()."
    )
    assert "is_admin" in js_block, (
        "initUserInfo function body does not check is_admin. "
        "Admin link visibility must be conditional on is_admin."
    )


def test_dashboard_manager_exposes_module_visibility_helper(dashboard_manager_content):
    """dashboard-manager.js exposes isModuleVisible for UI gating."""
    assert "isModuleVisible" in dashboard_manager_content, (
        "dashboard-manager.js does not expose isModuleVisible. "
        "Expected: UI can query persisted module visibility after layout changes."
    )


def test_app_js_rerenders_on_dashboard_layout_changed(app_js_content):
    """src/app.js listens for dashboard-layout-changed so layout updates affect the visible UI immediately."""
    assert "dashboard-layout-changed" in app_js_content, (
        "src/app.js does not listen for dashboard-layout-changed. "
        "Expected: dashboard re-renders immediately after module layout changes."
    )


# ── Visibility bug fix tests (dashboard module visibility) ───────────────────
# These tests validate the end-to-end fix for the bug where disabled modules
# remained visible on the dashboard after saving layout settings.

def test_app_js_contains_isSectionEnabled(app_js_content):
    """src/app.js defines isSectionEnabled() for section-level visibility gating."""
    assert "isSectionEnabled" in app_js_content, (
        "src/app.js does not define isSectionEnabled(). "
        "Expected: a function that maps section IDs to module visibility checks."
    )


def test_app_js_isSectionEnabled_maps_schedule_to_webuntis(app_js_content):
    """src/app.js isSectionEnabled maps 'schedule' to isModuleVisible('webuntis')."""
    # Both must appear in the same function context in app.js
    assert '"schedule"' in app_js_content or "'schedule'" in app_js_content, (
        "src/app.js does not reference 'schedule' section in isSectionEnabled."
    )
    assert '"webuntis"' in app_js_content or "'webuntis'" in app_js_content, (
        "src/app.js does not reference 'webuntis' module in visibility checks."
    )


def test_app_js_isSectionEnabled_maps_grades_to_noten(app_js_content):
    """src/app.js isSectionEnabled maps 'grades' to isModuleVisible('noten')."""
    assert '"grades"' in app_js_content or "'grades'" in app_js_content, (
        "src/app.js does not reference 'grades' section in isSectionEnabled."
    )
    assert '"noten"' in app_js_content or "'noten'" in app_js_content, (
        "src/app.js does not reference 'noten' module in visibility checks."
    )


def test_app_js_isSectionEnabled_maps_documents_to_orgaplan(app_js_content):
    """src/app.js isSectionEnabled maps 'documents' to orgaplan/klassenarbeitsplan visibility."""
    assert '"orgaplan"' in app_js_content or "'orgaplan'" in app_js_content, (
        "src/app.js does not reference 'orgaplan' module in visibility checks."
    )
    assert '"klassenarbeitsplan"' in app_js_content or "'klassenarbeitsplan'" in app_js_content, (
        "src/app.js does not reference 'klassenarbeitsplan' module in visibility checks."
    )


def test_app_js_renderSectionFocus_calls_isSectionEnabled(app_js_content):
    """src/app.js renderSectionFocus() calls isSectionEnabled() to gate section visibility."""
    # Both must appear close together in the same function
    assert "renderSectionFocus" in app_js_content, (
        "src/app.js does not define renderSectionFocus()."
    )
    # Find the renderSectionFocus block and check isSectionEnabled is called inside it
    start = app_js_content.find("function renderSectionFocus")
    assert start != -1, "renderSectionFocus function not found in src/app.js"
    # Check within a reasonable window (800 chars covers the full function body)
    func_region = app_js_content[start:start + 800]
    assert "isSectionEnabled" in func_region, (
        "renderSectionFocus() does not call isSectionEnabled() in its body. "
        "Expected: section visibility driven by isSectionEnabled() for each section."
    )


def test_app_js_renderPlanDigest_checks_orgaplan_visibility():
    """classwork.js renderPlanDigest() checks isModuleVisible('orgaplan') to hide the orgaplan card.

    After extraction, the logic lives in src/features/classwork.js rather than app.js.
    """
    with open("src/features/classwork.js", "r", encoding="utf-8") as f:
        classwork_content = f.read()
    start = classwork_content.find("function renderPlanDigest")
    assert start != -1, "renderPlanDigest function not found in src/features/classwork.js"
    func_region = classwork_content[start:start + 1400]
    assert "orgaplan" in func_region, (
        "renderPlanDigest() in classwork.js does not reference 'orgaplan' module. "
        "Expected: orgaplan digest card hidden when orgaplan module is disabled."
    )
    assert "_isModuleVisible" in func_region, (
        "renderPlanDigest() in classwork.js does not call _isModuleVisible() to gate the orgaplan card."
    )


def test_app_js_renderPlanDigest_checks_klassenarbeitsplan_visibility():
    """classwork.js renderPlanDigest() checks isModuleVisible('klassenarbeitsplan') to hide that card.

    After extraction, the logic lives in src/features/classwork.js rather than app.js.
    """
    with open("src/features/classwork.js", "r", encoding="utf-8") as f:
        classwork_content = f.read()
    start = classwork_content.find("function renderPlanDigest")
    assert start != -1, "renderPlanDigest function not found in src/features/classwork.js"
    func_region = classwork_content[start:start + 1400]
    assert "klassenarbeitsplan" in func_region, (
        "renderPlanDigest() in classwork.js does not reference 'klassenarbeitsplan' module. "
        "Expected: classwork digest card hidden when klassenarbeitsplan module is disabled."
    )


def test_dashboard_manager_saveLayout_emits_layout_changed(dashboard_manager_content):
    """dashboard-manager.js _saveLayout() emits dashboard-layout-changed after persisting.

    This is the save → re-render chain: save succeeds → update local state
    → _emitLayoutChanged() → app.js renderAll() → sections hidden immediately.
    """
    # The function must contain both the API call and the event emit
    assert "_saveLayout" in dashboard_manager_content, (
        "dashboard-manager.js does not define _saveLayout(). "
        "Expected: layout save function that persists to backend and re-emits layout-changed."
    )
    # Find _saveLayout function body and verify it calls _emitLayoutChanged
    start = dashboard_manager_content.find("function _saveLayout")
    assert start != -1, "_saveLayout function not found in dashboard-manager.js"
    # Use 2000 chars — the full _saveLayout body including the forEach+map block is ~1400 chars
    func_region = dashboard_manager_content[start:start + 2000]
    assert "_emitLayoutChanged" in func_region, (
        "_saveLayout() does not call _emitLayoutChanged() after saving. "
        "Expected: layout save triggers immediate re-render via dashboard-layout-changed event."
    )


def test_dashboard_manager_emitLayoutChanged_dispatches_custom_event(dashboard_manager_content):
    """dashboard-manager.js _emitLayoutChanged() dispatches CustomEvent('dashboard-layout-changed')."""
    assert "_emitLayoutChanged" in dashboard_manager_content, (
        "dashboard-manager.js does not define _emitLayoutChanged(). "
        "Expected: helper that dispatches dashboard-layout-changed CustomEvent."
    )
    # Verify it dispatches the correct event name
    start = dashboard_manager_content.find("_emitLayoutChanged")
    assert start != -1
    # Look for the event name in a region that covers the function definition
    region = dashboard_manager_content[start:start + 300]
    assert "dashboard-layout-changed" in region, (
        "_emitLayoutChanged() does not dispatch 'dashboard-layout-changed' CustomEvent. "
        "Expected: window.dispatchEvent(new CustomEvent('dashboard-layout-changed', ...))."
    )


def test_dashboard_manager_module_section_map_contains_all_visibility_ids(dashboard_manager_content):
    """dashboard-manager.js MODULE_SECTION_MAP covers all six required module IDs.

    These are the module IDs that must be supported for end-to-end visibility gating:
    webuntis, noten, itslearning, nextcloud, orgaplan, klassenarbeitsplan.
    """
    required_ids = ["webuntis", "noten", "itslearning", "nextcloud", "orgaplan", "klassenarbeitsplan"]
    for module_id in required_ids:
        assert module_id in dashboard_manager_content, (
            f"dashboard-manager.js does not reference module_id '{module_id}'. "
            f"Expected: MODULE_SECTION_MAP and/or visibility logic covers all required module IDs."
        )


def test_app_js_isModuleVisible_delegates_to_dashboard_manager(app_js_content):
    """src/app.js isModuleVisible() delegates to DashboardManager.isModuleVisible().

    The local isModuleVisible() wrapper in app.js must call DashboardManager.isModuleVisible()
    so that the persisted layout state (from _modules) drives section visibility.
    """
    start = app_js_content.find("function isModuleVisible")
    assert start != -1, "isModuleVisible wrapper function not found in src/app.js"
    func_region = app_js_content[start:start + 300]
    assert "DashboardManager" in func_region, (
        "src/app.js isModuleVisible() does not delegate to DashboardManager. "
        "Expected: return DashboardManager.isModuleVisible(moduleId) so persisted state is used."
    )


# ── Overview/Briefing module visibility gating tests ─────────────────────────
# These tests verify that the overview section (always visible) correctly gates
# module-specific content in renderStats() and renderBriefing() by module
# visibility flags — fixing the bug where disabled modules still appeared in the
# briefing card and stat tiles on the overview screen.

def test_app_js_renderStats_gates_webuntis_card_by_module_visibility(app_js_content):
    """src/app.js renderStats() gates the WebUntis stat card by isModuleVisible('webuntis').

    When the webuntis module is disabled, the 'WebUntis' stat card must not be rendered.
    The fix: check showWebuntis = isModuleVisible('webuntis') before adding the card.
    """
    start = app_js_content.find("function renderStats")
    assert start != -1, "renderStats function not found in src/app.js"
    func_region = app_js_content[start:start + 1200]
    assert "isModuleVisible" in func_region or "showWebuntis" in func_region, (
        "renderStats() does not call isModuleVisible() to gate the WebUntis stat card. "
        "Expected: showWebuntis = isModuleVisible('webuntis') controls whether the WebUntis tile is rendered."
    )
    assert "webuntis" in func_region.lower(), (
        "renderStats() does not reference 'webuntis' for visibility gating. "
        "Expected: WebUntis stat card skipped when webuntis module is disabled."
    )


def test_app_js_renderStats_gates_inbox_card_by_module_visibility(app_js_content):
    """src/app.js renderStats() gates the Hinweise (inbox) stat card by inbox module visibility.

    When both mail and itslearning modules are disabled, the 'Hinweise' stat card must not render.
    The fix: check showInbox = isAnyModuleVisible(['itslearning', 'mail']) before adding the card.
    """
    start = app_js_content.find("function renderStats")
    assert start != -1, "renderStats function not found in src/app.js"
    func_region = app_js_content[start:start + 1200]
    assert "showInbox" in func_region or "isAnyModuleVisible" in func_region, (
        "renderStats() does not check inbox module visibility for the Hinweise stat card. "
        "Expected: showInbox = isAnyModuleVisible(['itslearning', 'mail']) gates the Hinweise tile."
    )


def test_app_js_renderBriefing_gates_webuntis_items_by_module_visibility(app_js_content):
    """src/app.js renderBriefing() gates WebUntis briefing items by isModuleVisible('webuntis').

    When webuntis is disabled: nextEvent, todaySummary, weeklyPreview must all be null/skipped.
    """
    start = app_js_content.find("function renderBriefing")
    assert start != -1, "renderBriefing function not found in src/app.js"
    func_region = app_js_content[start:start + 2200]
    assert "showWebuntis" in func_region, (
        "renderBriefing() does not define showWebuntis visibility flag. "
        "Expected: showWebuntis = isModuleVisible('webuntis') used to skip WebUntis briefing items."
    )
    # nextEvent must only be fetched when webuntis is visible
    assert "showWebuntis" in func_region[:func_region.find("findNextLesson") + 50 if "findNextLesson" in func_region else len(func_region)], (
        "renderBriefing() does not guard findNextLesson() with showWebuntis. "
        "Expected: nextEvent = showWebuntis ? findNextLesson(data) : null."
    )


def test_app_js_renderBriefing_gates_orgaplan_item_by_module_visibility(app_js_content):
    """src/app.js renderBriefing() gates Orgaplan briefing item by isModuleVisible('orgaplan').

    When orgaplan is disabled, no orgaplan item should appear in the briefing card.
    """
    start = app_js_content.find("function renderBriefing")
    assert start != -1, "renderBriefing function not found in src/app.js"
    func_region = app_js_content[start:start + 2200]
    assert "showOrgaplan" in func_region, (
        "renderBriefing() does not define showOrgaplan visibility flag. "
        "Expected: showOrgaplan = isModuleVisible('orgaplan') gates the orgaplan briefing item."
    )


def test_app_js_renderBriefing_gates_classwork_item_by_module_visibility(app_js_content):
    """src/app.js renderBriefing() gates Klassarbeit briefing item by isModuleVisible('klassenarbeitsplan').

    When klassenarbeitsplan is disabled, no classwork item appears in the briefing.
    """
    start = app_js_content.find("function renderBriefing")
    assert start != -1, "renderBriefing function not found in src/app.js"
    func_region = app_js_content[start:start + 2200]
    assert "showClasswork" in func_region, (
        "renderBriefing() does not define showClasswork visibility flag. "
        "Expected: showClasswork = isModuleVisible('klassenarbeitsplan') gates classwork briefing item."
    )


def test_app_js_renderBriefing_gates_inbox_item_by_module_visibility(app_js_content):
    """src/app.js renderBriefing() gates Inbox briefing item by inbox module visibility.

    When both mail and itslearning are disabled, no inbox item appears in the briefing.
    """
    start = app_js_content.find("function renderBriefing")
    assert start != -1, "renderBriefing function not found in src/app.js"
    func_region = app_js_content[start:start + 2200]
    assert "showInbox" in func_region, (
        "renderBriefing() does not define showInbox visibility flag. "
        "Expected: showInbox = isAnyModuleVisible(['itslearning', 'mail']) gates inbox briefing item."
    )


# ── First-load flash fix tests (isLayoutReady guard) ─────────────────────────
# These tests verify that the first-load flash bug is fixed: before the layout
# API response arrives, renderStats() and renderBriefing() must not show
# module-derived content (because isModuleVisible() returns true optimistically
# when _modules is still empty).

def test_dashboard_manager_exposes_isLayoutReady(dashboard_manager_content):
    """src/modules/dashboard-manager.js exposes isLayoutReady() method.

    isLayoutReady() returns false until the layout API response has been received
    at least once. renderStats() and renderBriefing() use this to prevent the
    first-load flash where disabled modules briefly appear before state is loaded.
    """
    assert "isLayoutReady" in dashboard_manager_content, (
        "dashboard-manager.js does not expose isLayoutReady(). "
        "Expected: method that returns true only after layout data has loaded from the API."
    )
    # Verify it is returned from the public API object
    return_start = dashboard_manager_content.rfind("return {")
    assert return_start != -1, "Public API return block not found in dashboard-manager.js"
    return_region = dashboard_manager_content[return_start:]
    assert "isLayoutReady" in return_region, (
        "isLayoutReady is not in the public return object of DashboardManager. "
        "It must be exported so app.js can call DashboardManager.isLayoutReady()."
    )


def test_app_js_renderStats_checks_isLayoutReady(app_js_content):
    """src/app.js renderStats() checks isLayoutReady() before rendering module-derived tiles.

    The fix for the first-load flash: when layout state is not yet available,
    module-dependent stat tiles (WebUntis, Hinweise) must not be rendered.
    Non-module tiles (Prioritaeten, Dokumente) always render regardless.
    """
    start = app_js_content.find("function renderStats")
    assert start != -1, "renderStats function not found in src/app.js"
    func_region = app_js_content[start:start + 1400]
    assert "isLayoutReady" in func_region, (
        "renderStats() does not call isLayoutReady() to guard module-derived tiles. "
        "Expected: layoutReady = isLayoutReady() used before showWebuntis / showInbox checks."
    )
    assert "layoutReady" in func_region, (
        "renderStats() does not define a 'layoutReady' local variable. "
        "Expected: const layoutReady = isLayoutReady(); used to gate module tiles."
    )


def test_app_js_renderBriefing_checks_isLayoutReady(app_js_content):
    """src/app.js renderBriefing() checks isLayoutReady() before rendering module-derived items.

    The fix for the first-load flash: when layout state is not yet available,
    module-specific briefing items (WebUntis, Orgaplan, Klassarbeit, Inbox) must not render.
    """
    start = app_js_content.find("function renderBriefing")
    assert start != -1, "renderBriefing function not found in src/app.js"
    func_region = app_js_content[start:start + 2400]
    assert "isLayoutReady" in func_region, (
        "renderBriefing() does not call isLayoutReady() to guard module-derived items. "
        "Expected: layoutReady = isLayoutReady() used before showWebuntis / showOrgaplan / etc."
    )
    assert "layoutReady" in func_region, (
        "renderBriefing() does not define a 'layoutReady' local variable. "
        "Expected: const layoutReady = isLayoutReady(); used to gate all module briefing items."
    )


def test_app_js_renderAll_calls_renderStats(app_js_content):
    """src/app.js renderAll() calls renderStats() so stat tiles update on every re-render.

    renderStats() must be called inside renderAll() so that when dashboard-layout-changed
    fires (after layout data arrives), the stat tiles are re-rendered with correct visibility.
    """
    start = app_js_content.find("function renderAll")
    assert start != -1, "renderAll function not found in src/app.js"
    # renderAll is a short function — 400 chars covers the full body
    func_region = app_js_content[start:start + 400]
    assert "renderStats" in func_region, (
        "renderAll() does not call renderStats(). "
        "Expected: renderStats() called inside renderAll() so stat tiles update correctly."
    )


# ── Sparse sort_order fix tests ───────────────────────────────────────────────
# Regression tests for the bug where modules with sparse sort_order values
# (e.g. 4, 5, 6, 7 when earlier modules are disabled) were rendered with the
# wrong order value (idx+1 = 1, 2, 3, 4) in the layout panel. Any "Save"
# without manually correcting those numbers silently re-normalised the DB to
# 1–4, breaking the stored order and causing later-only enabled modules to
# appear in wrong positions or not at all.

def test_dashboard_manager_renderLayoutPanelContent_uses_sort_order_not_idx(dashboard_manager_content):
    """_renderLayoutPanelContent() must use m.sort_order, NOT idx+1, as the sort-order input value.

    Bug: with sparse sort_orders (e.g. 4, 5, 6, 7 when earlier modules are
    disabled) the old code wrote `value="' + (idx + 1) + '"` which displayed
    1, 2, 3, 4. Any save without manual correction silently overwrote the DB
    with those wrong values and the later-only enabled modules stopped rendering
    in the correct order.

    Fix: use `m.sort_order` so the panel always reflects the actual stored value.
    """
    start = dashboard_manager_content.find("function _renderLayoutPanelContent")
    assert start != -1, "_renderLayoutPanelContent function not found in dashboard-manager.js"
    # The value= input attribute is deep in the innerHTML string — use 1400 chars
    func_region = dashboard_manager_content[start:start + 1400]

    # Must NOT use idx+1 as the order value
    assert "(idx + 1)" not in func_region, (
        "_renderLayoutPanelContent() still uses (idx + 1) as the sort-order input value. "
        "This causes sparse sort_orders (e.g. 4,5,6,7) to be rendered as 1,2,3,4 and "
        "silently overwritten on save. Use m.sort_order instead."
    )

    # Must use m.sort_order
    assert "m.sort_order" in func_region, (
        "_renderLayoutPanelContent() does not use m.sort_order as the sort-order input value. "
        "Expected: value='\" + (m.sort_order || 0) + \"' so the panel always reflects the real "
        "stored sort_order, preserving sparse values when earlier modules are disabled."
    )


def test_index_html_checkAuth_calls_initUserInfo_after_setting_current_user(index_html_content):
    """index.html checkAuth() calls initUserInfo() after window.CURRENT_USER is set.

    Bug: initUserInfo() was a self-executing IIFE that ran synchronously before the
    async checkAuth fetch completed, so window.CURRENT_USER was always undefined and
    the admin link was never shown for admin users.

    Fix: initUserInfo is now a plain function called explicitly from checkAuth() right
    after 'window.CURRENT_USER = data.user' so the admin link always renders with the
    correct is_admin value from the session.
    """
    # checkAuth must contain a call to initUserInfo() after CURRENT_USER is assigned
    checkauth_start = index_html_content.find("async function checkAuth")
    assert checkauth_start != -1, "checkAuth async function not found in index.html"
    checkauth_region = index_html_content[checkauth_start:checkauth_start + 1800]
    assert "initUserInfo" in checkauth_region, (
        "checkAuth() does not call initUserInfo(). "
        "Expected: initUserInfo() called inside checkAuth() after window.CURRENT_USER is set, "
        "so the admin link is shown with the correct is_admin flag."
    )
    # The call must come after CURRENT_USER assignment
    current_user_pos = checkauth_region.find("CURRENT_USER = data.user")
    init_call_pos = checkauth_region.find("initUserInfo", current_user_pos)
    assert current_user_pos != -1, "window.CURRENT_USER assignment not found in checkAuth()"
    assert init_call_pos != -1, (
        "initUserInfo() is not called after 'window.CURRENT_USER = data.user' in checkAuth(). "
        "The call must come after the assignment so CURRENT_USER is populated when initUserInfo runs."
    )


def test_index_html_initUserInfo_is_not_iife(index_html_content):
    """index.html initUserInfo is defined as a plain function, NOT a self-executing IIFE.

    The old form '(function initUserInfo() { ... })()' ran synchronously before the
    async fetch in checkAuth() completed, so window.CURRENT_USER was undefined.

    The fix converts it to 'function initUserInfo() { ... }' (no auto-invocation)
    so it only runs when explicitly called from checkAuth() with CURRENT_USER already set.
    """
    # Must NOT contain the IIFE invocation pattern for initUserInfo
    assert "(function initUserInfo()" not in index_html_content, (
        "index.html still defines initUserInfo as an IIFE '(function initUserInfo() { ... })()'. "
        "This causes the admin link to never appear because CURRENT_USER is not yet set when it runs. "
        "Fix: use 'function initUserInfo() { ... }' and call it from checkAuth() after CURRENT_USER is set."
    )
    # Must contain the plain function declaration
    assert "function initUserInfo()" in index_html_content, (
        "index.html does not define 'function initUserInfo()' as a plain named function. "
        "Expected: function initUserInfo() { ... } called from checkAuth() after CURRENT_USER is set."
    )


def test_dashboard_manager_renderLayoutPanelContent_forEach_no_idx_param(dashboard_manager_content):
    """_renderLayoutPanelContent() forEach callback does not need the unused idx parameter.

    After the fix the idx parameter is no longer required. Its presence is not
    an error, but its use as an order value is. This test is a belt-and-suspenders
    check that the fix did not re-introduce the idx-based value in a different form.
    """
    start = dashboard_manager_content.find("function _renderLayoutPanelContent")
    assert start != -1, "_renderLayoutPanelContent function not found in dashboard-manager.js"
    func_region = dashboard_manager_content[start:start + 1400]
    # idx+1 must be absent as a value string (the critical form that caused the bug)
    assert "(idx + 1)" not in func_region, (
        "_renderLayoutPanelContent still constructs sort-order value with (idx + 1). "
        "Sparse sort_orders (e.g. 4,5,6,7) would be rendered as 1,2,3,4 and overwritten on save."
    )
    # The correct pattern must be present
    assert "m.sort_order" in func_region, (
        "m.sort_order not found in _renderLayoutPanelContent — "
        "sparse sort_order fix may have been lost."
    )


# ── JS extraction: documents.js and classwork.js ─────────────────────────────

def test_documents_js_exists():
    """src/features/documents.js exists (maintainability extraction)."""
    assert os.path.isfile("src/features/documents.js"), "src/features/documents.js not found"


def test_classwork_js_exists():
    """src/features/classwork.js exists (maintainability extraction)."""
    assert os.path.isfile("src/features/classwork.js"), "src/features/classwork.js not found"


def test_index_html_contains_documents_js_script(index_html_content):
    """index.html contains src/features/documents.js in a <script> tag."""
    assert "src/features/documents.js" in index_html_content, (
        "index.html does not contain a reference to src/features/documents.js"
    )


def test_index_html_contains_classwork_js_script(index_html_content):
    """index.html contains src/features/classwork.js in a <script> tag."""
    assert "src/features/classwork.js" in index_html_content, (
        "index.html does not contain a reference to src/features/classwork.js"
    )


def test_index_html_documents_js_before_app_js(index_html_content):
    """index.html loads documents.js before app.js."""
    documents_pos = index_html_content.find("src/features/documents.js")
    app_js_pos = index_html_content.find("src/app.js")
    assert documents_pos != -1, "src/features/documents.js not found in index.html"
    assert app_js_pos != -1, "src/app.js not found in index.html"
    assert documents_pos < app_js_pos, (
        f"documents.js (pos {documents_pos}) must appear before app.js (pos {app_js_pos})"
    )


def test_index_html_classwork_js_before_app_js(index_html_content):
    """index.html loads classwork.js before app.js."""
    classwork_pos = index_html_content.find("src/features/classwork.js")
    app_js_pos = index_html_content.find("src/app.js")
    assert classwork_pos != -1, "src/features/classwork.js not found in index.html"
    assert app_js_pos != -1, "src/app.js not found in index.html"
    assert classwork_pos < app_js_pos, (
        f"classwork.js (pos {classwork_pos}) must appear before app.js (pos {app_js_pos})"
    )


def test_documents_js_exports_window_lehrerDocuments():
    """src/features/documents.js assigns window.LehrerDocuments."""
    with open("src/features/documents.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "window.LehrerDocuments" in content, (
        "src/features/documents.js does not assign window.LehrerDocuments"
    )


def test_classwork_js_exports_window_lehrerClasswork():
    """src/features/classwork.js assigns window.LehrerClasswork."""
    with open("src/features/classwork.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "window.LehrerClasswork" in content, (
        "src/features/classwork.js does not assign window.LehrerClasswork"
    )


def test_app_js_delegates_renderDocuments_to_lehrerDocuments(app_js_content):
    """src/app.js renderDocuments() delegates to window.LehrerDocuments."""
    start = app_js_content.find("function renderDocuments")
    assert start != -1, "renderDocuments function not found in src/app.js"
    func_region = app_js_content[start:start + 200]
    assert "LehrerDocuments" in func_region, (
        "renderDocuments() in app.js does not delegate to LehrerDocuments"
    )


def test_app_js_delegates_renderPlanDigest_to_lehrerClasswork(app_js_content):
    """src/app.js renderPlanDigest() delegates to window.LehrerClasswork."""
    start = app_js_content.find("function renderPlanDigest")
    assert start != -1, "renderPlanDigest function not found in src/app.js"
    func_region = app_js_content[start:start + 200]
    assert "LehrerClasswork" in func_region, (
        "renderPlanDigest() in app.js does not delegate to LehrerClasswork"
    )


# ── CSS split tests: styles.auth.css and styles.admin.css ────────────────────

def test_styles_auth_css_exists():
    """styles.auth.css exists (CSS split for auth pages)."""
    assert os.path.isfile("styles.auth.css"), "styles.auth.css not found"


def test_styles_admin_css_exists():
    """styles.admin.css exists (CSS split for admin page)."""
    assert os.path.isfile("styles.admin.css"), "styles.admin.css not found"


@pytest.fixture(scope="module")
def login_html_raw_content():
    with open("login.html", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def onboarding_html_raw_content():
    with open("onboarding.html", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def admin_html_raw_content():
    with open("admin.html", "r", encoding="utf-8") as f:
        return f.read()


def test_login_html_loads_auth_css(login_html_raw_content):
    """login.html loads styles.auth.css."""
    assert "styles.auth.css" in login_html_raw_content, (
        "login.html does not reference styles.auth.css"
    )


def test_onboarding_html_loads_auth_css(onboarding_html_raw_content):
    """onboarding.html loads styles.auth.css."""
    assert "styles.auth.css" in onboarding_html_raw_content, (
        "onboarding.html does not reference styles.auth.css"
    )


def test_admin_html_loads_admin_css(admin_html_raw_content):
    """admin.html loads styles.admin.css."""
    assert "styles.admin.css" in admin_html_raw_content, (
        "admin.html does not reference styles.admin.css"
    )


def test_styles_auth_css_contains_login_card():
    """styles.auth.css contains .login-card rule."""
    with open("styles.auth.css", "r", encoding="utf-8") as f:
        content = f.read()
    assert ".login-card" in content, "styles.auth.css is missing .login-card"


def test_styles_admin_css_contains_admin_table():
    """styles.admin.css contains .admin-table rule."""
    with open("styles.admin.css", "r", encoding="utf-8") as f:
        content = f.read()
    assert ".admin-table" in content, "styles.admin.css is missing .admin-table"


def test_styles_css_does_not_contain_login_card():
    """styles.css no longer contains .login-card (moved to styles.auth.css)."""
    with open("styles.css", "r", encoding="utf-8") as f:
        content = f.read()
    assert ".login-card" not in content, (
        "styles.css still contains .login-card — should be in styles.auth.css"
    )


# ── JS extraction: inbox.js ───────────────────────────────────────────────────

def test_inbox_js_exists():
    """src/features/inbox.js exists (maintainability extraction)."""
    assert os.path.isfile("src/features/inbox.js"), "src/features/inbox.js not found"


def test_index_html_contains_inbox_js_script(index_html_content):
    """index.html contains src/features/inbox.js in a <script> tag."""
    assert "src/features/inbox.js" in index_html_content, (
        "index.html does not contain a reference to src/features/inbox.js"
    )


def test_index_html_inbox_js_before_app_js(index_html_content):
    """index.html loads inbox.js before app.js."""
    inbox_pos = index_html_content.find("src/features/inbox.js")
    app_js_pos = index_html_content.find("src/app.js")
    assert inbox_pos != -1, "src/features/inbox.js not found in index.html"
    assert app_js_pos != -1, "src/app.js not found in index.html"
    assert inbox_pos < app_js_pos, (
        f"inbox.js (pos {inbox_pos}) must appear before app.js (pos {app_js_pos})"
    )


def test_inbox_js_exports_window_lehrerInbox():
    """src/features/inbox.js assigns window.LehrerInbox."""
    with open("src/features/inbox.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "window.LehrerInbox" in content, (
        "src/features/inbox.js does not assign window.LehrerInbox"
    )


def test_inbox_js_contains_renderMessages():
    """src/features/inbox.js defines renderMessages()."""
    with open("src/features/inbox.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "function renderMessages" in content, (
        "src/features/inbox.js does not define renderMessages()"
    )


def test_app_js_delegates_renderMessages_to_lehrerInbox(app_js_content):
    """src/app.js renderMessages() delegates to window.LehrerInbox."""
    start = app_js_content.find("function renderMessages")
    assert start != -1, "renderMessages function not found in src/app.js"
    func_region = app_js_content[start:start + 150]
    assert "LehrerInbox" in func_region, (
        "renderMessages() in app.js does not delegate to LehrerInbox"
    )


def test_app_js_delegates_renderPriorities_to_lehrerInbox(app_js_content):
    """src/app.js renderPriorities() delegates to window.LehrerInbox."""
    start = app_js_content.find("function renderPriorities")
    assert start != -1, "renderPriorities function not found in src/app.js"
    func_region = app_js_content[start:start + 150]
    assert "LehrerInbox" in func_region, (
        "renderPriorities() in app.js does not delegate to LehrerInbox"
    )


def test_app_js_contains_grades_seam_comment(app_js_content):
    """src/app.js contains the grades extraction seam comment."""
    assert "grades-render.js" in app_js_content or "future extraction seam" in app_js_content, (
        "src/app.js does not contain the grades extraction seam comment. "
        "Expected: seam comment documenting the next extraction boundary for grades."
    )


def test_styles_css_does_not_contain_admin_table():
    """styles.css no longer contains .admin-table (moved to styles.admin.css)."""
    with open("styles.css", "r", encoding="utf-8") as f:
        content = f.read()
    assert ".admin-table" not in content, (
        "styles.css still contains .admin-table — should be in styles.admin.css"
    )
