/**
 * LehrerTasks — eigene Termine und Aufgaben.
 *
 *   Termin    erscheint im Kalender („Alle“ unter Termine)
 *   Aufgabe   mit oder ohne Frist; kommt zusätzlich auf „Heute“ in die Kachel
 *             „Zu erledigen“ und lässt sich dort abhaken
 *
 * Erinnerung: ab so vielen Tagen vor dem Datum steht der Eintrag auf „Heute“.
 * Alles liegt nur im Browser (localStorage) und reist über den Tresor
 * (vault.js) verschlüsselt auf die anderen Geräte – der Server kann es nicht
 * lesen, deshalb kommen eigene Einträge auch nicht ins Kalender-Abo.
 *
 * Exposes window.LehrerTasks = { all, get, save, remove, setDone, openEditor, parseQuick, renderTile }.
 */
(function () {
  'use strict';

  var KEY = 'lehrerCockpit.ownEntries';
  var REMIND = [[0, 'am Tag selbst'], [1, '1 Tag vorher'], [3, '3 Tage vorher'], [7, '1 Woche vorher'], [14, '2 Wochen vorher']];
  var DEFAULT_REMIND = { task: 3, event: 0 };
  var _showDone = false;
  var _showLater = false;

  // ── Helpers ────────────────────────────────────────────────────────────────
  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function iso(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function fromIso(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || ''));
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }
  function addDays(d, n) { var x = new Date(d.getFullYear(), d.getMonth(), d.getDate()); x.setDate(x.getDate() + n); return x; }
  function today() { return iso(new Date()); }
  function newId() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
  function validTime(t) { return /^([01]\d|2[0-3]):[0-5]\d$/.test(String(t || '')) ? t : ''; }

  // ── Speicher ───────────────────────────────────────────────────────────────
  function readMap() {
    try {
      var map = JSON.parse(localStorage.getItem(KEY) || '{}');
      return map && typeof map === 'object' && !Array.isArray(map) ? map : {};
    } catch (e) { return {}; }
  }
  function writeMap(map) {
    try { localStorage.setItem(KEY, JSON.stringify(map)); } catch (e) { /* storage full or blocked */ }
    changed();
  }
  function all() {
    var map = readMap();
    return Object.keys(map).map(function (id) { return clean(Object.assign({}, map[id], { id: id })); })
      .filter(function (e) { return e.title; });
  }
  function get(id) { var map = readMap(); return map[id] ? clean(Object.assign({}, map[id], { id: id })) : null; }

  function clean(e) {
    var kind = e.kind === 'event' ? 'event' : 'task';
    var date = fromIso(e.date) ? e.date : '';
    var time = date ? validTime(e.time) : '';
    var endTime = time ? validTime(e.endTime) : '';
    if (endTime && endTime <= time) endTime = '';
    var remind = parseInt(e.remind, 10);
    return {
      id: String(e.id || newId()), kind: kind, title: String(e.title || '').trim().slice(0, 200),
      date: kind === 'event' && !date ? today() : date, time: time, endTime: endTime,
      note: String(e.note || '').slice(0, 2000),
      remind: isNaN(remind) || remind < 0 || remind > 60 ? DEFAULT_REMIND[kind] : remind,
      done: kind === 'task' && !!e.done, doneAt: kind === 'task' && e.done ? (e.doneAt || today()) : '',
      created: e.created || new Date().toISOString(),
    };
  }

  function save(entry) {
    var e = clean(entry);
    if (!e.title) return null;
    var map = readMap();
    var stored = Object.assign({}, e);
    delete stored.id;
    map[e.id] = stored;
    writeMap(map);
    return e;
  }
  function remove(id) { var map = readMap(); delete map[id]; writeMap(map); }
  function setDone(id, done) {
    var e = get(id);
    if (!e || e.kind !== 'task') return;
    e.done = !!done;
    e.doneAt = done ? today() : '';
    save(e);
  }

  function changed() {
    renderTile();
    window.dispatchEvent(new Event('lehrer:tasks-changed'));  // the blue card on Heute shows tasks of the next class
    if (window.LehrerCalendar && window.LehrerCalendar.render) {
      try { window.LehrerCalendar.render(); } catch (e) { /* calendar not ready */ }
    }
  }

  // ── Schnell-Eingabe: „Kopien Klausur 8b bis Fr 14 Uhr“ ────────────────────
  var DAYS = { so: 0, sonntag: 0, mo: 1, montag: 1, di: 2, dienstag: 2, mi: 3, mittwoch: 3,
               do: 4, donnerstag: 4, fr: 5, freitag: 5, sa: 6, samstag: 6 };

  function parseQuick(text, now) {
    now = now || new Date();
    var rest = ' ' + String(text || '').trim() + ' ';
    var date = '';
    var time = '';
    function cut(re, fn) {
      var m = re.exec(rest);
      if (!m) return false;
      if (fn(m) === false) return false;
      rest = rest.slice(0, m.index) + ' ' + rest.slice(m.index + m[0].length);
      return true;
    }
    var pre = '(?:\\s(?:bis|am|ab|zum|für)(?=\\s))?\\s';
    // full names anywhere; "so", "do", "mi" are ordinary words too – as weekdays only after bis/am/… or at the end
    var full = Object.keys(DAYS).filter(function (k) { return k.length > 2; }).join('|');
    var short = Object.keys(DAYS).filter(function (k) { return k.length === 2; }).join('|');
    function weekday(m) {
      var target = DAYS[m[1].toLowerCase()];
      date = iso(addDays(now, (target - now.getDay() + 7) % 7)); // today counts: "bis Fr" on a Friday is today
    }
    var found = cut(new RegExp(pre + '(\\d{1,2})\\.(\\d{1,2})\\.(\\d{2,4})?(?=[\\s,]|$)', 'i'), function (m) {
      var y = m[3] ? (+m[3] < 100 ? 2000 + +m[3] : +m[3]) : now.getFullYear();
      var d = new Date(y, +m[2] - 1, +m[1]);
      if (d.getMonth() !== +m[2] - 1) return false;
      if (!m[3] && iso(d) < iso(addDays(now, -60))) d = new Date(y + 1, +m[2] - 1, +m[1]); // 05.01. in December → next year
      date = iso(d);
    })
      || cut(new RegExp(pre + '(heute|übermorgen|morgen)(?=[\\s,]|$)', 'i'), function (m) {
        var word = m[1].toLowerCase();
        date = iso(addDays(now, word === 'heute' ? 0 : word === 'morgen' ? 1 : 2));
      })
      || cut(new RegExp(pre + '(' + full + ')(?=[\\s,]|$)', 'i'), weekday)
      || cut(new RegExp('\\s(?:bis|am|ab|zum|für)\\s(' + short + ')\\.?(?=[\\s,]|$)', 'i'), weekday)
      || cut(/\s(Mo|Di|Mi|Do|Fr|Sa|So)\.?\s*$/, weekday); // at the end only capitalised: "mach das so" stays text
    void found;
    cut(/\s(?:um\s)?([01]?\d|2[0-3])(?::([0-5]\d))?\s?Uhr(?=[\s,]|$)|\s(?:um\s)?([01]?\d|2[0-3]):([0-5]\d)(?=[\s,]|$)/i, function (m) {
      var h = m[1] || m[3], min = m[2] || m[4] || '00';
      time = String(h).padStart(2, '0') + ':' + min;
    });
    var title = rest.replace(/\s+/g, ' ').replace(/\s([,.;:–-])\s*$/, '').trim().replace(/[,;:–-]$/, '').trim();
    return { title: title, date: date, time: date ? time : '' };
  }

  // ── Kachel „Zu erledigen“ auf Heute ───────────────────────────────────────
  function dueLabel(e, todayIso) {
    if (!e.date) return '';
    var d = fromIso(e.date);
    var diff = Math.round((d - fromIso(todayIso)) / 86400000);
    var text = diff === 0 ? 'heute' : diff === 1 ? 'morgen' : diff === -1 ? 'gestern'
      : diff < 0 ? 'seit ' + d.toLocaleDateString('de-DE', { day: 'numeric', month: 'numeric' })
      : diff < 7 ? d.toLocaleDateString('de-DE', { weekday: 'long' })
      : d.toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'numeric' });
    return text + (e.time ? ', ' + e.time + (e.endTime ? '–' + e.endTime : '') + ' Uhr' : '');
  }

  /** On "Heute" from (date − reminder) on; tasks until done, events until their day is over. */
  function visibleNow(e, todayIso) {
    if (e.kind === 'task' && !e.date) return true;
    if (e.kind === 'event' && e.date < todayIso) return false;
    return iso(addDays(fromIso(e.date), -e.remind)) <= todayIso;
  }

  function rowHtml(e, todayIso) {
    var overdue = e.kind === 'task' && e.date && e.date < todayIso && !e.done;
    var due = dueLabel(e, todayIso);
    var check = e.kind === 'task'
      ? '<input type="checkbox" class="task-check" data-task-done="' + esc(e.id) + '"' + (e.done ? ' checked' : '') + ' aria-label="' + esc(e.title) + ' erledigt" />'
      : '<span class="task-event-dot" aria-hidden="true"></span>';
    return '<li class="task-row' + (e.done ? ' is-done' : '') + (overdue ? ' is-overdue' : '') + (e.kind === 'event' ? ' is-event' : '') + '">'
      + check
      + '<button type="button" class="task-open" data-task-edit="' + esc(e.id) + '">'
      + '<span class="task-title">' + esc(e.title) + '</span>'
      + (due ? '<span class="task-due">' + (e.kind === 'event' ? 'Termin · ' : overdue ? 'überfällig · ' : 'bis ') + esc(due) + '</span>' : '')
      + '</button></li>';
  }

  function sortOpen(a, b) {
    return (a.date || '9999') .localeCompare(b.date || '9999') || (a.time || '99').localeCompare(b.time || '99')
      || a.created.localeCompare(b.created);
  }

  function renderTile() {
    var body = document.getElementById('today-tasks-body');
    if (!body) return;
    var t = today();
    var list = all();
    var open = list.filter(function (e) { return !e.done; });
    var now = open.filter(function (e) { return visibleNow(e, t); }).sort(sortOpen);
    var later = open.filter(function (e) { return !visibleNow(e, t) && !(e.kind === 'event' && e.date < t); }).sort(sortOpen);
    var doneToday = list.filter(function (e) { return e.done && e.doneAt === t; });
    var doneOlder = list.filter(function (e) { return e.done && e.doneAt !== t; })
      .sort(function (a, b) { return b.doneAt.localeCompare(a.doneAt); });

    var meta = document.getElementById('tile-tasks-meta');
    var overdueCount = now.filter(function (e) { return e.kind === 'task' && e.date && e.date < t; }).length;
    if (meta) meta.textContent = overdueCount ? overdueCount + ' überfällig' : now.length ? now.length + ' offen' : '';

    var html = '<form class="task-quick" data-task-quick autocomplete="off">'
      + '<input class="form-input" name="quick" maxlength="200" placeholder="z. B. „Kopien 8b bis Fr“" aria-label="Neue Aufgabe" />'
      + '<button class="btn btn-secondary btn-sm" type="submit">Hinzufügen</button></form>';

    if (!now.length && !doneToday.length) {
      html += '<p class="task-empty">' + (later.length ? 'Gerade nichts fällig.' : 'Nichts zu erledigen. Aufgaben und eigene Termine trägst du oben oder im Kalender ein.') + '</p>';
    } else {
      html += '<ul class="task-list">' + now.concat(doneToday).map(function (e) { return rowHtml(e, t); }).join('') + '</ul>';
    }
    if (later.length) {
      html += '<button type="button" class="tile-more" data-task-toggle="later">' + (_showLater ? 'Spätere ausblenden' : later.length + ' später – anzeigen') + '</button>';
      if (_showLater) html += '<ul class="task-list is-later">' + later.map(function (e) { return rowHtml(e, t); }).join('') + '</ul>';
    }
    if (doneOlder.length) {
      html += '<button type="button" class="tile-more" data-task-toggle="done">' + (_showDone ? 'Erledigte ausblenden' : doneOlder.length + ' erledigt – anzeigen') + '</button>';
      if (_showDone) {
        html += '<ul class="task-list is-done-list">' + doneOlder.map(function (e) { return rowHtml(e, t); }).join('') + '</ul>'
          + '<button type="button" class="tile-more task-clear" data-task-clear>Erledigte löschen</button>';
      }
    }
    body.innerHTML = html;
  }

  function onTileClick(e) {
    var edit = e.target.closest('[data-task-edit]');
    if (edit) { var entry = get(edit.dataset.taskEdit); if (entry) openEditor(entry); return; }
    var toggle = e.target.closest('[data-task-toggle]');
    if (toggle) {
      if (toggle.dataset.taskToggle === 'later') _showLater = !_showLater; else _showDone = !_showDone;
      renderTile();
      return;
    }
    if (e.target.closest('[data-task-clear]')) {
      var old = all().filter(function (x) { return x.done && x.doneAt !== today(); });
      if (!window.confirm(old.length + ' erledigte Aufgaben endgültig löschen?')) return;
      var map = readMap();
      old.forEach(function (x) { delete map[x.id]; });
      _showDone = false;
      writeMap(map);
      return;
    }
    if (e.target.closest('[data-tile-add]')) openEditor({ kind: 'task' });
  }

  function onTileChange(e) {
    var box = e.target.closest('[data-task-done]');
    if (box) setDone(box.dataset.taskDone, box.checked);
  }

  function onTileSubmit(e) {
    var form = e.target.closest('[data-task-quick]');
    if (!form) return;
    e.preventDefault();
    var input = form.elements.quick;
    var parsed = parseQuick(input.value);
    if (!parsed.title) { input.focus(); return; }
    save({ kind: 'task', title: parsed.title, date: parsed.date, time: parsed.time });
    var again = document.querySelector('#today-tasks-body [data-task-quick] input');
    if (again) again.focus();
  }

  // ── Eintrag anlegen / bearbeiten ───────────────────────────────────────────
  function closeEditor() {
    var open = document.querySelector('.task-editor-overlay');
    if (open) open.remove();
  }

  /** prefill: an existing entry, or {kind, date, time} for a new one */
  function openEditor(prefill) {
    prefill = prefill || {};
    var existing = prefill.id ? get(prefill.id) : null;
    var e = existing || clean(Object.assign({ kind: 'task' }, prefill, { id: newId(), title: prefill.title || 'x' }));
    if (!existing) e.title = prefill.title || '';
    if (!existing && prefill.kind === 'task' && !prefill.date) e.date = '';

    closeEditor();
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay task-editor-overlay';
    overlay.innerHTML = '<form class="modal task-editor" role="dialog" aria-modal="true" aria-labelledby="task-editor-title" novalidate>'
      + '<div class="modal-header"><h3 class="modal-title" id="task-editor-title">' + (existing ? 'Eintrag bearbeiten' : 'Neuer Eintrag') + '</h3>'
      + '<button class="modal-close" type="button" data-task-close aria-label="Schließen">✕</button></div>'
      + '<div class="task-kind" role="radiogroup" aria-label="Art">'
      + ['task', 'event'].map(function (k) {
        return '<label class="task-kind-opt"><input type="radio" name="kind" value="' + k + '"' + (e.kind === k ? ' checked' : '') + ' />'
          + '<span>' + (k === 'task' ? 'Aufgabe' : 'Termin') + '</span></label>';
      }).join('') + '</div>'
      + '<label class="form-label">Titel<input class="form-input" name="title" maxlength="200" required value="' + esc(e.title) + '" placeholder="z. B. Zeugnisnoten eintragen, Elterngespräch" /></label>'
      + '<div class="task-when">'
      + '<label class="form-label"><span data-date-label>' + (e.kind === 'task' ? 'Frist (optional)' : 'Datum') + '</span><input class="form-input" type="date" name="date" value="' + esc(e.date) + '" /></label>'
      + '<label class="form-label">Uhrzeit<input class="form-input" type="time" name="time" value="' + esc(e.time) + '" /></label>'
      + '<label class="form-label" data-end-field' + (e.kind === 'task' ? ' hidden' : '') + '>bis<input class="form-input" type="time" name="endTime" value="' + esc(e.endTime) + '" /></label>'
      + '</div>'
      + '<label class="form-label">Auf „Heute“ zeigen<select class="form-input" name="remind">'
      + REMIND.map(function (r) { return '<option value="' + r[0] + '"' + (e.remind === r[0] ? ' selected' : '') + '>' + r[1] + '</option>'; }).join('')
      + (REMIND.some(function (r) { return r[0] === e.remind; }) ? '' : '<option value="' + e.remind + '" selected>' + e.remind + ' Tage vorher</option>')
      + '</select></label>'
      + '<label class="form-label">Notiz (optional)<textarea class="form-input" name="note" rows="3" maxlength="2000">' + esc(e.note) + '</textarea></label>'
      + '<p class="task-editor-hint">Bleibt nur auf deinen Geräten. Bitte keine Schülernamen – Nummern oder Codes.</p>'
      + '<p class="task-editor-error" role="alert" hidden></p>'
      + '<div class="modal-actions task-editor-actions">'
      + (existing ? '<button class="btn btn-secondary task-delete" type="button" data-task-delete>Löschen</button>' : '')
      + (existing && e.kind === 'task' ? '<button class="btn btn-secondary" type="button" data-task-toggle-done>' + (e.done ? 'Wieder offen' : 'Erledigt') + '</button>' : '')
      + '<button class="btn btn-primary" type="submit">Speichern</button></div>'
      + '</form>';
    document.body.appendChild(overlay);
    var form = overlay.querySelector('form');
    var error = overlay.querySelector('.task-editor-error');

    function kind() { return form.elements.kind.value; }
    function syncKind() {
      overlay.querySelector('[data-date-label]').textContent = kind() === 'task' ? 'Frist (optional)' : 'Datum';
      overlay.querySelector('[data-end-field]').hidden = kind() === 'task';
    }
    form.addEventListener('change', function (ev) {
      if (ev.target.name === 'kind') {
        syncKind();
        if (!existing) form.elements.remind.value = String(DEFAULT_REMIND[kind()]);
      }
    });
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var title = form.elements.title.value.trim();
      var date = form.elements.date.value;
      if (!title) { error.textContent = 'Bitte gib einen Titel ein.'; error.hidden = false; form.elements.title.focus(); return; }
      if (kind() === 'event' && !date) { error.textContent = 'Ein Termin braucht ein Datum.'; error.hidden = false; form.elements.date.focus(); return; }
      if (form.elements.time.value && !date) { error.textContent = 'Zur Uhrzeit fehlt noch das Datum.'; error.hidden = false; form.elements.date.focus(); return; }
      save({
        id: e.id, kind: kind(), title: title, date: date, time: form.elements.time.value,
        endTime: kind() === 'event' ? form.elements.endTime.value : '',
        note: form.elements.note.value, remind: form.elements.remind.value,
        done: kind() === 'task' && e.done, doneAt: e.doneAt, created: e.created,
      });
      closeEditor();
    });
    overlay.addEventListener('click', function (ev) {
      if (ev.target === overlay || ev.target.closest('[data-task-close]')) { closeEditor(); return; }
      if (ev.target.closest('[data-task-delete]')) {
        if (!window.confirm('„' + e.title + '“ löschen?')) return;
        remove(e.id);
        closeEditor();
        return;
      }
      if (ev.target.closest('[data-task-toggle-done]')) { setDone(e.id, !e.done); closeEditor(); }
    });
    var first = form.elements.title;
    if (first) first.focus();
  }

  // ── Start ──────────────────────────────────────────────────────────────────
  function init() {
    var body = document.getElementById('today-tasks-body');
    if (body && !body.dataset.bound) {
      body.dataset.bound = '1';
      body.addEventListener('click', onTileClick);
      body.addEventListener('change', onTileChange);
      body.addEventListener('submit', onTileSubmit);
    }
    var add = document.querySelector('[data-task-new]');
    if (add && !add.dataset.bound) {
      add.dataset.bound = '1';
      add.addEventListener('click', function () { openEditor({ kind: 'task' }); });
    }
    renderTile();
  }

  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && document.querySelector('.task-editor-overlay')) closeEditor();
  });
  window.addEventListener('lehrer:vault-updated', changed);                         // edits from another device
  window.addEventListener('storage', function (ev) { if (ev.key === KEY) changed(); }); // another tab
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') renderTile(); }); // new day
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  window.LehrerTasks = {
    all: all, get: get, save: save, remove: remove, setDone: setDone,
    openEditor: openEditor, parseQuick: parseQuick, renderTile: renderTile,
  };
})();
