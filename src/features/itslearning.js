/**
 * LehrerItslearning — itslearning feature module (Phase 11d)
 *
 * Extracted from src/app.js to separate itslearning rendering, credential
 * management, and data-loading into an isolated module.
 *
 * WHAT THIS FILE DOES:
 *   - renderItslearningConnector()  — renders the itslearning connect card (local-only)
 *   - saveItslearningCredentials()  — saves credentials via PUT /api/v2/modules/itslearning/config
 *   - getRelevantInboxMessages()    — filters messages to mail + itslearning channels
 *   - loadItslearning()             — fetches GET /api/v2/modules/itslearning/data,
 *                                     overlays state.data, triggers re-render
 *   - applyItslearningData()        — merges v2 response into dashboard state
 *
 * v1 FALLBACK:
 *   When MULTIUSER_ENABLED is false (local runtime), renderItslearningConnector()
 *   reads from state.data.localConnections (provided by v1 payload) and
 *   loadItslearning() is a no-op (data already present from v1 dashboard call).
 *
 * PUBLIC API:
 *   window.LehrerItslearning.init(state, elements, callbacks)
 *   window.LehrerItslearning.renderItslearningConnector()
 *   window.LehrerItslearning.saveItslearningCredentials()
 *   window.LehrerItslearning.getRelevantInboxMessages(data)
 *   window.LehrerItslearning.loadItslearning()
 *   window.LehrerItslearning.applyItslearningData(data, v2)
 *
 * DEPENDS ON:
 *   - window.LehrerAPI    (src/api-client.js loaded before this file)
 *   - window.MULTIUSER_ENABLED
 */
