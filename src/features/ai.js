/**
 * LehrerAI — KI-Zusammenfassung und „Frag dein Cockpit“ in der Briefing-Karte.
 *
 * Backend: GET /api/v2/ai/status, POST /api/v2/ai/briefing, POST /api/v2/ai/chat
 * (backend/api/ai_routes.py). Only visible when the server has a key and the
 * teacher switched the assistant on under „Verbindungen“.
 *
 * Exposes window.LehrerAI = { init, reload }.
 */
(function () {
  'use strict';

  var MAX_HISTORY = 8;
  var _history = [];
  var _busy = false;
  var _loadedBriefing = false;

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function _api(path, body) {
    var init = { method: body === undefined ? 'GET' : 'POST', credentials: 'include', headers: {} };
    if (body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    return fetch((window.BACKEND_API_URL || '') + path, init).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (!resp.ok || data.ok === false) throw new Error(data.error || ('HTTP ' + resp.status));
        return data;
      });
    });
  }

  function _el(id) { return document.getElementById(id); }

  function _status(message, kind) {
    var el = _el('ai-status');
    if (!el) return;
    el.textContent = message || '';
    el.className = 'connection-feedback' + (kind ? ' is-' + kind : '');
  }

  function _renderBriefing(lines) {
    var list = _el('ai-briefing');
    if (!list) return;
    list.innerHTML = (lines || []).map(function (line) { return '<li>' + esc(line) + '</li>'; }).join('');
  }

  function loadBriefing(refresh) {
    if (_busy) return Promise.resolve();
    _busy = true;
    _status(refresh ? 'Erstelle neue Zusammenfassung …' : 'Fasse deinen Tag zusammen …');
    return _api('/api/v2/ai/briefing', { refresh: !!refresh })
      .then(function (data) {
        _renderBriefing(data.lines);
        _status(data.limited ? 'Tageslimit erreicht – das ist die letzte Zusammenfassung von heute.' : '');
      })
      .catch(function (err) { _status(err.message, 'error'); })
      .finally(function () { _busy = false; });
  }

  function _renderChat() {
    var log = _el('ai-chat-log');
    if (!log) return;
    log.innerHTML = _history.map(function (turn) {
      return '<p class="ai-chat-turn ai-chat-' + turn.role + '">' + esc(turn.content) + '</p>';
    }).join('');
    log.hidden = !_history.length;
  }

  function ask(question) {
    question = (question || '').trim();
    if (!question || _busy) return;
    _busy = true;
    var input = _el('ai-chat-input');
    if (input) input.value = '';
    var previous = _history.slice(-MAX_HISTORY);
    _history.push({ role: 'user', content: question });
    _renderChat();
    _status('Denke nach …');
    _api('/api/v2/ai/chat', { question: question, history: previous })
      .then(function (data) {
        _history.push({ role: 'assistant', content: data.answer });
        _history = _history.slice(-MAX_HISTORY * 2);
        _status('');
      })
      .catch(function (err) {
        _history.pop(); // let the teacher retry the same question
        if (input) input.value = question;
        _status(err.message, 'error');
      })
      .finally(function () { _busy = false; _renderChat(); });
  }

  function reload() {
    var panel = _el('ai-panel');
    if (!panel || !window.MULTIUSER_ENABLED) return;
    _api('/api/v2/ai/status').then(function (status) {
      panel.hidden = !(status.available && status.enabled);
      if (!panel.hidden && !_loadedBriefing) {
        _loadedBriefing = true;
        loadBriefing(false);
      }
    }).catch(function () { panel.hidden = true; });
  }

  function init() {
    var panel = _el('ai-panel');
    if (!panel || panel.dataset.bound) return;
    panel.dataset.bound = '1';
    var refresh = _el('ai-refresh');
    if (refresh) refresh.addEventListener('click', function () { loadBriefing(true); });
    var form = _el('ai-chat-form');
    if (form) form.addEventListener('submit', function (event) {
      event.preventDefault();
      ask((_el('ai-chat-input') || {}).value);
    });
    reload();
  }

  window.LehrerAI = { init: init, reload: function () { _loadedBriefing = false; reload(); } };
})();
