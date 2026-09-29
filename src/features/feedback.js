/**
 * LehrerFeedback — "Rückmeldung": Lehrkräfte schicken der Verwaltung Probleme,
 * Ideen, Fragen oder Lob und sehen Status und Antwort.
 *
 * Backend: GET/POST /api/v2/feedback, POST /api/v2/feedback/seen,
 * GET /api/v2/feedback/admin (Zähler für Admins). Siehe backend/api/feedback_routes.py.
 *
 * Öffnen: jedes Element mit data-open-feedback, oder …/index.html#rueckmeldung.
 * Exposes window.LehrerFeedback = { open, close, onUser }.
 */
(function () {
  'use strict';

  var PLACEHOLDERS = {
    problem: 'Was ist passiert, und wo im Cockpit?',
    idee: 'Was würde dir die Arbeit erleichtern?',
    frage: 'Was möchtest du wissen?',
    lob: 'Was gefällt dir?',
  };

  var _items = [];
  var _unread = 0;
  var _bound = false;

  function $(id) { return document.getElementById(id); }

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || 'GET', credentials: 'include', headers: {} };
    if (opts.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.body);
    }
    return fetch((window.BACKEND_API_URL || '') + path, init).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (!resp.ok || data.ok === false) throw new Error(data.error || 'Anfrage fehlgeschlagen (' + resp.status + ').');
        return data;
      });
    });
  }

  function shortDate(iso) {
    var date = new Date(iso);
    if (isNaN(date.getTime())) return '';
    return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
  }

  function renderBadges() {
    document.querySelectorAll('[data-feedback-unread]').forEach(function (badge) {
      badge.textContent = String(_unread);
      badge.hidden = !_unread;
    });
  }

  function renderList() {
    var box = $('feedback-history');
    var list = $('feedback-list');
    if (!box || !list) return;
    box.hidden = !_items.length;
    list.innerHTML = _items.map(function (item) {
      return '<article class="feedback-item' + (item.unread ? ' is-unread' : '') + '">' +
        '<div class="feedback-item-head"><strong>' + esc(item.kind_label) + '</strong>' +
        '<span>' + esc(shortDate(item.created_at)) + '</span>' +
        '<span class="status-badge is-' + esc(item.status) + '">' + esc(item.status_label) + '</span></div>' +
        '<p class="feedback-item-text">' + esc(item.message) + '</p>' +
        (item.reply ? '<div class="feedback-reply"><strong>Antwort</strong>' + esc(item.reply) + '</div>' : '') +
        '</article>';
    }).join('');
  }

  function load() {
    return api('/api/v2/feedback').then(function (data) {
      _items = data.items || [];
      _unread = data.unread || 0;
      renderBadges();
      renderList();
    });
  }

  function loadAdminCount() {
    var user = window.CURRENT_USER || {};
    var badge = $('admin-feedback-count');
    if (!badge || !(user.is_admin === true || user.role === 'admin')) return;
    api('/api/v2/feedback/admin').then(function (data) {
      var fresh = (data.counts || {}).neu || 0;
      badge.textContent = String(fresh);
      badge.hidden = !fresh;
      badge.title = fresh + (fresh === 1 ? ' neue Rückmeldung' : ' neue Rückmeldungen');
    }).catch(function () { /* badge stays hidden */ });
  }

  function setStatus(message, kind) {
    var el = $('feedback-status');
    if (!el) return;
    el.textContent = message || '';
    el.className = 'connection-feedback' + (kind ? ' is-' + kind : '');
  }

  function currentKind() {
    var checked = document.querySelector('input[name="feedback-kind"]:checked');
    return checked ? checked.value : 'problem';
  }

  function context() {
    var active = document.querySelector('.nav-link.active[data-section-target]');
    var script = document.querySelector('script[src*="src/app.js"]');
    var version = script ? (script.getAttribute('src').match(/[?&]v=(\w+)/) || [])[1] : '';
    return {
      section: active ? active.getAttribute('data-section-target') : '',
      version: version || '',
      viewport: window.innerWidth + '×' + window.innerHeight,
      theme: document.documentElement.dataset.theme || '',
    };
  }

  function open() {
    var modal = $('feedback-modal');
    if (!modal) return;
    var sheet = $('mobile-more-sheet');
    if (sheet) sheet.hidden = true;
    modal.hidden = false;
    setStatus('');
    setTimeout(function () { var text = $('feedback-message'); if (text) text.focus(); }, 40);
    load().then(function () {
      if (_unread) {
        api('/api/v2/feedback/seen', { method: 'POST' }).then(function () {
          _unread = 0;
          renderBadges();
        }).catch(function () { /* next open */ });
      }
    }).catch(function (err) { setStatus(err.message, 'error'); });
  }

  function close() {
    var modal = $('feedback-modal');
    if (modal) modal.hidden = true;
    _items.forEach(function (item) { item.unread = false; });
  }

  function submit(event) {
    event.preventDefault();
    var text = $('feedback-message');
    var button = $('feedback-submit');
    var message = (text.value || '').trim();
    if (message.length < 3) {
      setStatus('Bitte beschreibe kurz, worum es geht.', 'error');
      text.focus();
      return;
    }
    button.disabled = true;
    setStatus('Sende …');
    api('/api/v2/feedback', { method: 'POST', body: { kind: currentKind(), message: message, context: context() } })
      .then(function (data) {
        text.value = '';
        _items.unshift(data.item);
        renderList();
        setStatus('Danke! Deine Rückmeldung ist angekommen.', 'success');
      })
      .catch(function (err) { setStatus(err.message, 'error'); })
      .then(function () { button.disabled = false; });
  }

  function bind() {
    if (_bound) return;
    _bound = true;
    document.addEventListener('click', function (event) {
      if (event.target.closest('[data-open-feedback]')) { event.preventDefault(); open(); return; }
      if (event.target.closest('[data-feedback-close]')) close();
    });
    var modal = $('feedback-modal');
    if (modal) modal.addEventListener('click', function (event) { if (event.target === modal) close(); });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && modal && !modal.hidden) close();
    });
    var form = $('feedback-form');
    if (form) form.addEventListener('submit', submit);
    document.querySelectorAll('input[name="feedback-kind"]').forEach(function (radio) {
      radio.addEventListener('change', function () {
        var text = $('feedback-message');
        if (text) text.placeholder = PLACEHOLDERS[currentKind()] || '';
      });
    });
  }

  /** Called once the logged-in user is known (index.html → initUserInfo). */
  function onUser() {
    if (!window.MULTIUSER_ENABLED) return;
    bind();
    load().catch(function () { /* badge stays hidden */ });
    loadAdminCount();
    if ((window.location.hash || '') === '#rueckmeldung') {
      history.replaceState(null, '', window.location.pathname + window.location.search);
      open();
    }
  }

  window.LehrerFeedback = { open: open, close: close, onUser: onUser };
})();
