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
        detail: { modules: _modules.slice() }
      }));
    }

    function init() {
      if (!window.MULTIUSER_ENABLED) return;
      _initAsync().catch(function() {});
    }

    function _initAsync() {
      return (window.LehrerAPI ? window.LehrerAPI.getDashboardV2() : _apiFetch('/api/v2/dashboard'))
        .then(function(resp) {
          if (!resp.ok) return;
          return resp.json().then(function(data) {
            if (!data.ok) return;
            _modules = (data.modules || []).slice().sort(function(a, b) {
              return (a.sort_order || 0) - (b.sort_order || 0);
            });
            _systemSettings = data.system || {};
            _layoutReady = true;
            _emitLayoutChanged();

            // Show settings button in topbar
            var settingsBtn = document.getElementById('settings-button');
            if (settingsBtn) settingsBtn.style.display = '';

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
      btn.addEventListener('click', function() { openLayoutPanel(); });
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
      var list = document.getElementById('layout-module-list');
      if (!list) return;
      list.innerHTML = '';
      _modules.forEach(function(m, idx) {
        var row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:0.75rem;padding:0.5rem 0.25rem;border-bottom:1px solid var(--line);';
        row.innerHTML =
          '<input type="checkbox" id="lm-enabled-' + _esc(m.module_id) + '" ' +
          (m.is_visible ? 'checked' : '') + ' style="cursor:pointer;accent-color:var(--accent);width:16px;height:16px;" />' +
          '<label for="lm-enabled-' + _esc(m.module_id) + '" style="flex:1;font-size:0.85rem;color:var(--ink);cursor:pointer;">' +
          _esc(m.display_name) + '</label>' +
          '<input type="number" min="1" value="' + (idx + 1) + '" id="lm-order-' + _esc(m.module_id) + '" ' +
          'data-module-id="' + _esc(m.module_id) + '" ' +
          'style="width:50px;padding:0.25rem 0.4rem;border:1px solid var(--line-strong);border-radius:var(--radius-sm);' +
          'background:var(--panel-soft);color:var(--ink);font-size:0.82rem;text-align:center;" />';
        list.appendChild(row);
      });
    }

    function _saveLayout(saveBtn) {
      var feedbackEl = document.getElementById('layout-panel-feedback');
      if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Speichern…'; }

      var modulesPayload = _modules.map(function(m) {
        var enabledEl = document.getElementById('lm-enabled-' + m.module_id);
        var orderEl = document.getElementById('lm-order-' + m.module_id);
        return {
          module_id: m.module_id,
          is_visible: enabledEl ? enabledEl.checked : m.is_visible,
          sort_order: orderEl ? (parseInt(orderEl.value, 10) || m.sort_order) : m.sort_order,
        };
      });

      _apiFetch('/api/v2/dashboard/layout', {
        method: 'PUT',
        body: { modules: modulesPayload },
      }).then(function(resp) {
        if (!resp.ok) {
          return resp.json().catch(function() { return {}; }).then(function(err) {
            if (feedbackEl) feedbackEl.textContent = err.error || 'Fehler beim Speichern.';
          });
        }
        if (feedbackEl) feedbackEl.textContent = '✓ Layout gespeichert.';
        // Update local state
        modulesPayload.forEach(function(mp) {
          _modules = _modules.map(function(m) {
            return m.module_id === mp.module_id ? Object.assign({}, m, { is_visible: mp.is_visible, sort_order: mp.sort_order }) : m;
          });
        });
        _emitLayoutChanged();
        setTimeout(function() {
          var overlay = document.getElementById('layout-panel-overlay');
          if (overlay) overlay.hidden = true;
        }, 1000);
      }).catch(function() {
        if (feedbackEl) feedbackEl.textContent = 'Verbindungsfehler.';
      }).finally(function() {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Speichern'; }
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

    return {
      init: init,
      openLayoutPanel: openLayoutPanel,
      getActiveModuleIds: getActiveModuleIds,
      isModuleVisible: isModuleVisible,
      isLayoutReady: isLayoutReady
    };
  })();

  window.DashboardManager = DashboardManager;
})();
