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
          if (data.connections) _status = Object.assign({}, _status, data.connections);
          else if (_status && _status.nextcloud) _status.nextcloud.connected = true;
          render();
          var fresh = _body && _body.querySelector('[data-section="nextcloud"]');
          feedback(fresh, 'Nextcloud ist verbunden.', 'success');
          _onChanged();
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
    render: function (status) {
      var s = status.nextcloud || {};
      var waiting = s.pending || !!_nextcloudPoll;
      var head = '<div class="connection-head"><h3>Nextcloud</h3>' +
        statusPill(s.connected, 'verbunden', waiting ? 'Anmeldung läuft' : 'nicht verbunden') + '</div>';
      if (s.connected) {
        return head +
          '<p class="connection-copy">Verbunden als <strong>' + esc(s.account) + '</strong> auf ' + esc((s.server || '').replace(/^https:\/\//, '')) + '. ' +
          'Neue Dateien, Änderungen und Freigaben anderer erscheinen im Posteingang.</p>' +
          '<p class="connection-copy">Das Cockpit nutzt ein eigenes App-Passwort. Du kannst es jederzeit hier trennen oder in Nextcloud unter Einstellungen → Sicherheit widerrufen.</p>' +
          '<div class="connection-actions"><button class="btn btn-secondary" type="button" data-action="disconnect">Trennen</button></div>' +
          '<p class="connection-feedback" data-feedback></p>';
      }
      return head +
        '<p class="connection-copy">Du meldest dich direkt auf der Nextcloud-Seite deiner Schule an. Das Cockpit bekommt dabei nur ein eigenes App-Passwort – dein Passwort sieht es nie.</p>' +
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
              _status = Object.assign({}, _status, data.connections || {});
              render();
              var fresh = _body && _body.querySelector('[data-section="nextcloud"]');
              feedback(fresh, data.revoked ? 'Nextcloud wurde getrennt.' : 'Getrennt. Das App-Passwort bitte zusätzlich in Nextcloud löschen.', 'success');
              _onChanged();
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
              link.innerHTML = '<a href="' + esc(data.login_url) + '" target="_blank" rel="noopener noreferrer">Anmeldeseite von Nextcloud öffnen</a>';
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

  // ── Klassenarbeitsplan (OneDrive) ─────────────────────────────────────────

  var CLASSWORK_SOURCE_LABELS = {
    onedrive: 'automatisch von OneDrive (Server)',
    'onedrive-browser': 'automatisch von OneDrive (über einen Browser)',
    upload: 'manuell hochgeladen',
    auto: 'automatisch abgerufen',
  };

  function _refreshClasswork(el, cw) {
    feedback(el, 'Aktualisiere …');
    return api('/api/v2/modules/klassenarbeitsplan/fetch', { method: 'POST', body: {} })
      .then(function (data) {
        if (data.result === 'ok' || data.result === 'unchanged') {
          return data.result === 'ok' ? 'Neuer Stand von OneDrive geladen.' : 'Der Plan ist aktuell.';
        }
        // Microsoft refused the server – fetch in this browser instead.
        if (!window.LehrerOneDriveSync) throw new Error(data.error || 'Abruf nicht möglich.');
        feedback(el, 'Server wird von Microsoft geblockt – lade über deinen Browser …');
        return window.LehrerOneDriveSync.syncNow(cw.url, (data.sync || {}).etag || '')
          .then(function (result) {
            return result.state === 'ok' ? 'Neuer Stand über deinen Browser geladen.' : 'Der Plan ist aktuell.';
          });
      })
      .then(function (message) {
        _onChanged();
        return load().then(function () {
          feedback(_body && _body.querySelector('[data-section="klassenarbeitsplan"]'), message, 'success');
        });
      })
      .catch(function (err) { feedback(el, err.message, 'error'); });
  }

  registerSection({
    id: 'klassenarbeitsplan',
    render: function (status) {
      var cw = status.klassenarbeitsplan || {};
      var sync = cw.sync || {};
      var head = '<div class="connection-head"><h3>Klassenarbeitsplan</h3>' +
        statusPill(cw.onedrive, 'automatisch', cw.url ? 'nur manuell' : 'kein Link') + '</div>';
      var body = cw.onedrive
        ? '<p class="connection-copy">Der Plan bleibt auf OneDrive. Das Cockpit holt ihn automatisch – zuerst über den Server, und falls Microsoft den Server blockt, über den Browser einer Lehrkraft.</p>'
        : '<p class="connection-copy">' + (cw.url
          ? 'Der hinterlegte Link ist kein OneDrive-Freigabelink. Der Plan kann nur manuell hochgeladen werden.'
          : 'Noch kein OneDrive-Link hinterlegt. Bis dahin lässt sich der Plan unter „Pläne“ manuell hochladen.') + '</p>';
      if (cw.uploaded_at) {
        body += '<p class="connection-copy">Stand vom <strong>' + esc(cw.uploaded_at) + '</strong> – ' +
          esc(CLASSWORK_SOURCE_LABELS[cw.upload_source] || 'hochgeladen') + '.</p>';
      }
      if (cw.onedrive && sync.last_result === 'blocked') {
        body += '<p class="connection-copy">Der Server wird von Microsoft blockiert. Die Browser der Lehrkräfte übernehmen den Abruf.</p>';
      } else if (cw.onedrive && sync.last_result === 'error' && sync.last_error) {
        body += '<p class="connection-feedback is-error">' + esc(sync.last_error) + '</p>';
      }
      var actions = cw.onedrive
        ? '<button class="btn btn-primary" type="button" data-action="refresh">Jetzt aktualisieren</button>' : '';
      var edit = cw.can_edit
        ? '<label class="connection-field">OneDrive-Freigabelink (gilt für die ganze Schule)' +
          '<input class="form-input" type="url" data-field="classwork_url" value="' + esc(cw.url || '') + '" placeholder="https://1drv.ms/x/…" autocomplete="off" /></label>' +
          '<details class="connection-help"><summary>Welchen Link brauche ich?</summary><ol>' +
          '<li>In OneDrive die Excel-Datei des Klassenarbeitsplans auswählen → „Teilen“.</li>' +
          '<li>„Jeder mit dem Link kann anzeigen“ einstellen und den Link kopieren.</li></ol></details>'
        : '';
      var editActions = cw.can_edit
        ? '<button class="btn btn-secondary" type="button" data-action="save-link">Link speichern</button>' : '';
      return head + body + edit +
        ((actions || editActions) ? '<div class="connection-actions">' + actions + editActions + '</div>' : '') +
        '<p class="connection-feedback" data-feedback></p>';
    },
    bind: function (el, status) {
      var cw = status.klassenarbeitsplan || {};
      var refresh = el.querySelector('[data-action="refresh"]');
      if (refresh) refresh.addEventListener('click', function () { _refreshClasswork(el, cw); });
      var save = el.querySelector('[data-action="save-link"]');
      if (save) save.addEventListener('click', function () {
        var url = el.querySelector('[data-field="classwork_url"]').value.trim();
        if (url && !/^https:\/\//i.test(url)) { feedback(el, 'Bitte den vollständigen Link (https://…) einfügen.', 'error'); return; }
        feedback(el, 'Speichere …');
        api('/api/v2/modules/klassenarbeitsplan/config', { method: 'POST', body: { url: url } })
          .then(function () {
            return load().then(function () {
              var fresh = _body && _body.querySelector('[data-section="klassenarbeitsplan"]');
              feedback(fresh, 'Link gespeichert.', 'success');
              var freshStatus = (_status || {}).klassenarbeitsplan || {};
              if (freshStatus.onedrive) _refreshClasswork(fresh, freshStatus);
            });
          })
          .catch(function (err) { feedback(el, err.message, 'error'); });
      });
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
      return '<p class="connection-copy">Push-Nachrichten sind auf dem Server noch nicht eingerichtet (VAPID-Schlüssel fehlen).</p>';
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
    render: function () {
      return '<div class="connection-head"><h3>Push-Nachrichten</h3><span class="pill" data-push-pill>…</span></div>' +
        '<div data-push-body><p class="connection-copy">Prüfe dieses Gerät …</p></div>' +
        '<p class="connection-feedback" data-feedback></p>';
    },
    bind: function (el) {
      if (!window.LehrerPush) { el.hidden = true; return; }
      var body = el.querySelector('[data-push-body]');
      var pill = el.querySelector('[data-push-pill]');

      function refresh(message, kind) {
        return window.LehrerPush.status().then(function (st) {
          var active = st.subscribed && st.serverEnabled;
          pill.className = 'pill ' + (active ? 'pill-live' : 'pill-attention');
          pill.textContent = active ? 'aktiv' : 'aus';
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
    _stopNextcloudPolling();
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
