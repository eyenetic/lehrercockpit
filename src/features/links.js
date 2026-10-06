/**
 * LehrerLinks — Bereich „Links“: Nextcloud-Favoriten, eigene Links und Links
 * für das ganze Kollegium (z. B. der Bearbeitungslink zum Klassenarbeitsplan).
 *
 * Eigene Links liegen im Browser (localStorage „lehrerCockpit.links“) und reisen
 * verschlüsselt über den Tresor (vault.js) mit; Links für alle kommen vom Server
 * (GET/POST /api/v2/links, DELETE /api/v2/links/<id>, nur Admins ändern).
 * Verwaltet werden die Links unter „Verbindungen → Links“ (mountManager); der
 * Bereich selbst zeigt sie zum schnellen Öffnen.
 *
 * Exposes window.LehrerLinks = { load, getLinks, render, setDashboard, mountManager }.
 */
(function () {
  'use strict';

  var LOCAL_KEY = 'lehrerCockpit.links';
  var _links = { school: [], personal: loadPersonal(), can_edit_school: false };

  function loadPersonal() {
    try {
      var list = JSON.parse(localStorage.getItem(LOCAL_KEY) || '[]');
      return Array.isArray(list) ? list.filter(function (l) { return l && l.url; }) : [];
    } catch (e) { return []; }
  }

  function savePersonal() {
    try { localStorage.setItem(LOCAL_KEY, JSON.stringify(_links.personal)); } catch (e) { /* ignore */ }
  }
  var _loaded = false;
  var _loading = null;
  var _dashboard = {};
  var _listeners = [];

  var ICONS = {
    folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    school: '<path d="m4 6 8-4 8 4M18 10v10M6 10v10M2 22h20M10 22v-6h4v6"/>',
  };

  function svg(name) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[name] + '</svg>';
  }

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function host(url) {
    try { return new URL(url).host.replace(/^www\./, ''); } catch (e) { return ''; }
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

  function changed() {
    render();
    _listeners.forEach(function (fn) { try { fn(); } catch (e) { /* ignore */ } });
  }

  function load() {
    if (!window.MULTIUSER_ENABLED) return Promise.resolve(_links);
    if (_loading) return _loading;
    _loading = api('/api/v2/links').then(function (data) {
      _links = { school: data.school || [], personal: loadPersonal(), can_edit_school: !!data.can_edit_school };
      _loaded = true;
      changed();
      return _links;
    }).catch(function () { return _links; }).then(function (result) { _loading = null; return result; });
    return _loading;
  }

  function getLinks() { return _links; }

  function setDashboard(data) {
    _dashboard = data || {};
    if (!_loaded && !_loading) load();
    render();
  }

  // ── Bereich „Links“ ────────────────────────────────────────────────────────

  function tile(url, title, sub, icon) {
    return '<a class="link-tile" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer" title="' + esc(title) + '">'
      + '<span class="link-tile-icon">' + svg(icon) + '</span>'
      + '<span class="link-tile-text"><span class="link-tile-title">' + esc(title) + '</span>'
      + (sub ? '<span class="link-tile-sub">' + esc(sub) + '</span>' : '') + '</span></a>';
  }

  function card(title, actionHtml, bodyHtml) {
    return '<article class="card links-card"><header class="card-head"><h2>' + esc(title) + '</h2>'
      + (actionHtml ? '<span class="card-head-action">' + actionHtml + '</span>' : '') + '</header>' + bodyHtml + '</article>';
  }

  function render() {
    var root = document.getElementById('links-root');
    if (!root) return;
    var modules = _dashboard.modules || {};
    var nextcloud = modules.nextcloud || {};
    var feed = _dashboard.nextcloudFeed || {};
    var favorites = feed.favorites || [];

    var favBody;
    if (nextcloud.configured === false || (!feed.connected && !favorites.length && nextcloud.configured !== true)) {
      favBody = '<div class="tile-empty"><p>Verbinde Nextcloud – dann liegen deine Favoriten (★) hier einen Klick entfernt.</p>'
        + '<button class="btn btn-primary btn-sm" type="button" data-open-connections="nextcloud">Nextcloud verbinden</button></div>';
    } else if (feed.error) {
      favBody = '<div class="tile-empty"><p>' + esc(feed.error) + '</p></div>';
    } else if (!favorites.length) {
      favBody = '<div class="tile-empty"><p>Noch keine Favoriten. Markiere in Nextcloud wichtige Dateien und Ordner mit ★ – sie erscheinen dann hier.</p></div>';
    } else {
      favBody = '<div class="link-grid">' + favorites.map(function (fav) {
        return tile(fav.link, fav.name, fav.folder || (fav.is_folder ? 'Ordner' : ''), fav.is_folder ? 'folder' : 'file');
      }).join('') + '</div>';
    }
    var server = feed.server ? '<a class="tile-link" href="' + esc(feed.server) + '" target="_blank" rel="noopener noreferrer">Nextcloud öffnen</a>' : '';

    var manage = '<button class="tile-link" type="button" data-open-connections="links">Bearbeiten</button>';
    var personal = _links.personal.length
      ? '<div class="link-grid">' + _links.personal.map(function (l) { return tile(l.url, l.title, host(l.url), 'link'); }).join('') + '</div>'
      : '<div class="tile-empty"><p>Leg eigene Links an – z. B. zu Formularen, Tabellen oder Seiten, die du oft brauchst.</p>'
        + '<button class="btn btn-secondary btn-sm" type="button" data-open-connections="links">Link hinzufügen</button></div>';

    var schoolLinks = _links.school.map(function (l) { return tile(l.url, l.title, host(l.url), 'school'); })
      .concat((_dashboard.quickLinks || []).map(function (l) { return tile(l.url, l.title, l.note || host(l.url), 'link'); }));

    root.innerHTML = card('Nextcloud-Favoriten', server, favBody)
      + card('Meine Links', manage, personal)
      + card('Für alle', _links.can_edit_school ? manage : '', schoolLinks.length
        ? '<div class="link-grid">' + schoolLinks.join('') + '</div>'
        : '<div class="tile-empty"><p>Noch keine Links für das Kollegium.</p></div>');
  }

  // ── Verwaltung (Verbindungen → Links) ─────────────────────────────────────

  function managerList(items, emptyText) {
    if (!items.length) return '<p class="links-empty">' + esc(emptyText) + '</p>';
    return '<ul class="links-manage-list">' + items.map(function (l) {
      return '<li><span class="links-manage-text"><strong>' + esc(l.title) + '</strong><span>' + esc(host(l.url)) + '</span></span>'
        + '<button class="btn btn-sm btn-ghost" type="button" data-link-remove="' + l.id + '" aria-label="' + esc(l.title) + ' entfernen">Entfernen</button></li>';
    }).join('') + '</ul>';
  }

  function managerForm(scope) {
    // novalidate + text field: "schule.de/x" without https:// is completed below
    // instead of being blocked by the browser's URL check.
    return '<form class="links-add-form" data-link-scope="' + scope + '" autocomplete="off" novalidate>'
      + '<input class="form-input" name="title" placeholder="' + (scope === 'school' ? 'z. B. KA-Plan bearbeiten' : 'Name') + '" maxlength="80" />'
      + '<input class="form-input" name="url" type="text" inputmode="url" autocapitalize="off" spellcheck="false" placeholder="Adresse, z. B. schule.de/formular" />'
      + '<button class="btn btn-primary btn-sm" type="submit">Hinzufügen</button></form>';
  }

  function managerHtml() {
    var html = '<h4 class="links-manage-title">Meine Links</h4>'
      + '<p class="connection-copy">Nur für dich – gespeichert auf deinen Geräten (verschlüsselt abgeglichen), sichtbar unter „Links“ und auf „Heute“.</p>'
      + managerList(_links.personal, 'Noch keine eigenen Links.') + managerForm('personal');
    if (_links.can_edit_school) {
      html += '<h4 class="links-manage-title">Für das ganze Kollegium</h4>'
        + '<p class="connection-copy">Sehen alle angemeldeten Lehrkräfte – z. B. der Bearbeitungslink zum Klassenarbeitsplan, der nicht öffentlich auf der Webseite steht.</p>'
        + managerList(_links.school, 'Noch keine Links für alle.') + managerForm('school');
    } else if (_links.school.length) {
      html += '<h4 class="links-manage-title">Für das ganze Kollegium</h4>'
        + '<p class="connection-copy">Von der Verwaltung eingetragen: ' + _links.school.map(function (l) { return esc(l.title); }).join(', ') + '.</p>';
    }
    return html + '<p class="connection-feedback" data-links-feedback></p>';
  }

  function mountManager(container) {
    if (!container) return;
    var draw = function () { container.innerHTML = managerHtml(); };
    draw();
    load().then(draw);
    if (container.dataset.linksBound) return;
    container.dataset.linksBound = '1';
    var feedback = function (text, kind) {
      var el = container.querySelector('[data-links-feedback]');
      if (el) { el.textContent = text || ''; el.className = 'connection-feedback' + (kind ? ' is-' + kind : ''); }
    };
    container.addEventListener('submit', function (event) {
      var form = event.target.closest('[data-link-scope]');
      if (!form) return;
      event.preventDefault();
      var url = form.querySelector('[name="url"]').value.trim();
      if (!url) { feedback('Bitte eine Adresse eingeben.', 'error'); form.querySelector('[name="url"]').focus(); return; }
      if (!/^https?:\/\//i.test(url)) url = 'https://' + url;
      var button = form.querySelector('button');
      var scope = form.getAttribute('data-link-scope');
      var title = form.querySelector('[name="title"]').value.trim();
      if (scope === 'personal') {
        if (!/^https?:\/\/[^\s/]+\.[^\s]+/i.test(url)) { feedback('Bitte eine vollständige Adresse eingeben.', 'error'); return; }
        if (_links.personal.length >= 40) { feedback('Höchstens 40 eigene Links.', 'error'); return; }
        var link = { id: 'p' + Date.now().toString(36), title: (title || host(url)).slice(0, 80), url: url };
        _links.personal.push(link);
        savePersonal();
        draw();
        changed();
        feedback('„' + link.title + '“ hinzugefügt.', 'success');
        return;
      }
      button.disabled = true;
      api('/api/v2/links', { method: 'POST', body: { title: title, url: url } })
        .then(function (data) {
          _links.school.push(data.link);
          draw();
          changed();
          feedback('„' + data.link.title + '“ hinzugefügt.', 'success');
        })
        .catch(function (err) { button.disabled = false; feedback(err.message, 'error'); });
    });
    container.addEventListener('click', function (event) {
      var remove = event.target.closest('[data-link-remove]');
      if (!remove) return;
      var id = remove.getAttribute('data-link-remove');
      if (_links.personal.some(function (l) { return String(l.id) === id; })) {
        _links.personal = _links.personal.filter(function (l) { return String(l.id) !== id; });
        savePersonal();
        draw();
        changed();
        return;
      }
      remove.disabled = true;
      api('/api/v2/links/' + encodeURIComponent(id), { method: 'DELETE' })
        .then(function () {
          _links.school = _links.school.filter(function (l) { return String(l.id) !== id; });
          draw();
          changed();
        })
        .catch(function (err) { remove.disabled = false; feedback(err.message, 'error'); });
    });
  }

  window.LehrerLinks = {
    load: load,
    getLinks: getLinks,
    render: render,
    setDashboard: setDashboard,
    mountManager: mountManager,
    onChange: function (fn) { _listeners.push(fn); },
    reloadLocal: function () { _links.personal = loadPersonal(); changed(); },
  };
})();
