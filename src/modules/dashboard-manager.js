/**
 * DashboardManager — Multi-User module layout manager
 *
 * Extracted from src/app.js (Phase 8d).
 * Activated when window.MULTIUSER_ENABLED === true.
 *
 * Fetches GET /api/v2/dashboard, stores module layout, and injects
 * module-config banners.
 *
 * Public API: { init, isModuleVisible, isLayoutReady, getActiveModuleIds,
 *               getModules, getTodayLayout, isMandatoryModule, saveHeuteLayout }
 *
 * Depends on:
 *   - window.LehrerAPI  (from src/api-client.js, loaded first)
 *   - window.BACKEND_API_URL / window.LEHRER_COCKPIT_API_URL
 *   - window.MULTIUSER_ENABLED
 */
(function() {
  'use strict';

  var MANDATORY_MODULE_IDS = ['tagesbriefing', 'zugaenge'];
  var TODAY_LAYOUT_STORAGE_KEY = 'lehrerCockpit.todayLayout.local';

  function isMandatoryModule(moduleId) {
    return MANDATORY_MODULE_IDS.includes(moduleId);
  }

  var DashboardManager = (function() {
    var _modules = [];   // [{module_id, display_name, is_visible, sort_order, is_configured, requires_config, module_type}]
    var _systemSettings = {};
    // _layoutReady tracks whether the layout API response has arrived at least once.
    // Until this is true, isModuleVisible() returns optimistic true (all modules visible),
    // so callers that need accurate visibility state should check isLayoutReady() first.
    var _layoutReady = false;

    // Module-ID → DOM section id mapping (best-effort)
    var MODULE_SECTION_MAP = {
      webuntis:           'schedule',
      itslearning:        'inbox',
      nextcloud:          'access',
      orgaplan:           'documents',
      klassenarbeitsplan: 'documents',
      noten:              'grades',
      mail:               'inbox',
    };
    // Tiles on "Heute" (order + visibility, stored per device). Keep in sync with
    // TODAY_LAYOUT_IDS in src/app.js.
    var TODAY_LAYOUT_DEFINITION = [
      { id: 'schedule', label: 'Stundenplan', mandatory: false },
      { id: 'school', label: 'Heute an der Schule', mandatory: false },
      { id: 'classwork', label: 'Klassenarbeiten', mandatory: false },
      { id: 'inbox', label: 'Posteingang', mandatory: false },
      { id: 'ai', label: 'KI-Zusammenfassung', mandatory: false },
      { id: 'access', label: 'Zugänge', mandatory: false }
    ];
    var _todayLayout = null;

    function _backendBase() {
      return (window.BACKEND_API_URL || window.LEHRER_COCKPIT_API_URL || '').trim();
    }

    function _apiFetch(path, opts) {
      // Use LehrerAPI if available (preferred), otherwise fall back to direct fetch
      if (window.LehrerAPI) {
        // LehrerAPI.apiFetch is internal; replicate the same logic via fetch with credentials
        opts = opts || {};
        opts.credentials = 'include';
        if (opts.body && typeof opts.body === 'object') {
          opts.body = JSON.stringify(opts.body);
          opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
        }
        return fetch(_backendBase() + path, opts);
      }
      opts = opts || {};
      opts.credentials = 'include';
      if (opts.body && typeof opts.body === 'object') {
        opts.body = JSON.stringify(opts.body);
        opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
      }
      return fetch(_backendBase() + path, opts);
    }

    function _emitLayoutChanged() {
      window.dispatchEvent(new CustomEvent('dashboard-layout-changed', {
        detail: { modules: _modules.slice(), todayLayout: getTodayLayout() }
      }));
    }

    function _defaultTodayLayout() {
      return {
        order: TODAY_LAYOUT_DEFINITION.map(function(item) { return item.id; }),
        visibility: TODAY_LAYOUT_DEFINITION.reduce(function(acc, item) {
          acc[item.id] = true;
          return acc;
        }, {}),
      };
    }

    function _sanitizeTodayLayout(layout) {
      var base = _defaultTodayLayout();
      if (!layout || typeof layout !== 'object') return base;

      var knownIds = TODAY_LAYOUT_DEFINITION.map(function(item) { return item.id; });
      var order = Array.isArray(layout.order) ? layout.order.filter(function(id) { return knownIds.indexOf(id) !== -1; }) : [];
      knownIds.forEach(function(id) {
        if (order.indexOf(id) === -1) order.push(id);
      });

      var visibility = Object.assign({}, base.visibility);
      if (layout.visibility && typeof layout.visibility === 'object') {
        knownIds.forEach(function(id) {
          if (typeof layout.visibility[id] === 'boolean') {
            visibility[id] = layout.visibility[id];
          }
        });
      }

      // Mandatory modules are always visible — cannot be disabled by the user.
      TODAY_LAYOUT_DEFINITION.forEach(function(item) {
        if (item.mandatory) {
          visibility[item.id] = true;
        }
      });

      return { order: order, visibility: visibility };
    }

    function _loadTodayLayout() {
      try {
        var raw = localStorage.getItem(TODAY_LAYOUT_STORAGE_KEY);
        if (!raw) {
          var legacyUserId = window.CURRENT_USER && window.CURRENT_USER.id ? window.CURRENT_USER.id : 'local';
          raw = localStorage.getItem('lehrerCockpit.todayLayout.v2.' + legacyUserId);
        }
        return _sanitizeTodayLayout(raw ? JSON.parse(raw) : null);
      } catch (_error) {
        return _defaultTodayLayout();
      }
    }

    function _persistTodayLayout() {
      try {
        localStorage.setItem(TODAY_LAYOUT_STORAGE_KEY, JSON.stringify(_todayLayout));
      } catch (_error) {
        // ignore storage failures
      }
    }

    function getTodayLayout() {
      if (!_todayLayout) _todayLayout = _loadTodayLayout();
      return _sanitizeTodayLayout(_todayLayout);
    }

    function init() {
      if (!window.MULTIUSER_ENABLED) {
        // Local single-user mode has no module layout API: every module is visible,
        // so the layout is ready immediately (otherwise the briefing never renders).
        _layoutReady = true;
        _emitLayoutChanged();
        return;
      }
      _todayLayout = _loadTodayLayout();
      _initAsync().catch(function() {});
    }

    var _LAYOUT_RETRY_MS = 30000;
    var _LAYOUT_MAX_RETRIES = 5;
    var _layoutRetries = 0;

    // Layout API failed: render with all modules visible instead of blocking the
    // briefing forever, and try again later to pick up the user's real layout.
    function _fallbackToDefaultLayout() {
      if (!_layoutReady) {
        _layoutReady = true;
        _emitLayoutChanged();
      }
      if (_layoutRetries >= _LAYOUT_MAX_RETRIES) return;
      _layoutRetries += 1;
      setTimeout(function() { _initAsync().catch(function() {}); }, _LAYOUT_RETRY_MS);
    }

    function _ensureMandatoryModulesFirst(moduleList) {
      // Ensure tagesbriefing is always position 1, zugaenge always position 2
      var result = (moduleList || []).slice();
      var mandatoryDefaults = [
        { module_id: 'tagesbriefing', display_name: 'Tagesbriefing', is_visible: true, sort_order: 1, is_configured: false, requires_config: false, module_type: 'central' },
        { module_id: 'zugaenge',      display_name: 'Zugänge',        is_visible: true, sort_order: 2, is_configured: false, requires_config: false, module_type: 'central' },
      ];
      // Remove any existing mandatory entries (they will be prepended in order)
      result = result.filter(function(m) { return !isMandatoryModule(m.module_id); });
      // Prepend mandatory modules (inject defaults if absent, use existing entry if present)
      var prepend = mandatoryDefaults.map(function(def) {
        var existing = (moduleList || []).find(function(m) { return m.module_id === def.module_id; });
        return existing ? Object.assign({}, existing, { is_visible: true }) : def;
      });
      return prepend.concat(result);
    }

    function _initAsync() {
      return (window.LehrerAPI ? window.LehrerAPI.getDashboardV2() : _apiFetch('/api/v2/dashboard'))
        .then(function(resp) {
          if (!resp.ok) { _fallbackToDefaultLayout(); return; }
          return resp.json().then(function(data) {
            if (!data.ok) { _fallbackToDefaultLayout(); return; }
            var sorted = (data.modules || []).slice().sort(function(a, b) {
              return (a.sort_order || 0) - (b.sort_order || 0);
            });
            _modules = _ensureMandatoryModulesFirst(sorted);
            _systemSettings = data.system || {};
            _layoutReady = true;
            _emitLayoutChanged();

            // Note: #settings-button (old panel trigger) is intentionally kept hidden.
            // Phase 14 uses #heute-anpassen-btn inside the overview section instead.

            // Inject config banners for unconfigured individual modules
            _injectConfigBanners();
          });
        })
        .catch(function() {
          _fallbackToDefaultLayout();
        });
    }

    // Unconfigured personal sources get a short banner in their section; the
    // button opens "Verbindungen" at that source (one place to set things up).
    var BANNER_COPY = {
      webuntis: 'Verbinde WebUntis – dann siehst du hier deinen Stundenplan mit Vertretungen und Entfällen.',
    };

    function _injectConfigBanners() {
      if (!window.MULTIUSER_ENABLED) return;
      _modules.forEach(function(m) {
        if (!m.requires_config || m.is_configured || m.module_type !== 'individual') return;
        var sectionId = MODULE_SECTION_MAP[m.module_id];
        if (!sectionId || !BANNER_COPY[m.module_id]) return;
        var sectionEl = document.querySelector('[data-view-section="' + sectionId + '"]');
        if (!sectionEl || sectionEl.querySelector('[data-module-config-banner="' + m.module_id + '"]')) return;

        var banner = document.createElement('div');
        banner.className = 'module-config-banner';
        banner.setAttribute('data-module-config-banner', m.module_id);
        banner.innerHTML =
          '<span>' + _esc(BANNER_COPY[m.module_id]) + '</span>' +
          '<button class="btn btn-primary btn-sm" type="button" data-open-connections="' + _esc(m.module_id) + '">Jetzt verbinden</button>';
        sectionEl.prepend(banner);
      });
    }

    // Called after a source was connected under "Verbindungen".
    function markConfigured(moduleId) {
      _modules = _modules.map(function(m) {
        return m.module_id === moduleId ? Object.assign({}, m, { is_configured: true }) : m;
      });
      var banner = document.querySelector('[data-module-config-banner="' + moduleId + '"]');
      if (banner) banner.remove();
    }

    function _esc(str) {
      return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Returns true once the layout has been loaded from the API at least once.
    // Before this point, _modules is empty and isModuleVisible() defaults to true.
    // Callers that render module-derived content should skip that content until ready.
    function isLayoutReady() {
      return _layoutReady;
    }

    // Phase 11d: Return array of module IDs that are enabled/visible for the current user.
    // If the layout has not yet been loaded (init still pending), returns null so the caller
    // can fall back to fetching all modules rather than skipping them.
    function getActiveModuleIds() {
      if (!_modules || !_modules.length) return null;
      return _modules
        .filter(function(m) { return m.is_visible !== false && m.enabled !== false; })
        .map(function(m) { return m.module_id; });
    }

    function isModuleVisible(moduleId) {
      if (!moduleId || !_modules || !_modules.length) return true;
      var module = _modules.find(function(m) { return m.module_id === moduleId; });
      if (!module) return true;
      return module.is_visible !== false && module.enabled !== false;
    }

    function getModules() {
      return _modules.slice();
    }

    async function saveHeuteLayout(layoutOrUpdates) {
      if (Array.isArray(layoutOrUpdates)) {
        _todayLayout = _sanitizeTodayLayout({
          order: layoutOrUpdates.map(function(item) { return item.id; }),
          visibility: layoutOrUpdates.reduce(function(acc, item) {
            acc[item.id] = item.is_visible !== false;
            return acc;
          }, {})
        });
      } else if (layoutOrUpdates && typeof layoutOrUpdates === 'object') {
        _todayLayout = _sanitizeTodayLayout(layoutOrUpdates);
      } else {
        _todayLayout = _sanitizeTodayLayout(_todayLayout);
      }

      _persistTodayLayout();
      _emitLayoutChanged();

      // The Today layout is currently a UI personalization layer.
      // It is stored locally for both local and hosted usage so preview cards
      // can evolve independently of the backend module model.
      return true;
    }

    return {
      init: init,
      getActiveModuleIds: getActiveModuleIds,
      getModules: getModules,
      isModuleVisible: isModuleVisible,
      isLayoutReady: isLayoutReady,
      getTodayLayout: getTodayLayout,
      isMandatoryModule: isMandatoryModule,
      saveHeuteLayout: saveHeuteLayout,
      markConfigured: markConfigured
    };
  })();

  window.DashboardManager = DashboardManager;
})();
