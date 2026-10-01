/**
 * LehrerGrades — Notenrechner mit zwei schnellen Werkzeugen
 *
 *   Zeugnisnote     pro Bereich ein Feld, Noten einfach hintereinander tippen
 *                   („2 3+ 2- 1“, doppelt zählen: „2x2“), Gewichtung per Klick,
 *                   Ergebnis sofort – ohne „Berechnen“.
 *   Punkte → Note   Höchstpunktzahl eingeben, der ganze Notenschlüssel steht da;
 *                   Schwellen per Klick (Standard, Abitur) oder selbst anpassen.
 *
 * Bewusst kein Notenbuch: keine Namen, keine Speicherung von Noten. Nur die
 * Einstellungen (Skala, Gewichtung, Schlüssel) bleiben im Browser.
 * Schnittstelle zu app.js unverändert (init, renderGrades …).
 */
(function () {
  'use strict';

  var SETTINGS_KEY = 'lc.gradesSettings';
  var _root = null;

  var WEIGHTS = [
    { id: '50', label: '50 / 50', first: 50 },
    { id: '33', label: '⅓ / ⅔', first: 100 / 3 },
    { id: '67', label: '⅔ / ⅓', first: 200 / 3 },
    { id: '40', label: '40 / 60', first: 40 },
    { id: '60', label: '60 / 40', first: 60 },
  ];

  // Mindestprozent je Note
  var KEYS = {
    standard: { label: 'Standard', scale: 'noten', steps: [[1, 92], [2, 81], [3, 67], [4, 50], [5, 30], [6, 0]] },
    abitur: { label: 'Abitur (Punkte)', scale: 'punkte', steps: [[15, 95], [14, 90], [13, 85], [12, 80], [11, 75], [10, 70], [9, 65], [8, 60], [7, 55], [6, 50], [5, 45], [4, 40], [3, 33], [2, 27], [1, 20], [0, 0]] },
  };

  var _settings = loadSettings();
  var _inputs = { a: '', b: '' };   // eingegebene Noten (nicht gespeichert)
  var _max = '';
  var _reached = '';

  function loadSettings() {
    var defaults = { tool: 'zeugnis', scale: 'noten', weight: '50', custom: 50, nameA: 'Schriftlich', nameB: 'Mündlich & Sonstiges', key: 'standard', steps: null };
    try { return Object.assign(defaults, JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}')); } catch (e) { return defaults; }
  }

  function saveSettings() {
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(_settings)); } catch (e) { /* ignore */ }
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function de(number, digits) {
    return number.toLocaleString('de-DE', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  // ── Noten lesen ──────────────────────────────────────────────────────────

  /** "2 3+ 2- 1,5 2x2" → [{value, weight}], ungültige Eingaben getrennt. */
  function parseGrades(text, scale) {
    var grades = [];
    var invalid = [];
    String(text || '').replace(/[;,](?=\s)|\s+/g, ' ').split(' ').forEach(function (token) {
      if (!token) return;
      var match = token.match(/^(\d{1,2}(?:[.,]\d+)?)([+-]?)(?:[x×*](\d+))?$/i);
      if (!match) { invalid.push(token); return; }
      var value = parseFloat(match[1].replace(',', '.'));
      var weight = match[3] ? parseInt(match[3], 10) : 1;
      if (scale === 'noten') {
        if (match[2] === '+') value -= 0.3;
        if (match[2] === '-') value += 0.3;
        if (value < 0.7 || value > 6.3) { invalid.push(token); return; }
      } else if (value < 0 || value > 15 || match[2]) { invalid.push(token); return; }
      if (weight < 1 || weight > 9) { invalid.push(token); return; }
      grades.push({ value: value, weight: weight });
    });
    return { grades: grades, invalid: invalid };
  }

  function average(grades) {
    var total = grades.reduce(function (sum, g) { return sum + g.weight; }, 0);
    if (!total) return null;
    return grades.reduce(function (sum, g) { return sum + g.value * g.weight; }, 0) / total;
  }

  /** Note 1–6 mit Tendenz für einen Durchschnitt. */
  function gradeLabel(avg, scale) {
    if (avg == null) return '';
    if (scale === 'punkte') return String(Math.round(avg)) + ' Punkte';
    var whole = Math.min(6, Math.max(1, Math.floor(avg + 0.5)));
    var diff = avg - whole;
    var tendency = whole < 6 && diff > 0.16 ? '-' : (whole > 1 && diff < -0.16 ? '+' : '');
    return { whole: whole, withTendency: whole + tendency };
  }

  // ── Darstellung ──────────────────────────────────────────────────────────

  function segmented(name, options, active) {
    return '<div class="segmented-control gr-seg" role="radiogroup">' + options.map(function (option) {
      return '<button type="button" class="segment-button' + (option.id === active ? ' active' : '') + '" data-gr-' + name + '="' + option.id + '" aria-pressed="' + (option.id === active) + '">' + esc(option.label) + '</button>';
    }).join('') + '</div>';
  }

  function firstShare() {
    if (_settings.weight === 'custom') return Math.min(100, Math.max(0, Number(_settings.custom) || 0));
    var preset = WEIGHTS.filter(function (w) { return w.id === _settings.weight; })[0];
    return preset ? preset.first : 50;
  }

  function renderZeugnis() {
    var share = firstShare();
    var hint = _settings.scale === 'noten'
      ? 'Noten mit Leerzeichen trennen – „2+“ zählt 1,7, „2-“ 2,3. Doppelt zählen: „2x2“.'
      : 'Punkte mit Leerzeichen trennen. Doppelt zählen: „11x2“.';
    var box = function (id, name, pct) {
      return '<div class="gr-box">'
        + '<div class="gr-box-head"><input class="gr-name" data-gr-name="' + id + '" value="' + esc(name) + '" aria-label="Name des Bereichs" />'
        + '<span class="gr-pct">' + de(pct, pct % 1 ? 1 : 0) + ' %</span></div>'
        + '<input class="form-input gr-input" data-gr-input="' + id + '" value="' + esc(_inputs[id]) + '" inputmode="text" autocomplete="off" spellcheck="false" placeholder="' + (_settings.scale === 'noten' ? 'z. B. 2 3+ 2- 1' : 'z. B. 11 9 13') + '" />'
        + '<p class="gr-avg" data-gr-avg="' + id + '"></p></div>';
    };
    return '<div class="gr-row">'
      + '<span class="gr-label">Gewichtung</span>'
      + segmented('weight', WEIGHTS.concat([{ id: 'custom', label: 'eigene' }]), _settings.weight)
      + (_settings.weight === 'custom' ? '<label class="gr-custom"><input class="form-input" type="number" min="0" max="100" data-gr-custom value="' + esc(_settings.custom) + '" /> % / Rest</label>' : '')
      + '</div>'
      + '<div class="gr-boxes">' + box('a', _settings.nameA, share) + box('b', _settings.nameB, 100 - share) + '</div>'
      + '<p class="gr-hint">' + esc(hint) + '</p>'
      + '<div class="gr-result" data-gr-result></div>';
  }

  function updateZeugnis() {
    if (!_root) return;
    var share = firstShare() / 100;
    var parts = ['a', 'b'].map(function (id) {
      var parsed = parseGrades(_inputs[id], _settings.scale);
      var avg = average(parsed.grades);
      var el = _root.querySelector('[data-gr-avg="' + id + '"]');
      if (el) {
        var count = parsed.grades.reduce(function (sum, g) { return sum + g.weight; }, 0);
        el.innerHTML = (avg == null ? '<span class="gr-muted">noch keine Noten</span>'
          : 'Ø <strong>' + de(avg, 2) + '</strong> <span class="gr-muted">· ' + count + (count === 1 ? ' Note' : ' Noten') + '</span>')
          + (parsed.invalid.length ? ' <span class="gr-warn">nicht erkannt: ' + esc(parsed.invalid.join(' ')) + '</span>' : '');
      }
      return avg;
    });
    var result;
    if (parts[0] == null && parts[1] == null) result = null;
    else if (parts[0] == null) result = parts[1];
    else if (parts[1] == null) result = parts[0];
    else result = parts[0] * share + parts[1] * (1 - share);
    var box = _root.querySelector('[data-gr-result]');
    if (!box) return;
    if (result == null) { box.innerHTML = '<span class="gr-muted">Das Ergebnis erscheint, sobald du Noten eingibst.</span>'; return; }
    var label = gradeLabel(result, _settings.scale);
    var onlyOne = parts[0] == null || parts[1] == null;
    box.innerHTML = '<span class="gr-result-label">Gesamt</span>'
      + '<span class="gr-result-avg">' + de(result, 2) + '</span>'
      + '<span class="gr-result-arrow" aria-hidden="true">→</span>'
      + '<span class="gr-result-grade">' + esc(_settings.scale === 'noten' ? label.whole : label) + '</span>'
      + (_settings.scale === 'noten' ? '<span class="gr-result-tendency">Tendenz ' + esc(label.withTendency) + '</span>' : '')
      + (onlyOne ? '<span class="gr-muted gr-result-note">nur ein Bereich eingetragen</span>' : '')
      + '<button type="button" class="btn btn-sm btn-ghost gr-clear" data-gr-clear>Leeren</button>';
  }

  function currentSteps() {
    var preset = KEYS[_settings.key] || KEYS.standard;
    return _settings.key === 'custom' && Array.isArray(_settings.steps) ? _settings.steps : preset.steps;
  }

  function renderSchluessel() {
    return '<div class="gr-row">'
      + '<label class="gr-field"><span>Höchstpunktzahl</span><input class="form-input" type="number" min="1" step="0.5" inputmode="decimal" data-gr-max value="' + esc(_max) + '" placeholder="z. B. 48" /></label>'
      + '<label class="gr-field"><span>Erreicht (optional)</span><input class="form-input" type="number" min="0" step="0.5" inputmode="decimal" data-gr-reached value="' + esc(_reached) + '" placeholder="z. B. 37" /></label>'
      + '<span class="gr-label">Schlüssel</span>'
      + segmented('key', [{ id: 'standard', label: 'Standard' }, { id: 'abitur', label: 'Abitur (Punkte)' }, { id: 'custom', label: 'eigener' }], _settings.key)
      + '</div><div class="gr-reached" data-gr-reached-result></div><div data-gr-table></div>'
      + '<p class="gr-hint">' + (_settings.key === 'custom' ? 'Die Prozentwerte in der Tabelle kannst du ändern – sie bleiben gespeichert.' : 'Ab-Werte auf halbe Punkte gerundet. Eigene Grenzen: „eigener“ wählen.') + '</p>';
  }

  function updateSchluessel() {
    if (!_root) return;
    var max = parseFloat(String(_max).replace(',', '.'));
    var steps = currentSteps();
    var table = _root.querySelector('[data-gr-table]');
    var reachedBox = _root.querySelector('[data-gr-reached-result]');
    var editable = _settings.key === 'custom';
    var punkte = _settings.key === 'abitur' || (editable && steps.length > 6);
    var points = function (pct) { return Math.ceil(max * pct / 100 * 2) / 2; };
    table.innerHTML = '<table class="gr-table"><thead><tr><th>' + (punkte ? 'Punkte' : 'Note') + '</th><th>ab %</th><th>ab Punkten</th></tr></thead><tbody>'
      + steps.map(function (step, index) {
        var pct = step[1];
        var from = max > 0 ? points(pct) : null;
        var upper = index > 0 && max > 0 ? points(steps[index - 1][1]) - 0.5 : (max > 0 ? max : null);
        return '<tr><td><strong>' + esc(step[0]) + '</strong></td>'
          + '<td>' + (editable && index < steps.length - 1 ? '<input class="gr-pct-input" type="number" min="0" max="100" data-gr-step="' + index + '" value="' + esc(pct) + '" />' : esc(pct)) + '</td>'
          + '<td>' + (from == null ? '–' : de(from, from % 1 ? 1 : 0) + (upper != null && upper > from ? ' – ' + de(upper, upper % 1 ? 1 : 0) : '')) + '</td></tr>';
      }).join('') + '</tbody></table>';

    var reached = parseFloat(String(_reached).replace(',', '.'));
    if (max > 0 && reached >= 0 && reached <= max) {
      var pct = reached / max * 100;
      var hit = steps.filter(function (step) { return pct >= step[1]; })[0] || steps[steps.length - 1];
      reachedBox.innerHTML = '<span class="gr-result-avg">' + de(pct, 1) + ' %</span><span class="gr-result-arrow" aria-hidden="true">→</span>'
        + '<span class="gr-result-grade">' + esc(hit[0]) + (punkte ? ' P.' : '') + '</span>';
      reachedBox.hidden = false;
    } else {
      reachedBox.hidden = true;
    }
  }

  function renderGrades() {
    _root = document.getElementById('grades-root');
    if (!_root) return;
    var zeugnis = _settings.tool !== 'schluessel';
    _root.innerHTML = '<div class="gr-top">'
      + segmented('tool', [{ id: 'zeugnis', label: 'Zeugnisnote' }, { id: 'schluessel', label: 'Punkte → Note' }], zeugnis ? 'zeugnis' : 'schluessel')
      + (zeugnis ? segmented('scale', [{ id: 'noten', label: 'Noten 1–6' }, { id: 'punkte', label: 'Punkte 0–15' }], _settings.scale) : '')
      + '</div>'
      + (zeugnis ? renderZeugnis() : renderSchluessel())
      + '<p class="gr-privacy">Nichts davon wird gespeichert – nur deine Einstellungen.</p>';
    if (zeugnis) updateZeugnis(); else updateSchluessel();
    bind();
  }

  function bind() {
    if (_root.dataset.bound) return;
    _root.dataset.bound = '1';
    _root.addEventListener('click', function (event) {
      var btn = event.target.closest('button');
      if (!btn) return;
      if (btn.dataset.grTool) { _settings.tool = btn.dataset.grTool; saveSettings(); renderGrades(); }
      else if (btn.dataset.grScale) { _settings.scale = btn.dataset.grScale; saveSettings(); renderGrades(); }
      else if (btn.dataset.grWeight) { _settings.weight = btn.dataset.grWeight; saveSettings(); renderGrades(); }
      else if (btn.dataset.grKey) {
        if (btn.dataset.grKey === 'custom' && !Array.isArray(_settings.steps)) _settings.steps = KEYS.standard.steps.map(function (s) { return s.slice(); });
        _settings.key = btn.dataset.grKey; saveSettings(); renderGrades();
      } else if (btn.hasAttribute('data-gr-clear')) {
        _inputs = { a: '', b: '' };
        renderGrades();
        var first = _root.querySelector('[data-gr-input="a"]');
        if (first) first.focus();
      }
    });
    _root.addEventListener('input', function (event) {
      var el = event.target;
      if (el.dataset.grInput) { _inputs[el.dataset.grInput] = el.value; updateZeugnis(); }
      else if (el.hasAttribute('data-gr-custom')) { _settings.custom = el.value; saveSettings(); updatePercents(); updateZeugnis(); }
      else if (el.dataset.grName) { _settings[el.dataset.grName === 'a' ? 'nameA' : 'nameB'] = el.value.slice(0, 40); saveSettings(); }
      else if (el.hasAttribute('data-gr-max')) { _max = el.value; updateSchluessel(); }
      else if (el.hasAttribute('data-gr-reached')) { _reached = el.value; updateSchluessel(); }
    });
    _root.addEventListener('change', function (event) {
      var el = event.target;
      if (el.dataset.grStep !== undefined && Array.isArray(_settings.steps)) {
        _settings.steps[Number(el.dataset.grStep)][1] = Math.min(100, Math.max(0, Number(el.value) || 0));
        saveSettings();
        updateSchluessel();
      }
    });
  }

  function updatePercents() {
    var share = firstShare();
    var pcts = _root.querySelectorAll('.gr-pct');
    if (pcts[0]) pcts[0].textContent = de(share, share % 1 ? 1 : 0) + ' %';
    if (pcts[1]) pcts[1].textContent = de(100 - share, (100 - share) % 1 ? 1 : 0) + ' %';
  }

  // ── Schnittstelle zu app.js ──────────────────────────────────────────────

  function init() { renderGrades(); }
  function noop() { return Promise.resolve(); }
  // Kein Notenbuch: diese Teile der Schnittstelle liefern bewusst leere Daten.
  function getGradebookData() { return { entries: [] }; }
  function getNotesData() { return { notes: [] }; }
  function getGradeClasses() { return []; }
  function summarizeGrades() { return { averageLabel: '-', riskCount: 0 }; }
  function renderClassNotes() {}

  window.LehrerGrades = {
    init: init,
    renderGrades: renderGrades,
    parseGrades: parseGrades,
    loadGradebook: function () { renderGrades(); return Promise.resolve(); },
    loadNotes: noop,
    saveGradeEntry: noop,
    deleteGradeEntry: noop,
    saveClassNote: noop,
    clearClassNote: noop,
    getGradebookData: getGradebookData,
    getNotesData: getNotesData,
    getGradeClasses: getGradeClasses,
    summarizeGrades: summarizeGrades,
    renderClassNotes: renderClassNotes,
  };
})();
