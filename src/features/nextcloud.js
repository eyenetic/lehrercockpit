/**
 * LehrerNextcloud — Nextcloud feature module
 *
 * Extracted from src/app.js to separate Nextcloud rendering, credential
 * management, and last-opened tracking into an isolated module.
 *
 * WHAT THIS FILE DOES:
 *   - renderNextcloudConnector()  — renders the Nextcloud connect card (local-only)
 *   - saveNextcloudCredentials()  — saves credentials via PUT /api/v2/modules/nextcloud/config
 *   - loadNextcloudLastOpened()   — reads last-opened entry from localStorage
 *   - saveNextcloudLastOpened()   — writes last-opened entry to localStorage
 *
 * v1 FALLBACK:
 *   When MULTIUSER_ENABLED is false (local runtime), renderNextcloudConnector()
 *   reads from state.data.localConnections (provided by v1 payload).
 *
 * PUBLIC API:
 *   window.LehrerNextcloud.init(state, elements, callbacks)
 *   window.LehrerNextcloud.renderNextcloudConnector()
 *   window.LehrerNextcloud.saveNextcloudCredentials()
 *   window.LehrerNextcloud.loadNextcloudLastOpened()
 *   window.LehrerNextcloud.saveNextcloudLastOpened(id, label)
 *
 * DEPENDS ON:
 *   - window.LehrerAPI    (src/api-client.js loaded before this file)
 *   - window.MULTIUSER_ENABLED
 */
