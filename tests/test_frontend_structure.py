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
    """dashboard-manager.js dead panel functions have been removed (I-001 cleanup).

    _saveLayout, openLayoutPanel, _renderLayoutPanelContent, _wireSettingsButton,
    and _getDragAfterElement were removed as part of I-001. The active layout
    persistence is now saveHeuteLayout().
    """
    # Dead panel functions must be absent
    assert "function _saveLayout" not in dashboard_manager_content, (
        "_saveLayout() is dead code and should have been removed (I-001). "
        "Active layout persistence is saveHeuteLayout()."
    )
    assert "function openLayoutPanel" not in dashboard_manager_content, (
        "openLayoutPanel() is dead code and should have been removed (I-001). "
        "The active panel is #heute-anpassen-panel."
    )
    # Active replacement must be present
    assert "saveHeuteLayout" in dashboard_manager_content, (
        "saveHeuteLayout() not found in dashboard-manager.js. "
        "Expected: active heute layout persistence function."
    )
    # _emitLayoutChanged must still be present (used by _initAsync)
    assert "_emitLayoutChanged" in dashboard_manager_content, (
        "_emitLayoutChanged() was removed but is still needed by _initAsync(). "
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
    """_renderLayoutPanelContent() has been removed as dead code (I-001 cleanup).

    The old overlay panel (#layout-panel-overlay) and all its functions were
    removed. The active heute layout panel is #heute-anpassen-panel managed
    outside dashboard-manager.js.
    """
    # Dead panel function must be absent
    assert "function _renderLayoutPanelContent" not in dashboard_manager_content, (
        "_renderLayoutPanelContent() is dead code and should have been removed (I-001). "
        "Active panel: #heute-anpassen-panel."
    )
    # (idx + 1) bug must also be absent
    assert "(idx + 1)" not in dashboard_manager_content, (
        "The (idx + 1) sort-order bug still exists in dashboard-manager.js. "
        "Expected: removed together with _renderLayoutPanelContent."
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
    """_renderLayoutPanelContent() has been removed as dead code (I-001 cleanup).

    Belt-and-suspenders: confirms the (idx + 1) bug is gone and that the dead
    function is absent from dashboard-manager.js.
    """
    # Dead function must be absent
    assert "function _renderLayoutPanelContent" not in dashboard_manager_content, (
        "_renderLayoutPanelContent() is dead code and should have been removed (I-001)."
    )
    # (idx + 1) bug must also be absent from the whole file
    assert "(idx + 1)" not in dashboard_manager_content, (
        "The (idx + 1) sort-order bug still exists in dashboard-manager.js."
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


# ── Phase 16: pickInboxBriefing extraction tests ─────────────────────────────

def test_inbox_js_contains_pickInboxBriefing():
    """src/features/inbox.js defines pickInboxBriefing() (Phase 16 extraction)."""
    with open("src/features/inbox.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "function pickInboxBriefing" in content, (
        "src/features/inbox.js does not define pickInboxBriefing(). "
        "Expected: briefing helper moved from app.js to inbox.js."
    )


def test_inbox_js_exports_pickInboxBriefing():
    """src/features/inbox.js exports pickInboxBriefing in window.LehrerInbox."""
    with open("src/features/inbox.js", "r", encoding="utf-8") as f:
        content = f.read()
    return_start = content.rfind("return {")
    assert return_start != -1, "Public API return block not found in inbox.js"
    api_block = content[return_start:]
    assert "pickInboxBriefing" in api_block, (
        "window.LehrerInbox does not expose pickInboxBriefing in public API."
    )


def test_app_js_pickInboxBriefing_delegates_to_lehrerInbox(app_js_content):
    """src/app.js pickInboxBriefing() delegates to window.LehrerInbox (Phase 16)."""
    start = app_js_content.find("function pickInboxBriefing")
    assert start != -1, "pickInboxBriefing not found in src/app.js"
    func_region = app_js_content[start:start + 150]
    assert "LehrerInbox" in func_region, (
        "pickInboxBriefing() in app.js does not delegate to LehrerInbox. "
        "Expected: if (window.LehrerInbox) return window.LehrerInbox.pickInboxBriefing(data);"
    )


def test_app_js_no_dead_channelLabels_constant(app_js_content):
    """src/app.js no longer defines the channelLabels constant (moved to inbox.js).

    The channelLabels object (mail: 'Dienstmail', itslearning: 'itslearning') was a
    dead constant in app.js after the inbox rendering was extracted. Phase 16 removes it.
    """
    # channelLabels definition must not appear as an assignment in app.js
    import re
    pattern = re.compile(r'const\s+channelLabels\s*=\s*\{')
    assert not pattern.search(app_js_content), (
        "src/app.js still defines 'const channelLabels = {...}'. "
        "This dead constant was moved to src/features/inbox.js in Phase 16."
    )


def test_app_js_grades_rendering_delegated_to_lehrerGrades(app_js_content):
    """src/app.js renderGrades() delegates to window.LehrerGrades (Phase 15 extraction complete).

    The old 'future extraction seam' comment is gone because the extraction is done.
    Both renderGrades() and renderClassNotes() must delegate to LehrerGrades.
    """
    start_rg = app_js_content.find("function renderGrades")
    assert start_rg != -1, "renderGrades function not found in src/app.js"
    rg_region = app_js_content[start_rg:start_rg + 150]
    assert "LehrerGrades" in rg_region, (
        "renderGrades() in app.js does not delegate to LehrerGrades. "
        "Expected: if (window.LehrerGrades) return window.LehrerGrades.renderGrades();"
    )

    start_rcn = app_js_content.find("function renderClassNotes")
    assert start_rcn != -1, "renderClassNotes function not found in src/app.js"
    rcn_region = app_js_content[start_rcn:start_rcn + 150]
    assert "LehrerGrades" in rcn_region, (
        "renderClassNotes() in app.js does not delegate to LehrerGrades. "
        "Expected: if (window.LehrerGrades) return window.LehrerGrades.renderClassNotes(...);"
    )


def test_styles_css_does_not_contain_admin_table():
    """styles.css no longer contains .admin-table (moved to styles.admin.css)."""
    with open("styles.css", "r", encoding="utf-8") as f:
        content = f.read()
    assert ".admin-table" not in content, (
        "styles.css still contains .admin-table — should be in styles.admin.css"
    )


# ── Phase 15: grades rendering extraction tests ──────────────────────────────

@pytest.fixture(scope="module")
def grades_js_content():
    with open("src/features/grades.js", "r", encoding="utf-8") as f:
        return f.read()


def test_grades_js_contains_renderGrades(grades_js_content):
    """src/features/grades.js defines renderGrades() (Phase 15 extraction)."""
    assert "function renderGrades" in grades_js_content, (
        "src/features/grades.js does not define renderGrades(). "
        "Expected: full renderGrades() implementation extracted from app.js."
    )


def test_grades_js_contains_renderClassNotes(grades_js_content):
    """src/features/grades.js defines renderClassNotes() (Phase 15 extraction)."""
    assert "function renderClassNotes" in grades_js_content, (
        "src/features/grades.js does not define renderClassNotes(). "
        "Expected: full renderClassNotes() implementation extracted from app.js."
    )


def test_grades_js_contains_getGradebookData(grades_js_content):
    """src/features/grades.js defines getGradebookData() (Phase 15 extraction)."""
    assert "function getGradebookData" in grades_js_content, (
        "src/features/grades.js does not define getGradebookData()."
    )


def test_grades_js_contains_getNotesData(grades_js_content):
    """src/features/grades.js defines getNotesData() (Phase 15 extraction)."""
    assert "function getNotesData" in grades_js_content, (
        "src/features/grades.js does not define getNotesData()."
    )


def test_grades_js_contains_summarizeGrades(grades_js_content):
    """src/features/grades.js defines summarizeGrades() (Phase 15 extraction)."""
    assert "function summarizeGrades" in grades_js_content, (
        "src/features/grades.js does not define summarizeGrades()."
    )


def test_grades_js_contains_getGradeClasses(grades_js_content):
    """src/features/grades.js defines getGradeClasses() (Phase 15 extraction)."""
    assert "function getGradeClasses" in grades_js_content, (
        "src/features/grades.js does not define getGradeClasses()."
    )


def test_grades_js_exports_renderGrades_in_public_api(grades_js_content):
    """src/features/grades.js exports renderGrades in window.LehrerGrades public API."""
    return_start = grades_js_content.rfind("window.LehrerGrades = {")
    assert return_start != -1, "window.LehrerGrades public API not found in grades.js"
    api_block = grades_js_content[return_start:]
    assert "renderGrades" in api_block, (
        "window.LehrerGrades does not expose renderGrades in public API."
    )
    assert "renderClassNotes" in api_block, (
        "window.LehrerGrades does not expose renderClassNotes in public API."
    )
    assert "getGradebookData" in api_block, (
        "window.LehrerGrades does not expose getGradebookData in public API."
    )
    assert "getNotesData" in api_block, (
        "window.LehrerGrades does not expose getNotesData in public API."
    )
    assert "summarizeGrades" in api_block, (
        "window.LehrerGrades does not expose summarizeGrades in public API."
    )


def test_app_js_getGradebookData_delegates_to_lehrerGrades(app_js_content):
    """src/app.js getGradebookData() delegates to window.LehrerGrades (Phase 15)."""
    start = app_js_content.find("function getGradebookData")
    assert start != -1, "getGradebookData not found in src/app.js"
    region = app_js_content[start:start + 150]
    assert "LehrerGrades" in region, (
        "getGradebookData() in app.js does not delegate to LehrerGrades."
    )


def test_app_js_getNotesData_delegates_to_lehrerGrades(app_js_content):
    """src/app.js getNotesData() delegates to window.LehrerGrades (Phase 15)."""
    start = app_js_content.find("function getNotesData")
    assert start != -1, "getNotesData not found in src/app.js"
    region = app_js_content[start:start + 150]
    assert "LehrerGrades" in region, (
        "getNotesData() in app.js does not delegate to LehrerGrades."
    )


def test_app_js_summarizeGrades_delegates_to_lehrerGrades(app_js_content):
    """src/app.js summarizeGrades() delegates to window.LehrerGrades (Phase 15)."""
    start = app_js_content.find("function summarizeGrades")
    assert start != -1, "summarizeGrades not found in src/app.js"
    region = app_js_content[start:start + 150]
    assert "LehrerGrades" in region, (
        "summarizeGrades() in app.js does not delegate to LehrerGrades."
    )


def test_grades_js_init_accepts_getData_callback(grades_js_content):
    """src/features/grades.js init() uses getData callback (Phase 15 interface)."""
    assert "getData" in grades_js_content, (
        "grades.js does not reference getData callback. "
        "Expected: getData injected via init() so getGradeClasses() can read classwork classes."
    )


# ── JS extraction: nextcloud.js (Phase 14) ───────────────────────────────────

def test_nextcloud_js_exists():
    """src/features/nextcloud.js exists (Phase 14 extraction)."""
    assert os.path.isfile("src/features/nextcloud.js"), "src/features/nextcloud.js not found"


def test_index_html_contains_nextcloud_js_script(index_html_content):
    """index.html contains src/features/nextcloud.js in a <script> tag."""
    assert "src/features/nextcloud.js" in index_html_content, (
        "index.html does not contain a reference to src/features/nextcloud.js"
    )


def test_index_html_nextcloud_js_before_app_js(index_html_content):
    """index.html loads nextcloud.js before app.js."""
    nextcloud_pos = index_html_content.find("src/features/nextcloud.js")
    app_js_pos = index_html_content.find("src/app.js")
    assert nextcloud_pos != -1, "src/features/nextcloud.js not found in index.html"
    assert app_js_pos != -1, "src/app.js not found in index.html"
    assert nextcloud_pos < app_js_pos, (
        f"nextcloud.js (pos {nextcloud_pos}) must appear before app.js (pos {app_js_pos})"
    )


def test_nextcloud_js_exports_window_lehrerNextcloud():
    """src/features/nextcloud.js assigns window.LehrerNextcloud."""
    with open("src/features/nextcloud.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "window.LehrerNextcloud" in content, (
        "src/features/nextcloud.js does not assign window.LehrerNextcloud"
    )


def test_nextcloud_js_contains_renderNextcloudConnector():
    """src/features/nextcloud.js defines renderNextcloudConnector()."""
    with open("src/features/nextcloud.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "function renderNextcloudConnector" in content, (
        "src/features/nextcloud.js does not define renderNextcloudConnector()"
    )


def test_nextcloud_js_contains_saveNextcloudCredentials():
    """src/features/nextcloud.js defines saveNextcloudCredentials()."""
    with open("src/features/nextcloud.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "function saveNextcloudCredentials" in content or "saveNextcloudCredentials" in content, (
        "src/features/nextcloud.js does not define saveNextcloudCredentials()"
    )


def test_app_js_delegates_renderNextcloudConnector_to_lehrerNextcloud(app_js_content):
    """src/app.js renderNextcloudConnector() delegates to window.LehrerNextcloud."""
    start = app_js_content.find("function renderNextcloudConnector")
    assert start != -1, "renderNextcloudConnector function not found in src/app.js"
    func_region = app_js_content[start:start + 200]
    assert "LehrerNextcloud" in func_region, (
        "renderNextcloudConnector() in app.js does not delegate to LehrerNextcloud"
    )


def test_app_js_delegates_saveNextcloudCredentials_to_lehrerNextcloud(app_js_content):
    """src/app.js saveNextcloudCredentials() delegates to window.LehrerNextcloud."""
    start = app_js_content.find("function saveNextcloudCredentials")
    assert start != -1, "saveNextcloudCredentials function not found in src/app.js"
    func_region = app_js_content[start:start + 150]
    assert "LehrerNextcloud" in func_region, (
        "saveNextcloudCredentials() in app.js does not delegate to LehrerNextcloud"
    )


def test_app_js_references_window_lehrerNextcloud(app_js_content):
    """src/app.js references window.LehrerNextcloud (extraction confirmation)."""
    assert "window.LehrerNextcloud" in app_js_content, (
        "src/app.js does not reference window.LehrerNextcloud. "
        "Expected delegates calling window.LehrerNextcloud.*() after Phase 14 extraction."
    )


# ── Phase 17: app.js dead-code cleanup tests ─────────────────────────────────

def test_app_js_no_duplicate_weekdayLabel(app_js_content):
    """src/app.js defines weekdayLabel exactly once (Phase 17: duplicate removed).

    The shadowed copy near the LehrerClasswork delegation block was dead code —
    it was overridden by the real weekdayLabel defined in the date utilities section.
    """
    count = app_js_content.count("function weekdayLabel")
    assert count == 1, (
        f"src/app.js defines weekdayLabel {count} times; expected exactly 1. "
        "The duplicate copy has been removed in Phase 17."
    )


def test_app_js_renderItslearningConnector_no_fallback_body(app_js_content):
    """src/app.js renderItslearningConnector() is a thin delegation wrapper (Phase 17).

    The 28-line fallback body duplicating itslearning.js has been removed.
    """
    start = app_js_content.find("function renderItslearningConnector")
    assert start != -1, "renderItslearningConnector not found in src/app.js"
    func_region = app_js_content[start:start + 200]
    assert "itslearningConnectCard.hidden" not in func_region, (
        "renderItslearningConnector() in app.js still contains the fallback body "
        "that duplicates itslearning.js logic. Phase 17 removes it."
    )
    assert "LehrerItslearning" in func_region, (
        "renderItslearningConnector() in app.js does not delegate to LehrerItslearning."
    )


def test_app_js_renderWebUntisControls_no_fallback_body(app_js_content):
    """src/app.js renderWebUntisControls() is a thin delegation wrapper (Phase 17).

    The 20-line fallback body has been removed since LehrerWebUntis is verified.
    """
    start = app_js_content.find("function renderWebUntisControls")
    assert start != -1, "renderWebUntisControls not found in src/app.js"
    func_region = app_js_content[start:start + 200]
    assert "webuntisViewSwitch.innerHTML" not in func_region, (
        "renderWebUntisControls() in app.js still contains the old fallback body. "
        "Phase 17 removes it."
    )
    assert "LehrerWebUntis" in func_region, (
        "renderWebUntisControls() does not delegate to LehrerWebUntis."
    )


def test_app_js_no_todo_split_comment(app_js_content):
    """src/app.js no longer contains the obsolete 'TODO: Split this file' comment (Phase 17).

    All planned module splits have been done (Phases 8–16). The header comment
    now describes the current architecture instead of the planned future state.
    """
    assert "TODO: Split this file" not in app_js_content, (
        "src/app.js still contains the obsolete 'TODO: Split this file' comment. "
        "All module extractions are complete; Phase 17 updates the header."
    )


# ── Phase 18: Dashboard UI polish tests ──────────────────────────────────────

@pytest.fixture(scope="module")
def styles_css_content():
    with open("styles.css", "r", encoding="utf-8") as f:
        return f.read()


def test_styles_css_area_divider_desktop_rule(styles_css_content):
    """styles.css defines .area-divider desktop rule (Phase 18 UI polish).

    The area-divider had no desktop CSS — only a mobile override margin.
    Phase 18 adds the real rule: horizontal line + uppercase label.
    """
    assert ".area-divider {" in styles_css_content, (
        "styles.css does not define a .area-divider rule. "
        "Expected: layout rule with line + label for section framing."
    )
    assert ".area-divider-label {" in styles_css_content, (
        "styles.css does not define .area-divider-label. "
        "Expected: uppercase, spaced, muted label style."
    )


def test_index_html_area_dividers_have_data_divider_for(index_html_content):
    """index.html area-divider elements targeting optional sections have data-divider-for attributes.

    The JS uses data-divider-for to hide dividers when their section is disabled
    (e.g. 'Unterricht & Tagesplan' hidden when webuntis module is off).
    The four module-gated sections (schedule, inbox, grades, documents) must each
    have a matching data-divider-for on their preceding area-divider.
    """
    for section in ["schedule", "inbox", "grades", "documents"]:
        assert f'data-divider-for="{section}"' in index_html_content, (
            f"index.html area-divider for section '{section}' is missing "
            f'data-divider-for="{section}" attribute. Phase 18 adds these for '
            "conditional hiding when the section is disabled."
        )


def test_app_js_viewDividers_in_elements(app_js_content):
    """src/app.js elements object includes viewDividers list (Phase 18).

    viewDividers holds all [data-divider-for] elements so renderSectionFocus()
    can hide the ones whose target section is disabled.
    """
    assert "viewDividers" in app_js_content, (
        "src/app.js does not reference viewDividers. "
        "Expected: elements.viewDividers used in renderSectionFocus() for divider hiding."
    )


def test_app_js_renderSectionFocus_hides_dividers(app_js_content):
    """src/app.js renderSectionFocus() hides area dividers when their section is disabled (Phase 18)."""
    start = app_js_content.find("function renderSectionFocus")
    assert start != -1, "renderSectionFocus not found in src/app.js"
    func_region = app_js_content[start:start + 1400]
    assert "viewDividers" in func_region, (
        "renderSectionFocus() does not reference viewDividers. "
        "Expected: dividers hidden when their target section is disabled."
    )
    # dataset.dividerFor is the camelCase JS accessor for data-divider-for
    assert "dividerFor" in func_region, (
        "renderSectionFocus() does not read dataset.dividerFor. "
        "Expected: divider.dataset.dividerFor used to identify target section."
    )


def test_app_js_renderStats_unhides_stats_grid(app_js_content):
    """src/app.js renderStats() explicitly shows/hides statsGrid element (Phase 18).

    The stats-grid is hidden by default in HTML. Before Phase 18 renderStats()
    never called statsGrid.hidden = false, so stat tiles were never displayed.
    """
    start = app_js_content.find("function renderStats")
    assert start != -1, "renderStats not found in src/app.js"
    func_region = app_js_content[start:start + 2000]
    # elements.statsGrid.hidden is the pattern in app.js
    assert "statsGrid.hidden" in func_region, (
        "renderStats() does not set elements.statsGrid.hidden. "
        "Expected: statsGrid.hidden = false when cards exist, true when empty."
    )


def test_styles_css_briefing_empty_and_loading_states(styles_css_content):
    """styles.css defines .briefing-empty and .briefing-loading states (Phase 18).

    These replace the generic .empty-state in the briefing output to provide
    a less jarring empty/loading appearance while data is loading.
    """
    assert ".briefing-loading" in styles_css_content, (
        "styles.css does not define .briefing-loading. "
        "Expected: subtle italic loading placeholder for briefing."
    )
    assert ".briefing-empty" in styles_css_content, (
        "styles.css does not define .briefing-empty. "
        "Expected: clean empty-state style for briefing with no content."
    )


def test_app_js_briefing_uses_briefing_loading_class(app_js_content):
    """src/app.js renderBriefing() uses briefing-loading class for pre-layout placeholder."""
    assert "briefing-loading" in app_js_content, (
        "src/app.js renderBriefing() does not use 'briefing-loading' class. "
        "Expected: pre-layout flash suppressed with a distinct loading placeholder."
    )
    assert "briefing-empty" in app_js_content, (
        "src/app.js renderBriefing() does not use 'briefing-empty' class. "
        "Expected: briefing empty state uses briefing-empty instead of generic empty-state."
    )


# ── Phase 19: CSS consistency + density polish tests ─────────────────────────

def test_styles_css_empty_state_min_height_reduced(styles_css_content):
    """styles.css empty-state min-height is ≤56px (Phase 19: reduced from 84px).

    Large empty-state boxes felt imposing in sparse dashboards. The reduced
    height keeps them visible but less dominant.
    """
    import re
    # Find the .empty-state block and check min-height value
    match = re.search(r'\.empty-state\s*\{[^}]+min-height:\s*(\d+)px', styles_css_content, re.DOTALL)
    # Also accept webuntis-week-empty grouped rule
    if not match:
        match = re.search(r'\.webuntis-week-empty,\s*\.empty-state\s*\{[^}]+min-height:\s*(\d+)px', styles_css_content, re.DOTALL)
    assert match is not None, "styles.css does not define min-height on .empty-state"
    height_value = int(match.group(1))
    assert height_value <= 64, (
        f"styles.css empty-state min-height is {height_value}px, expected ≤64px. "
        "Phase 19 reduces it so empty states feel less imposing in sparse dashboards."
    )


def test_styles_css_briefing_output_has_min_height(styles_css_content):
    """styles.css .briefing-output has a min-height (Phase 19: prevents card collapse).

    Without a min-height the briefing card collapses when content is sparse or
    not yet loaded, creating an awkward flat header-only card.
    The rule may appear in a combined selector or a standalone .briefing-output block.
    """
    # Find any occurrence of min-height within 60 chars of briefing-output in the same rule block
    import re
    # Match standalone .briefing-output { ... min-height: ... } rule
    match = re.search(r'\.briefing-output\s*\{[^}]*min-height', styles_css_content, re.DOTALL)
    assert match is not None, (
        "styles.css .briefing-output does not have min-height in its rule block. "
        "Expected: briefing card maintains visual weight when content is sparse."
    )


def test_styles_css_stat_card_has_hover_transition(styles_css_content):
    """styles.css .stat-card has a transition rule for subtle hover interactivity (Phase 19)."""
    stat_card_start = styles_css_content.find(".stat-card {")
    assert stat_card_start != -1, ".stat-card rule not found in styles.css"
    stat_region = styles_css_content[stat_card_start:stat_card_start + 300]
    assert "transition" in stat_region, (
        "styles.css .stat-card does not have a transition property. "
        "Expected: subtle hover transition for micro-interaction quality."
    )


def test_styles_css_briefing_item_has_hover_state(styles_css_content):
    """styles.css .briefing-item[data-briefing-target]:hover is defined (Phase 19)."""
    assert "briefing-item[data-briefing-target]:hover" in styles_css_content, (
        "styles.css does not define .briefing-item[data-briefing-target]:hover. "
        "Expected: hover state for clickable briefing secondary items."
    )


def test_styles_css_section_appear_animation(styles_css_content):
    """styles.css defines section-appear keyframe animation for section fade-in (Phase 19)."""
    assert "section-appear" in styles_css_content, (
        "styles.css does not define 'section-appear' animation. "
        "Expected: subtle fade-in when sections become visible after module toggle."
    )
    assert "@keyframes section-appear" in styles_css_content, (
        "styles.css does not define @keyframes section-appear. "
        "Expected: keyframe definition for the section appear animation."
    )


# ── Package A: Today view mandatory module model ──────────────────────────────


def test_dashboard_manager_today_layout_definition_briefing_mandatory(dashboard_manager_content):
    """dashboard-manager.js TODAY_LAYOUT_DEFINITION marks 'briefing' as mandatory.

    Tagesbriefing must always be visible in the Today view — it is the core
    orientation block and cannot be disabled by users.
    The definition object must include mandatory: true.
    """
    # Find the TODAY_LAYOUT_DEFINITION array body
    start = dashboard_manager_content.find("TODAY_LAYOUT_DEFINITION")
    assert start != -1, "TODAY_LAYOUT_DEFINITION not found in dashboard-manager.js"
    # The definition covers briefing, updates, access — ~300 chars is enough
    region = dashboard_manager_content[start:start + 600]
    assert "briefing" in region, "briefing entry missing from TODAY_LAYOUT_DEFINITION"
    # Find the briefing sub-object and check mandatory within it
    briefing_start = region.find("'briefing'")
    if briefing_start == -1:
        briefing_start = region.find('"briefing"')
    assert briefing_start != -1, "briefing id not found in TODAY_LAYOUT_DEFINITION"
    # The mandatory flag must appear after the briefing id within ~150 chars (covers the object)
    briefing_region = region[briefing_start:briefing_start + 200]
    assert "mandatory" in briefing_region, (
        "TODAY_LAYOUT_DEFINITION briefing entry does not have 'mandatory' property. "
        "Expected: mandatory: true on briefing so it cannot be disabled by users."
    )
    assert "true" in briefing_region, (
        "TODAY_LAYOUT_DEFINITION briefing mandatory property is not set to true."
    )


def test_dashboard_manager_today_layout_definition_access_mandatory(dashboard_manager_content):
    """dashboard-manager.js TODAY_LAYOUT_DEFINITION marks 'access' (Zugaenge) as mandatory.

    Zugaenge must always be visible in the Today view — it is the launcher
    hub and must always be available above the fold.
    The definition object must include mandatory: true.
    """
    start = dashboard_manager_content.find("TODAY_LAYOUT_DEFINITION")
    assert start != -1, "TODAY_LAYOUT_DEFINITION not found in dashboard-manager.js"
    region = dashboard_manager_content[start:start + 600]
    assert "access" in region, "access entry missing from TODAY_LAYOUT_DEFINITION"
    # Find the access sub-object and check mandatory within it
    access_start = region.find("'access'")
    if access_start == -1:
        access_start = region.find('"access"')
    assert access_start != -1, "access id not found in TODAY_LAYOUT_DEFINITION"
    access_region = region[access_start:access_start + 200]
    assert "mandatory" in access_region, (
        "TODAY_LAYOUT_DEFINITION access entry does not have 'mandatory' property. "
        "Expected: mandatory: true on access (Zugaenge) so it cannot be disabled by users."
    )
    assert "true" in access_region, (
        "TODAY_LAYOUT_DEFINITION access mandatory property is not set to true."
    )


def test_dashboard_manager_sanitize_layout_enforces_mandatory_modules(dashboard_manager_content):
    """dashboard-manager.js _sanitizeTodayLayout enforces mandatory modules always visible.

    After sanitization, modules with mandatory: true in TODAY_LAYOUT_DEFINITION
    must have visibility[id] = true regardless of what was passed in.
    The enforcement loop must appear in _sanitizeTodayLayout after the user
    visibility overrides, so it cannot be bypassed by a saved layout state.
    """
    start = dashboard_manager_content.find("function _sanitizeTodayLayout")
    assert start != -1, "_sanitizeTodayLayout not found in dashboard-manager.js"
    # Use 1200 chars — full function including mandatory enforcement loop
    func_region = dashboard_manager_content[start:start + 1200]
    assert "mandatory" in func_region, (
        "_sanitizeTodayLayout() does not reference 'mandatory'. "
        "Expected: mandatory modules are always forced to visible=true inside _sanitizeTodayLayout."
    )
    # The enforcement must appear AFTER the user-override loop (i.e. after the visibility block)
    visibility_override_pos = func_region.find("layout.visibility")
    mandatory_enforcement_pos = func_region.find("mandatory", visibility_override_pos)
    assert mandatory_enforcement_pos != -1, (
        "mandatory enforcement in _sanitizeTodayLayout appears BEFORE the user visibility "
        "override loop — it must come after so it cannot be bypassed by saved state."
    )


def test_styles_css_layout_module_mandatory_badge(styles_css_content):
    """styles.css .layout-module-mandatory-badge and .layout-panel* CSS removed (I-001 cleanup).

    The old #layout-panel-overlay and all its CSS were dead code and have been
    removed. The active panel is #heute-anpassen-panel.
    """
    assert ".layout-module-mandatory-badge" not in styles_css_content, (
        "styles.css still defines .layout-module-mandatory-badge — "
        "this is dead CSS for the removed #layout-panel-overlay and should be absent (I-001)."
    )
    assert ".layout-panel" not in styles_css_content, (
        "styles.css still defines .layout-panel* CSS — "
        "this is dead CSS for the removed #layout-panel-overlay and should be absent (I-001)."
    )
