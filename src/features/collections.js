/**
 * src/features/collections.js — Einsammlungen
 *
 * Digitale Einsammel-Listen auf Basis der Klassenlisten aus classlist.js:
 *   „Wer hat abgegeben?“  Unterschriften, Geld, Dokumente … – abhaken, wer es hat.
 *   „Wer hat es nicht?“   Hausaufgaben, Material … (type "missing") – nur die
 *                         antippen, die es nicht haben, mit Grund. Jede Liste gilt
 *                         für einen Tag, es gibt bewusst keinen Verlauf pro Kind.
 *                         Nach der Aufbewahrungszeit (deleteOn) fragt das Cockpit:
 *                         als PDF/CSV sichern, dann löschen – oder länger behalten.
 *                         Ohne Klick der Lehrkraft wird nie etwas gelöscht.
 *
 * Datenstruktur (localStorage "lehrerCockpit.collections"):
 *   {
 *     "col_abc": {
 *       id, title, type, note, classIds, dueDate, createdAt,
 *       archived,
 *       checks: { studentId: { done: bool, note: string } }
 *       // nur type "missing":
 *       date, reasons: [text], marks: { studentId: reason }, keep, deleteOn
 *     }
 *   }
 *
 * Exports (window.LehrerCollections): init, render
 */
