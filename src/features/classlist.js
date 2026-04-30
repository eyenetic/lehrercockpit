/**
 * src/features/classlist.js — Klassenlisten & Einsammlungen
 *
 * Verwaltung von Schülerlisten pro Klasse:
 *   - Import via CSV oder Excel (.xlsx) mit Vorschau
 *   - Inline-Bearbeitung (hinzufügen, umbenennen, löschen)
 *   - Speicherung in localStorage
 *   - Basis für spätere Einsammel-Funktion
 *
 * Datenstruktur (localStorage "lehrerCockpit.classLists"):
 *   {
 *     "8a": { id: "8a", students: [{ id, lastName, firstName }, ...] },
 *     ...
 *   }
 *
 * Exports (window.LehrerClasslist):
 *   init, render, getClassLists, getStudentsForClass
 */
var LehrerClasslist = (function () {
  'use strict';

  var STORAGE_KEY = 'lehrerCockpit.classLists';

  // ── State ────────────────────────────────────────────────────────────────
  var _container = null;
  var _data = {};          // { classId: { id, students: [{id, lastName, firstName}] } }
  var _activeClass = null; // currently selected class id
  var _importPreview = null; // pending import rows before confirmation

  // ── Persistence ──────────────────────────────────────────────────────────
  function _load() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      _data = raw ? JSON.parse(raw) : {};
    } catch (e) {
      _data = {};
    }
  }

  function _save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(_data));
    } catch (e) { /* quota */ }
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
  function _uid() {
    return Math.random().toString(36).slice(2, 10);
  }

  function _sortedClasses() {
    return Object.keys(_data).sort(function (a, b) {
      return a.localeCompare(b, 'de', { numeric: true });
    });
  }

  function _sortedStudents(classId) {
    var cls = _data[classId];
    if (!cls) return [];
    return cls.students.slice().sort(function (a, b) {
      var ln = (a.lastName || '').localeCompare(b.lastName || '', 'de');
      if (ln !== 0) return ln;
      return (a.firstName || '').localeCompare(b.firstName || '', 'de');
    });
  }

  function _studentCount(classId) {
    return (_data[classId] && _data[classId].students) ? _data[classId].students.length : 0;
  }

  // ── CSV / Excel Parsing ───────────────────────────────────────────────────
  /**
   * Parse CSV text → array of { lastName, firstName }
   * Supports: "Nachname,Vorname" or "Nachname Vorname" or just "Name"
   */
  function _parseCSV(text) {
    var lines = text.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    var result = [];
    // detect delimiter
    var delim = lines[0] && lines[0].includes(';') ? ';' : ',';

    lines.forEach(function (line, idx) {
      // skip header if first line looks like it
      if (idx === 0 && /nachname|vorname|name|schüler/i.test(line)) return;

      var parts = line.split(delim).map(function (p) { return p.trim().replace(/^"|"$/g, ''); });
      if (parts.length >= 2) {
        result.push({ lastName: parts[0], firstName: parts[1] });
      } else if (parts.length === 1 && parts[0]) {
        // single column: "Nachname Vorname" → split on last space
        var space = parts[0].lastIndexOf(' ');
        if (space > 0) {
          result.push({ lastName: parts[0].slice(0, space), firstName: parts[0].slice(space + 1) });
        } else {
          result.push({ lastName: parts[0], firstName: '' });
        }
      }
    });
    return result;
  }

  /**
   * Parse Excel file using SheetJS (XLSX global).
   * Returns Promise<{ className: string|null, rows: [{lastName, firstName}] }>
   */
  function _parseExcel(file) {
    return new Promise(function (resolve, reject) {
      if (typeof XLSX === 'undefined') {
        reject(new Error('SheetJS nicht geladen'));
        return;
      }
      var reader = new FileReader();
      reader.onload = function (e) {
        try {
          var wb = XLSX.read(e.target.result, { type: 'array' });
          var sheet = wb.Sheets[wb.SheetNames[0]];
          var rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });
          var result = [];
          var detectedClass = null;

          rows.forEach(function (row, idx) {
            // Try to detect class name from header
            if (idx === 0) {
              var joined = row.join(' ').toLowerCase();
              if (/nachname|vorname|name|schüler/i.test(joined)) return; // skip header row
              // Check if a cell matches class pattern like "8a", "Q1"
              row.forEach(function (cell) {
                if (!detectedClass && /^\d+[a-z]$/i.test(String(cell).trim())) {
                  detectedClass = String(cell).trim();
                }
              });
            }
            if (idx === 0 && /nachname|vorname|name/i.test(row.join(' '))) return;

            var cols = row.map(function (c) { return String(c).trim(); });
            if (cols.length >= 2 && (cols[0] || cols[1])) {
              result.push({ lastName: cols[0], firstName: cols[1] });
            } else if (cols.length === 1 && cols[0]) {
              var space = cols[0].lastIndexOf(' ');
              if (space > 0) {
                result.push({ lastName: cols[0].slice(0, space), firstName: cols[0].slice(space + 1) });
              } else {
                result.push({ lastName: cols[0], firstName: '' });
              }
            }
          });
          resolve({ className: detectedClass, rows: result });
        } catch (err) {
          reject(err);
        }
      };
      reader.onerror = reject;
      reader.readAsArrayBuffer(file);
    });
  }

  // ── Render ───────────────────────────────────────────────────────────────
  function render() {
    if (!_container) return;
    _load();

    var classes = _sortedClasses();
    if (!_activeClass || !_data[_activeClass]) {
      _activeClass = classes[0] || null;
    }

    _container.innerHTML = _buildHTML(classes);
    _bindEvents();
  }

  function _buildHTML(classes) {
    return [
      '<div class="classlist-layout">',
        _buildSidebar(classes),
        '<div class="classlist-main">',
          _activeClass ? _buildStudentPanel(_activeClass) : _buildEmptyState(),
        '</div>',
      '</div>',
    ].join('');
  }

  function _buildSidebar(classes) {
    var items = classes.map(function (id) {
      var active = id === _activeClass ? ' active' : '';
      var n = _studentCount(id);
      return '<button class="classlist-class-btn' + active + '" data-class-id="' + id + '" type="button">'
        + '<span class="classlist-class-name">' + _esc(id) + '</span>'
        + '<span class="classlist-class-count">' + n + '</span>'
        + '</button>';
    }).join('');

    return '<aside class="classlist-sidebar">'
      + '<div class="classlist-sidebar-head">'
      +   '<h2 class="classlist-sidebar-title">Klassen</h2>'
      +   '<button class="classlist-add-class-btn icon-btn" type="button" title="Neue Klasse" data-action="add-class">＋</button>'
      + '</div>'
      + '<div class="classlist-class-list">' + (items || '<p class="classlist-empty-hint">Noch keine Klassen</p>') + '</div>'
      + '</aside>';
  }

  function _buildStudentPanel(classId) {
    var students = _sortedStudents(classId);
    var count = students.length;

    var rows = students.map(function (s) {
      return '<li class="classlist-student-row" data-student-id="' + s.id + '">'
        + '<span class="classlist-student-name">'
        +   '<span class="classlist-student-ln" data-field="lastName">' + _esc(s.lastName) + '</span>'
        +   '<span class="classlist-student-fn" data-field="firstName">' + _esc(s.firstName) + '</span>'
        + '</span>'
        + '<span class="classlist-student-actions">'
        +   '<button class="classlist-student-edit icon-btn-sm" type="button" data-action="edit-student" title="Bearbeiten">✎</button>'
        +   '<button class="classlist-student-delete icon-btn-sm classlist-delete-btn" type="button" data-action="delete-student" title="Löschen">✕</button>'
        + '</span>'
        + '</li>';
    }).join('');

    return '<div class="classlist-panel">'
      + '<div class="classlist-panel-head">'
      +   '<div>'
      +     '<h2 class="classlist-panel-title">Klasse ' + _esc(classId) + '</h2>'
      +     '<p class="classlist-panel-count">' + count + ' Schüler</p>'
      +   '</div>'
      +   '<div class="classlist-panel-actions">'
      +     '<button class="btn btn-sm btn-secondary" type="button" data-action="import">📥 Import</button>'
      +     '<button class="btn btn-sm btn-secondary" type="button" data-action="export-csv">📤 CSV</button>'
      +     '<button class="btn btn-sm btn-primary" type="button" data-action="add-student">+ Schüler</button>'
      +     '<button class="btn btn-sm btn-danger" type="button" data-action="delete-class">Klasse löschen</button>'
      +   '</div>'
      + '</div>'
      + '<ul class="classlist-student-list">' + (rows || '<li class="classlist-empty-hint">Noch keine Schüler – importieren oder manuell hinzufügen.</li>') + '</ul>'
      + '</div>';
  }

  function _buildEmptyState() {
    return '<div class="classlist-empty-state">'
      + '<div class="classlist-empty-icon">📋</div>'
      + '<h2>Noch keine Klassen</h2>'
      + '<p>Lege eine neue Klasse an oder importiere eine Schülerliste als CSV oder Excel-Datei.</p>'
      + '<button class="btn btn-primary" type="button" data-action="add-class">Erste Klasse anlegen</button>'
      + '</div>';
  }

  // ── Import Modal ──────────────────────────────────────────────────────────
  function _showImportModal(targetClassId) {
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay classlist-import-overlay';
    overlay.innerHTML = [
      '<div class="modal classlist-import-modal">',
        '<div class="modal-header">',
          '<span class="modal-title">Schülerliste importieren</span>',
          '<button class="modal-close" type="button" data-action="close-import">✕</button>',
        '</div>',
        '<div class="classlist-import-body">',
          '<p class="classlist-import-hint">CSV oder Excel-Datei auswählen.<br>',
          'Erwartet: <code>Nachname, Vorname</code> (mit Komma oder Semikolon getrennt)</p>',
          '<label class="classlist-upload-area" for="classlist-file-input">',
            '<span class="classlist-upload-icon">📂</span>',
            '<span>Datei auswählen oder hierher ziehen</span>',
            '<input type="file" id="classlist-file-input" accept=".csv,.xlsx,.xls" style="display:none">',
          '</label>',
          '<div id="classlist-import-preview" class="classlist-import-preview" style="display:none">',
            '<div class="classlist-import-preview-head">',
              '<span id="classlist-preview-count"></span>',
              '<label class="classlist-import-class-label">Klasse:',
                '<input id="classlist-import-class-input" class="classlist-import-class-input" type="text" placeholder="z.B. 8a" />',
              '</label>',
            '</div>',
            '<ul id="classlist-preview-list" class="classlist-preview-list"></ul>',
          '</div>',
          '<div class="classlist-import-footer">',
            '<button class="btn btn-secondary" type="button" data-action="close-import">Abbrechen</button>',
            '<button class="btn btn-primary" type="button" id="classlist-import-confirm" disabled data-action="confirm-import">Importieren</button>',
          '</div>',
        '</div>',
      '</div>',
    ].join('');

    document.body.appendChild(overlay);

    // pre-fill class
    var classInput = overlay.querySelector('#classlist-import-class-input');
    if (targetClassId) classInput.value = targetClassId;

    // File input
    var fileInput = overlay.querySelector('#classlist-file-input');
    var uploadArea = overlay.querySelector('.classlist-upload-area');

    uploadArea.addEventListener('click', function () { fileInput.click(); });
    uploadArea.addEventListener('dragover', function (e) { e.preventDefault(); uploadArea.classList.add('drag-over'); });
    uploadArea.addEventListener('dragleave', function () { uploadArea.classList.remove('drag-over'); });
    uploadArea.addEventListener('drop', function (e) {
      e.preventDefault();
      uploadArea.classList.remove('drag-over');
      var f = e.dataTransfer.files[0];
      if (f) _handleImportFile(f, overlay);
    });
    fileInput.addEventListener('change', function () {
      if (fileInput.files[0]) _handleImportFile(fileInput.files[0], overlay);
    });

    // Close
    overlay.addEventListener('click', function (e) {
      var action = e.target.closest('[data-action]');
      if (!action) return;
      if (action.dataset.action === 'close-import') { _closeImportModal(overlay); }
      if (action.dataset.action === 'confirm-import') { _confirmImport(overlay); }
    });
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) _closeImportModal(overlay);
    });
  }

  function _closeImportModal(overlay) {
    _importPreview = null;
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
  }

  function _handleImportFile(file, overlay) {
    var isExcel = /\.xlsx?$/i.test(file.name);
    var preview = overlay.querySelector('#classlist-import-preview');
    var previewList = overlay.querySelector('#classlist-preview-list');
    var previewCount = overlay.querySelector('#classlist-preview-count');
    var confirmBtn = overlay.querySelector('#classlist-import-confirm');
    var classInput = overlay.querySelector('#classlist-import-class-input');

    function _showRows(rows, detectedClass) {
      if (detectedClass && !classInput.value) classInput.value = detectedClass;
      _importPreview = rows.filter(function (r) { return r.lastName || r.firstName; });
      previewCount.textContent = _importPreview.length + ' Schüler gefunden';
      previewList.innerHTML = _importPreview.slice(0, 8).map(function (r) {
        return '<li>' + _esc(r.lastName) + (r.firstName ? ', ' + _esc(r.firstName) : '') + '</li>';
      }).join('') + (_importPreview.length > 8 ? '<li class="classlist-preview-more">… und ' + (_importPreview.length - 8) + ' weitere</li>' : '');
      preview.style.display = '';
      confirmBtn.disabled = _importPreview.length === 0;
    }

    if (isExcel) {
      _parseExcel(file).then(function (result) {
        _showRows(result.rows, result.className);
      }).catch(function (err) {
        previewCount.textContent = 'Fehler beim Lesen: ' + err.message;
        preview.style.display = '';
      });
    } else {
      var reader = new FileReader();
      reader.onload = function (e) {
        var rows = _parseCSV(e.target.result);
        _showRows(rows, null);
      };
      reader.readAsText(file, 'UTF-8');
    }
  }

  function _confirmImport(overlay) {
    if (!_importPreview || !_importPreview.length) return;
    var classInput = overlay.querySelector('#classlist-import-class-input');
    var classId = (classInput.value || '').trim();
    if (!classId) {
      classInput.focus();
      classInput.classList.add('input-error');
      return;
    }
    classId = classId.toLowerCase();

    if (!_data[classId]) {
      _data[classId] = { id: classId, students: [] };
    }

    var existing = _data[classId].students;
    var added = 0;
    _importPreview.forEach(function (r) {
      // avoid strict duplicates
      var dup = existing.some(function (s) {
        return s.lastName.toLowerCase() === (r.lastName || '').toLowerCase()
          && s.firstName.toLowerCase() === (r.firstName || '').toLowerCase();
      });
      if (!dup) {
        existing.push({ id: _uid(), lastName: r.lastName || '', firstName: r.firstName || '' });
        added++;
      }
    });

    _save();
    _activeClass = classId;
    _closeImportModal(overlay);
    render();
  }

  // ── Add/Edit/Delete ───────────────────────────────────────────────────────
  function _showAddClassDialog() {
    var name = window.prompt('Name der neuen Klasse (z.B. 8a, Q1):');
    if (!name) return;
    var id = name.trim().toLowerCase();
    if (!id) return;
    if (_data[id]) { alert('Diese Klasse existiert bereits.'); return; }
    _data[id] = { id: id, students: [] };
    _save();
    _activeClass = id;
    render();
  }

  function _showAddStudentDialog(classId) {
    var ln = window.prompt('Nachname:');
    if (ln === null) return;
    var fn = window.prompt('Vorname:');
    if (fn === null) return;
    _data[classId].students.push({ id: _uid(), lastName: ln.trim(), firstName: fn.trim() });
    _save();
    render();
  }

  function _showEditStudentDialog(classId, studentId) {
    var cls = _data[classId];
    if (!cls) return;
    var s = cls.students.find(function (x) { return x.id === studentId; });
    if (!s) return;
    var ln = window.prompt('Nachname:', s.lastName);
    if (ln === null) return;
    var fn = window.prompt('Vorname:', s.firstName);
    if (fn === null) return;
    s.lastName = ln.trim();
    s.firstName = fn.trim();
    _save();
    render();
  }

  function _deleteStudent(classId, studentId) {
    var cls = _data[classId];
    if (!cls) return;
    cls.students = cls.students.filter(function (s) { return s.id !== studentId; });
    _save();
    render();
  }

  function _deleteClass(classId) {
    var n = _studentCount(classId);
    var msg = 'Klasse "' + classId + '" mit ' + n + ' Schüler(n) wirklich löschen?';
    if (!window.confirm(msg)) return;
    delete _data[classId];
    _save();
    var classes = _sortedClasses();
    _activeClass = classes[0] || null;
    render();
  }

  // ── CSV Export ────────────────────────────────────────────────────────────
  function _exportCSV(classId) {
    var students = _sortedStudents(classId);
    var lines = ['Nachname,Vorname'].concat(students.map(function (s) {
      return '"' + (s.lastName || '').replace(/"/g, '""') + '","' + (s.firstName || '').replace(/"/g, '""') + '"';
    }));
    var blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'klasse-' + classId + '.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Event Binding ─────────────────────────────────────────────────────────
  function _bindEvents() {
    if (!_container) return;

    // Class selection
    _container.addEventListener('click', function (e) {
      var classBtn = e.target.closest('.classlist-class-btn');
      if (classBtn) {
        _activeClass = classBtn.dataset.classId;
        render();
        return;
      }

      var action = e.target.closest('[data-action]');
      if (!action) return;
      var act = action.dataset.action;

      if (act === 'add-class') { _showAddClassDialog(); return; }
      if (act === 'import') { _showImportModal(_activeClass); return; }
      if (act === 'export-csv') { _exportCSV(_activeClass); return; }
      if (act === 'add-student') { _showAddStudentDialog(_activeClass); return; }
      if (act === 'delete-class') { _deleteClass(_activeClass); return; }

      if (act === 'edit-student') {
        var row = action.closest('[data-student-id]');
        if (row) _showEditStudentDialog(_activeClass, row.dataset.studentId);
        return;
      }
      if (act === 'delete-student') {
        var row = action.closest('[data-student-id]');
        if (row) _deleteStudent(_activeClass, row.dataset.studentId);
        return;
      }
    });
  }

  // ── Escape helper ─────────────────────────────────────────────────────────
  function _esc(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Public API ────────────────────────────────────────────────────────────
  function init(container) {
    _container = container;
    _load();
    render();
  }

  function getClassLists() {
    _load();
    return _data;
  }

  function getStudentsForClass(classId) {
    _load();
    return _sortedStudents(classId);
  }

  return {
    init: init,
    render: render,
    getClassLists: getClassLists,
    getStudentsForClass: getStudentsForClass,
  };
})();

if (typeof window !== 'undefined') window.LehrerClasslist = LehrerClasslist;
