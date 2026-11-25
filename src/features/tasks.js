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
 * Listen (Schule, Privat, … – frei benennbar) liegen unter lehrerCockpit.taskLists und
 * reisen ebenfalls über den Tresor. Welche Liste die Kachel zeigt, merkt sich jedes Gerät.
 * Löschen: Wischen nach links (Touch) oder Papierkorb (Maus), danach kurz „Rückgängig“.
 *
 * Exposes window.LehrerTasks = { all, get, save, remove, setDone, openEditor, parseQuick, renderTile, lists }.
 */
(function () {
  'use strict';

  var KEY = 'lehrerCockpit.ownEntries';
  var REMIND = [[0, 'am Tag selbst'], [1, '1 Tag vorher'], [3, '3 Tage vorher'], [7, '1 Woche vorher'], [14, '2 Wochen vorher']];
  var DEFAULT_REMIND = { task: 3, event: 0 };
  var LISTS_KEY = 'lehrerCockpit.taskLists';
  var FILTER_KEY = 'lc.taskList';
  var DEFAULT_LISTS = [{ id: 'schule', name: 'Schule' }, { id: 'privat', name: 'Privat' }];
  var _showDone = false;
  var _showLater = false;
  var _undo = null;            // {entry, timer} – the last deleted entry, for „Rückgängig“

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
      list: String(e.list || '').slice(0, 40),
      // Anhänge: nur Verweise mit Schlüssel – die verschlüsselten Bytes liegen auf dem Server (files.js)
      files: window.LehrerFiles ? window.LehrerFiles.clean(e.files) : (Array.isArray(e.files) ? e.files : []),
    };
  }

  // ── Listen ─────────────────────────────────────────────────────────────────
  function lists() {
    var map = null;
    try { map = JSON.parse(localStorage.getItem(LISTS_KEY) || 'null'); } catch (e) { map = null; }
    if (!map || typeof map !== 'object' || Array.isArray(map) || !Object.keys(map).length) return DEFAULT_LISTS.slice();
    return Object.keys(map).map(function (id) {
      var item = map[id] || {};
      return { id: id, name: String(item.name || '').trim().slice(0, 30) || 'Liste', order: +item.order || 0 };
    }).sort(function (a, b) { return a.order - b.order; }).map(function (l) { return { id: l.id, name: l.name }; });
  }
  function writeLists(arr) {
    var map = {};
    arr.forEach(function (l, i) { map[l.id] = { name: l.name, order: i }; });
    try { localStorage.setItem(LISTS_KEY, JSON.stringify(map)); } catch (e) { /* storage blocked */ }
  }
  /** The list an entry belongs to; entries from before lists (or a deleted list) go to the first one. */
  function listOf(e, ls) {
    return ls.some(function (l) { return l.id === e.list; }) ? e.list : ls[0].id;
  }
  function activeList(ls) {
    var v = null;
    try { v = localStorage.getItem(FILTER_KEY); } catch (e) { v = null; }
    return v && ls.some(function (l) { return l.id === v; }) ? v : 'all';
  }
  function setActiveList(id) {
    try { localStorage.setItem(FILTER_KEY, id); } catch (e) { /* storage blocked */ }
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
  function filesOf(entry) { return ((entry && entry.files) || []).map(function (f) { return f.id; }); }
  function dropFiles(ids) { if (ids.length && window.LehrerFiles) window.LehrerFiles.remove(ids); }

  /** keepFiles: the attachments stay on the server for now (deleted with „Rückgängig“ still possible). */
  function remove(id, keepFiles) {
    var map = readMap();
    var entry = map[id];
    delete map[id];
    writeMap(map);
    if (!keepFiles) dropFiles(filesOf(entry));
  }
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

  var TRASH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/></svg>';

  function rowHtml(e, todayIso, listName) {
    var overdue = e.kind === 'task' && e.date && e.date < todayIso && !e.done;
    var due = dueLabel(e, todayIso);
    var check = e.kind === 'task'
      ? '<input type="checkbox" class="task-check" data-task-done="' + esc(e.id) + '"' + (e.done ? ' checked' : '') + ' aria-label="' + esc(e.title) + ' erledigt" />'
      : '<span class="task-event-dot" aria-hidden="true"></span>';
    var dueText = due ? (e.kind === 'event' ? 'Termin · ' : overdue ? 'überfällig · ' : 'bis ') + due : '';
    return '<li class="task-row' + (e.done ? ' is-done' : '') + (overdue ? ' is-overdue' : '') + (e.kind === 'event' ? ' is-event' : '') + '" data-task-id="' + esc(e.id) + '">'
      + '<span class="task-swipe-bg" aria-hidden="true">Löschen</span>'
      + '<div class="task-row-inner">'
      + check
      + '<button type="button" class="task-open" data-task-edit="' + esc(e.id) + '">'
      + '<span class="task-title">' + esc(e.title) + '</span>'
      + (dueText || listName || e.files.length ? '<span class="task-due">' + (listName ? '<span class="task-list-tag">' + esc(listName) + '</span>' : '')
        + esc(dueText) + (e.files.length ? '<span class="task-clip" title="' + e.files.length + (e.files.length === 1 ? ' Anhang' : ' Anhänge') + '">'
        + (dueText ? ' · ' : '') + '📎 ' + e.files.length + '</span>' : '') + '</span>' : '')
      + '</button>'
      + '<button type="button" class="task-del" data-task-del="' + esc(e.id) + '" aria-label="' + esc(e.title) + ' löschen" title="Löschen">' + TRASH + '</button>'
      + '</div></li>';
  }

  function sortOpen(a, b) {
    return (a.date || '9999') .localeCompare(b.date || '9999') || (a.time || '99').localeCompare(b.time || '99')
      || a.created.localeCompare(b.created);
  }

  function renderTile() {
    var body = document.getElementById('today-tasks-body');
    if (!body) return;
    var t = today();
    var ls = lists();
    var active = activeList(ls);
    var everything = all();
    var list = everything.filter(function (e) { return active === 'all' || listOf(e, ls) === active; });
    var names = {};
    ls.forEach(function (l) { names[l.id] = l.name; });
    // in „Alle“ every row says which list it is on
    var row = function (e) { return rowHtml(e, t, active === 'all' && ls.length > 1 ? names[listOf(e, ls)] : ''); };
    var open = list.filter(function (e) { return !e.done; });
    var now = open.filter(function (e) { return visibleNow(e, t); }).sort(sortOpen);
    var later = open.filter(function (e) { return !visibleNow(e, t) && !(e.kind === 'event' && e.date < t); }).sort(sortOpen);
    var doneToday = list.filter(function (e) { return e.done && e.doneAt === t; });
    var doneOlder = list.filter(function (e) { return e.done && e.doneAt !== t; })
      .sort(function (a, b) { return b.doneAt.localeCompare(a.doneAt); });

    var meta = document.getElementById('tile-tasks-meta');
    var overdueCount = now.filter(function (e) { return e.kind === 'task' && e.date && e.date < t; }).length;
    if (meta) meta.textContent = overdueCount ? overdueCount + ' überfällig' : now.length ? now.length + ' offen' : '';

    var openCount = function (id) {
      return everything.filter(function (e) { return !e.done && visibleNow(e, t) && (id === 'all' || listOf(e, ls) === id); }).length;
    };
    var html = '<div class="task-lists" role="tablist" aria-label="Listen">'
      + [{ id: 'all', name: 'Alle' }].concat(ls).map(function (l) {
        var n = openCount(l.id);
        return '<button type="button" role="tab" class="task-chip' + (l.id === active ? ' is-active' : '') + '" aria-selected="' + (l.id === active) + '" data-task-list="' + esc(l.id) + '">'
          + esc(l.name) + (n ? ' <span class="task-chip-count">' + n + '</span>' : '') + '</button>';
      }).join('')
      + '<button type="button" class="task-chip task-chip-edit" data-task-lists-edit>Listen …</button></div>'
      + '<form class="task-quick" data-task-quick autocomplete="off">'
      + '<input class="form-input" name="quick" maxlength="200" placeholder="' + (active === 'all' ? 'z. B. „Kopien 8b bis Fr“' : 'Neu in „' + esc(names[active]) + '“') + '" aria-label="Neue Aufgabe" />'
      + '<button class="btn btn-secondary btn-sm" type="submit">Hinzufügen</button></form>';
    if (_undo) {
      html += '<div class="task-undo" role="status"><span>„' + esc(_undo.entry.title) + '“ gelöscht</span>'
        + '<button type="button" data-task-undo>Rückgängig</button></div>';
    }

    if (!now.length && !doneToday.length) {
      html += '<p class="task-empty">' + (later.length ? 'Gerade nichts fällig.'
        : active !== 'all' ? 'In „' + esc(names[active]) + '“ ist nichts zu erledigen.'
        : 'Nichts zu erledigen. Aufgaben und eigene Termine trägst du oben oder im Kalender ein.') + '</p>';
    } else {
      html += '<ul class="task-list">' + now.concat(doneToday).map(row).join('') + '</ul>';
    }
    if (later.length) {
      html += '<button type="button" class="tile-more" data-task-toggle="later">' + (_showLater ? 'Spätere ausblenden' : later.length + ' später – anzeigen') + '</button>';
      if (_showLater) html += '<ul class="task-list is-later">' + later.map(row).join('') + '</ul>';
    }
    if (doneOlder.length) {
      html += '<button type="button" class="tile-more" data-task-toggle="done">' + (_showDone ? 'Erledigte ausblenden' : doneOlder.length + ' erledigt – anzeigen') + '</button>';
      if (_showDone) {
        html += '<ul class="task-list is-done-list">' + doneOlder.map(row).join('') + '</ul>'
          + '<button type="button" class="tile-more task-clear" data-task-clear>Erledigte löschen</button>';
      }
    }
    // The tile is rebuilt whenever new data arrives (e.g. a few seconds after opening the app):
    // keep what is being typed in the quick field, with focus and cursor – otherwise the first
    // „Hinzufügen“ finds an empty field and nothing is saved.
    var old = body.querySelector('[data-task-quick] input');
    var typing = old && (old.value || document.activeElement === old)
      ? { value: old.value, focused: document.activeElement === old, start: old.selectionStart, end: old.selectionEnd } : null;
    body.innerHTML = html;
    if (typing) {
      var input = body.querySelector('[data-task-quick] input');
      input.value = typing.value;
      if (typing.focused) {
        input.focus();
        try { input.setSelectionRange(typing.start, typing.end); } catch (e) { /* not supported */ }
      }
    }
  }

  // The attachments of a deleted entry go only when „Rückgängig“ is no longer possible.
  function finishUndo() {
    if (!_undo) return;
    clearTimeout(_undo.timer);
    var gone = _undo.entry;
    _undo = null;
    if (!get(gone.id)) dropFiles(filesOf(gone));
  }

  function deleteWithUndo(id) {
    var entry = get(id);
    if (!entry) return;
    finishUndo();
    _undo = { entry: entry, timer: setTimeout(function () { finishUndo(); renderTile(); }, 7000) };
    remove(id, true);
  }

  function onTileClick(e) {
    if (_suppressClick) { e.preventDefault(); return; }
    var del = e.target.closest('[data-task-del]');
    if (del) { deleteWithUndo(del.dataset.taskDel); return; }
    if (e.target.closest('[data-task-undo]')) {
      if (_undo) { clearTimeout(_undo.timer); var back = _undo.entry; _undo = null; save(back); }
      return;
    }
    var chip = e.target.closest('[data-task-list]');
    if (chip) { setActiveList(chip.dataset.taskList); renderTile(); return; }
    if (e.target.closest('[data-task-lists-edit]')) { openListManager(); return; }
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
      old.forEach(function (x) { dropFiles(filesOf(x)); });
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
    var ls = lists();
    var active = activeList(ls);
    input.value = '';  // before saving: the rebuilt tile keeps whatever is still in the field
    save({ kind: 'task', title: parsed.title, date: parsed.date, time: parsed.time, list: active === 'all' ? ls[0].id : active });
    var again = document.querySelector('#today-tasks-body [data-task-quick] input');
    if (again) again.focus();
  }

  // ── Wischen zum Löschen (Finger, Stift) ───────────────────────────────────
  var _swipe = null;
  var _suppressClick = false;

  function onSwipeStart(ev) {
    if (ev.pointerType === 'mouse' || ev.button > 0) return;
    var inner = ev.target.closest('.task-row-inner');
    if (!inner || ev.target.closest('.task-check')) return;
    _swipe = { inner: inner, row: inner.parentNode, x: ev.clientX, y: ev.clientY, dx: 0, active: false, pid: ev.pointerId };
  }
  function onSwipeMove(ev) {
    var s = _swipe;
    if (!s || ev.pointerId !== s.pid) return;
    var dx = ev.clientX - s.x, dy = ev.clientY - s.y;
    if (!s.active) {
      if (dx < -10 && Math.abs(dx) > Math.abs(dy) * 1.4) {
        s.active = true;
        s.row.classList.add('is-swiping');
        try { s.inner.setPointerCapture(ev.pointerId); } catch (e) { /* already released */ }
      } else if (Math.abs(dy) > 10 || dx > 10) { _swipe = null; return; } else return;
    }
    s.dx = Math.min(0, dx);
    s.inner.style.transform = 'translateX(' + s.dx + 'px)';
  }
  function onSwipeEnd(ev) {
    var s = _swipe;
    if (!s || ev.pointerId !== s.pid) return;
    _swipe = null;
    if (!s.active) return;
    _suppressClick = true;
    setTimeout(function () { _suppressClick = false; }, 400);
    s.inner.style.transition = 'transform 0.18s ease-out';
    if (ev.type === 'pointerup' && -s.dx > Math.min(110, s.row.offsetWidth * 0.33)) {
      s.inner.style.transform = 'translateX(-100%)';
      var id = s.row.dataset.taskId;
      setTimeout(function () { deleteWithUndo(id); }, 170);
    } else {
      s.inner.style.transform = '';
      setTimeout(function () { s.row.classList.remove('is-swiping'); s.inner.style.transition = ''; }, 200);
    }
  }

  // ── Listen verwalten ───────────────────────────────────────────────────────
  function openListManager() {
    closeEditor();
    var ls = lists();
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay task-editor-overlay';
    var rowFor = function (l) {
      return '<li class="task-lm-row" data-lm-id="' + esc(l.id) + '"><input class="form-input" maxlength="30" value="' + esc(l.name) + '" aria-label="Name der Liste" />'
        + '<button type="button" class="task-del is-visible" data-lm-del aria-label="Liste löschen" title="Liste löschen">' + TRASH + '</button></li>';
    };
    overlay.innerHTML = '<form class="modal task-editor" role="dialog" aria-modal="true" aria-labelledby="task-lm-title" novalidate>'
      + '<div class="modal-header"><h3 class="modal-title" id="task-lm-title">Listen</h3>'
      + '<button class="modal-close" type="button" data-task-close aria-label="Schließen">✕</button></div>'
      + '<ul class="task-lm">' + ls.map(rowFor).join('') + '</ul>'
      + '<button type="button" class="btn btn-secondary btn-sm task-lm-add" data-lm-add>+ Neue Liste</button>'
      + '<p class="task-editor-hint">Einträge einer gelöschten Liste kommen in die erste Liste.</p>'
      + '<p class="task-editor-error" role="alert" hidden></p>'
      + '<div class="modal-actions"><button class="btn btn-primary" type="submit">Speichern</button></div>'
      + '</form>';
    document.body.appendChild(overlay);
    var form = overlay.querySelector('form');
    var ul = form.querySelector('.task-lm');
    var error = form.querySelector('.task-editor-error');
    draggable(form, form.querySelector('.modal-header'));
    var downOnOverlay = false;
    overlay.addEventListener('pointerdown', function (ev) { downOnOverlay = ev.target === overlay; });
    overlay.addEventListener('click', function (ev) {
      if ((ev.target === overlay && downOnOverlay) || ev.target.closest('[data-task-close]')) { closeEditor(); return; }
      if (ev.target.closest('[data-lm-add]')) {
        ul.insertAdjacentHTML('beforeend', rowFor({ id: newId(), name: '' }));
        ul.lastElementChild.querySelector('input').focus();
        return;
      }
      var del = ev.target.closest('[data-lm-del]');
      if (del) {
        if (ul.children.length <= 1) { error.textContent = 'Eine Liste muss bleiben.'; error.hidden = false; return; }
        del.closest('li').remove();
      }
    });
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var next = [].map.call(ul.children, function (li) {
        return { id: li.dataset.lmId, name: li.querySelector('input').value.trim().slice(0, 30) };
      }).filter(function (l) { return l.name; });
      if (!next.length) { error.textContent = 'Gib der Liste einen Namen.'; error.hidden = false; return; }
      // entries of deleted lists move to the first list
      var keep = {};
      next.forEach(function (l) { keep[l.id] = true; });
      var map = readMap();
      Object.keys(map).forEach(function (id) {
        var current = listOf(map[id], ls);
        map[id].list = keep[current] ? current : next[0].id;
      });
      writeLists(next);
      try { localStorage.setItem(KEY, JSON.stringify(map)); } catch (e) { /* storage blocked */ }
      closeEditor();
      changed();
    });
    var first = ul.querySelector('input');
    if (first) first.focus();
  }

  // ── Eintrag anlegen / bearbeiten ───────────────────────────────────────────
  function closeEditor() {
    var open = document.querySelector('.task-editor-overlay');
    if (!open) return;
    if (open._discard) open._discard();   // closed without saving: drop attachments uploaded meanwhile
    open.remove();
  }

  function timeInput(name, value) {
    return '<input class="form-input" type="text" name="' + name + '" data-time inputmode="numeric" autocomplete="off" maxlength="9"'
      + ' placeholder="hh:mm" value="' + esc(value) + '" />';
  }

  /** "14", "930", "1430", "14.30", "14:30", "14 Uhr" → "14:30"; "" → ""; anything else → null */
  function normTime(value) {
    var text = String(value || '').trim().toLowerCase().replace(/\s*uhr$/, '').replace(/\s+/g, '');
    if (!text) return '';
    var m = /^(\d{1,2})(?:[:.,h]?(\d{2}))?$/.exec(text);
    if (!m || +m[1] > 23 || +(m[2] || 0) > 59) return null;
    return String(+m[1]).padStart(2, '0') + ':' + (m[2] || '00');
  }

  /** Move a dialog by its header (mouse, pen, finger), e.g. to look at the calendar behind it. */
  function draggable(box, handle) {
    if (!box || !handle) return;
    var x = 0, y = 0, start = null;
    handle.classList.add('is-draggable');
    handle.addEventListener('pointerdown', function (ev) {
      if (ev.button !== 0 || ev.target.closest('button, a, input, select, textarea')) return;
      start = { px: ev.clientX, py: ev.clientY, x: x, y: y, rect: box.getBoundingClientRect() };
      handle.setPointerCapture(ev.pointerId);
      ev.preventDefault();
    });
    handle.addEventListener('pointermove', function (ev) {
      if (!start) return;
      var dx = ev.clientX - start.px, dy = ev.clientY - start.py;
      // keep at least the header on the screen
      dx = Math.max(-start.rect.left - start.rect.width + 80, Math.min(window.innerWidth - start.rect.left - 80, dx));
      dy = Math.max(-start.rect.top, Math.min(window.innerHeight - start.rect.top - 48, dy));
      x = start.x + dx; y = start.y + dy;
      box.style.transform = 'translate(' + x + 'px, ' + y + 'px)';
    });
    function stop() { start = null; }
    handle.addEventListener('pointerup', stop);
    handle.addEventListener('pointercancel', stop);
  }

  /** prefill: an existing entry, or {kind, date, time} for a new one */
  function openEditor(prefill) {
    prefill = prefill || {};
    var existing = prefill.id ? get(prefill.id) : null;
    var e = existing || clean(Object.assign({ kind: 'task' }, prefill, { id: newId(), title: prefill.title || 'x' }));
    if (!existing) e.title = prefill.title || '';
    if (!existing && prefill.kind === 'task' && !prefill.date) e.date = '';

    var ls = lists();
    var active = activeList(ls);
    var listId = existing ? listOf(e, ls)
      : ls.some(function (l) { return l.id === prefill.list; }) ? prefill.list : active !== 'all' ? active : ls[0].id;

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
      + '<label class="form-label">Uhrzeit' + timeInput('time', e.time) + '</label>'
      + '<label class="form-label" data-end-field' + (e.kind === 'task' ? ' hidden' : '') + '>bis' + timeInput('endTime', e.endTime) + '</label>'
      + '</div>'
      + '<div class="task-when task-when-2">'
      + '<label class="form-label">Liste<select class="form-input" name="list">'
      + ls.map(function (l) { return '<option value="' + esc(l.id) + '"' + (l.id === listId ? ' selected' : '') + '>' + esc(l.name) + '</option>'; }).join('')
      + '</select></label>'
      + '<label class="form-label">Auf „Heute“ zeigen<select class="form-input" name="remind">'
      + REMIND.map(function (r) { return '<option value="' + r[0] + '"' + (e.remind === r[0] ? ' selected' : '') + '>' + r[1] + '</option>'; }).join('')
      + (REMIND.some(function (r) { return r[0] === e.remind; }) ? '' : '<option value="' + e.remind + '" selected>' + e.remind + ' Tage vorher</option>')
      + '</select></label></div>'
      + '<label class="form-label">Notiz (optional)<textarea class="form-input" name="note" rows="3" maxlength="2000">' + esc(e.note) + '</textarea></label>'
      + (window.LehrerFiles && window.MULTIUSER_ENABLED !== false
        ? '<div class="task-files"><span class="form-label-text">Anhänge</span><ul class="task-file-list" data-file-list></ul>'
          + '<label class="btn btn-secondary btn-sm task-file-add"><input type="file" accept="image/*,application/pdf,.pdf" multiple data-file-input hidden />'
          + '📎 Foto oder PDF anhängen</label><span class="task-file-usage" data-file-usage></span></div>'
        : '')
      + '<p class="task-editor-hint">Bleibt nur auf deinen Geräten, Anhänge liegen verschlüsselt auf dem Server. Bitte keine Schülernamen – auch nicht auf Fotos.</p>'
      + '<p class="task-editor-error" role="alert" hidden></p>'
      + '<div class="modal-actions task-editor-actions">'
      + (existing ? '<button class="btn btn-secondary task-delete" type="button" data-task-delete>Löschen</button>' : '')
      + (existing && e.kind === 'task' ? '<button class="btn btn-secondary" type="button" data-task-toggle-done>' + (e.done ? 'Wieder offen' : 'Erledigt') + '</button>' : '')
      + '<button class="btn btn-primary" type="submit">Speichern</button></div>'
      + '</form>';
    document.body.appendChild(overlay);
    var form = overlay.querySelector('form');
    var error = overlay.querySelector('.task-editor-error');

    // ── Anhänge: sofort verschlüsselt hochgeladen, mit dem Eintrag erst bei „Speichern“ verknüpft
    var files = (e.files || []).slice();
    var addedFiles = [];      // uploaded in this window
    var removedFiles = [];    // existing ones taken out (deleted on „Speichern“)
    var uploading = 0;
    var saved = false;
    overlay._discard = function () {
      if (!saved) dropFiles(addedFiles.filter(function (id) { return !existing || filesOf(get(e.id)).indexOf(id) === -1; }));
    };
    var fileList = form.querySelector('[data-file-list]');
    var fileInput = form.querySelector('[data-file-input]');
    var usageEl = form.querySelector('[data-file-usage]');
    function showUsage(data) {
      if (usageEl && data && data.quota) usageEl.textContent = window.LehrerFiles.sizeText(data.used) + ' von ' + Math.round(data.quota / 1024 / 1024) + ' MB belegt';
    }
    function renderFiles(pending) {
      if (!fileList) return;
      fileList.innerHTML = files.map(function (f, i) {
        return '<li class="task-file"><button type="button" class="task-file-open" data-file-open="' + i + '">'
          + '<span aria-hidden="true">' + (/^image\//.test(f.type) ? '🖼' : '📄') + '</span><span class="task-file-name">' + esc(f.name) + '</span>'
          + '<span class="task-file-size">' + window.LehrerFiles.sizeText(f.size) + '</span></button>'
          + '<button type="button" class="task-del is-visible" data-file-remove="' + i + '" aria-label="' + esc(f.name) + ' entfernen" title="Entfernen">' + TRASH + '</button></li>';
      }).join('') + (pending ? '<li class="task-file is-pending">' + esc(pending) + '</li>' : '');
    }
    renderFiles();
    if (fileInput) {
      window.LehrerFiles.usage().then(showUsage).catch(function () {});
      fileInput.addEventListener('change', function () {
        var picked = [].slice.call(fileInput.files || []);
        fileInput.value = '';
        if (files.length + picked.length > 10) { error.textContent = 'Höchstens 10 Anhänge pro Eintrag.'; error.hidden = false; return; }
        error.hidden = true;
        picked.reduce(function (chain, file) {
          return chain.then(function () {
            uploading++;
            renderFiles('„' + (file.name || 'Foto') + '“ wird verschlüsselt und hochgeladen …');
            return window.LehrerFiles.add(file).then(function (meta) {
              files.push(meta);
              addedFiles.push(meta.id);
            }).catch(function (err) {
              error.textContent = err.message || 'Hochladen hat nicht geklappt.';
              error.hidden = false;
            }).then(function () { uploading--; renderFiles(); });
          });
        }, Promise.resolve()).then(function () { window.LehrerFiles.usage().then(showUsage).catch(function () {}); });
      });
    }
    if (fileList) {
      fileList.addEventListener('click', function (ev) {
        var openBtn = ev.target.closest('[data-file-open]');
        if (openBtn) { window.LehrerFiles.open(files[+openBtn.dataset.fileOpen]); return; }
        var rm = ev.target.closest('[data-file-remove]');
        if (rm) {
          var f = files.splice(+rm.dataset.fileRemove, 1)[0];
          if (f) {
            if (addedFiles.indexOf(f.id) !== -1) dropFiles([f.id]); else removedFiles.push(f.id);
          }
          renderFiles();
        }
      });
    }

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
      var time = normTime(form.elements.time.value);
      var endTime = kind() === 'event' ? normTime(form.elements.endTime.value) : '';
      if (time === null || endTime === null) {
        error.textContent = 'Uhrzeit bitte so eingeben: 14:30 (oder 1430, 14.30, 14).'; error.hidden = false;
        (time === null ? form.elements.time : form.elements.endTime).focus(); return;
      }
      if (time && !date) { error.textContent = 'Zur Uhrzeit fehlt noch das Datum.'; error.hidden = false; form.elements.date.focus(); return; }
      if (uploading) { error.textContent = 'Einen Moment – die Anhänge werden noch hochgeladen.'; error.hidden = false; return; }
      saved = true;
      dropFiles(removedFiles);
      save({
        id: e.id, kind: kind(), title: title, date: date, time: time,
        endTime: time ? endTime : '',
        note: form.elements.note.value, remind: form.elements.remind.value, list: form.elements.list.value,
        done: kind() === 'task' && e.done, doneAt: e.doneAt, created: e.created, files: files,
      });
      closeEditor();
    });
    // times typed on the keyboard: tidied up when leaving the field
    form.addEventListener('focusout', function (ev) {
      if (!ev.target.matches || !ev.target.matches('[data-time]')) return;
      var t = normTime(ev.target.value);
      if (t !== null) ev.target.value = t;
    });
    draggable(form, form.querySelector('.modal-header'));
    // closes on a click beside the window – not when a drag or a text selection ends there
    var downOnOverlay = false;
    overlay.addEventListener('pointerdown', function (ev) { downOnOverlay = ev.target === overlay; });
    overlay.addEventListener('click', function (ev) {
      if ((ev.target === overlay && downOnOverlay) || ev.target.closest('[data-task-close]')) { closeEditor(); return; }
      if (ev.target.closest('[data-task-delete]')) {
        if (!window.confirm('„' + e.title + '“ löschen?' + (files.length ? ' Die Anhänge werden mit gelöscht.' : ''))) return;
        remove(e.id);
        dropFiles(addedFiles);
        saved = true;
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
      body.addEventListener('pointerdown', onSwipeStart);
      body.addEventListener('pointermove', onSwipeMove);
      body.addEventListener('pointerup', onSwipeEnd);
      body.addEventListener('pointercancel', onSwipeEnd);
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
  window.addEventListener('storage', function (ev) { if (ev.key === KEY || ev.key === LISTS_KEY) changed(); }); // another tab
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') renderTile(); }); // new day
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  window.LehrerTasks = {
    all: all, get: get, save: save, remove: remove, setDone: setDone,
    openEditor: openEditor, parseQuick: parseQuick, renderTile: renderTile, lists: lists,
  };
})();
