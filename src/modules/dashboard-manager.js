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
    var TODAY_LAYOUT_DEFINITION = [
      {
        id: 'briefing',
        label: 'Tagesbriefing',
        description: 'Stundenplan, Orgaplan und Klassenarbeiten fuer den aktuellen Tag.',
        mandatory: true
      },
      {
        id: 'access',
        label: 'Zugaenge',
        description: 'Direkte Arbeitswege fuer die wichtigsten Dienste des Tages.',
        mandatory: true
      },
      {
        id: 'schedule',
        label: 'Stundenplan',
        description: 'Kompakte Vorschau auf deinen Stundenplan.',
        mandatory: false
      },
      {
        id: 'inbox',
        label: 'Posteingang',
        description: 'Letzte Dienstmail und itslearning-Updates.',
        mandatory: false
      },
      {
        id: 'documents',
        label: 'Plaene',
        description: 'Orgaplan und Klassenarbeitsplan in Kurzform.',
        mandatory: false
      },
      {
        id: 'grades',
        label: 'Notenberechnung',
        description: 'Schneller Einstieg in den Notenbereich.',
        mandatory: false
      }
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

    function _todayLayoutKey() {
      var userId = window.CURRENT_USER && window.CURRENT_USER.id ? window.CURRENT_USER.id : 'local';
      return 'lehrerCockpit.todayLayout.v2.' + userId;
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
        var raw = localStorage.getItem(window.MULTIUSER_ENABLED ? _todayLayoutKey() : TODAY_LAYOUT_STORAGE_KEY);
        return _sanitizeTodayLayout(raw ? JSON.parse(raw) : null);
      } catch (_error) {
        return _defaultTodayLayout();
      }
    }

    function _persistTodayLayout() {
      try {
        localStorage.setItem(window.MULTIUSER_ENABLED ? _todayLayoutKey() : TODAY_LAYOUT_STORAGE_KEY, JSON.stringify(_todayLayout));
      } catch (_error) {
        // ignore storage failures
      }
    }

    function getTodayLayout() {
      if (!_todayLayout) _todayLayout = _loadTodayLayout();
      return _sanitizeTodayLayout(_todayLayout);
    }

    function init() {
      if (!window.MULTIUSER_ENABLED) return;
      _todayLayout = _loadTodayLayout();
      _initAsync().catch(function() {});
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
          if (!resp.ok) return;
          return resp.json().then(function(data) {
            if (!data.ok) return;
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
          // fail silently
        });
    }

    function _injectConfigBanners() {
      _modules.forEach(function(m) {
        if (!m.requires_config || m.is_configured || m.module_type !== 'individual') return;
        var sectionId = MODULE_SECTION_MAP[m.module_id];
        if (!sectionId) return;
        var sectionEl = document.querySelector('[data-view-section="' + sectionId + '"]');
        if (!sectionEl) return;
        // Avoid duplicate banners
        if (sectionEl.querySelector('[data-module-config-banner="' + m.module_id + '"]')) return;

        var banner = document.createElement('div');
        banner.className = 'module-config-banner';
        banner.setAttribute('data-module-config-banner', m.module_id);
        banner.innerHTML =
          '<span style="font-size:0.85rem;color:var(--muted);">' +
          '<strong>' + _esc(m.display_name) + '</strong> ist noch nicht konfiguriert.</span> ' +
          '<button class="btn-configure-module" type="button" data-module-id="' + _esc(m.module_id) + '" ' +
          'style="margin-left:0.75rem;padding:0.25rem 0.75rem;border:1px solid var(--accent);' +
          'border-radius:var(--radius-sm);background:transparent;color:var(--accent);font-size:0.82rem;cursor:pointer;">' +
          'Konfigurieren</button>';
        sectionEl.prepend(banner);
      });

      // Wire configure buttons
      document.querySelectorAll('.btn-configure-module').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var moduleId = btn.dataset.moduleId;
          _openConfigForm(moduleId, btn);
        });
      });
    }

    function _openConfigForm(moduleId, triggerEl) {
      var existing = document.getElementById('inline-config-form-' + moduleId);
      if (existing) { existing.remove(); return; }

      var form = document.createElement('form');
      form.id = 'inline-config-form-' + moduleId;
      form.className = 'module-config-inline-form';
      form.style.cssText = 'margin-top:0.75rem;display:flex;flex-direction:column;gap:0.6rem;padding:1rem;' +
        'background:var(--panel-soft);border:1px solid var(--line-strong);border-radius:var(--radius-md);';

      var fields = _getConfigFields(moduleId);
      var fieldsHtml = fields.map(function(f) {
        return '<label style="display:flex;flex-direction:column;gap:0.3rem;font-size:0.82rem;font-weight:500;color:var(--ink);">' +
          _esc(f.label) +
          '<input type="' + _esc(f.type) + '" name="' + _esc(f.key) + '" placeholder="' + _esc(f.placeholder || '') + '" ' +
          'style="padding:0.5rem 0.75rem;border:1px solid var(--line-strong);border-radius:var(--radius-sm);' +
          'background:var(--panel);color:var(--ink);font-size:0.85rem;" autocomplete="off" /></label>';
      }).join('');
      form.innerHTML = fieldsHtml +
        '<div id="config-form-feedback-' + _esc(moduleId) + '" style="min-height:1.2rem;font-size:0.8rem;"></div>' +
        '<div style="display:flex;gap:0.5rem;">' +
        '<button type="submit" style="padding:0.4rem 1rem;border:none;border-radius:var(--radius-sm);background:var(--accent);color:#fff;font-size:0.82rem;font-weight:600;cursor:pointer;">Speichern</button>' +
        '<button type="button" class="btn-cancel-config" style="padding:0.4rem 0.75rem;border:1px solid var(--line-strong);border-radius:var(--radius-sm);background:transparent;color:var(--muted);font-size:0.82rem;cursor:pointer;">Abbrechen</button>' +
        '</div>';

      form.querySelector('.btn-cancel-config').addEventListener('click', function() { form.remove(); });
      form.addEventListener('submit', function(e) {
        e.preventDefault();
        _submitConfigForm(moduleId, form);
      });

      var banner = triggerEl.closest('[data-module-config-banner]');
      if (banner) {
        banner.after(form);
      } else {
        triggerEl.after(form);
      }
    }

    function _getConfigFields(moduleId) {
      if (moduleId === 'webuntis') {
        return [{ key: 'ical_url', label: 'WebUntis iCal-URL', type: 'url', placeholder: 'https://mese.webuntis.com/WebUntis/ical?…' }];
      }
      if (moduleId === 'itslearning') {
        return [
          { key: 'server_url', label: 'Server-URL', type: 'url', placeholder: 'https://schule.itslearning.com' },
          { key: 'username',   label: 'Benutzername', type: 'text', placeholder: 'vorname.nachname' },
          { key: 'password',   label: 'Passwort', type: 'password', placeholder: '••••••••' },
        ];
      }
      if (moduleId === 'nextcloud') {
        return [
          { key: 'server_url', label: 'Server-URL', type: 'url', placeholder: 'https://cloud.schule.de' },
          { key: 'username',   label: 'Benutzername', type: 'text', placeholder: 'vorname.nachname' },
          { key: 'password',   label: 'Passwort', type: 'password', placeholder: '••••••••' },
        ];
      }
      return [];
    }

    function _submitConfigForm(moduleId, form) {
      var feedbackEl = document.getElementById('config-form-feedback-' + moduleId);
      var config = {};
      Array.from(form.elements).forEach(function(el) {
        if (el.name && el.value.trim()) config[el.name] = el.value.trim();
      });

      if (feedbackEl) feedbackEl.textContent = 'Speichere…';

      _apiFetch('/api/v2/dashboard/module-config/' + moduleId, {
        method: 'PUT',
        body: config,
      }).then(function(resp) {
        if (!resp.ok) {
          return resp.json().catch(function() { return {}; }).then(function(err) {
            if (feedbackEl) feedbackEl.textContent = err.error || 'Fehler beim Speichern.';
          });
        }
        if (feedbackEl) feedbackEl.textContent = '✓ Gespeichert!';
        // Remove banner and form
        setTimeout(function() {
          var banner = document.querySelector('[data-module-config-banner="' + moduleId + '"]');
          if (banner) banner.remove();
          form.remove();
          // Update local state
          _modules = _modules.map(function(m) {
            return m.module_id === moduleId ? Object.assign({}, m, { is_configured: true }) : m;
          });
        }, 800);
      }).catch(function() {
        if (feedbackEl) feedbackEl.textContent = 'Verbindungsfehler.';
      });
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
      saveHeuteLayout: saveHeuteLayout
    };
  })();

  window.DashboardManager = DashboardManager;
})();
