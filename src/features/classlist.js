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
  var _importOrder = 'last-first'; // how "Anna Müller" vs "Müller Anna" is read

  // ── Persistence ──────────────────────────────────────────────────────────
  function _load() {
    var raw;
    try {
      raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch (e) {
      raw = {};
    }
    // Stored data may come from older versions or another device: keep what
    // is usable instead of letting one odd entry break the page.
    _data = {};
    Object.keys(raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}).forEach(function (classId) {
      var cls = raw[classId];
      var students = Array.isArray(cls) ? cls : (cls && Array.isArray(cls.students) ? cls.students : null);
      if (!students) return;
      _data[classId] = Object.assign({}, Array.isArray(cls) ? {} : cls, {
        id: classId,
        students: students.filter(function (st) { return st && typeof st === 'object' && st.id; }).map(function (st) {
          return Object.assign({}, st, { lastName: String(st.lastName || ''), firstName: String(st.firstName || '') });
        }),
      });
    });
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
   * Splits one name into { lastName, firstName }.
   * order: 'last-first' ("Müller Anna Lena") or 'first-last' ("Anna Lena Müller").
   * Tabs, ";" and "," separate columns ("Müller<TAB>Anna", "Müller, Anna");
   * leading numbers ("1.", "12)") are dropped.
   */
  function _splitName(text, order) {
    var line = String(text || '').replace(/\u00a0/g, ' ').trim().replace(/^\d+[.)]?\s+/, '');
    var parts = null;
    if (line.indexOf('\t') !== -1) parts = line.split('\t');
    else if (line.indexOf(';') !== -1) parts = line.split(';');
    else if (line.indexOf(',') !== -1) parts = line.split(',');
    if (parts) {
      parts = parts.map(function (p) { return p.trim().replace(/^"|"$/g, '').trim(); }).filter(Boolean);
      if (parts.length > 2 && /^\d+$/.test(parts[0])) parts.shift();  // "Nr<TAB>Nachname<TAB>Vorname"
      if (parts.length >= 2) {
        return order === 'first-last'
          ? { lastName: parts[1], firstName: parts[0] }
          : { lastName: parts[0], firstName: parts[1] };
      }
      line = parts[0] || '';
    }
    var words = line.split(/\s+/).filter(Boolean);
    if (words.length < 2) return { lastName: words[0] || '', firstName: '' };
    return order === 'first-last'
      ? { lastName: words[words.length - 1], firstName: words.slice(0, -1).join(' ') }
      : { lastName: words[0], firstName: words.slice(1).join(' ') };
  }

  /**
   * Parse pasted text or CSV → array of { lastName, firstName }.
   * Every line is read on its own (a list may mix "Müller, Anna" and table rows).
   */
  function _parseCSV(text, order) {
    var lines = String(text || '').split(/\r?\n/).filter(function (l) { return l.trim(); });
    var result = [];
    lines.forEach(function (line, idx) {
      if (idx === 0 && /nachname|vorname|schüler|^\s*name\s*$/i.test(line)) return;  // header row
      var name = _splitName(line, order);
      if (name.lastName || name.firstName) result.push(name);
    });
    return result;
  }

  /**
   * Parse Excel file using SheetJS (XLSX global).
   * Returns Promise<{ className: string|null, rows: [{lastName, firstName}] }>
   */
  // SheetJS (~1 MB) is only needed for Excel imports – loaded on first use
  // instead of blocking every page load.
  var XLSX_SRC = 'https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js';
  var _xlsxLoading = null;
  function _loadXlsx() {
    if (typeof XLSX !== 'undefined') return Promise.resolve();
    if (!_xlsxLoading) {
      _xlsxLoading = new Promise(function (resolve, reject) {
        var script = document.createElement('script');
        script.src = XLSX_SRC;
        script.onload = function () { resolve(); };
        script.onerror = function () { _xlsxLoading = null; reject(new Error('Excel-Leser konnte nicht geladen werden.')); };
        document.head.appendChild(script);
      });
    }
    return _xlsxLoading;
  }

  function _parseExcel(file) {
    return _loadXlsx().then(function () { return _readExcel(file); });
  }

  function _readExcel(file) {
    return new Promise(function (resolve, reject) {
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
      +     '<p class="classlist-panel-count">' + count + (count === 1 ? ' Schüler:in' : ' Schüler:innen') + '</p>'
      +   '</div>'
      +   '<div class="classlist-panel-actions action-row">'
      +     '<button class="btn btn-sm btn-secondary" type="button" data-action="import">Importieren</button>'
      +     '<button class="btn btn-sm btn-secondary" type="button" data-action="print-list"' + (count ? '' : ' disabled') + ' title="Namensliste mit leeren Spalten – drucken oder als PDF sichern">PDF-Liste</button>'
      +     '<details class="more-menu"><summary class="btn btn-sm btn-secondary" aria-label="Weitere Aktionen">⋯</summary>'
      +       '<div class="more-menu-list" role="menu">'
      +         (count ? '<button type="button" role="menuitem" data-action="fix-names">Vor- und Nachnamen bearbeiten …</button>' : '')
      +         '<button type="button" role="menuitem" data-action="export-csv"' + (count ? '' : ' disabled') + '>Als CSV speichern</button>'
      +         '<button type="button" role="menuitem" class="is-danger" data-action="delete-class">Klasse löschen …</button>'
      +       '</div>'
      +     '</details>'
      +   '</div>'
      + '</div>'
      + '<form class="classlist-add-form" data-add-student-form autocomplete="off">'
      +   '<input class="form-input" name="lastName" placeholder="Nachname" aria-label="Nachname" required />'
      +   '<input class="form-input" name="firstName" placeholder="Vorname" aria-label="Vorname" />'
      +   '<button class="btn btn-primary btn-sm" type="submit">Hinzufügen</button>'
      + '</form>'
      + '<p class="classlist-add-hint">Enter fügt hinzu – danach gleich den nächsten Namen tippen. Mehrere auf einmal: „Importieren“.</p>'
      + '<p class="classlist-add-feedback" data-add-feedback role="status"></p>'
      + (_needsSplit(classId).length
          ? '<div class="seat-banner is-warn"><span>Bei ' + _needsSplit(classId).length + ' Namen steht alles im Nachnamen.</span>'
            + '<button class="btn btn-sm btn-secondary" type="button" data-action="fix-names">Namen trennen</button></div>'
          : '')
      + '<ul class="classlist-student-list">' + (rows || '<li class="classlist-empty-hint">Noch keine Schüler:innen – oben eintragen oder „Importieren“ nutzen.</li>') + '</ul>'
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
          '<p class="classlist-import-hint">Namen einfügen (eine Person pro Zeile, z. B. „Müller, Anna“) oder eine CSV-/Excel-Datei wählen.</p>',
          '<textarea id="classlist-paste" class="form-input classlist-paste" rows="5" placeholder="Müller, Anna&#10;Schmidt, Ben"></textarea>',
          '<label class="classlist-upload-area" for="classlist-file-input">',
            '<span class="classlist-upload-icon">📂</span>',
            '<span>Datei auswählen oder hierher ziehen</span>',
            '<input type="file" id="classlist-file-input" accept=".csv,.xlsx,.xls" style="display:none">',
          '</label>',
          '<div id="classlist-import-preview" class="classlist-import-preview" style="display:none">',
            '<div class="classlist-import-preview-head">',
              '<span id="classlist-preview-count"></span>',
              '<button class="btn btn-sm btn-secondary" type="button" data-action="swap-order" title="Vor- und Nachname vertauschen">Vor-/Nachname tauschen</button>',
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
    overlay.querySelector('#classlist-paste').addEventListener('input', function (e) {
      _showImportRows(overlay, _parseCSV(e.target.value, _importOrder), null);
    });

    // Close
    overlay.addEventListener('click', function (e) {
      var action = e.target.closest('[data-action]');
      if (!action) return;
      if (action.dataset.action === 'close-import') { _closeImportModal(overlay); }
      if (action.dataset.action === 'confirm-import') { _confirmImport(overlay); }
      if (action.dataset.action === 'swap-order') {
        _importOrder = _importOrder === 'first-last' ? 'last-first' : 'first-last';
        var pasted = overlay.querySelector('#classlist-paste').value;
        if (pasted.trim()) _showImportRows(overlay, _parseCSV(pasted, _importOrder), null);
        else if (_importPreview) {
          // Excel/CSV file: swap what was read
          _showImportRows(overlay, _importPreview.map(function (r) {
            if (!r.firstName) return _splitName(r.lastName, _importOrder);
            return { lastName: r.firstName, firstName: r.lastName };
          }), null);
        }
      }
    });
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) _closeImportModal(overlay);
    });
  }

  function _closeImportModal(overlay) {
    _importPreview = null;
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
  }

  function _showImportRows(overlay, rows, detectedClass) {
    var preview = overlay.querySelector('#classlist-import-preview');
    var previewList = overlay.querySelector('#classlist-preview-list');
    var previewCount = overlay.querySelector('#classlist-preview-count');
    var confirmBtn = overlay.querySelector('#classlist-import-confirm');
    var classInput = overlay.querySelector('#classlist-import-class-input');
    if (detectedClass && !classInput.value) classInput.value = detectedClass;
    _importPreview = rows.filter(function (r) { return r.lastName || r.firstName; });
    previewCount.textContent = _importPreview.length + (_importPreview.length === 1 ? ' Person gefunden' : ' Personen gefunden');
    var noFirst = _importPreview.filter(function (r) { return !r.firstName; }).length;
    previewList.innerHTML = '<li class="classlist-preview-legend"><span>Vorname</span><span>Nachname</span></li>' +
      _importPreview.slice(0, 8).map(function (r) {
        return '<li class="classlist-preview-row"><b>' + (_esc(r.firstName) || '<em>fehlt</em>') + '</b><span>' + _esc(r.lastName) + '</span></li>';
      }).join('') + (_importPreview.length > 8 ? '<li class="classlist-preview-more">… und ' + (_importPreview.length - 8) + ' weitere</li>' : '') +
      (noFirst ? '<li class="classlist-preview-warn">' + noFirst + ' ohne Vornamen – stimmt die Reihenfolge? Sonst „Vor-/Nachname tauschen“.</li>' : '');
    preview.style.display = _importPreview.length ? '' : 'none';
    confirmBtn.disabled = _importPreview.length === 0;
  }

  function _handleImportFile(file, overlay) {
    var isExcel = /\.xlsx?$/i.test(file.name);
    var preview = overlay.querySelector('#classlist-import-preview');
    var previewList = overlay.querySelector('#classlist-preview-list');
    var previewCount = overlay.querySelector('#classlist-preview-count');
    var confirmBtn = overlay.querySelector('#classlist-import-confirm');
    var classInput = overlay.querySelector('#classlist-import-class-input');

    function _showRows(rows, detectedClass) { _showImportRows(overlay, rows, detectedClass); }

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
        var rows = _parseCSV(e.target.result, _importOrder);
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

  function _addStudent(classId, form) {
    var cls = _data[classId];
    if (!cls) return;
    var lastInput = form.querySelector('[name="lastName"]');
    var firstInput = form.querySelector('[name="firstName"]');
    var lastName = lastInput.value.trim();
    var firstName = firstInput.value.trim();
    // "Müller, Anna" or "Anna Müller" typed into the first field
    if (lastName && !firstName) {
      if (lastName.indexOf(',') > 0) {
        firstName = lastName.slice(lastName.indexOf(',') + 1).trim();
        lastName = lastName.slice(0, lastName.indexOf(',')).trim();
      }
    }
    if (!lastName && !firstName) { lastInput.focus(); return; }
    var feedback = _container.querySelector('[data-add-feedback]');
    var duplicate = cls.students.some(function (s) {
      return (s.lastName || '').toLowerCase() === lastName.toLowerCase()
        && (s.firstName || '').toLowerCase() === firstName.toLowerCase();
    });
    if (duplicate) {
      if (feedback) {
        feedback.textContent = (firstName ? firstName + ' ' : '') + lastName + ' steht schon in der Liste.';
        feedback.classList.add('is-warn');
      }
      lastInput.select();
      return;
    }
    cls.students.push({ id: _uid(), lastName: lastName, firstName: firstName });
    _save();
    render();
    var nextForm = _container.querySelector('[data-add-student-form]');
    var nextFeedback = _container.querySelector('[data-add-feedback]');
    if (nextFeedback) nextFeedback.textContent = (firstName ? firstName + ' ' : '') + lastName + ' hinzugefügt.';
    if (nextForm) nextForm.querySelector('[name="lastName"]').focus();
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
  // Bound once per container: render() replaces the inner HTML, the listeners stay.
  // (Binding on every render stacked the handlers – one click then added a
  // student several times.)
  function _bindEvents() {
    if (!_container || _container.dataset.classlistBound) return;
    _container.dataset.classlistBound = '1';

    _container.addEventListener('submit', function (e) {
      var form = e.target.closest('[data-add-student-form]');
      if (!form) return;
      e.preventDefault();
      _addStudent(_activeClass, form);
    });

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
      if (act === 'print-list') { _showPrintListDialog(_activeClass); return; }
      if (act === 'fix-names') { _showFixNamesDialog(_activeClass); return; }
      if (act === 'delete-class') { _deleteClass(_activeClass); return; }

      var row = action.closest('[data-student-id]');
      if (act === 'edit-student' && row) { _showEditStudentDialog(_activeClass, row.dataset.studentId); return; }
      if (act === 'delete-student' && row) { _deleteStudent(_activeClass, row.dataset.studentId); return; }
    });
  }

  // ── Vor- und Nachnamen nachträglich trennen ───────────────────────────────
  // Older imports put a whole "Müller<TAB>Anna" or "Anna Müller" into lastName.
  function _needsSplit(classId) {
    var cls = _data[classId];
    if (!cls) return [];
    return cls.students.filter(function (st) { return !st.firstName && /[\s,;]/.test((st.lastName || '').trim()); });
  }

  /**
   * „Vor- und Nachnamen bearbeiten“: every word of a name is a chip – tap it to
   * switch between Vorname and Nachname. Names without a first name come first,
   * pre-split by the chosen reading order („Müller Anna“ or „Anna Müller“).
   */
  function _showFixNamesDialog(classId, onDone) {
    var cls = _data[classId];
    if (!cls || !cls.students.length) return;
    var broken = _needsSplit(classId);
    var order = broken.length && !/\t|,|;/.test(broken[0].lastName) ? 'first-last' : 'last-first';
    var rows = _sortedStudents(classId).map(function (st) {
      return { st: st, auto: !st.firstName, tokens: [] };
    }).sort(function (x, y) { return (y.auto ? 1 : 0) - (x.auto ? 1 : 0); });

    function assign(row) {
      if (!row.auto) {
        row.tokens = _words(row.st.firstName).map(function (w) { return { w: w, f: true }; })
          .concat(_words(row.st.lastName).map(function (w) { return { w: w, f: false }; }));
        return;
      }
      var name = _splitName(row.st.lastName, order);
      var first = _words(name.firstName), last = _words(name.lastName);
      // keep the words in the order they were typed
      var all = _words(row.st.lastName);
      row.tokens = all.map(function (w) {
        var i = first.indexOf(w);
        if (i !== -1 && last.indexOf(w) === -1) { first.splice(i, 1); return { w: w, f: true }; }
        var j = last.indexOf(w);
        if (j !== -1) last.splice(j, 1);
        return { w: w, f: false };
      });
    }
    rows.forEach(assign);

    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    document.body.appendChild(overlay);
    var close = function () { _removeOverlay(overlay); };

    function draw() {
      var list = overlay.querySelector('.name-chip-list');
      var scroll = list ? list.scrollTop : 0;
      overlay.innerHTML = '<div class="modal classlist-print-modal classlist-fix-modal" role="dialog" aria-label="Vor- und Nachnamen">'
        + '<div class="modal-header"><span class="modal-title">Vor- und Nachnamen · ' + _esc(classId) + '</span>'
        +   '<button class="modal-close" type="button" data-close>✕</button></div>'
        + '<div class="classlist-print-form">'
        +   '<p class="classlist-import-hint">Tippe auf ein Wort, um es zum <b class="name-key is-first">Vornamen</b> oder <b class="name-key">Nachnamen</b> zu machen.'
        +   (broken.length ? ' ' + broken.length + ' Namen ohne Vornamen stehen oben.' : '') + '</p>'
        +   '<ul class="name-chip-list">' + rows.map(function (row, r) {
              var noFirst = !row.tokens.some(function (t) { return t.f; });
              return '<li class="name-chip-row' + (row.auto ? ' is-auto' : '') + '">' + row.tokens.map(function (t, i) {
                return '<button type="button" class="name-chip' + (t.f ? ' is-first' : '') + '" data-row="' + r + '" data-tok="' + i + '" aria-pressed="' + (t.f ? 'true' : 'false') + '">' + _esc(t.w) + '</button>';
              }).join('') + (noFirst ? '<span class="name-chip-warn">kein Vorname</span>' : '') + '</li>';
            }).join('') + '</ul>'
        +   '<div class="classlist-import-footer">'
        +     (broken.length ? '<button class="btn btn-secondary" type="button" data-swap>Reihenfolge tauschen</button>' : '')
        +     '<button class="btn btn-primary" type="button" data-apply>Übernehmen</button>'
        +   '</div>'
        + '</div></div>';
      var next = overlay.querySelector('.name-chip-list');
      if (next) next.scrollTop = scroll;
    }
    draw();
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay || e.target.closest('[data-close]')) { close(); return; }
      var chip = e.target.closest('[data-tok]');
      if (chip) {
        var row = rows[parseInt(chip.dataset.row, 10)];
        var tok = row.tokens[parseInt(chip.dataset.tok, 10)];
        tok.f = !tok.f;
        row.touched = true;
        draw();
        return;
      }
      if (e.target.closest('[data-swap]')) {
        order = order === 'first-last' ? 'last-first' : 'first-last';
        rows.forEach(function (row) { if (row.auto && !row.touched) assign(row); });
        draw();
        return;
      }
      if (e.target.closest('[data-apply]')) {
        rows.forEach(function (row) {
          var first = row.tokens.filter(function (t) { return t.f; }).map(function (t) { return t.w; }).join(' ');
          var last = row.tokens.filter(function (t) { return !t.f; }).map(function (t) { return t.w; }).join(' ');
          if (!first && !last) return;
          row.st.firstName = first;   // the id stays: seating plans and collections keep their entries
          row.st.lastName = last;
        });
        _save();
        close();
        render();
        if (typeof onDone === 'function') onDone();
      }
    });
  }

  function _words(text) {
    return String(text || '').split(/[\s,;]+/).map(function (w) { return w.trim(); }).filter(Boolean);
  }

  // ── Printing ──────────────────────────────────────────────────────────────
  // Built in a new window and printed there ("Als PDF sichern" in the print
  // dialog). Names never leave the device.
  function printDocument(title, bodyHtml, options) {
    options = options || {};
    var win = window.open('', '_blank');
    if (!win) { alert('Bitte Pop-ups für das Cockpit erlauben, um die PDF zu öffnen.'); return; }
    win.document.write('<!doctype html><html lang="de"><head><meta charset="utf-8">'
      + '<title>' + _esc(title) + '</title><style>'
      + 'body{font:12px/1.4 -apple-system,"Segoe UI",Roboto,sans-serif;color:#111;margin:24px}'
      + 'h1{font-size:18px;margin:0 0 2px}h2{font-size:14px;margin:16px 0 6px}p.meta{margin:0 0 14px;color:#555}'
      + 'table{border-collapse:collapse;width:100%;page-break-inside:auto}tr{page-break-inside:avoid}'
      + 'th,td{border:1px solid #999;padding:3px 6px;text-align:left;vertical-align:middle}'
      + 'th{background:#f1f3f5;font-weight:600}td.nr{width:2.2em;text-align:right;color:#555}'
      + '.name{white-space:nowrap}td.mark{text-align:center;width:6em}'
      + '@page{size:A4 ' + (options.landscape ? 'landscape' : 'portrait') + ';margin:12mm}@media print{body{margin:0}}'
      + (options.css || '')
      + '</style></head><body>' + bodyHtml
      + '<script>window.onload=function(){window.print();};<\/script></body></html>');
    win.document.close();
  }

  var PRINT_COLUMNS_KEY = 'lc.printColumns';

  function _showPrintListDialog(classId) {
    var saved = 6;
    try { saved = parseInt(localStorage.getItem(PRINT_COLUMNS_KEY), 10) || 6; } catch (e) { /* private mode */ }
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = '<div class="modal classlist-print-modal" role="dialog" aria-label="PDF-Liste">'
      + '<div class="modal-header"><span class="modal-title">PDF-Liste · Klasse ' + _esc(classId) + '</span>'
      +   '<button class="modal-close" type="button" data-close>✕</button></div>'
      + '<form class="classlist-print-form" data-print-form>'
      +   '<label class="form-label">Überschrift (optional)'
      +     '<input class="form-input" name="title" placeholder="z. B. Hausaufgaben 2. Halbjahr" maxlength="80" /></label>'
      +   '<label class="form-label">Anzahl leerer Spalten'
      +     '<input class="form-input" name="columns" type="number" min="1" max="25" inputmode="numeric" value="' + saved + '" required /></label>'
      +   '<div class="classlist-import-footer">'
      +     '<button class="btn btn-secondary" type="button" data-close>Abbrechen</button>'
      +     '<button class="btn btn-primary" type="submit">PDF erstellen</button>'
      +   '</div>'
      + '</form></div>';
    document.body.appendChild(overlay);
    var close = function () { _removeOverlay(overlay); };
    overlay.addEventListener('click', function (e) { if (e.target === overlay || e.target.closest('[data-close]')) close(); });
    var form = overlay.querySelector('[data-print-form]');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var columns = Math.max(1, Math.min(25, parseInt(form.elements.columns.value, 10) || 1));
      try { localStorage.setItem(PRINT_COLUMNS_KEY, String(columns)); } catch (err) { /* private mode */ }
      close();
      _printEmptyList(classId, columns, form.elements.title.value.trim());
    });
    form.elements.columns.select();
  }

  function _removeOverlay(el) { if (el && el.parentNode) el.parentNode.removeChild(el); }

  /** Class list with numbered names and empty columns to fill in by hand. */
  function _printEmptyList(classId, columns, heading) {
    var students = _sortedStudents(classId);
    var landscape = columns > 8;
    // fit one page: A4 minus margins and heading, split across header + rows
    var usable = (landscape ? 186 : 273) - 22;
    var rowMm = Math.max(5.5, Math.min(9, Math.floor(usable / (students.length + 1) * 10) / 10));
    var empty = '';
    for (var i = 0; i < columns; i++) empty += '<td></td>';
    var headCells = '';
    for (var j = 0; j < columns; j++) headCells += '<th></th>';
    var rows = students.map(function (s, n) {
      return '<tr><td class="nr">' + (n + 1) + '</td><td class="name">' + _esc(s.lastName) + (s.firstName ? ', ' + _esc(s.firstName) : '') + '</td>' + empty + '</tr>';
    }).join('');
    var title = 'Klasse ' + classId + (heading ? ' – ' + heading : '');
    printDocument(title,
      '<h1>' + _esc(title) + '</h1>'
      + '<table><thead><tr><th class="nr"></th><th class="name">Name</th>' + headCells + '</tr></thead><tbody>' + rows + '</tbody></table>',
      { landscape: landscape, css: 'tr{height:' + rowMm + 'mm}td.name{width:1%}' });
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
    printDocument: printDocument,
    editNames: function (classId, onDone) { _load(); _showFixNamesDialog(classId, onDone); },
  };
})();

if (typeof window !== 'undefined') window.LehrerClasslist = LehrerClasslist;