(function () {
  'use strict';

  // ── Constants ────────────────────────────────────────────────────────────────

  var NEXTCLOUD_LAST_OPENED_KEY = 'lehrerCockpit.nextcloud.lastOpened';

  // ── Internal state references (set via init) ─────────────────────────────────

  var _state = null;
  var _elements = null;
  var _callbacks = {};

  // ── Private helpers — delegate to callbacks ──────────────────────────────────

  function _getData() {
    return _callbacks.getData ? _callbacks.getData() : (_state && _state.data) || {};
  }

  function _refreshDashboard(force) {
    if (_callbacks.refreshDashboard) return _callbacks.refreshDashboard(force);
    return Promise.resolve();
  }

  function _isLocalRuntime() {
    if (typeof _callbacks.IS_LOCAL_RUNTIME !== 'undefined') return _callbacks.IS_LOCAL_RUNTIME;
    return (
      window.location.protocol === 'file:' ||
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1'
    );
  }

  function _isModuleVisible(moduleId) {
    if (_callbacks.isModuleVisible) return _callbacks.isModuleVisible(moduleId);
    return true;
  }

  function _formatTime(value) {
    if (_callbacks.formatTime) return _callbacks.formatTime(value);
    // Minimal fallback if callback not provided
    if (!value) return '';
    var d = value instanceof Date ? value : new Date(value);
    return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  }

  // ── localStorage helpers ─────────────────────────────────────────────────────

  /**
   * Load last-opened Nextcloud item from localStorage.
   * @returns {{ id: string, label: string, when: string }|null}
   */
  function loadNextcloudLastOpened() {
    try {
      var raw = localStorage.getItem(NEXTCLOUD_LAST_OPENED_KEY);
      if (!raw) return null;
      var payload = JSON.parse(raw);
      if (!payload || !payload.label || !payload.when) return null;
      return payload;
    } catch (_error) {
      return null;
    }
  }

  /**
   * Persist the last-opened Nextcloud link to localStorage.
   * @param {string} id    - 'root' | 'q1q2' | 'q3q4' | custom id
   * @param {string} label - display label for the link
   */
  function saveNextcloudLastOpened(id, label) {
    var normalizedLabel =
      id === 'root' ? 'Nextcloud' :
      id === 'q1q2' ? 'Q1 / Q2' :
      id === 'q3q4' ? 'Q3 / Q4' :
      (label || 'Nextcloud');
    var payload = {
      id: id || 'nextcloud',
      label: normalizedLabel,
      when: _formatTime(new Date()),
    };
    localStorage.setItem(NEXTCLOUD_LAST_OPENED_KEY, JSON.stringify(payload));
  }

  // ── Rendering: Nextcloud connector card ──────────────────────────────────────

  /**
   * Renders the Nextcloud connect card in the "Zugaenge" section.
   * Only visible on IS_LOCAL_RUNTIME (Mac Mini / localhost) and when
   * the 'nextcloud' module is enabled in the layout.
   * In SaaS mode (MULTIUSER_ENABLED), the card is hidden — credentials are
   * managed via the DashboardManager config form.
   */
  function renderNextcloudConnector() {
    if (!_elements || !_elements.nextcloudConnectCard) return;

    if (!_isModuleVisible('nextcloud')) {
      _elements.nextcloudConnectCard.hidden = true;
      return;
    }

    if (!_isLocalRuntime()) {
      _elements.nextcloudConnectCard.hidden = true;
      return;
    }

    var data = _getData();
    var source = (data.sources || []).find(function (item) { return item.id === 'nextcloud'; });
    var connection = (data.localConnections && data.localConnections.nextcloud) || {};
    var workspaceUrl = connection.workspaceUrl || connection.baseUrl || 'https://nextcloud-g2.b-sz-heos.logoip.de/index.php/apps/files/';
    var q1q2Url = connection.q1q2Url || 'https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008901';
    var q3q4Url = connection.q3q4Url || 'https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008900';
    var workspaceLinks = Array.isArray(connection.workspaceLinks) ? connection.workspaceLinks : [];
    var lastOpened = loadNextcloudLastOpened();

    _elements.nextcloudConnectCard.hidden = false;

    if (_elements.nextcloudConnectStatus) {
      _elements.nextcloudConnectStatus.className = 'pill ' + (
        source && source.status === 'ok'
          ? 'pill-live'
          : connection.configured ? 'pill-attention' : 'pill-positive'
      );
      _elements.nextcloudConnectStatus.textContent =
        source && source.status === 'ok'
          ? (connection.configured ? 'verbunden' : 'bereit')
          : connection.configured
            ? 'gespeichert'
            : 'lokal';
    }

    if (_elements.nextcloudConnectCopy) {
      _elements.nextcloudConnectCopy.textContent =
        (source && source.detail) ||
        'Nextcloud ist als Arbeitsbereich vorbereitet. Von hier aus oeffnest du die Fehlzeiten-Dateien direkt im Browser.';
    }

    if (_elements.nextcloudOpenRoot) {
      _elements.nextcloudOpenRoot.href = workspaceUrl;
    }
    if (_elements.nextcloudOpenQ1Q2) {
      _elements.nextcloudOpenQ1Q2.href = q1q2Url;
    }
    if (_elements.nextcloudOpenQ3Q4) {
      _elements.nextcloudOpenQ3Q4.href = q3q4Url;
    }

    if (_elements.nextcloudCustomLinks) {
      _elements.nextcloudCustomLinks.hidden = !workspaceLinks.length;
      _elements.nextcloudCustomLinks.innerHTML = workspaceLinks
        .map(function (link) {
          return (
            '<a class="nextcloud-work-card" href="' + link.url +
            '" target="_blank" rel="noreferrer" data-nextcloud-link="' + link.id + '">' +
            '<span class="meta-tag low">Arbeitslink</span>' +
            '<strong>' + link.label + '</strong>' +
            '<p>Direkt in Nextcloud oeffnen</p>' +
            '<span class="quick-link-action">oeffnen</span>' +
            '</a>'
          );
        })
        .join('');
      _elements.nextcloudCustomLinks.querySelectorAll('[data-nextcloud-link]').forEach(function (link) {
        link.addEventListener('click', function () {
          saveNextcloudLastOpened(
            link.dataset.nextcloudLink,
            (link.querySelector('strong') && link.querySelector('strong').textContent) || link.textContent
          );
          renderNextcloudConnector();
        });
      });
    }

    if (_elements.nextcloudLastOpened) {
      _elements.nextcloudLastOpened.textContent = lastOpened
        ? lastOpened.label + ' - ' + lastOpened.when
        : 'Noch kein Zugriff gespeichert';
    }

    if (_elements.nextcloudWorkspaceUrl && !_elements.nextcloudWorkspaceUrl.value) {
      _elements.nextcloudWorkspaceUrl.value = workspaceUrl;
    }
    if (_elements.nextcloudUsername && !_elements.nextcloudUsername.value && connection.username) {
      _elements.nextcloudUsername.value = connection.username;
    }
    if (_elements.nextcloudQ1Q2UrlInput && !_elements.nextcloudQ1Q2UrlInput.value) {
      _elements.nextcloudQ1Q2UrlInput.value = q1q2Url;
    }
    if (_elements.nextcloudQ3Q4UrlInput && !_elements.nextcloudQ3Q4UrlInput.value) {
      _elements.nextcloudQ3Q4UrlInput.value = q3q4Url;
    }
    if (_elements.nextcloudLink1Label && !_elements.nextcloudLink1Label.value) {
      _elements.nextcloudLink1Label.value = (workspaceLinks[0] && workspaceLinks[0].label) || '';
    }
    if (_elements.nextcloudLink1Url && !_elements.nextcloudLink1Url.value) {
      _elements.nextcloudLink1Url.value = (workspaceLinks[0] && workspaceLinks[0].url) || '';
    }
    if (_elements.nextcloudLink2Label && !_elements.nextcloudLink2Label.value) {
      _elements.nextcloudLink2Label.value = (workspaceLinks[1] && workspaceLinks[1].label) || '';
    }
    if (_elements.nextcloudLink2Url && !_elements.nextcloudLink2Url.value) {
      _elements.nextcloudLink2Url.value = (workspaceLinks[1] && workspaceLinks[1].url) || '';
    }
    if (_elements.nextcloudLink3Label && !_elements.nextcloudLink3Label.value) {
      _elements.nextcloudLink3Label.value = (workspaceLinks[2] && workspaceLinks[2].label) || '';
    }
    if (_elements.nextcloudLink3Url && !_elements.nextcloudLink3Url.value) {
      _elements.nextcloudLink3Url.value = (workspaceLinks[2] && workspaceLinks[2].url) || '';
    }
    if (connection.configured && _elements.nextcloudPassword) {
      _elements.nextcloudPassword.placeholder = 'Passwort lokal gespeichert';
    }
  }

  // ── Credential management ─────────────────────────────────────────────────────

  /**
   * Save Nextcloud credentials via v2 API (PUT /api/v2/modules/nextcloud/config).
   * Reads username/password/workspaceUrl from DOM elements.
   * Calls refreshDashboard(true) on success.
   */
  async function saveNextcloudCredentials() {
    if (!_elements) return;

    var username = (_elements.nextcloudUsername && _elements.nextcloudUsername.value.trim()) || '';
    var password = (_elements.nextcloudPassword && _elements.nextcloudPassword.value.trim()) || '';
    var workspaceUrl = (
      _elements.nextcloudWorkspaceUrl && _elements.nextcloudWorkspaceUrl.value.trim()
    ) || 'https://nextcloud-g2.b-sz-heos.logoip.de/index.php/apps/files/';

    if (_elements.nextcloudConnectFeedback) {
      _elements.nextcloudConnectFeedback.textContent = 'Speichere Nextcloud-Arbeitsbereich ...';
      _elements.nextcloudConnectFeedback.className = 'connect-feedback';
    }

    // Always use v2 API (Phase 8d: if/else removed)
    try {
      var resp = await window.LehrerAPI.saveModuleConfig('nextcloud', {
        server_url: workspaceUrl,
        username: username,
        password: password,
      });
      var payload = await resp.json();
      if (!resp.ok) throw new Error(payload.error || 'Speichern fehlgeschlagen.');
      if (_elements.nextcloudConnectFeedback) {
        _elements.nextcloudConnectFeedback.textContent = 'Nextcloud-Arbeitsbereich gespeichert.';
        _elements.nextcloudConnectFeedback.className = 'connect-feedback success';
      }
      if (_elements.nextcloudPassword) _elements.nextcloudPassword.value = '';
      await _refreshDashboard(true);
    } catch (error) {
      if (_elements.nextcloudConnectFeedback) {
        _elements.nextcloudConnectFeedback.textContent =
          (error && error.message) || 'Nextcloud-Zugang konnte nicht gespeichert werden.';
        _elements.nextcloudConnectFeedback.className = 'connect-feedback warning';
      }
    }
  }

  // ── Public API ───────────────────────────────────────────────────────────────

  /**
   * Initialize the Nextcloud module with shared state, DOM element references,
   * and render callbacks from the parent app.js IIFE.
   *
   * @param {object} state    - The shared `state` object from app.js (by reference)
   * @param {object} elements - The shared `elements` object from app.js (by reference)
   * @param {object} cbs      - Render callbacks: {
   *   getData, refreshDashboard, isModuleVisible, formatTime, IS_LOCAL_RUNTIME
   * }
   */
  function init(state, elements, cbs) {
    _state = state;
    _elements = elements;
    _callbacks = cbs || {};
  }

  window.LehrerNextcloud = {
    init: init,
    renderNextcloudConnector: renderNextcloudConnector,
    saveNextcloudCredentials: saveNextcloudCredentials,
    loadNextcloudLastOpened: loadNextcloudLastOpened,
    saveNextcloudLastOpened: saveNextcloudLastOpened,
  };

})();
