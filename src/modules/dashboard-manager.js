/**
 * DashboardManager — Multi-User module layout manager
 *
 * Extracted from src/app.js (Phase 8d).
 * Activated when window.MULTIUSER_ENABLED === true.
 *
 * Fetches GET /api/v2/dashboard, stores module layout, wires the settings
 * panel (layout management), and injects module-config banners.
 *
 * Public API: { init, openLayoutPanel }
 *
 * Depends on:
 *   - window.LehrerAPI  (from src/api-client.js, loaded first)
 *   - window.BACKEND_API_URL / window.LEHRER_COCKPIT_API_URL
 *   - window.MULTIUSER_ENABLED
 */
(function() {
  'use strict';

  var MANDATORY_MODULE_IDS = ['tagesbriefing', 'zugaenge'];

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
        id: 'updates',
        label: 'Updates aus der Webseite',
        description: 'Kompakter Block fuer die letzte Woche.'
      },
      {
        id: 'access',
        label: 'Alle Zugaenge',
        description: 'Kleine Sammlung der wichtigsten Arbeitslinks fuer heute.',
        mandatory: true
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
        var raw = localStorage.getItem(_todayLayoutKey());
        return _sanitizeTodayLayout(raw ? JSON.parse(raw) : null);
      } catch (_error) {
        return _defaultTodayLayout();
      }
    }

    function _persistTodayLayout() {
      try {
        localStorage.setItem(_todayLayoutKey(), JSON.stringify(_todayLayout));
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

            // Show settings button in topbar
            var settingsBtn = document.getElementById('settings-button');
            if (settingsBtn) {
              settingsBtn.style.display = '';
              settingsBtn.textContent = 'Heute anpassen';
            }

            // Inject config banners for unconfigured individual modules
            _injectConfigBanners();

            // Wire settings button
            _wireSettingsButton();
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

    function _wireSettingsButton() {
      var btn = document.getElementById('settings-button');
      if (!btn) return;
      btn.onclick = function() { openLayoutPanel(); };
    }

    function openLayoutPanel() {
      var overlay = document.getElementById('layout-panel-overlay');
      if (!overlay) return;
      _renderLayoutPanelContent();
      overlay.hidden = false;

      var closeBtn = document.getElementById('layout-panel-close');
      var cancelBtn = document.getElementById('layout-panel-cancel');
      var saveBtn = document.getElementById('layout-panel-save');

      function closePanel() { overlay.hidden = true; }
      if (closeBtn) closeBtn.onclick = closePanel;
      if (cancelBtn) cancelBtn.onclick = closePanel;
      overlay.onclick = function(e) { if (e.target === overlay) closePanel(); };
      if (saveBtn) {
        saveBtn.onclick = function() { _saveLayout(saveBtn); };
      }
    }

    function _renderLayoutPanelContent() {
      var title = document.getElementById('layout-panel-title');
      var description = document.getElementById('layout-panel-description');
      var list = document.getElementById('layout-module-list');
      if (!list) return;
      if (title) title.textContent = 'Heute personalisieren';
      if (description) {
        description.textContent = 'Ordne die optionalen Bereiche in der gewuenschten Reihenfolge. Tagesbriefing und Zugaenge sind immer sichtbar und koennen nicht entfernt werden.';
      }
      list.innerHTML = '';
      var layout = getTodayLayout();
      (layout.order || []).forEach(function(moduleId) {
        var definition = TODAY_LAYOUT_DEFINITION.find(function(item) { return item.id === moduleId; });
        if (!definition) return;
        var isMandatory = definition.mandatory === true;
        var row = document.createElement('div');
        row.className = 'layout-module-row' + (isMandatory ? ' layout-module-row-mandatory' : '');
        row.draggable = !isMandatory;
        row.dataset.todayModuleId = definition.id;
        if (isMandatory) {
          // Mandatory modules: locked checkbox (always checked, disabled) + "Fest" badge
          row.innerHTML =
            '<span class="layout-drag-handle layout-drag-handle-locked" aria-hidden="true">⋮⋮</span>' +
            '<input type="checkbox" id="lm-enabled-' + _esc(definition.id) + '" ' +
            'checked disabled style="cursor:not-allowed;accent-color:var(--accent);width:16px;height:16px;opacity:0.5;" />' +
            '<label class="layout-module-meta" for="lm-enabled-' + _esc(definition.id) + '">' +
            '<strong>' + _esc(definition.label) + '</strong>' +
            '<span>' + _esc(definition.description) + '</span>' +
            '</label>' +
            '<span class="layout-module-mandatory-badge" title="Pflichtmodul — kann nicht entfernt werden">Fest</span>';
        } else {
          // Optional modules: normal draggable row with active checkbox
          row.innerHTML =
            '<span class="layout-drag-handle" aria-hidden="true">⋮⋮</span>' +
            '<input type="checkbox" id="lm-enabled-' + _esc(definition.id) + '" ' +
            (layout.visibility[definition.id] !== false ? 'checked' : '') + ' style="cursor:pointer;accent-color:var(--accent);width:16px;height:16px;" />' +
            '<label class="layout-module-meta" for="lm-enabled-' + _esc(definition.id) + '">' +
            '<strong>' + _esc(definition.label) + '</strong>' +
            '<span>' + _esc(definition.description) + '</span>' +
            '</label>';
        }
        if (!isMandatory) {
          row.addEventListener('dragstart', function() {
            row.classList.add('is-dragging');
          });
          row.addEventListener('dragend', function() {
            row.classList.remove('is-dragging');
          });
        }
        list.appendChild(row);
      });

      list.ondragover = function(event) {
        event.preventDefault();
        var dragging = list.querySelector('.layout-module-row.is-dragging');
        if (!dragging) return;
        var afterElement = _getDragAfterElement(list, event.clientY);
        if (!afterElement) {
          list.appendChild(dragging);
          return;
        }
        list.insertBefore(dragging, afterElement);
      };
    }

    function _saveLayout(saveBtn) {
      var feedbackEl = document.getElementById('layout-panel-feedback');
      if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Speichern…'; }

      var list = document.getElementById('layout-module-list');
      var order = Array.from(list.querySelectorAll('.layout-module-row')).map(function(row) {
        return row.dataset.todayModuleId;
      });
      var visibility = {};
      TODAY_LAYOUT_DEFINITION.forEach(function(item) {
        var enabledEl = document.getElementById('lm-enabled-' + item.id);
        visibility[item.id] = enabledEl ? enabledEl.checked : true;
      });

      _todayLayout = _sanitizeTodayLayout({ order: order, visibility: visibility });
      _persistTodayLayout();
      if (feedbackEl) feedbackEl.textContent = '✓ Heute-Seite gespeichert.';
      _emitLayoutChanged();
      setTimeout(function() {
        var overlay = document.getElementById('layout-panel-overlay');
        if (overlay) overlay.hidden = true;
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Speichern'; }
      }, 450);
    }

    function _getDragAfterElement(container, y) {
      var draggableElements = Array.from(container.querySelectorAll('.layout-module-row:not(.is-dragging)'));

      return draggableElements.reduce(function(closest, child) {
        var box = child.getBoundingClientRect();
        var offset = y - box.top - (box.height / 2);
        if (offset < 0 && offset > closest.offset) {
          return { offset: offset, element: child };
        }
        return closest;
      }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
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

    async function saveHeuteLayout(moduleUpdates) {
      // PUT /api/v2/dashboard/heute-layout
      // filters out mandatory modules before sending
      var filtered = (moduleUpdates || []).filter(function(m) { return !isMandatoryModule(m.id); });
      try {
        var resp = await fetch(_backendBase() + '/api/v2/dashboard/heute-layout', {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ modules: filtered })
        });
        return resp.ok;
      } catch (_e) {
        return false;
      }
    }

    return {
      init: init,
      openLayoutPanel: openLayoutPanel,
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
