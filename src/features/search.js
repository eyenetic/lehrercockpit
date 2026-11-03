/**
 * LehrerSearch — eine Suche für alles (⌘K / Strg+K oder die Lupe oben).
 *
 * Durchsucht, was das Cockpit ohnehin geladen hat – nichts geht dafür an den
 * Server: Termine (Orgaplan, Klassenarbeiten, Schultermine, itslearning),
 * Dienstmail, itslearning-Nachrichten, Stundenplan, Klassen und Schülernamen
 * (nur auf diesem Gerät), Einsammlungen und Links. Treffer nach Quelle
 * gruppiert; ein Klick springt an die Stelle.
 *
 * Exports (window.LehrerSearch): init, open
 */
var LehrerSearch = (function () {
  'use strict';

  var _h = null;          // helpers from app.js
  var _overlay = null;
  var _results = [];
  var _active = 0;

  var GROUPS = [
    ['termine', 'Termine'], ['mail', 'Posteingang'], ['schedule', 'Stundenplan'],
    ['classes', 'Klassen'], ['collections', 'Einsammlungen'], ['links', 'Links'],
  ];

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // "Müller" finds "muller", "Mueller" stays as typed; case and accents ignored.
  function fold(text) {
    return String(text || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/ß/g, 'ss');
  }

  function dateLabel(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
    if (!m) return '';
    var d = new Date(+m[1], +m[2] - 1, +m[3]);
    return d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' }).replace(',', '');
  }

  // ── Index: everything searchable, built on each open (data is already in memory) ──
  function buildIndex() {
    var data = _h.getData() || {};
    var items = [];
    var todayIso = new Date().toLocaleDateString('en-CA');
    function add(group, title, sub, when, action, extra) {
      if (!title) return;
      items.push({ group: group, title: String(title), sub: sub || '', when: when || '', action: action,
                   hay: fold([title, sub, extra || ''].join(' ')), titleHay: fold(title) });
    }

    var orgaplan = (data.planDigest || {}).orgaplan || {};
    (orgaplan.upcoming || []).concat(orgaplan.today_entries || []).forEach(function (entry) {
      (_h.orgaplanParts(entry) || []).forEach(function (part) {
        if (part && part.text) add('termine', part.text, 'Orgaplan · ' + (part.tag || ''), entry.isoDate, { section: 'documents', tab: 'orgaplan' });
      });
    });
    (((data.planDigest || {}).classwork || {}).entries || []).forEach(function (entry) {
      if (!entry.isoDate || entry.isoDate < todayIso) return;
      add('termine', 'Klassenarbeit ' + (entry.classLabel || '') + (entry.summary || entry.title ? ' · ' + (entry.summary || entry.title) : ''),
          'Klassenarbeitsplan', entry.isoDate, { section: 'documents', tab: 'klassenarbeitsplan' });
    });
    ((data.schoolCalendar || {}).events || []).forEach(function (event) {
      add('termine', event.title, 'Schultermine' + (event.location ? ' · ' + event.location : ''), event.start,
          { section: 'documents', tab: 'termine' }, event.description);
    });
    ((data.itslearningCalendar || {}).events || []).forEach(function (event) {
      add('termine', event.title, 'itslearning' + (event.kind === 'todo' ? ' · Abgabe' : ''), event.start,
          { section: 'documents', tab: 'itslearning' }, event.detail);
    });

    // Ferien of this and the next school year
    if (window.LehrerSchoolYear) {
      var SY = window.LehrerSchoolYear;
      var now = new Date();
      [SY.schoolYear(now), SY.schoolYear(SY.addDays(now, 365))].forEach(function (year) {
        year.breaks.forEach(function (b) {
          if (b.end < todayIso) return;
          add('termine', b.name, 'Ferien ' + year.label + ' · bis ' + dateLabel(b.end), b.start, { schoolyear: true }, 'ferien schulfrei');
        });
      });
    }

    var mail = data.dienstmail;
    ((mail && !mail.error && mail.messages) || []).forEach(function (m) {
      add('mail', m.subject, 'Dienstmail · ' + (m.from || ''), m.date, { section: 'inbox', mail: m.id }, m.from_address);
    });
    (_h.inboxMessages(data) || []).filter(function (m) { return m.channel === 'itslearning'; }).forEach(function (m) {
      add('mail', m.title, 'itslearning · ' + (m.sender || ''), '', m.url ? { url: m.url } : { section: 'inbox' }, m.snippet);
    });

    // Stundenplan: one hit per lesson group (class + subject), with its next date
    var seen = {};
    ((data.webuntisCenter || {}).events || []).filter(function (e) {
      return e.startsAt && !e.cancelled && e.startsAt.slice(0, 10) >= todayIso;
    }).sort(function (a, b) { return a.startsAt.localeCompare(b.startsAt); }).forEach(function (e) {
      var p = _h.lessonParts(e);
      var key = p.main + '|' + p.sub;
      if (seen[key]) return;
      seen[key] = true;
      add('schedule', p.main + (p.sub ? ' · ' + p.sub : ''), 'nächste Stunde ' + new Date(e.startsAt).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
          + (p.room ? ' · Raum ' + p.room : ''), e.startsAt, { section: 'overview' }, e.location);
    });

    var lists = window.LehrerClasslist ? window.LehrerClasslist.getClassLists() : {};
    Object.keys(lists).forEach(function (classId) {
      var students = lists[classId].students || [];
      add('classes', 'Klasse ' + classId, students.length + ' Schüler:innen', '', { classTab: 'list', classId: classId });
      students.forEach(function (st) {
        add('classes', [st.firstName, st.lastName].filter(Boolean).join(' '), 'Klasse ' + classId, '', { classTab: 'list', classId: classId });
      });
    });
    (window.LehrerCollections && window.LehrerCollections.summary ? window.LehrerCollections.summary() : []).forEach(function (c) {
      add('collections', c.title, 'Klasse ' + c.classIds.join(', ') + ' · ' + c.done + ' von ' + c.total, c.dueDate, { classTab: 'collections', collection: c.id });
    });
    var links = window.LehrerLinks ? window.LehrerLinks.getLinks() : {};
    (links.school || []).concat(links.personal || []).forEach(function (l) {
      add('links', l.title, String(l.url || '').replace(/^https?:\/\//, '').slice(0, 60), '', { url: l.url });
    });
    return items;
  }

  function search(query) {
    var words = fold(query).split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    var todayIso = new Date().toLocaleDateString('en-CA');
    return buildIndex().filter(function (item) {
      return words.every(function (w) { return item.hay.indexOf(w) !== -1; });
    }).map(function (item) {
      // title hits first, then upcoming dates before past ones
      var score = (words.every(function (w) { return item.titleHay.indexOf(w) !== -1; }) ? 0 : 10)
        + (item.when && String(item.when).slice(0, 10) < todayIso ? 5 : 0);
      return { item: item, score: score };
    }).sort(function (a, b) {
      return a.score - b.score || String(a.item.when || '9').localeCompare(String(b.item.when || '9'));
    }).map(function (r) { return r.item; });
  }

  function mark(text, query) {
    var html = esc(text);
    fold(query).split(/\s+/).filter(Boolean).forEach(function (w) {
      // highlight on the folded text, mapped back by position (folding keeps the length for German text)
      var folded = fold(text);
      var at = folded.indexOf(w);
      if (at === -1 || folded.length !== text.length) return;
      var part = text.slice(at, at + w.length);
      html = html.replace(esc(part), '<mark>' + esc(part) + '</mark>');
    });
    return html;
  }

  // ── UI ──────────────────────────────────────────────────────────────────────
  function render(query) {
    var box = _overlay.querySelector('[data-search-results]');
    if (!query.trim()) {
      _results = [];
      box.innerHTML = '<p class="search-hint">Suche in Terminen, Dienstmail, Stundenplan, Klassen, Einsammlungen und Links.</p>';
      return;
    }
    var hits = search(query);
    _results = [];
    if (!hits.length) {
      box.innerHTML = '<p class="search-hint">Nichts gefunden zu „' + esc(query) + '“.</p>';
      return;
    }
    var html = '';
    GROUPS.forEach(function (g) {
      var list = hits.filter(function (h) { return h.group === g[0]; }).slice(0, g[0] === 'classes' ? 8 : 6);
      if (!list.length) return;
      html += '<div class="search-group"><p class="search-group-title">' + esc(g[1]) + '</p>';
      list.forEach(function (h) {
        var i = _results.length;
        _results.push(h);
        html += '<button type="button" class="search-hit" data-hit="' + i + '" role="option">'
          + '<span class="search-hit-title">' + mark(h.title, query) + '</span>'
          + '<span class="search-hit-sub">' + (h.when ? esc(dateLabel(h.when)) + ' · ' : '') + esc(h.sub) + '</span></button>';
      });
      html += '</div>';
    });
    box.innerHTML = html;
    _active = 0;
    highlight();
  }

  function highlight() {
    _overlay.querySelectorAll('.search-hit').forEach(function (el, i) {
      el.classList.toggle('is-active', i === _active);
      if (i === _active) el.scrollIntoView({ block: 'nearest' });
    });
  }

  function go(hit) {
    if (!hit) return;
    close();
    var a = hit.action || {};
    if (a.url) { window.open(a.url, '_blank', 'noopener'); return; }
    _h.go(a);
  }

  function open() {
    if (!_overlay) build();
    _overlay.hidden = false;
    var input = _overlay.querySelector('input');
    input.value = '';
    render('');
    setTimeout(function () { input.focus(); }, 0);
  }

  function close() { if (_overlay) _overlay.hidden = true; }

  function build() {
    _overlay = document.createElement('div');
    _overlay.className = 'modal-overlay search-overlay';
    _overlay.hidden = true;
    _overlay.innerHTML = '<div class="search-panel" role="dialog" aria-label="Suche">'
      + '<div class="search-field"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>'
      + '<input type="search" placeholder="Suchen … (z. B. Klassenrat, 9a, Müller)" autocomplete="off" spellcheck="false" aria-label="Suchbegriff" />'
      + '<kbd class="search-esc">Esc</kbd></div>'
      + '<div class="search-results" data-search-results role="listbox"></div></div>';
    document.body.appendChild(_overlay);
    var input = _overlay.querySelector('input');
    input.addEventListener('input', function () { render(input.value); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); _active = Math.min(_active + 1, _results.length - 1); highlight(); }
      if (e.key === 'ArrowUp') { e.preventDefault(); _active = Math.max(_active - 1, 0); highlight(); }
      if (e.key === 'Enter') { e.preventDefault(); go(_results[_active]); }
      if (e.key === 'Escape') close();
    });
    _overlay.addEventListener('click', function (e) {
      if (e.target === _overlay) { close(); return; }
      var hit = e.target.closest('[data-hit]');
      if (hit) go(_results[+hit.getAttribute('data-hit')]);
    });
  }

  function init(helpers) {
    _h = helpers;
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); open(); }
      if (e.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || '') && !document.activeElement.isContentEditable) {
        e.preventDefault(); open();
      }
    });
    document.querySelectorAll('[data-open-search]').forEach(function (b) { b.addEventListener('click', open); });
  }

  return { init: init, open: open };
})();

if (typeof window !== 'undefined') window.LehrerSearch = LehrerSearch;