(function () {
  'use strict';

  // ── Internal state references (set via init) ─────────────────────────────────

  var _state = null;
  var _elements = null;
  var _callbacks = {};

  // ── Private helpers — delegate to callbacks ──────────────────────────────────

  function _getData() {
    return _callbacks.getData ? _callbacks.getData() : (_state && _state.data) || {};
  }

  function _renderMessages() {
    if (_callbacks.renderMessages) _callbacks.renderMessages();
  }

  function _renderChannelFilters() {
    if (_callbacks.renderChannelFilters) _callbacks.renderChannelFilters();
  }

  function _renderNavSignals() {
    if (_callbacks.renderNavSignals) _callbacks.renderNavSignals();
  }

  function _refreshDashboard(force) {
    if (_callbacks.refreshDashboard) return _callbacks.refreshDashboard(force);
    return Promise.resolve();
  }

  function _isLocalRuntime() {
    // Accept IS_LOCAL_RUNTIME from callbacks (passed at init time from app.js closure)
    if (typeof _callbacks.IS_LOCAL_RUNTIME !== 'undefined') return _callbacks.IS_LOCAL_RUNTIME;
    return (
      window.location.protocol === 'file:' ||
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1'
    );
  }

  // ── Message helpers ──────────────────────────────────────────────────────────

  /**
   * Returns messages that belong to the 'mail' or 'itslearning' channels.
   * Used by renderChannelFilters() and renderMessages() in app.js.
   *
   * @param {object} data - dashboard data (defaults to current state.data)
   */
  function getRelevantInboxMessages(data) {
    var d = data || _getData();
    return (d.messages || []).filter(function (m) {
      return m.channel === 'mail' || m.channel === 'itslearning';
    });
  }

  // ── Data helpers ─────────────────────────────────────────────────────────────

  /**
   * Merge v2 itslearning response into the dashboard data object.
   * v2 shape: { source, messages[], priorities[], mode, note }
   * Replaces itslearning-channel messages; preserves other channels.
   *
   * @param {object} data - current dashboard data (mutated in place)
   * @param {object} v2   - ItslearningSyncResult dict from backend
   */
  function applyItslearningData(data, v2) {
    if (!data || !v2) return;

    // Overlay itslearning messages (replace itslearning channel, keep others)
    if (Array.isArray(v2.messages)) {
      var nonItslearning = (data.messages || []).filter(function (m) {
        return m.channel !== 'itslearning';
      });
      data.messages = v2.messages.concat(nonItslearning);
    }

    // Overlay itslearning source entry
    if (v2.source) {
      var filtered = (data.sources || []).filter(function (s) {
        return s.id !== 'itslearning';
      });
      data.sources = [v2.source].concat(filtered);
    }

    // Overlay priorities (itslearning priorities replace existing itslearning ones)
    if (Array.isArray(v2.priorities) && v2.priorities.length) {
      var incoming = v2.priorities;
      var incomingSources = {};
      incoming.forEach(function (p) { if (p.source) incomingSources[p.source] = true; });
      var merged = incoming.concat(
        (data.priorities || []).filter(function (p) { return !incomingSources[p.source]; })
      );
      data.priorities = merged.slice(0, 8);
    }
  }

  // ── Core API functions ───────────────────────────────────────────────────────

  /**
   * Load itslearning data from v2 endpoint (GET /api/v2/modules/itslearning/data).
   * Updates state.data with fresh per-user itslearning messages/source/priorities.
   * Triggers renderMessages() + renderChannelFilters() + renderNavSignals().
   *
   * Only runs when MULTIUSER_ENABLED is true and LehrerAPI is available.
   * Silent on error — v1 data already in state.data remains usable.
   */
  async function loadItslearning() {
    if (!_state) return;
    if (!window.MULTIUSER_ENABLED) return;
    if (!window.LehrerAPI || typeof window.LehrerAPI.getModuleData !== 'function') return;
    try {
      var resp = await window.LehrerAPI.getModuleData('itslearning');
      if (!resp.ok) return;
      var json = await resp.json();
      if (!json || !json.ok || !json.data) return;
      if (_state.data) {
        applyItslearningData(_state.data, json.data);
      }
      _renderMessages();
      _renderChannelFilters();
      _renderNavSignals();
    } catch (_err) {
      // fail silently — itslearning is optional
    }
  }

  // ── Rendering: itslearning connector card (local-only) ───────────────────────

  /**
   * Renders the itslearning connect card in the "Zugaenge" section.
   * Only visible on IS_LOCAL_RUNTIME (Mac Mini / localhost).
   * In SaaS mode (MULTIUSER_ENABLED), the card is hidden — credentials are
   * managed via the DashboardManager config form.
   */
  function renderItslearningConnector() {
    if (!_elements || !_elements.itslearningConnectCard) return;

    if (!_isLocalRuntime()) {
      _elements.itslearningConnectCard.hidden = true;
      return;
    }

    var data = _getData();
    var source = (data.sources || []).find(function (item) { return item.id === 'itslearning'; });
    var connection = (data.localConnections && data.localConnections.itslearning) || {};

    _elements.itslearningConnectCard.hidden = false;

    if (_elements.itslearningConnectStatus) {
      _elements.itslearningConnectStatus.className = 'pill ' + (
        source && source.status === 'ok'
          ? 'pill-live'
          : connection.configured ? 'pill-attention' : 'pill-positive'
      );
      _elements.itslearningConnectStatus.textContent =
        source && source.status === 'ok' ? 'verbunden' : connection.configured ? 'gespeichert' : 'lokal';
    }

    var updateCount = getRelevantInboxMessages(data).filter(function (m) {
      return m.channel === 'itslearning';
    }).length;

    if (_elements.itslearningConnectCopy) {
      _elements.itslearningConnectCopy.textContent =
        source && source.status === 'ok'
          ? updateCount + ' Update' + (updateCount === 1 ? '' : 's') + ' erscheinen oben im Kommunikationsbereich. Zugang bleibt lokal auf diesem Mac gespeichert.'
          : (source && source.detail) ||
            'Lokale Verbindung fuer Benutzername und Passwort. Updates erscheinen danach oben im Kommunikationsbereich.';
    }

    if (_elements.itslearningUsername && !_elements.itslearningUsername.value && connection.username) {
      _elements.itslearningUsername.value = connection.username;
    }

    if (_elements.itslearningPassword && connection.configured) {
      _elements.itslearningPassword.placeholder = 'Passwort lokal gespeichert';
    }
  }

  // ── Credential management ─────────────────────────────────────────────────────

  /**
   * Save itslearning credentials via v2 API (PUT /api/v2/modules/itslearning/config).
   * Reads username/password from elements.itslearningUsername/Password.
   * Calls refreshDashboard(true) on success.
   */
  async function saveItslearningCredentials() {
    if (!_elements) return;

    var username = (_elements.itslearningUsername && _elements.itslearningUsername.value.trim()) || '';
    var password = (_elements.itslearningPassword && _elements.itslearningPassword.value.trim()) || '';

    if (!username || !password) {
      if (_elements.itslearningConnectFeedback) {
        _elements.itslearningConnectFeedback.textContent = 'Bitte Benutzername und Passwort eintragen.';
        _elements.itslearningConnectFeedback.className = 'connect-feedback warning';
      }
      return;
    }

    if (_elements.itslearningConnectFeedback) {
      _elements.itslearningConnectFeedback.textContent = 'Speichere itslearning-Zugangsdaten ...';
      _elements.itslearningConnectFeedback.className = 'connect-feedback';
    }

    try {
      var resp = await window.LehrerAPI.saveModuleConfig('itslearning', { username: username, password: password });
      var payload = await resp.json();
      if (!resp.ok) throw new Error(payload.error || 'Speichern fehlgeschlagen.');
      if (_elements.itslearningConnectFeedback) {
        _elements.itslearningConnectFeedback.textContent = 'itslearning-Zugang gespeichert.';
        _elements.itslearningConnectFeedback.className = 'connect-feedback success';
      }
      if (_elements.itslearningPassword) _elements.itslearningPassword.value = '';
      await _refreshDashboard(true);
    } catch (error) {
      if (_elements.itslearningConnectFeedback) {
        _elements.itslearningConnectFeedback.textContent = (error && error.message) || 'itslearning-Zugang konnte nicht gespeichert werden.';
        _elements.itslearningConnectFeedback.className = 'connect-feedback warning';
      }
    }
  }

  // ── Public API ───────────────────────────────────────────────────────────────

  /**
   * Initialize the itslearning module with shared state, DOM element references,
   * and render callbacks from the parent app.js IIFE.
   *
   * @param {object} state    - The shared `state` object from app.js (by reference)
   * @param {object} elements - The shared `elements` object from app.js (by reference)
   * @param {object} cbs      - Render callbacks: {
   *   getData, renderMessages, renderChannelFilters, renderNavSignals,
   *   refreshDashboard, IS_LOCAL_RUNTIME
   * }
   */
  function init(state, elements, cbs) {
    _state = state;
    _elements = elements;
    _callbacks = cbs || {};
  }

  window.LehrerItslearning = {
    init: init,
    renderItslearningConnector: renderItslearningConnector,
    saveItslearningCredentials: saveItslearningCredentials,
    getRelevantInboxMessages: getRelevantInboxMessages,
    loadItslearning: loadItslearning,
    applyItslearningData: applyItslearningData,
  };

})();
