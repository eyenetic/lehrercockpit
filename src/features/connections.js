/**
 * LehrerConnections — "Verbindungen": one place to connect and manage the
 * teacher's personal sources (multi-user mode only).
 *
 * Backend: GET /api/v2/connections, PATCH /api/v2/connections/<module>.
 * Sections register themselves via LehrerConnections.registerSection() so later
 * features (Nextcloud, Klassenarbeitsplan, Push, KI) plug into the same dialog.
 *
 * Exposes window.LehrerConnections = { init, open, close, registerSection, api, esc }.
 */
(function () {
  'use strict';

  var _sections = [];
  var _status = null;
  var _onChanged = function () {};
  var _modal = null;
  var _body = null;

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
        if (!resp.ok || data.ok === false) {
          var err = new Error(data.error || 'Anfrage fehlgeschlagen (' + resp.status + ').');
          err.status = resp.status;
          throw err;
        }
        return data;
      });
    });
  }

  function statusPill(ok, okLabel, offLabel) {
    return '<span class="pill ' + (ok ? 'pill-live' : 'pill-attention') + '">' +
      esc(ok ? okLabel : offLabel) + '</span>';
  }

  function feedback(sectionEl, message, kind) {
    var el = sectionEl && sectionEl.querySelector('[data-feedback]');
    if (!el) return;
    el.textContent = message || '';
    el.className = 'connection-feedback' + (kind ? ' is-' + kind : '');
  }

  // ── Built-in sections: WebUntis + itslearning ─────────────────────────────

  function _patch(moduleId, fields, sectionEl, okMessage) {
    feedback(sectionEl, 'Speichere …');
    return api('/api/v2/connections/' + moduleId, { method: 'PATCH', body: fields })
      .then(function (data) {
        _status = Object.assign({}, _status, data.connections || {});
        render();
        var fresh = _body && _body.querySelector('[data-section="' + moduleId + '"]');
        feedback(fresh, okMessage, 'success');
        _onChanged();
      })
      .catch(function (err) { feedback(sectionEl, err.message, 'error'); });
  }

  registerSection({
    id: 'webuntis',
    render: function (status) {
      var s = status.webuntis || {};
      return '' +
        '<div class="connection-head"><h3>WebUntis</h3>' + statusPill(s.configured, 'verbunden', 'nicht verbunden') + '</div>' +
        '<p class="connection-copy">Dein persönlicher Stundenplan über das Kalender-Abo (iCal).</p>' +
        '<label class="connection-field">Kalender-Abo-Link' +
        '<input class="form-input" type="url" data-field="ical_url" placeholder="' +
        (s.configured ? 'Link gespeichert – zum Ändern neuen Link einfügen' : 'https://…webuntis.com/WebUntis/ical…') + '" autocomplete="off" /></label>' +
        '<details class="connection-help"><summary>Wo finde ich den Link?</summary><ol>' +
        '<li>In WebUntis anmelden.</li><li>Oben rechts auf deinen Namen → „Mein Profil“.</li>' +
        '<li>Reiter „Kalenderabonnement“ öffnen und den iCal-Link kopieren.</li></ol></details>' +
        '<div class="connection-actions">' +
        '<button class="btn btn-primary" type="button" data-action="save">Speichern</button>' +
        (s.configured ? '<button class="btn btn-secondary" type="button" data-action="remove">Trennen</button>' : '') +
        '</div><p class="connection-feedback" data-feedback></p>';
    },
    bind: function (el) {
      el.querySelector('[data-action="save"]').addEventListener('click', function () {
        var value = el.querySelector('[data-field="ical_url"]').value.trim();
        if (!value) { feedback(el, 'Bitte zuerst den Link einfügen.', 'error'); return; }
        _patch('webuntis', { ical_url: value }, el, 'WebUntis ist verbunden.');
      });
      var remove = el.querySelector('[data-action="remove"]');
      if (remove) remove.addEventListener('click', function () {
        _patch('webuntis', { ical_url: null }, el, 'WebUntis wurde getrennt.');
      });
    },
  });

  registerSection({
    id: 'itslearning',
    render: function (status) {
      var s = status.itslearning || {};
      var connected = s.calendar || s.login;
      return '' +
        '<div class="connection-head"><h3>itslearning</h3>' + statusPill(connected, s.calendar ? 'Kalender verbunden' : 'verbunden', 'nicht verbunden') + '</div>' +
        '<p class="connection-copy">Termine und Abgabefristen über das offizielle Kalender-Abo – ganz ohne Passwort.</p>' +
        '<label class="connection-field">Kalender-Abo-Link' +
        '<input class="form-input" type="url" data-field="calendar_url" placeholder="' +
        (s.calendar ? 'Link gespeichert – zum Ändern neuen Link einfügen' : 'https://berlin.itslearning.com/…') + '" autocomplete="off" /></label>' +
        '<details class="connection-help"><summary>Wo finde ich den Link?</summary><ol>' +
        '<li>In itslearning den <strong>Kalender</strong> öffnen.</li>' +
        '<li>Oben rechts auf das Zahnrad → „Abonnieren“.</li>' +
        '<li>Den angezeigten Link kopieren und hier einfügen.</li></ol>' +
        '<p>Der Link funktioniert ohne Passwort. Er wird deshalb verschlüsselt gespeichert.</p></details>' +
        '<div class="connection-actions">' +
        '<button class="btn btn-primary" type="button" data-action="save-calendar">Speichern</button>' +
        (s.calendar ? '<button class="btn btn-secondary" type="button" data-action="remove-calendar">Kalender trennen</button>' : '') +
        '</div>' +
        '<details class="connection-optional"' + (s.login ? ' open' : '') + '><summary>Nachrichten per Login (optional, experimentell)</summary>' +
        '<p class="connection-copy">Liest die Hinweise unter der Glocke über deinen itslearning-Login. Das kann bei Änderungen an itslearning ausfallen.</p>' +
        '<label class="connection-field">Benutzername<input class="form-input" type="text" data-field="username" value="' + esc(s.username || '') + '" autocomplete="off" /></label>' +
        '<label class="connection-field">Passwort<input class="form-input" type="password" data-field="password" placeholder="' +
        (s.login ? 'Passwort gespeichert' : '') + '" autocomplete="new-password" /></label>' +
        '<div class="connection-actions">' +
        '<button class="btn btn-secondary" type="button" data-action="save-login">Login speichern</button>' +
        (s.login ? '<button class="btn btn-secondary" type="button" data-action="remove-login">Login löschen</button>' : '') +
        '</div></details>' +
        '<p class="connection-feedback" data-feedback></p>';
    },
    bind: function (el) {
      el.querySelector('[data-action="save-calendar"]').addEventListener('click', function () {
        var value = el.querySelector('[data-field="calendar_url"]').value.trim();
        if (!value) { feedback(el, 'Bitte zuerst den Link einfügen.', 'error'); return; }
        _patch('itslearning', { calendar_url: value }, el, 'Kalender-Abo ist verbunden.');
      });
      var removeCal = el.querySelector('[data-action="remove-calendar"]');
      if (removeCal) removeCal.addEventListener('click', function () {
        _patch('itslearning', { calendar_url: null }, el, 'Kalender-Abo wurde getrennt.');
      });
      el.querySelector('[data-action="save-login"]').addEventListener('click', function () {
        var username = el.querySelector('[data-field="username"]').value.trim();
        var password = el.querySelector('[data-field="password"]').value;
        if (!username || !password) { feedback(el, 'Bitte Benutzername und Passwort eintragen.', 'error'); return; }
        _patch('itslearning', { username: username, password: password }, el, 'Login gespeichert.');
      });
      var removeLogin = el.querySelector('[data-action="remove-login"]');
      if (removeLogin) removeLogin.addEventListener('click', function () {
        _patch('itslearning', { username: null, password: null }, el, 'Login gelöscht.');
      });
    },
  });

  // ── Dialog ────────────────────────────────────────────────────────────────

  function registerSection(section) {
    _sections = _sections.filter(function (s) { return s.id !== section.id; });
    _sections.push(section);
    if (_body && !_modal.hidden && _status) render();
  }

  function render() {
    if (!_body) return;
    var status = _status || {};
    _body.innerHTML = _sections.map(function (section) {
      return '<section class="connection-section" data-section="' + esc(section.id) + '">' +
        section.render(status) + '</section>';
    }).join('');
    _sections.forEach(function (section) {
      var el = _body.querySelector('[data-section="' + section.id + '"]');
      if (el && section.bind) section.bind(el, status);
    });
  }

  function load() {
    _body.innerHTML = '<p class="connection-copy">Lade Verbindungen …</p>';
    return api('/api/v2/connections')
      .then(function (data) { _status = data.connections || {}; render(); })
      .catch(function (err) {
        _body.innerHTML = '<p class="connection-feedback is-error">' + esc(err.message) + '</p>';
      });
  }

  function open() {
    if (!_modal) return;
    _modal.hidden = false;
    load();
  }

  function close() {
    if (_modal) _modal.hidden = true;
  }

  function init(options) {
    options = options || {};
    if (typeof options.onChanged === 'function') _onChanged = options.onChanged;
    _modal = document.getElementById('connections-modal');
    _body = document.getElementById('connections-body');
    if (!_modal || !_body) return;

    ['sidebar-connections-btn', 'more-sheet-connections-btn'].forEach(function (id) {
      var btn = document.getElementById(id);
      if (!btn) return;
      btn.hidden = !window.MULTIUSER_ENABLED;
      btn.addEventListener('click', function () {
        var sheet = document.getElementById('mobile-more-sheet');
        if (sheet) sheet.hidden = true;
        open();
      });
    });
    var closeBtn = document.getElementById('connections-close');
    if (closeBtn) closeBtn.addEventListener('click', close);
    _modal.addEventListener('click', function (event) { if (event.target === _modal) close(); });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !_modal.hidden) close();
    });
  }

  window.LehrerConnections = {
    init: init,
    open: open,
    close: close,
    reload: function () { if (_modal && !_modal.hidden) load(); },
    registerSection: registerSection,
    api: api,
    esc: esc,
    feedback: feedback,
    statusPill: statusPill,
  };
})();
