/**
 * src/features/collections.js — Einsammlungen
 *
 * Digitale Einsammel-Listen (Unterschriften, Geld, Dokumente, …)
 * basierend auf den Klassenlisten aus classlist.js.
 *
 * Datenstruktur (localStorage "lehrerCockpit.collections"):
 *   {
 *     "col_abc": {
 *       id, title, type, note, classIds, dueDate, createdAt,
 *       archived,
 *       checks: { studentId: { done: bool, note: string } }
 *     }
 *   }
 *
 * Exports (window.LehrerCollections): init, render
 */
var LehrerCollections = (function () {
  'use strict';

  var STORAGE_KEY  = 'lehrerCockpit.collections';
  var TYPES = [
    { value: 'signature', label: '✍️  Unterschrift' },
    { value: 'money',     label: '💰 Geld' },
    { value: 'document',  label: '📄 Dokument' },
    { value: 'other',     label: '📦 Sonstiges' },
  ];

  var _container   = null;
  var _data        = {};
  var _activeId    = null;
  var _showArchive = false;

  // ── Persistence ──────────────────────────────────────────────────────────
  function _load() {
    try { _data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); }
    catch(e) { _data = {}; }
  }
  function _save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(_data)); } catch(e) {}
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function _uid() { return 'col_' + Math.random().toString(36).slice(2, 10); }
  function _esc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function _typeLabel(v) {
    var t = TYPES.find(function(x){ return x.value === v; });
    return t ? t.label : v;
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
    var done  = students.filter(function(s){ return col.checks && col.checks[s.id] && col.checks[s.id].done; }).length;
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
        +   '<span class="col-progress-bar"><span class="col-progress-fill" style="width:' + pct + '%"></span></span>'
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

  function _buildChecklist(col) {
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
      ? '<button class="btn btn-sm btn-secondary" type="button" data-action="unarchive">♻️ Reaktivieren</button>'
      : '<button class="btn btn-sm btn-secondary" type="button" data-action="archive">📦 Archivieren</button>';

    return '<div class="col-panel">'
      + '<div class="col-panel-head">'
      +   '<div class="col-panel-title-block">'
      +     '<h2 class="col-panel-title">' + _esc(col.title) + '</h2>'
      +     '<p class="col-panel-meta">'
      +       _typeLabel(col.type) + ' · Klasse ' + _esc(col.classIds.join(', '))
      +       (col.dueDate ? ' · Fällig: ' + _formatDate(col.dueDate) : '')
      +       (col.note ? ' · ' + _esc(col.note) : '')
      +     '</p>'
      +   '</div>'
      +   '<div class="col-panel-actions">'
      +     '<span class="col-panel-progress">' + p.done + ' von ' + p.total + ' (' + pct + '%)</span>'
      +     '<button class="btn btn-sm btn-secondary" type="button" data-action="export-col">📤 Export</button>'
      +     archBtn
      +     '<button class="btn btn-sm btn-danger" type="button" data-action="delete-col">Löschen</button>'
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
      + '<div class="classlist-empty-icon">📥</div>'
      + '<h2>Noch keine Einsammlungen</h2>'
      + '<p>Erstelle eine neue Einsammlung – Schüler werden automatisch aus den Klassenlisten geladen.</p>'
      + '<button class="btn btn-primary" type="button" data-action="new-col">Erste Einsammlung erstellen</button>'
      + '</div>';
  }

  function _missingLabel(col) {
    var students = _getStudentsForCollection(col);
    var missing = students.filter(function(s){ return !(col.checks && col.checks[s.classId+'|'+s.id] && col.checks[s.classId+'|'+s.id].done); });
    if (!missing.length) return '✅ Alle abgegeben!';
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

    var classOptions = classes.map(function(c) {
      return '<label class="col-class-check"><input type="checkbox" value="' + _esc(c) + '"> ' + _esc(c) + '</label>';
    }).join('');

    var typeOptions = TYPES.map(function(t) {
      return '<option value="' + t.value + '">' + t.label + '</option>';
    }).join('');

    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = [
      '<div class="modal" style="width:min(480px,95vw)">',
        '<div class="modal-header">',
          '<span class="modal-title">Neue Einsammlung</span>',
          '<button class="modal-close" type="button" data-action="close">✕</button>',
        '</div>',
        '<div style="padding:16px 20px 20px;display:flex;flex-direction:column;gap:14px;">',
          '<label class="col-form-label">Titel<input class="col-form-input" type="text" id="col-new-title" placeholder="z.B. Geld Klassenfahrt" autocomplete="off"></label>',
          '<label class="col-form-label">Art',
            '<select class="col-form-input" id="col-new-type">' + typeOptions + '</select>',
          '</label>',
          '<div class="col-form-label">Klasse(n) *',
            '<div class="col-class-checks">' + (classOptions || '<p class="classlist-empty-hint">Zuerst Klassen anlegen.</p>') + '</div>',
          '</div>',
          '<label class="col-form-label">Fälligkeit (optional)<input class="col-form-input" type="date" id="col-new-due"></label>',
          '<label class="col-form-label">Notiz (optional)<input class="col-form-input" type="text" id="col-new-note" placeholder="z.B. 15 €" autocomplete="off"></label>',
          '<div style="display:flex;justify-content:flex-end;gap:8px;margin-top:4px;">',
            '<button class="btn btn-secondary" type="button" data-action="close">Abbrechen</button>',
            '<button class="btn btn-primary" type="button" data-action="create">Erstellen</button>',
          '</div>',
        '</div>',
      '</div>',
    ].join('');

    document.body.appendChild(overlay);

    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) { _removeEl(overlay); return; }
      var action = e.target.closest('[data-action]');
      if (!action) return;
      if (action.dataset.action === 'close') { _removeEl(overlay); return; }
      if (action.dataset.action === 'create') {
        var title = overlay.querySelector('#col-new-title').value.trim();
        if (!title) { overlay.querySelector('#col-new-title').focus(); return; }
        var type  = overlay.querySelector('#col-new-type').value;
        var due   = overlay.querySelector('#col-new-due').value;
        var note  = overlay.querySelector('#col-new-note').value.trim();
        var classIds = Array.from(overlay.querySelectorAll('.col-class-check input:checked')).map(function(cb){ return cb.value; });
        if (!classIds.length) { alert('Bitte mindestens eine Klasse auswählen.'); return; }
        var id = _uid();
        _data[id] = { id: id, title: title, type: type, note: note, classIds: classIds, dueDate: due, createdAt: new Date().toISOString(), archived: false, checks: {} };
        _save();
        _activeId = id;
        _removeEl(overlay);
        render();
      }
    });
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
    // update sidebar progress
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

  function _archiveCol(colId, archived) {
    if (_data[colId]) { _data[colId].archived = archived; _save(); render(); }
  }

  function _deleteCol(colId) {
    var col = _data[colId];
    if (!col) return;
    if (!confirm('Einsammlung "' + col.title + '" wirklich löschen?')) return;
    delete _data[colId];
    _save();
    _activeId = null;
    render();
  }

  function _exportCol(colId) {
    var col = _data[colId];
    if (!col) return;
    var students = _getStudentsForCollection(col);
    var lines = ['Klasse,Nachname,Vorname,Abgegeben,Notiz'];
    students.forEach(function(s) {
      var sid = s.classId+'|'+s.id;
      var c = col.checks && col.checks[sid] || {};
      lines.push([s.classId, s.lastName, s.firstName, c.done?'Ja':'Nein', c.note||''].map(function(v){ return '"'+String(v).replace(/"/g,'""')+'"'; }).join(','));
    });
    var blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a'); a.href = url; a.download = col.title.replace(/[^a-z0-9äöü]/gi,'_') + '.csv'; a.click();
    URL.revokeObjectURL(url);
  }

  function _updateSidebarProgress(colId) {
    var btn = _container.querySelector('[data-col-id="' + colId + '"]');
    if (!btn) return;
    var col = _data[colId];
    var p = _progress(col);
    var pct = p.total ? Math.round(p.done/p.total*100) : 0;
    var fill = btn.querySelector('.col-progress-fill');
    var text = btn.querySelector('.col-progress-text');
    if (fill) fill.style.width = pct + '%';
    if (text) text.textContent = p.done + '/' + p.total;
  }

  // ── Event Binding ─────────────────────────────────────────────────────────
  function _bindEvents() {
    if (!_container) return;

    _container.addEventListener('click', function(e) {
      var colBtn = e.target.closest('.col-item-btn');
      if (colBtn) { _activeId = colBtn.dataset.colId; render(); return; }

      var action = e.target.closest('[data-action]');
      if (!action) return;
      var act = action.dataset.action;
      if (act === 'new-col')      { _showNewDialog(); return; }
      if (act === 'toggle-archive') { _showArchive = !_showArchive; render(); return; }
      if (act === 'archive')      { _archiveCol(_activeId, true); return; }
      if (act === 'unarchive')    { _archiveCol(_activeId, false); return; }
      if (act === 'delete-col')   { _deleteCol(_activeId); return; }
      if (act === 'export-col')   { _exportCol(_activeId); return; }
      if (act === 'mark-all')     { _markAll(_activeId, true); return; }
      if (act === 'clear-all')    { _markAll(_activeId, false); return; }
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

  return { init: init, render: render };
})();

if (typeof window !== 'undefined') window.LehrerCollections = LehrerCollections;
