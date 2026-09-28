/**
 * LehrerConnections — "Verbindungen": every information source of the cockpit
 * in one place, grouped into
 *   Deine Zugänge        WebUntis, itslearning, Nextcloud (per teacher)
 *   Schulweite Quellen   Orgaplan, Klassenarbeitsplan, Schultermine, Dienstmail
 *                        (status for everyone, changeable by admins)
 *   Benachrichtigungen   Push on this device, KI-Assistent
 *
 * Backend: GET /api/v2/connections, PATCH /api/v2/connections/<module>,
 * /api/v2/connections/nextcloud/*, /api/v2/connections/school/*,
 * /api/v2/modules/klassenarbeitsplan/{config,fetch}.
 *
 * The same sections render in the dialog (index.html) and in the setup wizard
 * (onboarding.html, via mount()).
 *
 * Exposes window.LehrerConnections = { init, open, close, reload, mount,
 *   registerSection, api, esc, feedback, statusPill }.
 */
(function () {
  'use strict';

  var GROUPS = [
    { id: 'personal', title: 'Deine Zugänge', hint: 'Nur für dich. Links und Zugänge werden verschlüsselt gespeichert.' },
    { id: 'school', title: 'Schulweite Quellen', hint: 'Gelten für alle Lehrkräfte eurer Schule.' },
    { id: 'notify', title: 'Benachrichtigungen & Assistent', hint: '' },
  ];

  var _sections = [];
  var _status = null;
  var _onChanged = function () {};
  var _modal = null;
  var _body = null;
  var _only = null;          // section ids when mounted into the setup wizard
  var _showSummary = true;
  var _pendingSection = '';

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

  // kind: ok | warn | error | off
  function pill(kind, label) {
    var cls = { ok: 'pill-live', warn: 'pill-attention', error: 'pill-danger' }[kind] || '';
    return '<span class="pill ' + cls + '">' + esc(label) + '</span>';
  }

  function statusPill(ok, okLabel, offLabel) {
    return pill(ok ? 'ok' : 'warn', ok ? okLabel : offLabel);
  }

  function feedback(sectionEl, message, kind) {
    var el = sectionEl && sectionEl.querySelector('[data-feedback]');
    if (!el) return;
    el.textContent = message || '';
    el.className = 'connection-feedback' + (kind ? ' is-' + kind : '');
  }

  function _host(url) {
    try { return new URL(url).host.replace(/^www\./, ''); } catch (e) { return url || ''; }
  }

  function _deDate(value) {
    if (!value) return '';
    var match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
    return match ? match[3] + '.' + match[2] + '.' + match[1] : String(value);
  }

  function relTime(iso) {
    if (!iso) return '';
    var date = new Date(iso);
    if (isNaN(date.getTime())) return '';
    var minutes = Math.round((Date.now() - date.getTime()) / 60000);
    if (minutes < 1) return 'gerade eben';
    if (minutes < 60) return 'vor ' + minutes + ' Min.';
    var hours = Math.round(minutes / 60);
    if (hours < 24) return 'vor ' + hours + ' Std.';
    var days = Math.round(hours / 24);
    if (days === 1) return 'gestern';
    if (days < 7) return 'vor ' + days + ' Tagen';
    return 'am ' + date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
  }

  function facts(rows) {
    rows = rows.filter(function (row) { return row && row[1]; });
    if (!rows.length) return '';
    return '<dl class="connection-facts">' + rows.map(function (row) {
      return '<div><dt>' + esc(row[0]) + '</dt><dd>' + row[1] + '</dd></div>';
    }).join('') + '</dl>';
  }

  function alertBox(kind, html) {
    return html ? '<div class="connection-alert is-' + kind + '">' + html + '</div>' : '';
  }

  function extLink(url, label) {
    return '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(label) + '</a>';
  }

  function _replaceStatus(connections) {
    _status = Object.assign({}, _status, connections || {});
    render();
  }

  function _freshSection(id) {
    return _body && _body.querySelector('[data-section="' + id + '"]');
  }

  // ── Deine Zugänge ─────────────────────────────────────────────────────────

  function _patch(moduleId, fields, sectionEl, okMessage) {
    feedback(sectionEl, 'Speichere …');
    return api('/api/v2/connections/' + moduleId, { method: 'PATCH', body: fields })
      .then(function (data) {
        _replaceStatus(data.connections);
        feedback(_freshSection(moduleId), okMessage, 'success');
        _onChanged(moduleId);
      })
      .catch(function (err) { feedback(sectionEl, err.message, 'error'); });
  }

  registerSection({
    id: 'webuntis',
    group: 'personal',
    title: 'WebUntis',
    state: function (status) { return (status.webuntis || {}).configured ? 'ok' : 'off'; },
    render: function (status) {
      var s = status.webuntis || {};
      return '' +
        '<div class="connection-head"><h3>WebUntis</h3>' + pill(s.configured ? 'ok' : 'warn', s.configured ? 'verbunden' : 'nicht verbunden') + '</div>' +
        '<p class="connection-copy">Dein persönlicher Stundenplan mit Vertretungen und Entfällen – über das Kalender-Abo (iCal) von WebUntis.</p>' +
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
    group: 'personal',
    title: 'itslearning',
    state: function (status) { var s = status.itslearning || {}; return s.calendar || s.login ? 'ok' : 'off'; },
    render: function (status) {
      var s = status.itslearning || {};
      var connected = s.calendar || s.login;
      return '' +
        '<div class="connection-head"><h3>itslearning</h3>' + pill(connected ? 'ok' : 'warn', s.calendar ? 'Kalender verbunden' : (connected ? 'verbunden' : 'nicht verbunden')) + '</div>' +
        '<p class="connection-copy">Termine und Abgabefristen deiner Kurse über das offizielle Kalender-Abo – ganz ohne Passwort.</p>' +
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

  // ── Nextcloud (Login Flow v2) ─────────────────────────────────────────────

  var NEXTCLOUD_POLL_MS = 2500;
  var NEXTCLOUD_POLL_LIMIT_MS = 20 * 60 * 1000; // Nextcloud poll tokens live 20 minutes
  var _nextcloudPoll = null;

  function _stopNextcloudPolling() {
    if (_nextcloudPoll) { clearTimeout(_nextcloudPoll.timer); _nextcloudPoll = null; }
  }

  function _pollNextcloud(sectionEl) {
    if (!_nextcloudPoll) return;
    if (Date.now() - _nextcloudPoll.started > NEXTCLOUD_POLL_LIMIT_MS) {
      _stopNextcloudPolling();
      feedback(sectionEl, 'Die Anmeldung ist abgelaufen. Bitte erneut verbinden.', 'error');
      return;
    }
    api('/api/v2/connections/nextcloud/poll', { method: 'POST' })
      .then(function (data) {
        if (data.status === 'connected') {
          _stopNextcloudPolling();
          if (data.connections) _replaceStatus(data.connections);
          else if (_status && _status.nextcloud) { _status.nextcloud.connected = true; render(); }
          feedback(_freshSection('nextcloud'), 'Nextcloud ist verbunden.', 'success');
          _onChanged('nextcloud');
          if (!data.connections) load();
          return;
        }
        if (data.status === 'expired') {
          _stopNextcloudPolling();
          feedback(sectionEl, 'Die Anmeldung ist abgelaufen. Bitte erneut verbinden.', 'error');
          return;
        }
        _nextcloudPoll.timer = setTimeout(function () { _pollNextcloud(sectionEl); }, NEXTCLOUD_POLL_MS);
      })
      .catch(function (err) {
        // Transient errors: keep waiting, the teacher may still be signing in.
        feedback(sectionEl, err.message + ' – ich versuche es weiter …', 'error');
        if (_nextcloudPoll) {
          _nextcloudPoll.timer = setTimeout(function () { _pollNextcloud(sectionEl); }, NEXTCLOUD_POLL_MS * 2);
        }
      });
  }

  function _startNextcloudPolling(sectionEl) {
    _stopNextcloudPolling();
    _nextcloudPoll = { started: Date.now(), timer: null };
    _nextcloudPoll.timer = setTimeout(function () { _pollNextcloud(sectionEl); }, NEXTCLOUD_POLL_MS);
  }

  registerSection({
    id: 'nextcloud',
    group: 'personal',
    title: 'Nextcloud',
    state: function (status) { return (status.nextcloud || {}).connected ? 'ok' : 'off'; },
    render: function (status) {
      var s = status.nextcloud || {};
      var waiting = s.pending || !!_nextcloudPoll;
      var head = '<div class="connection-head"><h3>Nextcloud</h3>' +
        pill(s.connected ? 'ok' : 'warn', s.connected ? 'verbunden' : (waiting ? 'Anmeldung läuft' : 'nicht verbunden')) + '</div>';
      if (s.connected) {
        return head +
          '<p class="connection-copy">Verbunden als <strong>' + esc(s.account) + '</strong> auf ' + esc(_host(s.server)) + '. ' +
          'Neue Dateien, Änderungen und Freigaben anderer erscheinen im Posteingang.</p>' +
          '<p class="connection-copy">Das Cockpit nutzt ein eigenes App-Passwort. Du kannst es jederzeit hier trennen oder in Nextcloud unter Einstellungen → Sicherheit widerrufen.</p>' +
          '<div class="connection-actions"><button class="btn btn-secondary" type="button" data-action="disconnect">Trennen</button></div>' +
          '<p class="connection-feedback" data-feedback></p>';
      }
      return head +
        '<p class="connection-copy">Neue Dateien, Änderungen und Freigaben aus euren geteilten Ordnern. Du meldest dich direkt auf der Nextcloud-Seite deiner Schule an – das Cockpit bekommt nur ein eigenes App-Passwort, dein Passwort sieht es nie.</p>' +
        '<label class="connection-field">Adresse eurer Nextcloud' +
        '<input class="form-input" type="url" data-field="base_url" value="' + esc(s.suggested_server || '') + '" placeholder="https://cloud.schule.de" autocomplete="off" /></label>' +
        '<div class="connection-actions">' +
        '<button class="btn btn-primary" type="button" data-action="connect">' + (waiting ? 'Erneut öffnen' : 'Mit Nextcloud verbinden') + '</button>' +
        (waiting ? '<button class="btn btn-secondary" type="button" data-action="cancel">Abbrechen</button>' : '') +
        '</div>' +
        '<p class="connection-feedback" data-feedback>' + (waiting ? 'Warte auf die Anmeldung in Nextcloud …' : '') + '</p>' +
        '<p class="connection-copy" data-login-link hidden></p>';
    },
    bind: function (el, status) {
      var s = status.nextcloud || {};
      var disconnect = el.querySelector('[data-action="disconnect"]');
      if (disconnect) {
        disconnect.addEventListener('click', function () {
          feedback(el, 'Trenne …');
          api('/api/v2/connections/nextcloud', { method: 'DELETE' })
            .then(function (data) {
              _replaceStatus(data.connections);
              feedback(_freshSection('nextcloud'), data.revoked ? 'Nextcloud wurde getrennt.' : 'Getrennt. Das App-Passwort bitte zusätzlich in Nextcloud löschen.', 'success');
              _onChanged('nextcloud');
            })
            .catch(function (err) { feedback(el, err.message, 'error'); });
        });
        return;
      }

      var cancel = el.querySelector('[data-action="cancel"]');
      if (cancel) cancel.addEventListener('click', function () {
        _stopNextcloudPolling();
        if (_status && _status.nextcloud) _status.nextcloud.pending = false;
        render();
      });

      el.querySelector('[data-action="connect"]').addEventListener('click', function () {
        var baseUrl = el.querySelector('[data-field="base_url"]').value.trim();
        if (!baseUrl) { feedback(el, 'Bitte die Adresse eurer Nextcloud eintragen.', 'error'); return; }
        // Open the tab synchronously (popup blockers), navigate once the login URL is known.
        var loginWindow = window.open('', '_blank');
        if (loginWindow) loginWindow.opener = null;
        feedback(el, 'Verbinde mit Nextcloud …');
        api('/api/v2/connections/nextcloud/start', { method: 'POST', body: { base_url: baseUrl } })
          .then(function (data) {
            if (loginWindow && !loginWindow.closed) {
              loginWindow.location.href = data.login_url;
              feedback(el, 'Bitte im neuen Tab bei Nextcloud anmelden und „Zugriff gewähren“ bestätigen. Danach geht es hier automatisch weiter.');
            } else {
              var link = el.querySelector('[data-login-link]');
              link.innerHTML = extLink(data.login_url, 'Anmeldeseite von Nextcloud öffnen');
              link.hidden = false;
              feedback(el, 'Bitte über den Link unten bei Nextcloud anmelden und „Zugriff gewähren“ bestätigen. Danach geht es hier automatisch weiter.');
            }
            _startNextcloudPolling(el);
          })
          .catch(function (err) {
            if (loginWindow && !loginWindow.closed) loginWindow.close();
            feedback(el, err.message, 'error');
          });
      });

      if (s.pending && !_nextcloudPoll) _startNextcloudPolling(el);
    },
  });

  // ── Schulweite Quellen: Orgaplan ──────────────────────────────────────────

  var ORGAPLAN_STATES = {
    ok: ['ok', 'aktuell'], outdated: ['warn', 'veraltet'], error: ['error', 'Fehler'], pending: ['off', 'wird geladen'],
  };

  function _orgaplanState(status) {
    var o = status.orgaplan || {};
    if (o.status === 'ok') return 'ok';
    if (o.status === 'outdated' || o.status === 'error') return 'warn';
    return 'off';
  }

  registerSection({
    id: 'orgaplan',
    group: 'school',
    title: 'Orgaplan',
    state: _orgaplanState,
    render: function (status) {
      var o = status.orgaplan || {};
      var look = ORGAPLAN_STATES[o.status] || ['off', 'unbekannt'];
      var source = o.mode === 'fixed'
        ? 'Feste PDF, die ein Admin hinterlegt hat.'
        : 'Das Cockpit sucht auf ' + esc(_host(o.site)) + ' selbst die neueste PDF mit „' + esc(o.query || 'Orgaplan') +
          '“ im Namen – ein neuer Plan der Schule wird so automatisch übernommen.';
      var html = '<div class="connection-head"><h3>Orgaplan</h3>' + pill(look[0], look[1]) + '</div>' +
        '<p class="connection-copy">Allgemeine Termine, Mittel- und Oberstufe – das Cockpit liest den ganzen Plan und zeigt dir die nächsten Wochen. ' + source + '</p>' +
        facts([
          ['Datei', o.name ? (o.current_url ? extLink(o.current_url, o.name) : esc(o.name)) : ''],
          ['Plan', [o.school_year ? 'Schuljahr ' + esc(o.school_year) : '', o.stand ? 'Stand ' + esc(o.stand) : ''].filter(Boolean).join(' · ')],
          ['Veröffentlicht', o.published_at ? esc(_deDate(o.published_at)) : ''],
          ['Einträge', o.entries ? esc(o.entries) + ' im ganzen Schuljahr' : ''],
          ['Geprüft', o.checked_at ? esc(relTime(o.checked_at)) : ''],
        ]);
      if (o.status === 'error' || (o.error && o.status !== 'ok')) html += alertBox('error', esc(o.error || o.detail));
      else if (o.status === 'outdated') html += alertBox('warning', esc(o.detail));
      else if (o.error) html += alertBox('warning', 'Letzte Prüfung fehlgeschlagen: ' + esc(o.error) + ' Angezeigt wird der zuletzt gelesene Plan.');
      html += '<div class="connection-actions">' +
        '<button class="btn btn-primary" type="button" data-action="orgaplan-refresh">Jetzt prüfen</button>' +
        (o.current_url ? '<a class="btn btn-secondary" href="' + esc(o.current_url) + '" target="_blank" rel="noopener noreferrer">PDF öffnen ↗</a>' : '') +
        '</div>';
      if (o.can_edit) {
        var auto = o.mode !== 'fixed';
        html += '<details class="connection-optional"><summary>Quelle ändern (Admin)</summary>' +
          '<label class="connection-check"><input type="radio" name="orgaplan-mode" value="auto"' + (auto ? ' checked' : '') + ' /> Automatisch die neueste PDF von der Schulwebseite</label>' +
          '<label class="connection-field">Schulwebseite oder Seite mit dem Orgaplan<input class="form-input" type="url" data-field="site" value="' + esc(o.site || '') + '" placeholder="https://meine-schule.de" autocomplete="off" /></label>' +
          '<label class="connection-field">Begriff im Dateinamen<input class="form-input" type="text" data-field="query" value="' + esc(o.query || 'Orgaplan') + '" autocomplete="off" /></label>' +
          '<label class="connection-check"><input type="radio" name="orgaplan-mode" value="fixed"' + (!auto ? ' checked' : '') + ' /> Immer diese PDF verwenden</label>' +
          '<label class="connection-field">PDF-Link<input class="form-input" type="url" data-field="pdf_url" value="' + esc(o.pdf_url || '') + '" placeholder="https://…/orgaplan.pdf" autocomplete="off" /></label>' +
          '<div class="connection-actions"><button class="btn btn-secondary" type="button" data-action="orgaplan-save">Quelle speichern</button></div>' +
          '</details>';
      }
      return html + '<p class="connection-feedback" data-feedback></p>';
    },
    bind: function (el) {
      el.querySelector('[data-action="orgaplan-refresh"]').addEventListener('click', function (event) {
        var button = event.currentTarget;
        button.disabled = true;
        feedback(el, 'Suche den aktuellen Orgaplan …');
        api('/api/v2/connections/school/orgaplan/refresh', { method: 'POST' })
          .then(function (data) {
            _replaceStatus(data.connections);
            var o = (_status || {}).orgaplan || {};
            feedback(_freshSection('orgaplan'), o.status === 'ok' ? 'Orgaplan ist aktuell.' : (o.detail || 'Geprüft.'), o.status === 'ok' ? 'success' : 'error');
            _onChanged('orgaplan');
          })
          .catch(function (err) { button.disabled = false; feedback(el, err.message, 'error'); });
      });
      var save = el.querySelector('[data-action="orgaplan-save"]');
      if (save) save.addEventListener('click', function () {
        var modeInput = el.querySelector('input[name="orgaplan-mode"]:checked');
        var mode = modeInput ? modeInput.value : 'auto';
        var body = mode === 'fixed'
          ? { mode: 'fixed', pdf_url: el.querySelector('[data-field="pdf_url"]').value.trim() }
          : { mode: 'auto', site: el.querySelector('[data-field="site"]').value.trim(), query: el.querySelector('[data-field="query"]').value.trim() };
        save.disabled = true;
        feedback(el, 'Speichere und lese den Orgaplan ein …');
        api('/api/v2/connections/school/orgaplan', { method: 'PUT', body: body })
          .then(function (data) {
            _replaceStatus(data.connections);
            var o = (_status || {}).orgaplan || {};
            feedback(_freshSection('orgaplan'), o.status === 'ok' ? 'Gespeichert – der Orgaplan ist eingelesen.' : (o.detail || 'Gespeichert.'), o.status === 'ok' ? 'success' : 'error');
            _onChanged('orgaplan');
          })
          .catch(function (err) { save.disabled = false; feedback(el, err.message, 'error'); });
      });
    },
  });

  // ── Schulweite Quellen: Klassenarbeitsplan (OneDrive) ─────────────────────

  var CLASSWORK_SOURCE_LABELS = {
    onedrive: 'automatisch von OneDrive',
    'onedrive-browser': 'automatisch von OneDrive (über einen Browser)',
    upload: 'manuell hochgeladen',
    auto: 'automatisch abgerufen',
  };

  function _classworkState(status) {
    var cw = status.klassenarbeitsplan || {};
    var plan = cw.plan || {};
    var sync = cw.sync || {};
    if (plan.state === 'outdated') return 'warn';
    if (cw.onedrive && (sync.last_result === 'error' || sync.last_result === 'blocked') && sync.needs_browser) return 'warn';
    if (cw.url || plan.state === 'ok') return 'ok';
    return 'off';
  }

  function _refreshClasswork(el, cw) {
    feedback(el, 'Prüfe den Plan auf OneDrive …');
    return api('/api/v2/modules/klassenarbeitsplan/fetch', { method: 'POST', body: {} })
      .then(function (data) {
        if (data.result === 'ok' || data.result === 'unchanged') {
          return data.result === 'ok' ? 'Neuer Stand geladen.' : 'Geprüft – die Datei auf OneDrive ist unverändert.';
        }
        // Microsoft refused the server – fetch in this browser instead.
        if (!window.LehrerOneDriveSync) throw new Error(data.error || 'Abruf nicht möglich.');
        feedback(el, 'Der Server wird von Microsoft geblockt – lade über deinen Browser …');
        return window.LehrerOneDriveSync.syncNow(cw.url, (data.sync || {}).etag || '')
          .then(function (result) {
            return result.state === 'ok' ? 'Neuer Stand über deinen Browser geladen.' : 'Geprüft – die Datei ist unverändert.';
          });
      })
      .then(function (message) {
        _onChanged('klassenarbeitsplan');
        return load().then(function () {
          var fresh = _freshSection('klassenarbeitsplan');
          var plan = (((_status || {}).klassenarbeitsplan || {}).plan) || {};
          if (plan.state === 'outdated') feedback(fresh, message + ' Der Plan enthält aber keine kommenden Termine.', 'error');
          else feedback(fresh, message, 'success');
        });
      })
      .catch(function (err) { feedback(el, err.message, 'error'); });
  }

  function _saveClassworkLink(el, url) {
    if (url && !/^https:\/\//i.test(url)) { feedback(el, 'Bitte den vollständigen Link (https://…) einfügen.', 'error'); return; }
    feedback(el, 'Speichere …');
    api('/api/v2/modules/klassenarbeitsplan/config', { method: 'POST', body: { url: url } })
      .then(function () {
        return load().then(function () {
          var fresh = _freshSection('klassenarbeitsplan');
          feedback(fresh, url ? 'Link gespeichert – lade den Plan …' : 'Link entfernt.', 'success');
          var freshStatus = (_status || {}).klassenarbeitsplan || {};
          if (url) _refreshClasswork(fresh, freshStatus);
          else _onChanged('klassenarbeitsplan');
        });
      })
      .catch(function (err) { feedback(el, err.message, 'error'); });
  }

  registerSection({
    id: 'klassenarbeitsplan',
    group: 'school',
    title: 'Klassenarbeitsplan',
    state: _classworkState,
    render: function (status) {
      var cw = status.klassenarbeitsplan || {};
      var plan = cw.plan || {};
      var sync = cw.sync || {};
      var state = _classworkState(status);
      var label = plan.state === 'outdated' ? 'veraltet'
        : state === 'warn' ? 'Abruf gestört'
        : cw.onedrive ? 'automatisch' : cw.url ? 'verlinkt' : (plan.state === 'ok' ? 'hochgeladen' : 'kein Link');
      var html = '<div class="connection-head"><h3>Klassenarbeitsplan</h3>' + pill(state, label) + '</div>' +
        '<p class="connection-copy">' + (cw.onedrive
          ? 'Der Plan bleibt auf OneDrive. Das Cockpit prüft ihn stündlich, übernimmt Änderungen und zeigt nur kommende Arbeiten.'
          : cw.url
            ? 'Der Plan wird vom hinterlegten Link geladen.'
            : 'Noch kein Link hinterlegt. Bis dahin lässt sich die Excel-Datei unter „Pläne“ hochladen.') + '</p>' +
        facts([
          ['Datei', plan.fileName ? esc(plan.fileName) + (plan.folder ? ' <span class="connection-muted">(aus dem Ordner „' + esc(plan.folder) + '“)</span>' : '') : ''],
          ['Schuljahr', plan.schoolYear ? esc(plan.schoolYear) : ''],
          ['Geändert', plan.fileModified ? 'am ' + esc(_deDate(plan.fileModified)) + ' (auf OneDrive)' : ''],
          ['Übernommen', cw.uploaded_at ? esc(cw.uploaded_at) + ' – ' + esc(CLASSWORK_SOURCE_LABELS[cw.upload_source] || 'hochgeladen') : ''],
          ['Geprüft', sync.last_success ? esc(relTime(sync.last_success)) : ''],
          ['Einträge', plan.state ? esc(plan.upcomingCount || 0) + ' ab heute' + (plan.lastDate ? ' · letzter Eintrag ' + esc(_deDate(plan.lastDate)) : '') : ''],
        ]);
      if (plan.state === 'outdated') {
        html += alertBox('warning', esc(plan.message) + ' ' + (cw.can_edit
          ? 'Trag unten den Link zum aktuellen Plan ein – am besten den Link zum <strong>OneDrive-Ordner</strong>, dann findet das Cockpit neue Dateien künftig selbst.'
          : 'Bitte gib der Person Bescheid, die das Cockpit an eurer Schule verwaltet.'));
      }
      if (cw.onedrive && sync.last_result === 'error' && sync.last_error) {
        html += alertBox('error', 'Letzter Abruf fehlgeschlagen: ' + esc(sync.last_error));
      } else if (cw.onedrive && sync.last_result === 'blocked') {
        html += alertBox('info', 'Microsoft blockiert gerade den Server. Die Browser der Lehrkräfte übernehmen den Abruf.');
      }
      if (cw.candidate_url) {
        html += alertBox('info', 'Im Admin-Bereich war außerdem dieser Link eingetragen: ' + extLink(cw.candidate_url, _host(cw.candidate_url) + ' …') +
          ' <button class="btn btn-secondary btn-inline" type="button" data-action="use-candidate">Diesen Link verwenden</button>');
      }
      html += '<div class="connection-actions">' +
        (cw.url ? '<button class="btn btn-primary" type="button" data-action="refresh">Jetzt prüfen</button>' : '') +
        (cw.url ? '<a class="btn btn-secondary" href="' + esc(cw.url) + '" target="_blank" rel="noopener noreferrer">Auf OneDrive öffnen ↗</a>' : '') +
        '</div>';
      if (cw.can_edit) {
        html += '<details class="connection-optional"' + (!cw.url || plan.state === 'outdated' ? ' open' : '') + '><summary>Link ändern (Admin)</summary>' +
          '<label class="connection-field">OneDrive-Freigabelink (Datei oder Ordner)' +
          '<input class="form-input" type="url" data-field="classwork_url" value="' + esc(cw.url || '') + '" placeholder="https://1drv.ms/…" autocomplete="off" /></label>' +
          '<details class="connection-help"><summary>Welchen Link brauche ich?</summary><ol>' +
          '<li>In OneDrive den <strong>Ordner</strong> mit den Klassenarbeitsplänen auswählen (oder die Excel-Datei) → „Teilen“.</li>' +
          '<li>„Jeder mit dem Link kann anzeigen“ einstellen und den Link kopieren.</li></ol>' +
          '<p>Mit dem Ordner-Link nimmt das Cockpit automatisch die neueste Excel-Datei – der Plan fürs nächste Schuljahr braucht dann keinen neuen Link.</p></details>' +
          '<div class="connection-actions"><button class="btn btn-secondary" type="button" data-action="save-link">Link speichern</button></div>' +
          '</details>';
      }
      return html + '<p class="connection-feedback" data-feedback></p>';
    },
    bind: function (el, status) {
      var cw = status.klassenarbeitsplan || {};
      var refresh = el.querySelector('[data-action="refresh"]');
      if (refresh) refresh.addEventListener('click', function () { _refreshClasswork(el, cw); });
      var save = el.querySelector('[data-action="save-link"]');
      if (save) save.addEventListener('click', function () {
        _saveClassworkLink(el, el.querySelector('[data-field="classwork_url"]').value.trim());
      });
      var candidate = el.querySelector('[data-action="use-candidate"]');
      if (candidate) candidate.addEventListener('click', function () { _saveClassworkLink(el, cw.candidate_url); });
    },
  });

  // ── Schulweite Quellen: Schultermine ──────────────────────────────────────

  registerSection({
    id: 'termine',
    group: 'school',
    title: 'Schultermine',
    state: function (status) { return (status.termine || {}).ok ? 'ok' : 'warn'; },
    render: function (status) {
      var t = status.termine || {};
      var html = '<div class="connection-head"><h3>Schultermine</h3>' +
        pill(t.ok ? 'ok' : 'error', t.ok ? 'verbunden' : 'nicht erreichbar') + '</div>' +
        '<p class="connection-copy">Ferien, Fahrten, Konferenzen und Veranstaltungen aus dem Kalender der Schulwebseite – im Tagesbriefing und unter „Pläne“.</p>' +
        facts([
          ['Quelle', t.url ? esc(_host(t.url)) + (t.is_default ? ' (Schulwebseite)' : '') : ''],
          ['Termine', t.ok ? esc(t.upcoming || 0) + ' in den nächsten sechs Wochen' : ''],
        ]);
      if (!t.ok && t.error) html += alertBox('error', esc(t.error));
      if (t.can_edit) {
        html += '<details class="connection-optional"><summary>Kalender-Adresse ändern (Admin)</summary>' +
          '<label class="connection-field">iCal-Adresse des Schulkalenders<input class="form-input" type="url" data-field="calendar_feed" value="' +
          esc(t.is_default ? '' : (t.url || '')) + '" placeholder="leer = Kalender der Schulwebseite" autocomplete="off" /></label>' +
          '<div class="connection-actions"><button class="btn btn-secondary" type="button" data-action="save-feed">Speichern</button></div>' +
          '</details>';
      }
      return html + '<p class="connection-feedback" data-feedback></p>';
    },
    bind: function (el) {
      var save = el.querySelector('[data-action="save-feed"]');
      if (save) save.addEventListener('click', function () {
        feedback(el, 'Speichere …');
        api('/api/v2/connections/school/termine', { method: 'PUT', body: { url: el.querySelector('[data-field="calendar_feed"]').value.trim() } })
          .then(function (data) {
            _replaceStatus(data.connections);
            feedback(_freshSection('termine'), 'Gespeichert.', 'success');
            _onChanged('termine');
          })
          .catch(function (err) { feedback(el, err.message, 'error'); });
      });
    },
  });

  // ── Schulweite Quellen: Dienstmail (nur Direktlink) ───────────────────────

  registerSection({
    id: 'dienstmail',
    group: 'school',
    title: 'Dienstmail',
    state: function () { return 'ok'; },
    render: function (status) {
      var d = status.dienstmail || {};
      var url = d.url || 'https://lehrkraeftemail.schule.berlin.de/?iam_sso=1';
      return '<div class="connection-head"><h3>Dienstmail</h3>' + pill('ok', 'Direktlink') + '</div>' +
        '<p class="connection-copy">Die Berliner Dienstmail erlaubt anderen Programmen keinen Zugriff (kein IMAP) – Mails kann das Cockpit deshalb nicht anzeigen. ' +
        'Es öffnet dein Postfach mit einem Klick; angemeldet wirst du über das Schulportal.</p>' +
        '<div class="connection-actions"><a class="btn btn-secondary" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">Dienstmail öffnen ↗</a></div>';
    },
  });

  // ── Push-Nachrichten (dieses Gerät) ───────────────────────────────────────

  function _pushBody(st) {
    var prefs = st.prefs || { morning: true, weekly: true };
    if (!st.supported) {
      return '<p class="connection-copy">Dieser Browser unterstützt keine Push-Nachrichten.</p>';
    }
    if (st.iosNeedsInstall) {
      return '<p class="connection-copy">Auf iPhone und iPad funktionieren Push-Nachrichten nur mit dem installierten Cockpit: ' +
        'in Safari auf „Teilen“ → „Zum Home-Bildschirm“, das Cockpit von dort öffnen und hier aktivieren.</p>';
    }
    if (!st.serverEnabled) {
      return '<p class="connection-copy">Push-Nachrichten sind auf dem Server noch nicht eingerichtet.</p>';
    }
    return '<p class="connection-copy">Das Cockpit meldet sich von selbst – du musst es nicht öffnen.</p>' +
      '<label class="connection-check"><input type="checkbox" data-pref="morning"' + (prefs.morning ? ' checked' : '') + ' /> ' +
      'Schultags morgens: dein Tag in drei Zeilen</label>' +
      '<label class="connection-check"><input type="checkbox" data-pref="weekly"' + (prefs.weekly ? ' checked' : '') + ' /> ' +
      'Sonntagabend: Vorschau auf die Woche</label>' +
      '<div class="connection-actions">' +
      (st.subscribed
        ? '<button class="btn btn-secondary" type="button" data-action="push-test">Test senden</button>' +
          '<button class="btn btn-secondary" type="button" data-action="push-off">Auf diesem Gerät ausschalten</button>'
        : '<button class="btn btn-primary" type="button" data-action="push-on">Auf diesem Gerät aktivieren</button>') +
      '</div>' +
      (st.permission === 'denied'
        ? '<p class="connection-feedback is-error">Benachrichtigungen sind in den Browser-Einstellungen blockiert.</p>' : '');
  }

  registerSection({
    id: 'push',
    group: 'notify',
    title: 'Push-Nachrichten',
    render: function () {
      return '<div class="connection-head"><h3>Push-Nachrichten</h3><span class="pill" data-push-pill>…</span></div>' +
        '<div data-push-body><p class="connection-copy">Prüfe dieses Gerät …</p></div>' +
        '<p class="connection-feedback" data-feedback></p>';
    },
    bind: function (el) {
      if (!window.LehrerPush) { el.hidden = true; return; }
      var body = el.querySelector('[data-push-body]');
      var pillEl = el.querySelector('[data-push-pill]');

      function refresh(message, kind) {
        return window.LehrerPush.status().then(function (st) {
          var active = st.subscribed && st.serverEnabled;
          pillEl.className = 'pill ' + (active ? 'pill-live' : '');
          pillEl.textContent = active ? 'aktiv' : 'aus';
          body.innerHTML = _pushBody(st);
          if (message) feedback(el, message, kind);
        });
      }

      function currentPrefs() {
        var prefs = {};
        el.querySelectorAll('[data-pref]').forEach(function (box) { prefs[box.getAttribute('data-pref')] = box.checked; });
        return prefs;
      }

      function run(promise, okMessage) {
        feedback(el, 'Einen Moment …');
        return promise
          .then(function () { return refresh(okMessage, 'success'); })
          .catch(function (err) { feedback(el, err.message, 'error'); });
      }

      body.addEventListener('click', function (event) {
        var button = event.target.closest('[data-action]');
        if (!button) return;
        var action = button.getAttribute('data-action');
        if (action === 'push-on') run(window.LehrerPush.enable(currentPrefs()), 'Push ist auf diesem Gerät aktiv.');
        if (action === 'push-off') run(window.LehrerPush.disable(), 'Push ist auf diesem Gerät ausgeschaltet.');
        if (action === 'push-test') run(window.LehrerPush.test(), 'Testnachricht verschickt.');
      });
      body.addEventListener('change', function (event) {
        if (!event.target.matches('[data-pref]')) return;
        run(window.LehrerPush.updatePrefs(currentPrefs()), 'Gespeichert.');
      });
      refresh();
    },
  });

  // ── KI-Assistent ──────────────────────────────────────────────────────────

  registerSection({
    id: 'ai',
    group: 'notify',
    title: 'KI-Assistent',
    render: function () {
      return '<div class="connection-head"><h3>KI-Assistent</h3><span class="pill" data-ai-pill>…</span></div>' +
        '<div data-ai-body><p class="connection-copy">Prüfe …</p></div>' +
        '<p class="connection-feedback" data-feedback></p>';
    },
    bind: function (el) {
      var body = el.querySelector('[data-ai-body]');
      var pillEl = el.querySelector('[data-ai-pill]');

      function draw(status) {
        pillEl.className = 'pill ' + (status.available && status.enabled ? 'pill-live' : '');
        pillEl.textContent = !status.available ? 'nicht eingerichtet' : (status.enabled ? 'an' : 'aus');
        if (!status.available) {
          body.innerHTML = '<p class="connection-copy">Der KI-Assistent ist auf diesem Server noch nicht eingerichtet.</p>';
          return;
        }
        var usage = status.usage || {};
        var limits = status.limits || {};
        body.innerHTML =
          '<p class="connection-copy">Fasst deinen Tag zusammen und beantwortet Fragen wie „Wann schreibt die 10b die nächste Arbeit?“.</p>' +
          '<details class="connection-help"><summary>Welche Daten gehen an die KI?</summary>' +
          '<p>Nur Plan- und Termindaten: Stunden (Fach, Klasse, Raum), Termine, Fristen und Klassenarbeiten deiner Klassen. ' +
          'Keine Noten, keine Notizen, keine Inhalte aus Nextcloud oder itslearning-Nachrichten – davon nur die Anzahl. ' +
          'Verarbeitet wird über die Claude API von Anthropic.</p></details>' +
          '<label class="connection-check"><input type="checkbox" data-ai-toggle' + (status.enabled ? ' checked' : '') + ' /> Für mich einschalten</label>' +
          (status.enabled
            ? '<p class="connection-copy">Heute: ' + (usage.briefings || 0) + ' von ' + limits.briefings + ' Zusammenfassungen, ' +
              (usage.questions || 0) + ' von ' + limits.questions + ' Fragen.</p>'
            : '');
      }

      function loadAi(message, kind) {
        return api('/api/v2/ai/status').then(function (status) {
          draw(status);
          if (message) feedback(el, message, kind);
        }).catch(function (err) { feedback(el, err.message, 'error'); });
      }

      body.addEventListener('change', function (event) {
        if (!event.target.matches('[data-ai-toggle]')) return;
        var enabled = event.target.checked;
        feedback(el, 'Speichere …');
        api('/api/v2/ai/settings', { method: 'PUT', body: { enabled: enabled } })
          .then(function () {
            if (window.LehrerAI) window.LehrerAI.reload();
            return loadAi(enabled ? 'Der KI-Assistent ist an. Die Zusammenfassung erscheint im Tagesbriefing.' : 'Der KI-Assistent ist aus.', 'success');
          })
          .catch(function (err) { feedback(el, err.message, 'error'); });
      });
      loadAi();
    },
  });

  // ── Rendering ─────────────────────────────────────────────────────────────

  function registerSection(section) {
    _sections = _sections.filter(function (s) { return s.id !== section.id; });
    _sections.push(section);
    if (_body && _status && (!_modal || !_modal.hidden)) render();
  }

  function _visibleSections() {
    return _sections.filter(function (s) { return !_only || _only.indexOf(s.id) !== -1; });
  }

  function _summaryHtml(status) {
    var chips = _sections.filter(function (s) { return typeof s.state === 'function'; }).map(function (s) {
      var state = s.state(status);
      return '<button type="button" class="conn-chip is-' + state + '" data-goto="' + esc(s.id) + '">' +
        '<span class="conn-chip-dot" aria-hidden="true"></span>' + esc(s.title) + '</button>';
    });
    var attention = _sections.filter(function (s) { return typeof s.state === 'function' && s.state(status) === 'warn'; }).length;
    return '<div class="connections-summary">' +
      '<p class="connection-copy">' + (attention
        ? '<strong>' + attention + (attention === 1 ? ' Quelle braucht' : ' Quellen brauchen') + ' Aufmerksamkeit.</strong> '
        : 'Alle eingerichteten Quellen laufen. ') +
      'Tippe auf eine Quelle, um direkt dorthin zu springen.</p>' +
      '<div class="conn-chips">' + chips.join('') + '</div></div>';
  }

  function render() {
    if (!_body) return;
    var status = _status || {};
    var sections = _visibleSections();
    var html = (_showSummary && !_only) ? _summaryHtml(status) : '';
    GROUPS.forEach(function (group) {
      var members = sections.filter(function (s) { return (s.group || 'notify') === group.id; });
      if (!members.length) return;
      var hint = group.hint;
      if (group.id === 'school') {
        var editable = members.some(function (s) { return ((status[s.id] || {}).can_edit); });
        hint += editable ? ' Du kannst sie als Admin ändern.' : ' Ändern können Admins.';
      }
      html += (_only ? '' : '<div class="connections-group"><h3 class="connections-group-title">' + esc(group.title) + '</h3>' +
        (hint ? '<p class="connections-group-hint">' + esc(hint) + '</p>' : '') + '</div>') +
        members.map(function (section) {
          return '<section class="connection-section" data-section="' + esc(section.id) + '">' + section.render(status) + '</section>';
        }).join('');
    });
    _body.innerHTML = html;
    sections.forEach(function (section) {
      var el = _body.querySelector('[data-section="' + section.id + '"]');
      if (el && section.bind) section.bind(el, status);
    });
    _body.querySelectorAll('[data-goto]').forEach(function (chip) {
      chip.addEventListener('click', function () { _scrollTo(chip.getAttribute('data-goto')); });
    });
    if (_pendingSection) {
      var target = _pendingSection;
      _pendingSection = '';
      _scrollTo(target);
    }
  }

  function _scrollTo(sectionId) {
    var el = _freshSection(sectionId);
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    el.classList.remove('is-highlighted');
    void el.offsetWidth; // restart the highlight animation
    el.classList.add('is-highlighted');
  }

  function load() {
    if (!_body) return Promise.resolve();
    if (!_status) _body.innerHTML = '<p class="connection-copy">Lade Verbindungen …</p>';
    return api('/api/v2/connections')
      .then(function (data) { _status = data.connections || {}; render(); return _status; })
      .catch(function (err) {
        _body.innerHTML = '<p class="connection-feedback is-error">' + esc(err.message) + '</p>';
      });
  }

  function open(sectionId) {
    if (!_modal) return;
    _body = document.getElementById('connections-body');
    _only = null;
    _showSummary = true;
    _modal.hidden = false;
    _pendingSection = sectionId || '';
    load();
  }

  function close() {
    if (_modal) _modal.hidden = true;
    _stopNextcloudPolling();
  }

  /** Render some sections into another container (setup wizard). */
  function mount(container, options) {
    options = options || {};
    _body = container;
    _only = options.sections || null;
    _showSummary = false;
    if (typeof options.onChanged === 'function') _onChanged = options.onChanged;
    if (_status) { render(); return Promise.resolve(_status); }
    return load();
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
    // Any element with data-open-connections="<section>" opens the dialog there.
    document.addEventListener('click', function (event) {
      var trigger = event.target.closest('[data-open-connections]');
      if (!trigger) return;
      event.preventDefault();
      open(trigger.getAttribute('data-open-connections'));
    });
    var closeBtn = document.getElementById('connections-close');
    if (closeBtn) closeBtn.addEventListener('click', close);
    _modal.addEventListener('click', function (event) { if (event.target === _modal) close(); });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !_modal.hidden) close();
    });
    // Deep link: …/index.html#verbindungen or #verbindungen/orgaplan (e.g. from the admin area)
    var match = (window.location.hash || '').match(/^#verbindungen(?:\/([\w-]+))?$/);
    if (match && window.MULTIUSER_ENABLED) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
      open(match[1] || '');
    }
  }

  window.LehrerConnections = {
    init: init,
    open: open,
    close: close,
    reload: function () { if (_body && (_only || (_modal && !_modal.hidden))) return load(); return Promise.resolve(); },
    mount: mount,
    registerSection: registerSection,
    api: api,
    esc: esc,
    feedback: feedback,
    statusPill: statusPill,
    relTime: relTime,
  };
})();
