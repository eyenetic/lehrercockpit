/**
 * LehrerSeating — Sitzplan je Klasse, gebaut aus den Klassenlisten.
 *
 * - Raster aus Plätzen und Lücken (Vorlagen: Reihen, Gruppentische, U-Form;
 *   „Tische bearbeiten“ schaltet einzelne Felder um, Reihen/Spalten ±)
 * - Setzen: ziehen (Maus) oder antippen – erst Name bzw. Platz, dann Ziel.
 *   Ein besetzter Platz als Ziel tauscht die beiden.
 * - „Zufällig verteilen“, „Leeren“, Ansicht drehen (Tafel oben/unten), PDF
 * - Speicherung in localStorage "lehrerCockpit.seatingPlans" (Tresor-Sync wie
 *   die Klassenlisten – Namen verlassen das Gerät nur verschlüsselt)
 *
 * Datenstruktur: { classId: { rows, cols, cells: [1|0 …], seats: { index: studentId },
 *                             front: 'top'|'bottom', updatedAt } }
 *
 * Exports (window.LehrerSeating): init, render
 */
var LehrerSeating = (function () {
  'use strict';

  var STORAGE_KEY = 'lehrerCockpit.seatingPlans';
  var CLASS_KEY = 'lc.seatingClass';
  var MAX_ROWS = 12;
  var MAX_COLS = 14;

  var _container = null;
  var _plans = {};
  var _activeClass = null;
  var _editing = false;
  var _selected = null;   // { kind: 'student'|'seat', id } – picked, waiting for a target

  // ── Raum aufbauen ─────────────────────────────────────────────────────────
  // 1 = Platz, 0 = Lücke. Built from what the teacher enters in „Raum einrichten“.
  var KINDS = { rows: 'Reihen', groups: 'Gruppentische', u: 'U-Form' };

  function _defaultSetup(n) {
    return { kind: 'rows', rows: Math.max(3, Math.ceil(n / 6)), perRow: 6, desk: 2, tables: Math.max(4, Math.ceil(n / 4)), perTable: 4,
             side: Math.max(3, Math.ceil((n - 6) / 2)), back: 6 };
  }

  function _clamp(v, lo, hi, fallback) {
    var n = parseInt(v, 10);
    return isNaN(n) ? fallback : Math.max(lo, Math.min(hi, n));
  }

  function _buildRoom(o) {
    if (o.kind === 'groups') {
      // tables of 2×2 (4) or 2×3 (6), three per band, an empty row and column between them
      var tw = o.perTable === 6 ? 3 : 2, perBand = 3;
      var bands = Math.ceil(o.tables / perBand);
      var cols = Math.min(perBand, o.tables) * (tw + 1) - 1;
      return _grid(Math.min(MAX_ROWS, bands * 3 - 1), Math.min(MAX_COLS, cols), function (r, c) {
        if ((r + 1) % 3 === 0 || (c + 1) % (tw + 1) === 0) return false;
        var table = Math.floor(r / 3) * perBand + Math.floor(c / (tw + 1));
        return table < o.tables;
      });
    }
    if (o.kind === 'u') {
      // seats along the left, the back and the right; open towards the board
      var width = Math.min(MAX_COLS, Math.max(3, o.back));
      var depth = Math.min(MAX_ROWS - 1, o.side);
      return _grid(depth + 1, width, function (r, c) { return r === depth || c === 0 || c === width - 1; });
    }
    // rows: desks of 1–4 seats, one aisle between desks
    var desk = Math.max(1, Math.min(4, o.desk));
    var desks = Math.ceil(o.perRow / desk);
    var colsR = Math.min(MAX_COLS, o.perRow + desks - 1);
    return _grid(Math.min(MAX_ROWS, o.rows), colsR, function (r, c) {
      if ((c + 1) % (desk + 1) === 0) return false;
      return c - Math.floor(c / (desk + 1)) < o.perRow;
    });
  }

  function _grid(rows, cols, isSeat) {
    var cells = [];
    for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) cells.push(isSeat(r, c) ? 1 : 0);
    return { rows: rows, cols: cols, cells: cells };
  }

  // ── Speicher ──────────────────────────────────────────────────────────────
  function _load() {
    var raw;
    try { raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch (e) { raw = {}; }
    _plans = {};
    Object.keys(raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}).forEach(function (classId) {
      var p = raw[classId];
      if (!p || typeof p !== 'object') return;
      var rows = Math.max(1, Math.min(MAX_ROWS, parseInt(p.rows, 10) || 0));
      var cols = Math.max(1, Math.min(MAX_COLS, parseInt(p.cols, 10) || 0));
      var cells = Array.isArray(p.cells) ? p.cells.slice(0, rows * cols).map(function (v) { return v ? 1 : 0; }) : [];
      while (cells.length < rows * cols) cells.push(0);
      var seats = {};
      Object.keys(p.seats && typeof p.seats === 'object' ? p.seats : {}).forEach(function (index) {
        var i = parseInt(index, 10);
        if (i >= 0 && i < cells.length && cells[i] && p.seats[index]) seats[i] = String(p.seats[index]);
      });
      // Teacher's view (board at the bottom) unless the teacher chose the class's view.
      var front = p.frontSet && p.front === 'top' ? 'top' : 'bottom';
      _plans[classId] = { rows: rows, cols: cols, cells: cells, seats: seats, front: front, frontSet: !!p.frontSet,
                          validFrom: typeof p.validFrom === 'string' ? p.validFrom : '', room: typeof p.room === 'string' ? p.room : '',
                          heading: typeof p.heading === 'string' ? p.heading : '', subject: typeof p.subject === 'string' ? p.subject : '',
                          teacher: typeof p.teacher === 'string' ? p.teacher : '', setup: p.setup && typeof p.setup === 'object' ? p.setup : null,
                          updatedAt: p.updatedAt || null };
    });
  }

  function _save() {
    var plan = _plans[_activeClass];
    if (plan) plan.updatedAt = new Date().toISOString();
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(_plans)); } catch (e) { /* quota */ }
  }

  // ── Daten aus den Klassenlisten ───────────────────────────────────────────
  function _classes() {
    var lists = window.LehrerClasslist ? window.LehrerClasslist.getClassLists() : {};
    return Object.keys(lists).sort(function (a, b) { return a.localeCompare(b, 'de', { numeric: true }); });
  }

  function _students(classId) {
    return window.LehrerClasslist ? window.LehrerClasslist.getStudentsForClass(classId) : [];
  }

  function _plan(classId) {
    if (!_plans[classId]) {
      var t = _buildRoom(_defaultSetup(_students(classId).length));
      _plans[classId] = { rows: t.rows, cols: t.cols, cells: t.cells, seats: {}, front: 'bottom', frontSet: false, validFrom: '', room: '', updatedAt: null };
    }
    var plan = _plans[classId];
    // students removed from the class list leave their seat
    var ids = {};
    _students(classId).forEach(function (s) { ids[s.id] = true; });
    Object.keys(plan.seats).forEach(function (i) { if (!ids[plan.seats[i]]) delete plan.seats[i]; });
    return plan;
  }

  /** Just the first name; only when it repeats in the class "Anna M." (or "Anna Mü." if that repeats too). */
  function _labels(students) {
    var labels = {};
    students.forEach(function (s) {
      var first = s.firstName || s.lastName || '?';
      var sameFirst = students.filter(function (o) { return (o.firstName || o.lastName) === first; });
      var initial = '';
      if (sameFirst.length > 1 && s.firstName && s.lastName) {
        var len = 1;
        while (len < s.lastName.length && sameFirst.some(function (o) {
          return o !== s && (o.lastName || '').slice(0, len) === s.lastName.slice(0, len);
        })) len++;
        initial = s.lastName.slice(0, len) + '.';
      }
      labels[s.id] = { first: first, initial: initial, short: first + (initial ? ' ' + initial : ''),
                       full: (s.firstName ? s.firstName + ' ' : '') + (s.lastName || '') };
    });
    return labels;
  }

  // ── Rendern ───────────────────────────────────────────────────────────────
  function render() {
    if (!_container) return;
    _load();
    var classes = _classes();
    if (!_activeClass || classes.indexOf(_activeClass) === -1) {
      var saved = null;
      try { saved = localStorage.getItem(CLASS_KEY); } catch (e) { /* private mode */ }
      _activeClass = classes.indexOf(saved) !== -1 ? saved : (classes[0] || null);
    }
    _container.innerHTML = '<div class="classlist-layout seat-layout">' + _sidebar(classes) +
      '<div class="classlist-main">' + (_activeClass ? _panel(_activeClass) : _empty()) + '</div></div>';
    _bind();
  }

  function _sidebar(classes) {
    var items = classes.map(function (id) {
      var plan = _plans[id];
      var placed = plan ? Object.keys(plan.seats).length : 0;
      return '<button class="classlist-class-btn' + (id === _activeClass ? ' active' : '') + '" data-seat-class="' + _esc(id) + '" type="button">' +
        '<span class="classlist-class-name">' + _esc(id) + '</span>' +
        '<span class="classlist-class-count">' + (placed ? placed + '/' + _students(id).length : '–') + '</span></button>';
    }).join('');
    return '<aside class="classlist-sidebar"><div class="classlist-sidebar-head"><h2 class="classlist-sidebar-title">Klassen</h2></div>' +
      '<div class="classlist-class-list">' + (items || '<p class="classlist-empty-hint">Noch keine Klassen</p>') + '</div></aside>';
  }

  function _empty() {
    return '<div class="seat-empty"><h3>Noch keine Klasse</h3><p>Leg unter „Klassenlisten“ eine Klasse mit Namen an – daraus entsteht hier der Sitzplan.</p></div>';
  }

  function _panel(classId) {
    var plan = _plan(classId);
    var students = _students(classId);
    var labels = _labels(students);
    var seatCount = plan.cells.filter(Boolean).length;
    var placedIds = {};
    Object.keys(plan.seats).forEach(function (i) { placedIds[plan.seats[i]] = true; });
    var unplaced = students.filter(function (s) { return !placedIds[s.id]; });
    var missingFirst = students.filter(function (s) { return !s.firstName; }).length;

    if (!students.length) {
      return '<div class="seat-empty"><h3>Klasse ' + _esc(classId) + ' hat noch keine Namen</h3>' +
        '<p>Trag die Schüler:innen unter „Klassenlisten“ ein – dann kannst du sie hier auf Plätze setzen.</p></div>';
    }

    var board = '<div class="seat-board">Tafel</div>';
    var order = [];
    for (var i = 0; i < plan.cells.length; i++) order.push(i);
    if (plan.front === 'bottom') order.reverse();  // teacher's view: the board is at the bottom, the room turned
    // Aisles (columns/rows without any seat) stay narrow, so the whole room fits a phone.
    var colHasSeat = [], rowHasSeat = [];
    for (var ci = 0; ci < plan.cols; ci++) colHasSeat.push(false);
    for (var ri = 0; ri < plan.rows; ri++) rowHasSeat.push(false);
    plan.cells.forEach(function (v, index) {
      if (!v) return;
      colHasSeat[index % plan.cols] = true;
      rowHasSeat[Math.floor(index / plan.cols)] = true;
    });
    var colSizes = colHasSeat.map(function (has) { return has || _editing ? 'minmax(40px, 1fr)' : '14px'; });
    if (plan.front === 'bottom') colSizes.reverse();
    var cells = order.map(function (index) {
      if (!plan.cells[index]) {
        var thin = !_editing && !rowHasSeat[Math.floor(index / plan.cols)];
        return '<div class="seat-cell is-gap' + (thin ? ' is-thin' : '') + (_editing ? ' is-editable' : '') + '" data-cell="' + index + '"' +
          (_editing ? ' role="button" tabindex="0" aria-label="Platz hinzufügen"' : '') + '></div>';
      }
      var sid = plan.seats[index];
      var label = sid && labels[sid];
      var selected = _selected && _selected.kind === 'seat' && String(_selected.id) === String(index);
      return '<div class="seat-cell is-seat' + (label ? ' is-taken' : '') + (selected ? ' is-selected' : '') + (_editing ? ' is-editable' : '') + '"' +
        ' data-cell="' + index + '" role="button" tabindex="0"' + (label && !_editing ? ' draggable="true"' : '') +
        ' title="' + _esc(label ? label.full : (_editing ? 'Platz entfernen' : 'Freier Platz')) + '">' +
        (label ? '<span class="seat-name"><span class="seat-first">' + _esc(label.first) + '</span>' +
          (label.initial ? '<span class="seat-initial">' + _esc(label.initial) + '</span>' : '') + '</span>' : '<span class="seat-free" aria-hidden="true">+</span>') + '</div>';
    }).join('');

    var hint;
    if (_editing) hint = 'Tippe auf Felder, um Plätze hinzuzufügen oder zu entfernen.';
    else if (_selected) {
      var pickedId = _selected.kind === 'seat' ? plan.seats[_selected.id] : _selected.id;
      var picked = labels[pickedId] ? labels[pickedId].full : '';
      hint = (picked ? picked + ': ' : '') + 'jetzt auf einen Platz tippen' +
        (_selected.kind === 'seat' ? ' – oder unten auf „Ohne Platz“, um ihn frei zu machen.' : '.');
    }
    else if (seatCount < students.length) hint = 'Es fehlen ' + (students.length - seatCount) + ' Plätze – unter „Raum einrichten“ mehr anlegen.';
    else hint = 'Name antippen oder ziehen, dann auf einen Platz. Besetzten Platz antippen zum Tauschen.';

    return '<div class="seat-panel">' +
      '<div class="classlist-panel-head">' +
        '<div><h2 class="classlist-panel-title">Sitzplan ' + _esc(classId) + '</h2>' +
        '<p class="classlist-panel-count">' + (students.length - unplaced.length) + ' von ' + students.length + ' sitzen · ' + seatCount + ' Plätze</p></div>' +
        '<div class="classlist-panel-actions action-row">' +
          (_editing
            ? '<button class="btn btn-sm btn-primary" type="button" data-seat-action="done">Fertig</button>'
            : '<button class="btn btn-sm btn-secondary" type="button" data-seat-action="shuffle">Zufällig</button>' +
              '<button class="btn btn-sm btn-secondary" type="button" data-seat-action="print">PDF</button>') +
          '<details class="more-menu"><summary class="btn btn-sm btn-secondary" aria-label="Weitere Aktionen">⋯</summary>' +
            '<div class="more-menu-list" role="menu">' +
              (_editing ? '' : '<button type="button" role="menuitem" data-seat-action="edit">Tische bearbeiten</button>') +
              '<button type="button" role="menuitem" data-seat-action="flip">' + (plan.front === 'top' ? 'Aus Sicht der Lehrkraft (Tafel unten)' : 'Aus Sicht der Klasse (Tafel oben)') + '</button>' +
              '<button type="button" role="menuitem" data-seat-action="setup">Raum einrichten …</button>' +
              '<button type="button" role="menuitem" class="is-danger" data-seat-action="clear">Alle Plätze leeren</button>' +
            '</div></details>' +
        '</div>' +
      '</div>' +
      (_editing
        ? '<div class="seat-edit-bar">' +
            '<span>Reihen</span><button class="btn btn-sm btn-secondary" type="button" data-seat-action="rows-">−</button><b>' + plan.rows + '</b><button class="btn btn-sm btn-secondary" type="button" data-seat-action="rows+">+</button>' +
            '<span>Spalten</span><button class="btn btn-sm btn-secondary" type="button" data-seat-action="cols-">−</button><b>' + plan.cols + '</b><button class="btn btn-sm btn-secondary" type="button" data-seat-action="cols+">+</button>' +
          '</div>'
        : '') +
      (!plan.setup && !_editing
        ? '<div class="seat-banner"><span>Wie ist dein Raum aufgebaut? Reihen und Plätze pro Reihe kannst du selbst festlegen.</span>' +
          '<button class="btn btn-sm btn-primary" type="button" data-seat-action="setup">Raum einrichten</button></div>' : '') +
      (missingFirst && !_editing
        ? '<div class="seat-banner is-warn"><span>Bei ' + missingFirst + ' Namen fehlt der Vorname – im Sitzplan steht dann der ganze Name.</span>' +
          '<button class="btn btn-sm btn-secondary" type="button" data-seat-action="names">Namen trennen</button></div>' : '') +
      '<p class="seat-hint" role="status">' + _esc(hint) + '</p>' +
      '<div class="seat-room' + (plan.front === 'bottom' ? ' is-teacher-view' : '') + '">' +
        (plan.front === 'top' ? board : '') +
        '<div class="seat-scroll"><div class="seat-grid" style="grid-template-columns: ' + colSizes.join(' ') + ';">' + cells + '</div></div>' +
        (plan.front === 'bottom' ? board : '') +
      '</div>' +
      (_editing ? '' :
        '<div class="seat-pool" data-pool="1">' +
          '<h3>Ohne Platz <span>' + unplaced.length + '</span></h3>' +
          (unplaced.length
            ? '<div class="seat-chips">' + unplaced.map(function (s) {
                var selected = _selected && _selected.kind === 'student' && _selected.id === s.id;
                return '<button type="button" class="seat-chip' + (selected ? ' is-selected' : '') + '" draggable="true" data-student="' + _esc(s.id) + '" title="' + _esc(labels[s.id].full) + '">' + _esc(labels[s.id].short) + '</button>';
              }).join('') + '</div>'
            : '<p class="seat-pool-done">Alle haben einen Platz.</p>') +
        '</div>') +
      '</div>';
  }

  // ── Aktionen ──────────────────────────────────────────────────────────────
  function _place(studentId, index) {
    var plan = _plan(_activeClass);
    if (!plan.cells[index]) return;
    var from = null;
    Object.keys(plan.seats).forEach(function (i) { if (plan.seats[i] === studentId) from = i; });
    var occupant = plan.seats[index];
    if (from !== null) delete plan.seats[from];
    plan.seats[index] = studentId;
    if (occupant && occupant !== studentId && from !== null) plan.seats[from] = occupant;  // swap
    _save();
  }

  function _moveSeat(fromIndex, toIndex) {
    var plan = _plan(_activeClass);
    if (String(fromIndex) === String(toIndex) || !plan.cells[toIndex]) return;
    var a = plan.seats[fromIndex], b = plan.seats[toIndex];
    delete plan.seats[fromIndex];
    delete plan.seats[toIndex];
    if (a) plan.seats[toIndex] = a;
    if (b) plan.seats[fromIndex] = b;
    _save();
  }

  function _unseat(index) {
    delete _plan(_activeClass).seats[index];
    _save();
  }

  function _shuffle() {
    var plan = _plan(_activeClass);
    if (Object.keys(plan.seats).length && !window.confirm('Alle neu und zufällig verteilen? Der jetzige Plan wird ersetzt.')) return;
    var ids = _students(_activeClass).map(function (s) { return s.id; });
    for (var i = ids.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = ids[i]; ids[i] = ids[j]; ids[j] = t; }
    var seats = [];
    plan.cells.forEach(function (v, index) { if (v) seats.push(index); });
    plan.seats = {};
    seats.slice(0, ids.length).forEach(function (index, n) { plan.seats[index] = ids[n]; });
    _save();
  }

  /** „Raum einrichten“: arrangement, rows and seats per row (or tables / U sides). */
  function _showSetupDialog() {
    var plan = _plan(_activeClass);
    var n = _students(_activeClass).length;
    var o = Object.assign(_defaultSetup(n), plan.setup || {});
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    document.body.appendChild(overlay);
    var close = function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); };

    function field(name, label, value, min, max) {
      return '<label class="form-label seat-setup-field">' + label +
        '<span class="seat-stepper"><button class="btn btn-secondary btn-sm" type="button" data-step="' + name + ':-1" aria-label="weniger">−</button>' +
        '<input class="form-input" name="' + name + '" type="number" inputmode="numeric" min="' + min + '" max="' + max + '" value="' + value + '" />' +
        '<button class="btn btn-secondary btn-sm" type="button" data-step="' + name + ':1" aria-label="mehr">+</button></span></label>';
    }
    function seatsOf(x) { return _buildRoom(x).cells.filter(Boolean).length; }
    function draw() {
      var fields;
      if (o.kind === 'groups') fields = field('tables', 'Anzahl Gruppentische', o.tables, 1, 12) +
        '<label class="form-label">Plätze pro Tisch<span class="seg">' + [4, 6].map(function (v) {
          return '<button type="button" class="seg-btn' + (o.perTable === v ? ' is-active' : '') + '" data-pertable="' + v + '">' + v + '</button>'; }).join('') + '</span></label>';
      else if (o.kind === 'u') fields = field('side', 'Plätze je Seite (links und rechts)', o.side, 1, MAX_ROWS - 1) + field('back', 'Plätze hinten', o.back, 3, MAX_COLS);
      else fields = field('rows', 'Anzahl Reihen', o.rows, 1, MAX_ROWS) + field('perRow', 'Plätze pro Reihe', o.perRow, 1, 10) +
        '<label class="form-label">Tische für<span class="seg">' + [1, 2, 3, 4].map(function (v) {
          return '<button type="button" class="seg-btn' + (o.desk === v ? ' is-active' : '') + '" data-desk="' + v + '">' + (v === 1 ? 'Einzeln' : v + ' Plätze') + '</button>'; }).join('') + '</span></label>';
      var seats = seatsOf(o);
      overlay.innerHTML = '<div class="modal classlist-print-modal seat-setup-modal" role="dialog" aria-label="Raum einrichten">' +
        '<div class="modal-header"><span class="modal-title">Raum einrichten · ' + _esc(_activeClass) + '</span>' +
          '<button class="modal-close" type="button" data-close>✕</button></div>' +
        '<form class="classlist-print-form" data-setup-form>' +
          '<span class="seg seg-wide">' + Object.keys(KINDS).map(function (k) {
            return '<button type="button" class="seg-btn' + (o.kind === k ? ' is-active' : '') + '" data-kind="' + k + '">' + KINDS[k] + '</button>'; }).join('') + '</span>' +
          fields +
          '<p class="seat-setup-sum' + (seats < n ? ' is-short' : '') + '">' + seats + ' Plätze für ' + n + ' Schüler:innen' +
            (seats < n ? ' – es fehlen ' + (n - seats) : '') + '</p>' +
          (Object.keys(plan.seats).length ? '<p class="seat-hint">Danach stehen alle wieder ohne Platz – „Zufällig“ verteilt sie neu.</p>' : '') +
          '<div class="classlist-import-footer"><button class="btn btn-secondary" type="button" data-close>Abbrechen</button>' +
          '<button class="btn btn-primary" type="submit">Übernehmen</button></div>' +
        '</form></div>';
    }
    function readInputs() {
      var form = overlay.querySelector('[data-setup-form]');
      if (!form) return;
      ['rows', 'perRow', 'tables', 'side', 'back'].forEach(function (name) {
        var input = form.elements[name];
        if (input) o[name] = _clamp(input.value, parseInt(input.min, 10), parseInt(input.max, 10), o[name]);
      });
    }
    draw();
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay || e.target.closest('[data-close]')) { close(); return; }
      var t = e.target.closest('[data-kind], [data-desk], [data-pertable], [data-step]');
      if (!t) return;
      readInputs();
      if (t.dataset.kind) o.kind = t.dataset.kind;
      if (t.dataset.desk) o.desk = parseInt(t.dataset.desk, 10);
      if (t.dataset.pertable) o.perTable = parseInt(t.dataset.pertable, 10);
      if (t.dataset.step) {
        var parts = t.dataset.step.split(':');
        var input = overlay.querySelector('[name="' + parts[0] + '"]');
        o[parts[0]] = _clamp(o[parts[0]] + parseInt(parts[1], 10), parseInt(input.min, 10), parseInt(input.max, 10), o[parts[0]]);
      }
      draw();
    });
    overlay.addEventListener('change', function () { readInputs(); draw(); });
    overlay.addEventListener('submit', function (e) {
      e.preventDefault();
      readInputs();
      var room = _buildRoom(o);
      plan.rows = room.rows; plan.cols = room.cols; plan.cells = room.cells; plan.seats = {};
      plan.setup = o;
      _selected = null;
      _save();
      close();
      render();
    });
  }

  function _resize(dRows, dCols) {
    var plan = _plan(_activeClass);
    var rows = Math.max(1, Math.min(MAX_ROWS, plan.rows + dRows));
    var cols = Math.max(1, Math.min(MAX_COLS, plan.cols + dCols));
    var cells = [], seats = {};
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        var old = r < plan.rows && c < plan.cols ? r * plan.cols + c : -1;
        var index = r * cols + c;
        cells.push(old >= 0 ? plan.cells[old] : 1);
        if (old >= 0 && plan.seats[old]) seats[index] = plan.seats[old];
      }
    }
    plan.rows = rows; plan.cols = cols; plan.cells = cells; plan.seats = seats;
    _save();
  }

  function _toggleCell(index) {
    var plan = _plan(_activeClass);
    plan.cells[index] = plan.cells[index] ? 0 : 1;
    if (!plan.cells[index]) delete plan.seats[index];
    _save();
  }

  function _todayIso() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  function _deDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    return m ? m[3] + '.' + m[2] + '.' + m[1] : '';
  }

  function _userName() {
    var u = window.CURRENT_USER || {};
    return u.full_name || [u.first_name, u.last_name].filter(Boolean).join(' ');
  }

  /** Heading, subject, room, teacher and "gültig ab" before printing – remembered per class. */
  function _showPrintDialog() {
    var plan = _plan(_activeClass);
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = '<div class="modal classlist-print-modal" role="dialog" aria-label="Sitzplan als PDF">' +
      '<div class="modal-header"><span class="modal-title">Sitzplan ' + _esc(_activeClass) + ' als PDF</span>' +
        '<button class="modal-close" type="button" data-close>✕</button></div>' +
      '<form class="classlist-print-form" data-seat-print-form>' +
        '<label class="form-label">Klasse<input class="form-input" name="heading" maxlength="40" value="' + _esc(plan.heading || ('Klasse ' + _activeClass)) + '" /></label>' +
        '<div class="seat-form-row">' +
          '<label class="form-label">Fach (optional)<input class="form-input" name="subject" maxlength="40" placeholder="z. B. Mathematik" value="' + _esc(plan.subject) + '" /></label>' +
          '<label class="form-label">Raum (optional)<input class="form-input" name="room" maxlength="30" placeholder="z. B. 220" value="' + _esc(plan.room) + '" /></label>' +
        '</div>' +
        '<div class="seat-form-row">' +
          '<label class="form-label">Lehrkraft (optional)<input class="form-input" name="teacher" maxlength="60" value="' + _esc(plan.teacher || _userName()) + '" /></label>' +
          '<label class="form-label">Gültig ab<input class="form-input" name="validFrom" type="date" value="' + _esc(plan.validFrom || _todayIso()) + '" required /></label>' +
        '</div>' +
        '<div class="classlist-import-footer">' +
          '<button class="btn btn-secondary" type="button" data-close>Abbrechen</button>' +
          '<button class="btn btn-primary" type="submit">PDF erstellen</button>' +
        '</div>' +
      '</form></div>';
    document.body.appendChild(overlay);
    var close = function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); };
    overlay.addEventListener('click', function (e) { if (e.target === overlay || e.target.closest('[data-close]')) close(); });
    var form = overlay.querySelector('[data-seat-print-form]');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      plan.validFrom = form.elements.validFrom.value || _todayIso();
      plan.room = form.elements.room.value.trim();
      plan.heading = form.elements.heading.value.trim();
      plan.subject = form.elements.subject.value.trim();
      plan.teacher = form.elements.teacher.value.trim();
      _save();
      close();
      _print();
    });
  }

  /** A4 landscape: heading, "gültig ab", the room as the teacher (or the class) sees it. */
  function _print() {
    var plan = _plan(_activeClass);
    var students = _students(_activeClass);
    var labels = _labels(students);
    var byId = {};
    students.forEach(function (s) { byId[s.id] = s; });
    if (!window.LehrerClasslist || !window.LehrerClasslist.printDocument) return;

    // Only the area with seats is printed; the teacher's view turns the room by 180°.
    var turned = plan.front === 'bottom';
    var usedRows = [], usedCols = [];
    for (var r0 = 0; r0 < plan.rows; r0++) {
      for (var c0 = 0; c0 < plan.cols; c0++) {
        if (plan.cells[r0 * plan.cols + c0]) { usedRows[r0] = true; usedCols[c0] = true; }
      }
    }
    var rowIdx = [], colIdx = [];
    for (var r1 = 0; r1 < plan.rows; r1++) if (usedRows[r1] || (r1 > 0 && r1 < plan.rows - 1)) rowIdx.push(r1);
    for (var c1 = 0; c1 < plan.cols; c1++) if (usedCols[c1] || (c1 > 0 && c1 < plan.cols - 1)) colIdx.push(c1);
    if (turned) { rowIdx.reverse(); colIdx.reverse(); }
    var seatRows = rowIdx.filter(function (r) { return usedRows[r]; }).length || 1;
    // A4 landscape 297×210 mm, 12 mm margins, ~40 mm for heading, board and footer
    var seatH = Math.max(11, Math.min(26, Math.floor((210 - 24 - 46) / (seatRows + (rowIdx.length - seatRows) * 0.35))));

    var grid = rowIdx.map(function (r) {
      var seatRow = !!usedRows[r];
      return '<tr class="' + (seatRow ? '' : 'aisle') + '">' + colIdx.map(function (c) {
        var index = r * plan.cols + c;
        if (!plan.cells[index]) return '<td class="gap' + (usedCols[c] ? '' : ' col-aisle') + '"></td>';
        var st = byId[plan.seats[index]];
        if (!st) return '<td class="seat empty"></td>';
        var label = labels[st.id];
        return '<td class="seat"><span class="first">' + _esc(label.first) + (label.initial ? ' ' + _esc(label.initial) : '') + '</span>' +
          '<span class="last">' + _esc(st.lastName && st.firstName ? st.lastName : '') + '</span></td>';
      }).join('') + '</tr>';
    }).join('');

    var placed = Object.keys(plan.seats).length;
    var heading = plan.heading || ('Klasse ' + _activeClass);
    var meta = [];
    if (plan.subject) meta.push(plan.subject);
    if (plan.room) meta.push('Raum ' + plan.room);
    if (plan.teacher) meta.push(plan.teacher);
    meta.push(placed + ' Schüler:innen');
    var board = '<div class="board"><span>Tafel</span></div>';
    var title = 'Sitzplan ' + heading;
    window.LehrerClasslist.printDocument(title,
      '<header class="head"><div><p class="kicker">Sitzplan</p><h1>' + _esc(heading) + '</h1><p class="sub">' + _esc(meta.join(' · ')) + '</p></div>' +
        '<div class="valid"><span>gültig ab</span><b>' + _esc(_deDate(plan.validFrom) || _deDate(_todayIso())) + '</b></div></header>' +
      (turned ? '' : board) +
      '<table class="room">' + grid + '</table>' +
      (turned ? board : '') +
      '<footer class="foot">' + (turned ? 'Ansicht vom Pult aus' : 'Ansicht von der Klasse aus') + ' · erstellt am ' + _esc(_deDate(_todayIso())) + '</footer>',
      { landscape: true,
        css: 'body{margin:0;font-family:-apple-system,"Segoe UI",Roboto,sans-serif;color:#1d1d1b}' +
          '.head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;padding-bottom:8px;border-bottom:2px solid #1d1d1b;margin-bottom:10px}' +
          '.kicker{margin:0 0 2px;font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#666}' +
          '.head h1{font-size:24px;margin:0;letter-spacing:-0.01em}.sub{margin:3px 0 0;color:#555;font-size:12px}' +
          '.valid{text-align:right;line-height:1.2}.valid span{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#666}.valid b{font-size:15px}' +
          'table.room{width:100%;table-layout:fixed;border-collapse:separate;border-spacing:5px;margin:0 auto}' +
          'table.room td{height:' + seatH + 'mm;padding:2px 3px;text-align:center;vertical-align:middle;border:0}' +
          'table.room tr.aisle td{height:' + Math.max(3, Math.round(seatH * 0.35)) + 'mm}' +
          'td.col-aisle{width:4mm}' +
          'td.seat{border:1.2px solid #444 !important;border-radius:6px;background:#fff}' +
          'td.seat.empty{border:1px dashed #aaa !important}' +
          'td.seat .first{display:block;font-size:13px;font-weight:700}td.seat .last{display:block;font-size:9px;color:#666;margin-top:1px}' +
          '.board{display:flex;justify-content:center;margin:8px 0}' +
          '.board span{display:block;width:45%;text-align:center;padding:5px 0;border-radius:4px;background:#1d1d1b;color:#fff;font-size:11px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;-webkit-print-color-adjust:exact;print-color-adjust:exact}' +
          '.foot{margin-top:8px;font-size:9px;color:#888;text-align:right}' +
          '@page{size:A4 landscape;margin:12mm}' });
  }

  // ── Ereignisse ────────────────────────────────────────────────────────────
  function _bind() {
    if (!_container || _container.dataset.seatBound) return;
    _container.dataset.seatBound = '1';

    _container.addEventListener('click', function (e) {
      var classBtn = e.target.closest('[data-seat-class]');
      if (classBtn) {
        _activeClass = classBtn.getAttribute('data-seat-class');
        _selected = null;
        _editing = false;
        try { localStorage.setItem(CLASS_KEY, _activeClass); } catch (err) { /* private mode */ }
        render();
        return;
      }
      var action = e.target.closest('[data-seat-action]');
      if (action) {
        var menu = action.closest('details');
        if (menu) menu.open = false;
        var act = action.getAttribute('data-seat-action');
        if (act === 'setup') { _showSetupDialog(); return; }
        if (act === 'names') {
          if (window.LehrerClasslist && window.LehrerClasslist.editNames) window.LehrerClasslist.editNames(_activeClass, render);
          return;
        }
        var plan = _plan(_activeClass);
        if (act === 'shuffle') _shuffle();
        if (act === 'print') { _showPrintDialog(); return; }
        if (act === 'edit') { _editing = true; _selected = null; }
        if (act === 'done') _editing = false;
        if (act === 'flip') { plan.front = plan.front === 'top' ? 'bottom' : 'top'; plan.frontSet = true; _save(); }
        if (act === 'clear' && window.confirm('Alle Plätze in ' + _activeClass + ' leeren?')) { plan.seats = {}; _save(); }
        if (act === 'rows+') _resize(1, 0);
        if (act === 'rows-') _resize(-1, 0);
        if (act === 'cols+') _resize(0, 1);
        if (act === 'cols-') _resize(0, -1);
        render();
        return;
      }
      var chip = e.target.closest('[data-student]');
      if (chip) {
        var id = chip.getAttribute('data-student');
        _selected = _selected && _selected.kind === 'student' && _selected.id === id ? null : { kind: 'student', id: id };
        render();
        return;
      }
      var cell = e.target.closest('[data-cell]');
      if (cell) {
        var index = parseInt(cell.getAttribute('data-cell'), 10);
        if (_editing) { _toggleCell(index); render(); return; }
        var current = _plan(_activeClass);
        if (!current.cells[index]) { _selected = null; render(); return; }
        if (_selected && _selected.kind === 'student') { _place(_selected.id, index); _selected = null; }
        else if (_selected && _selected.kind === 'seat') {
          if (String(_selected.id) !== String(index)) _moveSeat(_selected.id, index);
          _selected = null;
        } else if (current.seats[index]) _selected = { kind: 'seat', id: index };
        render();
        return;
      }
      if (e.target.closest('[data-pool]') && _selected && _selected.kind === 'seat') {
        _unseat(_selected.id);
        _selected = null;
        render();
      }
    });

    _container.addEventListener('keydown', function (e) {
      if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[data-cell]')) { e.preventDefault(); e.target.click(); }
      if (e.key === 'Escape' && _selected) { _selected = null; render(); }
    });

    // Ziehen mit der Maus (am Handy: antippen, siehe oben)
    _container.addEventListener('dragstart', function (e) {
      var chip = e.target.closest('[data-student]');
      var cell = e.target.closest('[data-cell]');
      var payload = chip ? 's:' + chip.getAttribute('data-student') : cell ? 'c:' + cell.getAttribute('data-cell') : '';
      if (!payload) return;
      e.dataTransfer.setData('text/plain', payload);
      e.dataTransfer.effectAllowed = 'move';
    });
    _container.addEventListener('dragover', function (e) {
      var target = e.target.closest('.seat-cell.is-seat, [data-pool]');
      if (!target) return;
      e.preventDefault();
      _container.querySelectorAll('.is-drop').forEach(function (el) { el.classList.remove('is-drop'); });
      target.classList.add('is-drop');
    });
    _container.addEventListener('dragleave', function (e) {
      var target = e.target.closest('.is-drop');
      if (target && !target.contains(e.relatedTarget)) target.classList.remove('is-drop');
    });
    _container.addEventListener('drop', function (e) {
      var payload = e.dataTransfer.getData('text/plain') || '';
      var cell = e.target.closest('.seat-cell.is-seat');
      var pool = e.target.closest('[data-pool]');
      if (!payload || (!cell && !pool)) return;
      e.preventDefault();
      var value = payload.slice(2);
      if (cell) {
        var index = parseInt(cell.getAttribute('data-cell'), 10);
        if (payload[0] === 's') _place(value, index); else _moveSeat(value, index);
      } else if (payload[0] === 'c') _unseat(value);
      _selected = null;
      render();
    });
  }

  function _esc(str) {
    return String(str == null ? '' : str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function init(container) {
    _container = container;
    render();
  }

  /** For „Heute“: does this class have a plan with people seated? */
  function hasPlan(classId) {
    _load();
    var plan = _plans[String(classId || '').toLowerCase()];
    return !!plan && Object.keys(plan.seats).length > 0;
  }

  /** Select a class here (the caller switches to Klassen → Sitzplan). */
  function select(classId) {
    _activeClass = String(classId || '').toLowerCase();
    try { localStorage.setItem(CLASS_KEY, _activeClass); } catch (e) { /* private mode */ }
    _selected = null;
    _editing = false;
  }

  return { init: init, render: render, hasPlan: hasPlan, select: select };
})();

if (typeof window !== 'undefined') window.LehrerSeating = LehrerSeating;