var LehrerCollections = (function () {
  'use strict';

  var STORAGE_KEY  = 'lehrerCockpit.collections';
  var TYPES = [
    { value: 'signature', label: 'Unterschrift' },
    { value: 'money',     label: 'Geld' },
    { value: 'document',  label: 'Dokument' },
    { value: 'other',     label: 'Sonstiges' },
  ];
  var MISSING = 'missing';
  var PRESETS = [
    { title: 'Hausaufgaben', reasons: ['vergessen', 'unvollständig'] },
    { title: 'Material', reasons: ['Heft', 'Buch', 'Mappe', 'Sportzeug'] },
  ];
  var KEEP = [
    { id: '4w', label: '4 Wochen' },
    { id: 'hj', label: 'Halbjahresende' },
    { id: 'sj', label: 'Schuljahresende' },
  ];
  var MODE_KEY = 'lc.colNewMode';

  var _container   = null;
  var _data        = {};
  var _activeId    = null;
  var _showArchive = false;
  var _reason      = {};      // list id → reason for the next tap
  var _editReasons = false;

  // ── Persistence ──────────────────────────────────────────────────────────
  function _load() {
    var raw;
    try { raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); }
    catch(e) { raw = {}; }
    // Stored data may come from older versions or another device: never let
    // one odd entry break the page.
    _data = {};
    var today = _todayIso();
    var list = Array.isArray(raw) ? raw : Object.values(raw && typeof raw === 'object' ? raw : {});
    list.forEach(function (c) {
      if (!c || typeof c !== 'object' || !c.id) return;
      c.title = String(c.title || '');
      c.type = c.type || 'other';
      c.createdAt = String(c.createdAt || '');
      c.classIds = Array.isArray(c.classIds) ? c.classIds : [];
      c.checks = c.checks && typeof c.checks === 'object' ? c.checks : {};
      if (c.type === MISSING) {
        c.deleteOn = /^\d{4}-\d{2}-\d{2}$/.test(String(c.deleteOn || '')) ? c.deleteOn : '';
        c.date = /^\d{4}-\d{2}-\d{2}$/.test(String(c.date || '')) ? c.date : today;
        c.reasons = (Array.isArray(c.reasons) ? c.reasons : []).map(function (r) { return String(r || '').trim().slice(0, 30); }).filter(Boolean).slice(0, 8);
        if (!c.reasons.length) c.reasons = ['fehlt'];
        c.marks = c.marks && typeof c.marks === 'object' ? c.marks : {};
      }
      _data[c.id] = c;
    });
  }
  function _save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(_data)); } catch(e) {}
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function _uid() { return 'col_' + Math.random().toString(36).slice(2, 10); }
  function _iso(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  function _todayIso() { return _iso(new Date()); }
  function _addDays(iso, n) { var d = new Date(iso + 'T12:00:00'); d.setDate(d.getDate() + n); return _iso(d); }

  /** Day a „Wer hat es nicht?“ list is kept until (then the cockpit asks to save and delete): 4 weeks after, or the first day of the
   *  next Winter-/Sommerferien (Halbjahresende) or Sommerferien (Schuljahresende). */
  function _deleteOn(keep, iso) {
    if (keep === '4w') return _addDays(iso, 28);
    var re = keep === 'sj' ? /^Sommerferien/ : /^(Winter|Sommer)ferien/;
    var SY = window.LehrerSchoolYear;
    var breaks = [];
    if (SY && SY.schoolYear) {
      var d = new Date(iso + 'T12:00:00');
      breaks = SY.schoolYear(d).breaks.concat(SY.schoolYear(new Date(d.getFullYear() + 1, d.getMonth(), d.getDate())).breaks);
    }
    var hit = breaks.filter(function (b) { return re.test(b.name) && b.start > iso; })[0];
    return hit ? hit.start : _addDays(iso, keep === 'sj' ? 365 : 182);
  }
  function _longDate(iso) {
    return iso ? new Date(iso + 'T12:00:00').toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' }) : '';
  }
  function _isExpired(col) { return col.type === MISSING && !!col.deleteOn && col.deleteOn <= _todayIso(); }

  function _activeReason(col) {
    var r = _reason[col.id];
    return r && col.reasons.indexOf(r) !== -1 ? r : col.reasons[0];
  }
  function _esc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function _typeLabel(v) {
    var t = TYPES.find(function(x){ return x.value === v; });
    return t ? t.label : String(v || '');
  }
  function _sortedCollections() {
    return Object.values(_data).sort(function(a,b){
      // active first, then by date desc
      if (!!a.archived !== !!b.archived) return a.archived ? 1 : -1;
      return (b.createdAt||'').localeCompare(a.createdAt||'');
    });
  }

  /** Returns { done, total } for a collection */
  function _progress(col) {
    var students = _getStudentsForCollection(col);
    var total = students.length;
    // Checks are stored per "<class>|<student id>" (see _buildChecklist / _setCheck).
    var done  = students.filter(function(s){ var c = col.checks && col.checks[s.classId + '|' + s.id]; return !!(c && c.done); }).length;
    return { done: done, total: total };
  }

  /** Get merged, deduplicated student list for a collection's classes */
  function _getStudentsForCollection(col) {
    if (!window.LehrerClasslist || !col.classIds || !col.classIds.length) return [];
    var seen = {};
    var result = [];
    col.classIds.forEach(function(cid) {
      var students = window.LehrerClasslist.getStudentsForClass(cid);
      students.forEach(function(s) {
        var key = cid + '|' + s.id;
        if (!seen[key]) { seen[key] = true; result.push(Object.assign({}, s, { classId: cid })); }
      });
    });
    return result;
  }

  // ── Render ────────────────────────────────────────────────────────────────
  function render() {
    if (!_container) return;
    _load();

    var cols = _sortedCollections().filter(function(c){ return _showArchive || !c.archived; });
    if (_activeId && !_data[_activeId]) _activeId = null;
    if (!_activeId && cols.length) _activeId = cols[0].id;

    _container.innerHTML = [
      '<div class="col-layout">',
        _buildSidebar(cols),
        '<div class="col-main">',
          _activeId && _data[_activeId] ? _buildChecklist(_data[_activeId]) : _buildEmpty(),
        '</div>',
      '</div>',
    ].join('');
    _bindEvents();
  }

  function _buildSidebar(cols) {
    var items = cols.map(function(c) {
      if (c.type === MISSING) return _sidebarMissing(c);
      var p   = _progress(c);
      var pct = p.total ? Math.round(p.done/p.total*100) : 0;
      var due = c.dueDate ? '<span class="col-item-due">' + _formatDate(c.dueDate) + '</span>' : '';
      var active = c.id === _activeId ? ' active' : '';
      var arch   = c.archived ? ' col-item-archived' : '';
      return '<button class="col-item-btn' + active + arch + '" type="button" data-col-id="' + c.id + '">'
        + '<span class="col-item-title">' + _esc(c.title) + '</span>'
        + '<span class="col-item-meta">'
        +   _esc(c.classIds.join(', ')) + ' · ' + _typeLabel(c.type).replace(/\S+\s/,'')
        +   due
        + '</span>'
        + '<span class="col-item-progress">'
        +   '<span class="col-progress-bar"><span class="col-progress-fill' + (p.total && p.done === p.total ? ' is-complete' : '') + '" style="width:' + pct + '%"></span></span>'
        +   '<span class="col-progress-text">' + p.done + '/' + p.total + '</span>'
        + '</span>'
        + '</button>';
    }).join('');

    return '<aside class="col-sidebar">'
      + '<div class="col-sidebar-head">'
      +   '<h2 class="col-sidebar-title">Einsammlungen</h2>'
      +   '<button class="classlist-add-class-btn" type="button" data-action="new-col" title="Neue Einsammlung">＋</button>'
      + '</div>'
      + '<div class="col-list">' + (items || '<p class="classlist-empty-hint">Noch keine Einsammlungen</p>') + '</div>'
      + '<div class="col-sidebar-footer">'
      +   '<button class="col-archive-toggle" type="button" data-action="toggle-archive">'
      +   (_showArchive ? 'Archiv ausblenden' : 'Archiv anzeigen') + '</button>'
      + '</div>'
      + '</aside>';
  }

  function _missCount(col) {
    return _getStudentsForCollection(col).filter(function (s) { return col.marks[s.classId + '|' + s.id]; }).length;
  }

  function _sidebarMissing(c) {
    var n = _missCount(c);
    return '<button class="col-item-btn' + (c.id === _activeId ? ' active' : '') + (c.archived ? ' col-item-archived' : '') + '" type="button" data-col-id="' + c.id + '">'
      + '<span class="col-item-title">' + _esc(c.title) + '</span>'
      + '<span class="col-item-meta">' + _esc(c.classIds.join(', ')) + ' · ' + _formatDate(c.date) + '</span>'
      + '<span class="col-item-progress"><span class="col-miss-count' + (n ? '' : ' is-zero') + '">' + (n ? n + ' ohne' : 'alle hatten es') + '</span></span>'
      + '</button>';
  }

  function _missRowInner(s, mark) {
    return '<span class="col-miss-mark" aria-hidden="true">' + (mark ? '✗' : '') + '</span>'
      + '<span class="col-check-name"><span class="col-ln">' + _esc(s.lastName) + '</span> <span class="col-fn">' + _esc(s.firstName) + '</span></span>'
      + (mark ? '<span class="col-miss-reason">' + _esc(mark) + '</span>' : '');
  }

  function _missLabel(col) {
    var marked = _getStudentsForCollection(col).filter(function (s) { return col.marks[s.classId + '|' + s.id]; });
    if (!marked.length) return 'Noch niemand angetippt – alle hatten es.';
    return 'Ohne: ' + marked.slice(0, 6).map(function (s) { return s.lastName + ' (' + col.marks[s.classId + '|' + s.id] + ')'; }).join(', ')
      + (marked.length > 6 ? ' +' + (marked.length - 6) : '');
  }

  function _missProgressText(col) {
    var n = _missCount(col);
    var total = _getStudentsForCollection(col).length;
    return n ? n + ' von ' + total + ' ohne' : 'Alle ' + total + ' hatten es';
  }

  function _buildMissing(col) {
    var students = _getStudentsForCollection(col);
    var active = _activeReason(col);
    var byClass = {};
    students.forEach(function (s) { (byClass[s.classId] = byClass[s.classId] || []).push(s); });
    var rows = '';
    Object.keys(byClass).sort().forEach(function (cid) {
      if (col.classIds.length > 1) rows += '<li class="col-check-classhead">Klasse ' + _esc(cid) + '</li>';
      byClass[cid].forEach(function (s) {
        var sid = s.classId + '|' + s.id;
        var mark = col.marks[sid] || '';
        rows += '<li><button type="button" class="col-miss-row' + (mark ? ' is-missing' : '') + '" data-miss="' + _esc(sid) + '" aria-pressed="' + !!mark + '">'
          + _missRowInner(s, mark) + '</button></li>';
      });
    });
    var today = _todayIso();
    var expired = _isExpired(col);
    var archBtn = col.archived
      ? '<button class="btn btn-sm btn-secondary" type="button" data-action="unarchive">Reaktivieren</button>'
      : '<button class="btn btn-sm btn-secondary" type="button" data-action="archive">Archivieren</button>';
    return '<div class="col-panel">'
      + '<div class="col-panel-head">'
      +   '<div class="col-panel-title-block">'
      +     '<h2 class="col-panel-title">' + _esc(col.title) + '</h2>'
      +     '<p class="col-panel-meta">Wer hat es nicht? · Klasse ' + _esc(col.classIds.join(', ')) + ' · ' + _esc(_longDate(col.date)) + '</p>'
      +     '<span class="col-panel-progress col-miss-progress" data-col-progress>' + _missProgressText(col) + '</span>'
      +   '</div>'
      +   '<div class="col-panel-actions action-row">'
      +     (col.date !== today && !col.archived ? '<button class="btn btn-sm btn-primary" type="button" data-action="repeat-col" title="Gleiche Liste (Titel, Klasse, Gründe) für heute neu anlegen">Nochmal für heute</button>' : '')
      +     '<button class="btn btn-sm btn-secondary" type="button" data-action="print-col" title="Nur diese Liste – drucken oder als PDF sichern">PDF</button>'
      +     archBtn
      +     '<details class="more-menu"><summary class="btn btn-sm btn-secondary" aria-label="Weitere Aktionen">⋯</summary>'
      +       '<div class="more-menu-list" role="menu">'
      +         '<button type="button" role="menuitem" data-action="export-col">Als CSV speichern</button>'
      +         '<button type="button" role="menuitem" data-action="clear-miss">Alle Striche entfernen</button>'
      +         '<button type="button" role="menuitem" class="is-danger" data-action="delete-col">Liste löschen …</button>'
      +       '</div>'
      +     '</details>'
      +   '</div>'
      + '</div>'
      + '<div class="col-miss-bar">'
      +   '<span class="col-miss-bar-label">Antippen trägt ein:</span>'
      +   col.reasons.map(function (r) {
            return '<button type="button" class="col-reason' + (r === active ? ' is-active' : '') + '" data-reason="' + _esc(r) + '" aria-pressed="' + (r === active) + '">' + _esc(r) + '</button>';
          }).join('')
      +   '<button type="button" class="col-reason-edit" data-action="edit-reasons">' + (_editReasons ? 'Abbrechen' : 'Gründe ändern') + '</button>'
      + '</div>'
      + (_editReasons
          ? '<div class="col-reason-form"><input class="col-form-input" data-reasons-input value="' + _esc(col.reasons.join(', ')) + '" placeholder="z. B. vergessen, unvollständig" autocomplete="off">'
            + '<button class="btn btn-sm btn-primary" type="button" data-action="save-reasons">Fertig</button>'
            + '<p class="col-hint">Mit Komma trennen, höchstens 8. Schon gesetzte Striche behalten ihren Grund.</p></div>'
          : '')
      + '<div class="col-check-toolbar"><span class="col-missing-label" id="col-missing-label">' + _esc(_missLabel(col)) + '</span></div>'
      + '<ul class="col-check-list">' + (rows || '<li class="classlist-empty-hint">Keine Schüler in dieser Klasse.</li>') + '</ul>'
      + (expired
          ? '<div class="col-delete-note is-soon"><p>Aufbewahrt bis ' + _esc(_longDate(col.deleteOn)) + ' – die Zeit ist um. Sichere die Liste auf deinem Gerät und lösch sie dann hier.</p>'
            + '<div class="col-expire-actions">'
            +   '<button class="btn btn-sm btn-secondary" type="button" data-action="print-col">Als PDF sichern</button>'
            +   '<button class="btn btn-sm btn-secondary" type="button" data-action="export-col">Als CSV sichern</button>'
            +   '<button class="btn btn-sm btn-secondary" type="button" data-action="keep-col">4 Wochen länger behalten</button>'
            +   '<button class="btn btn-sm btn-danger" type="button" data-action="delete-col">Löschen …</button>'
            + '</div></div>'
          : '<p class="col-delete-note">Aufbewahrt bis ' + _esc(_longDate(col.deleteOn)) + '. Danach fragt dich das Cockpit, ob du sie sichern und löschen willst – von selbst wird nichts gelöscht.</p>')
      + '</div>';
  }

  function _buildChecklist(col) {
    if (col.type === MISSING) return _buildMissing(col);
    var students = _getStudentsForCollection(col);
    var p = _progress(col);
    var pct = p.total ? Math.round(p.done/p.total*100) : 0;

    // Group by class if multiple
    var byClass = {};
    students.forEach(function(s) {
      if (!byClass[s.classId]) byClass[s.classId] = [];
      byClass[s.classId].push(s);
    });

    var rows = '';
    Object.keys(byClass).sort().forEach(function(cid) {
      if (col.classIds.length > 1) {
        rows += '<li class="col-check-classhead">Klasse ' + _esc(cid) + '</li>';
      }
      byClass[cid].forEach(function(s) {
        var check = col.checks && col.checks[s.classId+'|'+s.id] || {};
        var done  = !!check.done;
        var note  = check.note || '';
        var sid   = s.classId + '|' + s.id;
        rows += '<li class="col-check-row' + (done?' is-done':'') + '" data-sid="' + _esc(sid) + '">'
          + '<label class="col-check-label">'
          +   '<input type="checkbox" class="col-checkbox" data-sid="' + _esc(sid) + '"' + (done?' checked':'') + '>'
          +   '<span class="col-check-name"><span class="col-ln">' + _esc(s.lastName) + '</span> <span class="col-fn">' + _esc(s.firstName) + '</span></span>'
          + '</label>'
          + '<input type="text" class="col-note-input" placeholder="Notiz…" value="' + _esc(note) + '" data-sid="' + _esc(sid) + '">'
          + '</li>';
      });
    });

    var archBtn = col.archived
      ? '<button class="btn btn-sm btn-secondary" type="button" data-action="unarchive">Reaktivieren</button>'
      : '<button class="btn btn-sm btn-secondary" type="button" data-action="archive">Archivieren</button>';

    return '<div class="col-panel">'
      + '<div class="col-panel-head">'
      +   '<div class="col-panel-title-block">'
      +     '<h2 class="col-panel-title">' + _esc(col.title) + '</h2>'
      +     '<p class="col-panel-meta">'
      +       _typeLabel(col.type) + ' · Klasse ' + _esc(col.classIds.join(', '))
      +       (col.dueDate ? ' · Fällig: ' + _formatDate(col.dueDate) : '')
      +       (col.note ? ' · ' + _esc(col.note) : '')
      +     '</p>'
      +     '<span class="col-panel-progress" data-col-progress>' + p.done + ' von ' + p.total + ' (' + pct + '%)</span>'
      +   '</div>'
      +   '<div class="col-panel-actions action-row">'
      +     '<button class="btn btn-sm btn-secondary" type="button" data-action="print-col" title="Nur diese Einsammlung – drucken oder als PDF sichern">PDF</button>'
      +     archBtn
      +     '<details class="more-menu"><summary class="btn btn-sm btn-secondary" aria-label="Weitere Aktionen">⋯</summary>'
      +       '<div class="more-menu-list" role="menu">'
      +         '<button type="button" role="menuitem" data-action="export-col">Als CSV speichern</button>'
      +         '<button type="button" role="menuitem" class="is-danger" data-action="delete-col">Einsammlung löschen …</button>'
      +       '</div>'
      +     '</details>'
      +   '</div>'
      + '</div>'
      + '<div class="col-progress-full"><div class="col-progress-full-fill" style="width:' + pct + '%"></div></div>'
      + '<div class="col-check-toolbar">'
      +   '<button class="btn btn-sm btn-secondary" type="button" data-action="mark-all">Alle ✓</button>'
      +   '<button class="btn btn-sm btn-secondary" type="button" data-action="clear-all">Alle zurück</button>'
      +   '<span class="col-missing-label" id="col-missing-label">' + _missingLabel(col) + '</span>'
      + '</div>'
      + '<ul class="col-check-list">' + (rows || '<li class="classlist-empty-hint">Keine Schüler in dieser Klasse.</li>') + '</ul>'
      + '</div>';
  }

  function _buildEmpty() {
    return '<div class="classlist-empty-state">'
      + '<div class="classlist-empty-icon"><svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg></div>'
      + '<h2>Noch keine Einsammlungen</h2>'
      + '<p>Erstelle eine neue Einsammlung – Schüler werden automatisch aus den Klassenlisten geladen.</p>'
      + '<button class="btn btn-primary" type="button" data-action="new-col">Erste Einsammlung erstellen</button>'
      + '</div>';
  }

  function _missingLabel(col) {
    var students = _getStudentsForCollection(col);
    var missing = students.filter(function(s){ return !(col.checks && col.checks[s.classId+'|'+s.id] && col.checks[s.classId+'|'+s.id].done); });
    if (!missing.length) return '✓ Alle abgegeben';
    return 'Noch ausstehend: ' + missing.slice(0,5).map(function(s){ return s.lastName; }).join(', ') + (missing.length > 5 ? ' +' + (missing.length-5) : '');
  }

  function _formatDate(iso) {
    if (!iso) return '';
    var d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('de-DE', { day:'2-digit', month:'2-digit' });
  }

  // ── New Collection Dialog ─────────────────────────────────────────────────
  function _showNewDialog() {
    var classes = window.LehrerClasslist ? Object.keys(window.LehrerClasslist.getClassLists()).sort(function(a,b){ return a.localeCompare(b,'de',{numeric:true}); }) : [];
    var mode = 'positive';
    try { if (localStorage.getItem(MODE_KEY) === MISSING) mode = MISSING; } catch (e) { /* private mode */ }
    var today = _todayIso();

    var classOptions = classes.map(function(c) {
      return '<label class="col-class-check"><input type="checkbox" value="' + _esc(c) + '"> ' + _esc(c) + '</label>';
    }).join('');

    var typeOptions = TYPES.map(function(t) {
      return '<option value="' + t.value + '">' + t.label + '</option>';
    }).join('');

    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = [
      '<div class="modal" style="width:min(500px,95vw)">',
        '<div class="modal-header">',
          '<span class="modal-title">Neue Liste</span>',
          '<button class="modal-close" type="button" data-action="close">✕</button>',
        '</div>',
        '<div class="col-new-body">',
          '<div class="col-mode" role="radiogroup" aria-label="Art der Liste">',
            '<button type="button" class="col-mode-btn" data-mode="positive" role="radio"><strong>✓ Wer hat abgegeben?</strong><span>Unterschrift, Geld, Dokument – du hakst ab, wer es hat.</span></button>',
            '<button type="button" class="col-mode-btn" data-mode="missing" role="radio"><strong>✗ Wer hat es nicht?</strong><span>Hausaufgaben, Material – du tippst nur die an, die es nicht haben.</span></button>',
          '</div>',
          '<div class="col-presets" data-only="missing">' + PRESETS.map(function (p, n) {
            return '<button type="button" class="col-preset" data-preset="' + n + '">' + _esc(p.title) + '</button>';
          }).join('') + '</div>',
          '<label class="col-form-label">Titel<input class="col-form-input" type="text" id="col-new-title" autocomplete="off"></label>',
          '<label class="col-form-label" data-only="positive">Art',
            '<select class="col-form-input" id="col-new-type">' + typeOptions + '</select>',
          '</label>',
          '<div class="col-form-label">Klasse(n) *',
            '<div class="col-class-checks">' + (classOptions || '<p class="classlist-empty-hint">Zuerst Klassen anlegen.</p>') + '</div>',
          '</div>',
          '<div class="col-form-row" data-only="missing">',
            '<label class="col-form-label">Datum<input class="col-form-input" type="date" id="col-new-date" value="' + today + '"></label>',
            '<label class="col-form-label">Aufbewahren bis<select class="col-form-input" id="col-new-keep"></select></label>',
          '</div>',
          '<label class="col-form-label" data-only="missing">Gründe zum Antippen<input class="col-form-input" type="text" id="col-new-reasons" value="vergessen, unvollständig" autocomplete="off"></label>',
          '<p class="col-hint" data-only="missing">Mit Komma trennen. Jede Liste gilt für einen Tag – mit „Nochmal für heute“ legst du sie in der nächsten Stunde mit einem Tipp neu an. Ist die Aufbewahrungszeit um, erinnert dich das Cockpit: sichern, dann löschen.</p>',
          '<label class="col-form-label" data-only="positive">Fälligkeit (optional)<input class="col-form-input" type="date" id="col-new-due"></label>',
          '<label class="col-form-label" data-only="positive">Notiz (optional)<input class="col-form-input" type="text" id="col-new-note" placeholder="z.B. 15 €" autocomplete="off"></label>',
          '<div style="display:flex;justify-content:flex-end;gap:8px;margin-top:4px;">',
            '<button class="btn btn-secondary" type="button" data-action="close">Abbrechen</button>',
            '<button class="btn btn-primary" type="button" data-action="create">Erstellen</button>',
          '</div>',
        '</div>',
      '</div>',
    ].join('');

    document.body.appendChild(overlay);
    var $ = function (sel) { return overlay.querySelector(sel); };

    function keepOptions() {
      var day = $('#col-new-date').value || today;
      var select = $('#col-new-keep');
      var chosen = select.value || 'hj';
      select.innerHTML = KEEP.map(function (k) {
        return '<option value="' + k.id + '"' + (k.id === chosen ? ' selected' : '') + '>' + k.label + ' (' + _formatDate(_deleteOn(k.id, day)) + ')</option>';
      }).join('');
    }
    function setMode(next) {
      mode = next;
      overlay.querySelectorAll('[data-mode]').forEach(function (b) {
        var on = b.dataset.mode === mode;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-checked', String(on));
      });
      overlay.querySelectorAll('[data-only]').forEach(function (el) { el.hidden = el.dataset.only !== mode; });
      $('#col-new-title').placeholder = mode === MISSING ? 'z. B. Hausaufgaben' : 'z. B. Geld Klassenfahrt';
    }
    keepOptions();
    setMode(mode);
    $('#col-new-date').addEventListener('change', keepOptions);
    setTimeout(function () { $('#col-new-title').focus(); }, 0);

    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) { _removeEl(overlay); return; }
      var modeBtn = e.target.closest('[data-mode]');
      if (modeBtn) { setMode(modeBtn.dataset.mode); return; }
      var preset = e.target.closest('[data-preset]');
      if (preset) {
        var p = PRESETS[+preset.dataset.preset];
        var title = $('#col-new-title');
        if (!title.value.trim() || PRESETS.some(function (x) { return x.title === title.value.trim(); })) title.value = p.title;
        $('#col-new-reasons').value = p.reasons.join(', ');
        return;
      }
      var action = e.target.closest('[data-action]');
      if (!action) return;
      if (action.dataset.action === 'close') { _removeEl(overlay); return; }
      if (action.dataset.action === 'create') {
        var titleText = $('#col-new-title').value.trim();
        if (!titleText) { $('#col-new-title').focus(); return; }
        var classIds = Array.from(overlay.querySelectorAll('.col-class-check input:checked')).map(function(cb){ return cb.value; });
        if (!classIds.length) { alert('Bitte mindestens eine Klasse auswählen.'); return; }
        var id = _uid();
        if (mode === MISSING) {
          var day = $('#col-new-date').value || today;
          var keep = $('#col-new-keep').value || 'hj';
          var reasons = _parseReasons($('#col-new-reasons').value);
          _data[id] = { id: id, title: titleText, type: MISSING, note: '', classIds: classIds, date: day, reasons: reasons, marks: {},
                        keep: keep, deleteOn: _deleteOn(keep, day), createdAt: new Date().toISOString(), archived: false, checks: {} };
        } else {
          _data[id] = { id: id, title: titleText, type: $('#col-new-type').value, note: $('#col-new-note').value.trim(), classIds: classIds,
                        dueDate: $('#col-new-due').value, createdAt: new Date().toISOString(), archived: false, checks: {} };
        }
        try { localStorage.setItem(MODE_KEY, mode); } catch (err) { /* private mode */ }
        _save();
        _activeId = id;
        _removeEl(overlay);
        render();
      }
    });
  }

  function _parseReasons(text) {
    var seen = {};
    var list = String(text || '').split(',').map(function (r) { return r.trim().slice(0, 30); }).filter(function (r) {
      if (!r || seen[r.toLowerCase()]) return false;
      seen[r.toLowerCase()] = true;
      return true;
    }).slice(0, 8);
    return list.length ? list : ['fehlt'];
  }

  // ── Actions ───────────────────────────────────────────────────────────────
  function _setCheck(colId, sid, done) {
    var col = _data[colId];
    if (!col) return;
    if (!col.checks) col.checks = {};
    if (!col.checks[sid]) col.checks[sid] = {};
    col.checks[sid].done = done;
    _save();
    // Update UI without full re-render
    var row = _container.querySelector('[data-sid="' + CSS.escape(sid) + '"].col-check-row');
    if (row) row.classList.toggle('is-done', done);
    var missing = _container.querySelector('#col-missing-label');
    if (missing) missing.textContent = _missingLabel(col);
    // update header and sidebar progress
    var p = _progress(col);
    var pct = p.total ? Math.round(p.done / p.total * 100) : 0;
    var headline = _container.querySelector('[data-col-progress]');
    if (headline) headline.textContent = p.done + ' von ' + p.total + ' (' + pct + '%)';
    var bar = _container.querySelector('.col-progress-full-fill');
    if (bar) bar.style.width = pct + '%';
    _updateSidebarProgress(colId);
  }

  function _setNote(colId, sid, note) {
    var col = _data[colId];
    if (!col) return;
    if (!col.checks) col.checks = {};
    if (!col.checks[sid]) col.checks[sid] = {};
    col.checks[sid].note = note;
    _save();
  }

  function _markAll(colId, done) {
    var col = _data[colId];
    if (!col) return;
    if (!col.checks) col.checks = {};
    _getStudentsForCollection(col).forEach(function(s) {
      var sid = s.classId+'|'+s.id;
      if (!col.checks[sid]) col.checks[sid] = {};
      col.checks[sid].done = done;
    });
    _save();
    render();
  }

  /** Tap on a name: mark with the chosen reason, tap again to remove, other reason → switch. */
  function _toggleMiss(colId, sid) {
    var col = _data[colId];
    if (!col || col.type !== MISSING) return;
    var reason = _activeReason(col);
    if (col.marks[sid] === reason) delete col.marks[sid]; else col.marks[sid] = reason;
    _save();
    var row = _container.querySelector('[data-miss="' + CSS.escape(sid) + '"]');
    var student = _getStudentsForCollection(col).filter(function (s) { return s.classId + '|' + s.id === sid; })[0];
    if (row && student) {
      row.classList.toggle('is-missing', !!col.marks[sid]);
      row.setAttribute('aria-pressed', String(!!col.marks[sid]));
      row.innerHTML = _missRowInner(student, col.marks[sid] || '');
    }
    _refreshMissing(col);
  }

  function _refreshMissing(col) {
    var label = _container.querySelector('#col-missing-label');
    if (label) label.textContent = _missLabel(col);
    var head = _container.querySelector('[data-col-progress]');
    if (head) head.textContent = _missProgressText(col);
    var btn = _container.querySelector('[data-col-id="' + col.id + '"] .col-miss-count');
    if (btn) {
      var n = _missCount(col);
      btn.textContent = n ? n + ' ohne' : 'alle hatten es';
      btn.classList.toggle('is-zero', !n);
    }
  }

  function _setReason(colId, reason) {
    var col = _data[colId];
    if (!col) return;
    _reason[colId] = reason;
    _container.querySelectorAll('[data-reason]').forEach(function (b) {
      var on = b.dataset.reason === reason;
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-pressed', String(on));
    });
  }

  function _saveReasons(colId) {
    var col = _data[colId];
    var input = _container.querySelector('[data-reasons-input]');
    if (!col || !input) return;
    col.reasons = _parseReasons(input.value);
    _save();
    _editReasons = false;
    render();
  }

  /** Same list (title, class, reasons, deletion rule) for today – one tap in the next lesson. */
  function _repeatCol(colId) {
    var col = _data[colId];
    if (!col) return;
    var today = _todayIso();
    var same = Object.values(_data).filter(function (c) {
      return c.type === MISSING && !c.archived && c.date === today && c.title === col.title && c.classIds.join('|') === col.classIds.join('|');
    })[0];
    if (!same) {
      var id = _uid();
      var keep = col.keep || 'hj';
      same = _data[id] = { id: id, title: col.title, type: MISSING, note: '', classIds: col.classIds.slice(), date: today, reasons: col.reasons.slice(), marks: {},
                           keep: keep, deleteOn: _deleteOn(keep, today), createdAt: new Date().toISOString(), archived: false, checks: {} };
      _save();
    }
    _activeId = same.id;
    render();
  }

  function _clearMiss(colId) {
    var col = _data[colId];
    if (!col || !Object.keys(col.marks).length) return;
    if (!confirm('Alle Striche in „' + col.title + '“ entfernen?')) return;
    col.marks = {};
    _save();
    render();
  }

  function _archiveCol(colId, archived) {
    if (_data[colId]) { _data[colId].archived = archived; _save(); render(); }
  }

  function _deleteCol(colId) {
    var col = _data[colId];
    if (!col) return;
    if (!confirm((col.type === MISSING ? 'Liste' : 'Einsammlung') + ' "' + col.title + '" wirklich löschen?')) return;
    delete _data[colId];
    _save();
    _activeId = null;
    render();
    _dropCleanupHints();
  }

  function _csvCell(v) { return '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"'; }

  function _downloadCsv(name, lines) {
    var blob = new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a'); a.href = url; a.download = name.replace(/[^a-z0-9äöüß._-]/gi, '_') + '.csv';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  var MISSING_CSV_HEAD = 'Liste,Datum,Klasse,Nachname,Vorname,Ohne,Grund';
  function _missingCsvLines(col) {
    return _getStudentsForCollection(col).map(function (s) {
      var mark = col.marks[s.classId + '|' + s.id] || '';
      return [col.title, col.date, s.classId, s.lastName, s.firstName, mark ? 'Ja' : 'Nein', mark].map(_csvCell).join(',');
    });
  }

  function _exportCol(colId) {
    var col = _data[colId];
    if (!col) return;
    if (col.type === MISSING) { _downloadCsv(col.title + '_' + col.date, [MISSING_CSV_HEAD].concat(_missingCsvLines(col))); return; }
    var lines = ['Klasse,Nachname,Vorname,Abgegeben,Notiz'];
    _getStudentsForCollection(col).forEach(function(s) {
      var c = col.checks && col.checks[s.classId + '|' + s.id] || {};
      lines.push([s.classId, s.lastName, s.firstName, c.done ? 'Ja' : 'Nein', c.note || ''].map(_csvCell).join(','));
    });
    _downloadCsv(col.title, lines);
  }

  /** PDF of this one collection: per class a table with ✓ and note. */
  function _printCol(colId) {
    var col = _data[colId];
    if (!col || !window.LehrerClasslist || !window.LehrerClasslist.printDocument) return;
    if (col.type === MISSING) { _printMissing(col); return; }
    var students = _getStudentsForCollection(col);
    var p = _progress(col);
    var today = new Date().toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
    var multi = col.classIds.length > 1;
    var tables = col.classIds.map(function (cid) {
      var rows = students.filter(function (s) { return s.classId === cid; }).map(function (s, n) {
        var c = col.checks && col.checks[cid + '|' + s.id] || {};
        return '<tr><td class="nr">' + (n + 1) + '</td><td class="name">' + _esc(s.lastName) + (s.firstName ? ', ' + _esc(s.firstName) : '') + '</td>'
          + '<td class="mark">' + (c.done ? '✓' : '') + '</td><td>' + _esc(c.note || '') + '</td></tr>';
      }).join('');
      if (!rows) return '';
      return (multi ? '<h2>Klasse ' + _esc(cid) + '</h2>' : '')
        + '<table><thead><tr><th class="nr"></th><th class="name">Name</th><th class="mark">Abgegeben</th><th>Notiz</th></tr></thead><tbody>' + rows + '</tbody></table>';
    }).join('');
    var meta = [_typeLabel(col.type).replace(/^[^A-Za-zÄÖÜäöü]+/, ''), 'Klasse ' + col.classIds.join(', ')];
    if (col.dueDate) meta.push('Fällig: ' + _formatDate(col.dueDate));
    meta.push(p.done + ' von ' + p.total + ' abgegeben', 'Stand ' + today);
    window.LehrerClasslist.printDocument(col.title,
      '<h1>' + _esc(col.title) + '</h1><p class="meta">' + _esc(meta.join(' · ')) + '</p>'
      + (col.note ? '<p class="meta">' + _esc(col.note) + '</p>' : '')
      + (tables || '<p>Keine Schüler:innen in dieser Einsammlung.</p>'),
      { css: 'tr{height:6.5mm}td.name{width:1%}' });
  }

  function _missingBody(col) {
    var students = _getStudentsForCollection(col);
    var multi = col.classIds.length > 1;
    var tables = col.classIds.map(function (cid) {
      var rows = students.filter(function (s) { return s.classId === cid; }).map(function (s, n) {
        var mark = col.marks[cid + '|' + s.id] || '';
        return '<tr><td class="nr">' + (n + 1) + '</td><td class="name">' + _esc(s.lastName) + (s.firstName ? ', ' + _esc(s.firstName) : '') + '</td>'
          + '<td class="mark">' + (mark ? '✗' : '') + '</td><td>' + _esc(mark) + '</td></tr>';
      }).join('');
      if (!rows) return '';
      return (multi ? '<h2>Klasse ' + _esc(cid) + '</h2>' : '')
        + '<table><thead><tr><th class="nr"></th><th class="name">Name</th><th class="mark">Ohne</th><th>Grund</th></tr></thead><tbody>' + rows + '</tbody></table>';
    }).join('');
    var meta = ['Wer hat es nicht?', 'Klasse ' + col.classIds.join(', '), _longDate(col.date), _missProgressText(col)];
    return '<h1>' + _esc(col.title) + '</h1><p class="meta">' + _esc(meta.join(' · ')) + '</p>'
      + (tables || '<p>Keine Schüler:innen in dieser Liste.</p>');
  }

  function _printMissing(col) {
    window.LehrerClasslist.printDocument(col.title + ' ' + _formatDate(col.date), _missingBody(col), { css: 'tr{height:6.5mm}td.name{width:1%}' });
  }

  /** Several lists in one PDF, each on its own page. */
  function _printMany(cols) {
    if (!cols.length || !window.LehrerClasslist || !window.LehrerClasslist.printDocument) return;
    window.LehrerClasslist.printDocument('Listen ' + _formatDate(_todayIso()),
      cols.map(function (c, n) { return '<section' + (n ? ' style="page-break-before:always"' : '') + '>' + _missingBody(c) + '</section>'; }).join(''),
      { css: 'tr{height:6.5mm}td.name{width:1%}' });
  }

  function _keepLonger(cols) {
    var today = _todayIso();
    cols.forEach(function (c) { c.deleteOn = _addDays(c.deleteOn && c.deleteOn > today ? c.deleteOn : today, 28); });
    _save();
  }

  function _expiredLists() {
    return _sortedCollections().filter(_isExpired).sort(function (a, b) { return a.date.localeCompare(b.date); });
  }

  function _dropCleanupHints() {
    document.querySelectorAll('[data-col-cleanup]').forEach(function (el) { if (!_expiredLists().length) el.remove(); });
  }

  /** Expired lists: save them on this device (PDF/CSV), then delete – or keep them longer. */
  function openCleanup() {
    _load();
    var cols = _expiredLists();
    if (!cols.length) return;
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = '<div class="modal" role="dialog" aria-label="Abgelaufene Listen" style="width:min(500px,95vw)">'
      + '<div class="modal-header"><span class="modal-title">Aufbewahrungszeit um</span><button class="modal-close" type="button" data-x="close">✕</button></div>'
      + '<div class="col-new-body">'
      +   '<p class="col-hint" style="font-size:0.84rem;color:var(--ink-2)">Diese ' + (cols.length === 1 ? 'Liste ist' : cols.length + ' Listen sind') + ' über die Aufbewahrungszeit. '
      +   'Sichere sie zuerst auf deinem Gerät (PDF oder CSV, z. B. in „Dateien“ oder im Downloads-Ordner) und lösch sie dann aus dem Cockpit.</p>'
      +   '<ul class="col-cleanup-list">' + cols.map(function (c) {
            return '<li><strong>' + _esc(c.title) + '</strong> <span>Klasse ' + _esc(c.classIds.join(', ')) + ' · ' + _esc(_formatDate(c.date)) + ' · ' + _esc(_missProgressText(c)) + '</span></li>';
          }).join('') + '</ul>'
      +   '<div class="col-expire-actions">'
      +     '<button class="btn btn-sm btn-secondary" type="button" data-x="pdf">Als PDF sichern</button>'
      +     '<button class="btn btn-sm btn-secondary" type="button" data-x="csv">Als CSV sichern</button>'
      +   '</div>'
      +   '<p class="col-hint" data-x-saved hidden>Gesichert? Dann kannst du die Listen jetzt löschen.</p>'
      +   '<div class="col-expire-actions" style="justify-content:flex-end">'
      +     '<button class="btn btn-sm btn-ghost" type="button" data-x="keep">4 Wochen länger behalten</button>'
      +     '<button class="btn btn-sm btn-danger" type="button" data-x="delete">' + (cols.length === 1 ? 'Liste löschen' : 'Alle ' + cols.length + ' löschen') + '</button>'
      +   '</div>'
      + '</div></div>';
    document.body.appendChild(overlay);
    var close = function () { _removeEl(overlay); _dropCleanupHints(); if (_container) render(); };
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) { close(); return; }
      var btn = e.target.closest('[data-x]');
      if (!btn) return;
      var act = btn.dataset.x;
      if (act === 'close') { close(); return; }
      if (act === 'pdf' || act === 'csv') {
        if (act === 'pdf') _printMany(cols);
        else _downloadCsv('Listen_bis_' + _todayIso(), [MISSING_CSV_HEAD].concat([].concat.apply([], cols.map(_missingCsvLines))));
        overlay.querySelector('[data-x-saved]').hidden = false;
        return;
      }
      if (act === 'keep') { _keepLonger(cols); close(); return; }
      if (act === 'delete') {
        if (!confirm((cols.length === 1 ? 'Die Liste' : 'Alle ' + cols.length + ' Listen') + ' endgültig löschen? Das geht nicht rückgängig – hast du sie gesichert?')) return;
        cols.forEach(function (c) { delete _data[c.id]; });
        if (_activeId && !_data[_activeId]) _activeId = null;
        _save();
        close();
      }
    });
  }

  function _updateSidebarProgress(colId) {
    var btn = _container.querySelector('[data-col-id="' + colId + '"]');
    if (!btn) return;
    var col = _data[colId];
    var p = _progress(col);
    var pct = p.total ? Math.round(p.done/p.total*100) : 0;
    var fill = btn.querySelector('.col-progress-fill');
    var text = btn.querySelector('.col-progress-text');
    if (fill) {
      fill.style.width = pct + '%';
      fill.classList.toggle('is-complete', !!p.total && p.done === p.total);
    }
    if (text) text.textContent = p.done + '/' + p.total;
  }

  // ── Event Binding ─────────────────────────────────────────────────────────
  // Bound once per container: render() replaces the inner HTML, the listeners stay.
  function _bindEvents() {
    if (!_container || _container.dataset.colBound) return;
    _container.dataset.colBound = '1';

    _container.addEventListener('click', function(e) {
      var colBtn = e.target.closest('.col-item-btn');
      if (colBtn) { _activeId = colBtn.dataset.colId; _editReasons = false; render(); return; }
      var miss = e.target.closest('[data-miss]');
      if (miss) { _toggleMiss(_activeId, miss.dataset.miss); return; }
      var reason = e.target.closest('[data-reason]');
      if (reason) { _setReason(_activeId, reason.dataset.reason); return; }

      var action = e.target.closest('[data-action]');
      if (!action) return;
      var act = action.dataset.action;
      if (act === 'new-col')      { _showNewDialog(); return; }
      if (act === 'toggle-archive') { _showArchive = !_showArchive; render(); return; }
      if (act === 'archive')      { _archiveCol(_activeId, true); return; }
      if (act === 'unarchive')    { _archiveCol(_activeId, false); return; }
      if (act === 'delete-col')   { _deleteCol(_activeId); return; }
      if (act === 'export-col')   { _exportCol(_activeId); return; }
      if (act === 'print-col')    { _printCol(_activeId); return; }
      if (act === 'mark-all')     { _markAll(_activeId, true); return; }
      if (act === 'clear-all')    { _markAll(_activeId, false); return; }
      if (act === 'clear-miss')   { _clearMiss(_activeId); return; }
      if (act === 'keep-col')     { if (_data[_activeId]) { _keepLonger([_data[_activeId]]); render(); _dropCleanupHints(); } return; }
      if (act === 'repeat-col')   { _repeatCol(_activeId); return; }
      if (act === 'save-reasons') { _saveReasons(_activeId); return; }
      if (act === 'edit-reasons') {
        _editReasons = !_editReasons;
        render();
        var input = _container.querySelector('[data-reasons-input]');
        if (input) input.focus();
        return;
      }
    });

    _container.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && e.target.hasAttribute('data-reasons-input')) { e.preventDefault(); _saveReasons(_activeId); }
      if (e.key === 'Escape' && e.target.hasAttribute('data-reasons-input')) { _editReasons = false; render(); }
    });

    _container.addEventListener('change', function(e) {
      if (e.target.classList.contains('col-checkbox')) {
        _setCheck(_activeId, e.target.dataset.sid, e.target.checked);
      }
    });

    _container.addEventListener('input', function(e) {
      if (e.target.classList.contains('col-note-input')) {
        _setNote(_activeId, e.target.dataset.sid, e.target.value);
      }
    });
  }

  function _removeEl(el) { if (el && el.parentNode) el.parentNode.removeChild(el); }

  // ── Public ────────────────────────────────────────────────────────────────
  function init(container) { _container = container; _load(); render(); }

  // The reminder on „Heute“ opens the clean-up dialog.
  if (typeof document !== 'undefined') {
    document.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('[data-col-cleanup]')) { e.preventDefault(); e.stopPropagation(); openCleanup(); }
    }, true);
  }

  /** Open collections with progress, nearest due date first (for „Heute wichtig“). */
  function summary() {
    _load();
    return _sortedCollections().filter(function (c) { return !c.archived && c.type !== MISSING; }).map(function (c) {
      var p = _progress(c);
      return { id: c.id, title: c.title, classIds: c.classIds.slice(), dueDate: c.dueDate || '', done: p.done, total: p.total };
    }).filter(function (c) { return c.total > 0 && c.done < c.total; }).sort(function (a, b) {
      return (a.dueDate || '9999').localeCompare(b.dueDate || '9999');
    });
  }

  /** „Wer hat es nicht?“ lists past their keeping time (reminder on „Heute“). */
  function expired() {
    _load();
    return _expiredLists().map(function (c) { return { id: c.id, title: c.title, classIds: c.classIds.slice(), date: c.date, deleteOn: c.deleteOn }; });
  }

  /** Show this collection when the tab is opened next. */
  function select(id) { _activeId = id; }

  return { init: init, render: render, summary: summary, select: select, expired: expired, openCleanup: openCleanup };
})();

if (typeof window !== 'undefined') window.LehrerCollections = LehrerCollections;
