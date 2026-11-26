/**
 * LehrerGrades — Notenrechner mit zwei schnellen Werkzeugen
 *
 *   Zeugnisnote     so viele Teilnoten wie nötig (Schriftlich, Mündlich, Tests …),
 *                   je ein Feld, Noten einfach hintereinander tippen
 *                   („2 3+ 2- 1“, doppelt zählen: „2x2“), Gewichtung in Prozent
 *                   (bei zwei Teilnoten auch per Klick), Ergebnis sofort.
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

  // Mindestprozent je Note. Einen landesweit verbindlichen Berliner Schlüssel gibt
  // es nicht (Sek I-VO, § 15 VO-GO: die Gesamtkonferenz legt ihn fest) – deshalb
  // trägt jede Lehrkraft ihren Schulschlüssel einmal selbst ein. Bis dahin gelten
  // diese Beispielwerte.
  var EXAMPLE_KEYS = {
    noten: [[1, 92], [2, 81], [3, 67], [4, 50], [5, 30], [6, 0]],
    punkte: [[15, 95], [14, 90], [13, 85], [12, 80], [11, 75], [10, 70], [9, 65], [8, 60], [7, 55], [6, 50], [5, 45], [4, 40], [3, 33], [2, 27], [1, 20], [0, 0]],
  };

  var MAX_AREAS = 8;

  function copySteps(steps) { return steps.map(function (step) { return step.slice(); }); }
  function areaId() { return 'x' + Math.random().toString(36).slice(2, 8); }
  function num(value) { return parseFloat(String(value == null ? '' : value).replace(',', '.')); }

  var _settings = loadSettings();
  var _inputs = {};   // Bereich → eingegebene Noten (nicht gespeichert)
  var _max = '';
  var _reached = '';
  var _editKey = false;

  function loadSettings() {
    var defaults = { tool: 'zeugnis', scale: 'noten', weight: '50', custom: 50, nameA: 'Schriftlich', nameB: 'Mündlich & Sonstiges',
      keyScale: 'noten', keys: { noten: copySteps(EXAMPLE_KEYS.noten), punkte: copySteps(EXAMPLE_KEYS.punkte) }, keysOwn: { noten: false, punkte: false } };
    var stored = {};
    try { stored = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}') || {}; } catch (e) { stored = {}; }
    // earlier versions: key "custom" with own steps for the 1–6 scale
    if (stored.key === 'custom' && Array.isArray(stored.steps)) {
      stored.keys = { noten: stored.steps, punkte: copySteps(EXAMPLE_KEYS.punkte) };
      stored.keysOwn = { noten: true, punkte: false };
    }
    if (stored.key === 'abitur') stored.keyScale = 'punkte';
    delete stored.key; delete stored.steps;
    var merged = Object.assign(defaults, stored);
    if (!merged.keys || !Array.isArray(merged.keys.noten) || !Array.isArray(merged.keys.punkte)) merged.keys = defaults.keys;
    merged.keysOwn = Object.assign({ noten: false, punkte: false }, merged.keysOwn);
    // earlier versions: exactly two areas (nameA/nameB) with a preset or own share
    if (!Array.isArray(merged.areas) || !merged.areas.length) {
      var preset = WEIGHTS.filter(function (w) { return w.id === merged.weight; })[0];
      var first = merged.weight === 'custom' ? Math.min(100, Math.max(0, Number(merged.custom) || 0)) : (preset ? preset.first : 50);
      merged.areas = [{ id: 'a', name: merged.nameA, weight: first }, { id: 'b', name: merged.nameB, weight: 100 - first }];
    }
    var seen = {};
    merged.areas = merged.areas.filter(function (a) { return a && typeof a === 'object'; }).slice(0, MAX_AREAS).map(function (a) {
      var id = /^[a-z0-9]{1,12}$/i.test(String(a.id || '')) && !seen[a.id] ? String(a.id) : areaId();
      seen[id] = true;
      var weight = num(a.weight);
      return { id: id, name: String(a.name == null ? 'Teilnote' : a.name).slice(0, 40), weight: weight >= 0 && weight <= 100 ? weight : 0 };
    });
    if (!merged.areas.length) merged.areas = [{ id: 'a', name: 'Schriftlich', weight: 50 }, { id: 'b', name: 'Mündlich & Sonstiges', weight: 50 }];
    return merged;
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

  function pctText(value) {
    var rounded = Math.round(value * 10) / 10;
    return de(rounded, rounded % 1 ? 1 : 0);
  }

  function weightSum() {
    return _settings.areas.reduce(function (sum, a) { return sum + a.weight; }, 0);
  }

  /** The preset that matches two areas, if any. */
  function activePreset() {
    var areas = _settings.areas;
    if (areas.length !== 2) return '';
    var hit = WEIGHTS.filter(function (w) {
      return Math.abs(areas[0].weight - w.first) < 0.2 && Math.abs(areas[1].weight - (100 - w.first)) < 0.2;
    })[0];
    return hit ? hit.id : '';
  }

  function renderZeugnis() {
    var areas = _settings.areas;
    var hint = _settings.scale === 'noten'
      ? 'Noten mit Leerzeichen trennen – „2+“ zählt 1,7, „2-“ 2,3. Doppelt zählen: „2x2“.'
      : 'Punkte mit Leerzeichen trennen. Doppelt zählen: „11x2“.';
    var box = function (area) {
      return '<div class="gr-box" data-gr-area="' + area.id + '">'
        + '<div class="gr-box-head"><input class="gr-name" data-gr-name="' + area.id + '" value="' + esc(area.name) + '" aria-label="Name der Teilnote" />'
        + '<label class="gr-weight"><input class="gr-weight-input" data-gr-w="' + area.id + '" value="' + esc(pctText(area.weight)) + '" inputmode="decimal" autocomplete="off" aria-label="Gewicht von ' + esc(area.name) + ' in Prozent" />%</label>'
        + (areas.length > 1 ? '<button type="button" class="gr-remove" data-gr-remove="' + area.id + '" aria-label="' + esc(area.name || 'Teilnote') + ' entfernen" title="Teilnote entfernen">✕</button>' : '')
        + '</div>'
        + '<input class="form-input gr-input" data-gr-input="' + area.id + '" value="' + esc(_inputs[area.id] || '') + '" inputmode="text" autocomplete="off" spellcheck="false" placeholder="' + (_settings.scale === 'noten' ? 'z. B. 2 3+ 2- 1' : 'z. B. 11 9 13') + '" />'
        + '<p class="gr-avg" data-gr-avg="' + area.id + '"></p></div>';
    };
    return (areas.length === 2
        ? '<div class="gr-row"><span class="gr-label">Gewichtung</span>' + segmented('weight', WEIGHTS, activePreset()) + '</div>'
        : '')
      + '<div class="gr-boxes' + (areas.length > 2 ? ' is-many' : '') + '">' + areas.map(box).join('') + '</div>'
      + '<div class="gr-area-actions">'
      +   (areas.length < MAX_AREAS ? '<button type="button" class="btn btn-sm btn-secondary" data-gr-add>＋ Teilnote</button>' : '')
      +   (areas.length > 1 ? '<button type="button" class="btn btn-sm btn-ghost" data-gr-equal>Gleich gewichten</button>' : '')
      +   '<span class="gr-sum" data-gr-sum></span>'
      + '</div>'
      + '<p class="gr-hint">' + esc(hint) + '</p>'
      + '<div class="gr-result" data-gr-result></div>';
  }

  function updateZeugnis() {
    if (!_root) return;
    var areas = _settings.areas;
    var parts = areas.map(function (area) {
      var parsed = parseGrades(_inputs[area.id], _settings.scale);
      var avg = average(parsed.grades);
      var el = _root.querySelector('[data-gr-avg="' + area.id + '"]');
      if (el) {
        var count = parsed.grades.reduce(function (sum, g) { return sum + g.weight; }, 0);
        el.innerHTML = (avg == null ? '<span class="gr-muted">noch keine Noten</span>'
          : 'Ø <strong>' + de(avg, 2) + '</strong> <span class="gr-muted">· ' + count + (count === 1 ? ' Note' : ' Noten') + '</span>')
          + (parsed.invalid.length ? ' <span class="gr-warn">nicht erkannt: ' + esc(parsed.invalid.join(' ')) + '</span>' : '');
      }
      return { area: area, avg: avg };
    });

    var sum = weightSum();
    var sumEl = _root.querySelector('[data-gr-sum]');
    if (sumEl) {
      var off = areas.length > 1 && Math.abs(sum - 100) > 0.5;
      sumEl.className = 'gr-sum' + (off ? ' gr-warn' : ' gr-muted');
      sumEl.textContent = areas.length < 2 ? '' : off
        ? 'Zusammen ' + pctText(sum) + ' % statt 100 % – gerechnet wird anteilig.'
        : 'Zusammen 100 %';
    }
    var preset = activePreset();
    _root.querySelectorAll('[data-gr-weight]').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.grWeight === preset);
      btn.setAttribute('aria-pressed', String(btn.dataset.grWeight === preset));
    });

    var counted = parts.filter(function (p) { return p.avg != null && p.area.weight > 0; });
    var missing = parts.filter(function (p) { return p.avg == null; });
    var total = counted.reduce(function (s, p) { return s + p.area.weight; }, 0);
    var result = total ? counted.reduce(function (s, p) { return s + p.avg * p.area.weight; }, 0) / total : null;
    var box = _root.querySelector('[data-gr-result]');
    if (!box) return;
    if (result == null) {
      var anyGrades = parts.some(function (p) { return p.avg != null; });
      box.innerHTML = '<span class="gr-muted">' + (anyGrades ? 'Die Teilnoten mit Noten haben 0 % Gewicht.' : 'Das Ergebnis erscheint, sobald du Noten eingibst.') + '</span>';
      return;
    }
    var label = gradeLabel(result, _settings.scale);
    var note = missing.length && areas.length > 1
      ? 'ohne Noten, nicht mitgerechnet: ' + missing.map(function (p) { return p.area.name || 'Teilnote'; }).join(', ')
      : '';
    box.innerHTML = '<span class="gr-result-label">Gesamt</span>'
      + '<span class="gr-result-avg">' + de(result, 2) + '</span>'
      + '<span class="gr-result-arrow" aria-hidden="true">→</span>'
      + '<span class="gr-result-grade">' + esc(_settings.scale === 'noten' ? label.whole : label) + '</span>'
      + (_settings.scale === 'noten' ? '<span class="gr-result-tendency">Tendenz ' + esc(label.withTendency) + '</span>' : '')
      + (note ? '<span class="gr-muted gr-result-note">' + esc(note) + '</span>' : '')
      + '<button type="button" class="btn btn-sm btn-ghost gr-clear" data-gr-clear>Leeren</button>';
  }

  function addArea() {
    var areas = _settings.areas;
    if (areas.length >= MAX_AREAS) return;
    var rest = 100 - weightSum();
    var area = { id: areaId(), name: 'Teilnote ' + (areas.length + 1), weight: rest > 0.5 ? rest : 0 };
    areas.push(area);
    if (rest <= 0.5) equalWeights();
    saveSettings();
    renderGrades();
    var name = _root.querySelector('[data-gr-name="' + area.id + '"]');
    if (name) { name.focus(); name.select(); }
  }

  function removeArea(id) {
    var areas = _settings.areas;
    if (areas.length < 2) return;
    _settings.areas = areas.filter(function (a) { return a.id !== id; });
    delete _inputs[id];
    var left = _settings.areas;
    var sum = weightSum();
    if (left.length === 1) left[0].weight = 100;
    else if (sum > 0) left.forEach(function (a) { a.weight = a.weight * 100 / sum; });
    else equalWeights();
    saveSettings();
    renderGrades();
  }

  function equalWeights() {
    var areas = _settings.areas;
    areas.forEach(function (a) { a.weight = 100 / areas.length; });
  }

  function setWeight(id, text) {
    var value = num(text);
    if (!(value >= 0 && value <= 100)) return;
    var areas = _settings.areas;
    var area = areas.filter(function (a) { return a.id === id; })[0];
    if (!area) return;
    area.weight = value;
    if (areas.length === 2) {   // two areas: the other one takes the rest
      var other = areas[0] === area ? areas[1] : areas[0];
      other.weight = 100 - value;
      var otherInput = _root.querySelector('[data-gr-w="' + other.id + '"]');
      if (otherInput) otherInput.value = pctText(other.weight);
    }
    saveSettings();
    updateZeugnis();
  }

  function currentSteps() {
    return _settings.keys[_settings.keyScale === 'punkte' ? 'punkte' : 'noten'];
  }

  function renderSchluessel() {
    var scale = _settings.keyScale === 'punkte' ? 'punkte' : 'noten';
    var own = _settings.keysOwn[scale];
    return '<div class="gr-row">'
      + '<label class="gr-field"><span>Höchstpunktzahl</span><input class="form-input" type="number" min="1" step="0.5" inputmode="decimal" data-gr-max value="' + esc(_max) + '" placeholder="z. B. 48" /></label>'
      + '<label class="gr-field"><span>Erreicht (optional)</span><input class="form-input" type="number" min="0" step="0.5" inputmode="decimal" data-gr-reached value="' + esc(_reached) + '" placeholder="z. B. 37" /></label>'
      + segmented('keyscale', [{ id: 'noten', label: 'Noten 1–6' }, { id: 'punkte', label: 'Punkte 0–15' }], scale)
      + '</div>'
      + (own ? '' : '<p class="gr-keynote">Einen verbindlichen Berliner Schlüssel gibt es nicht – eure Gesamtkonferenz legt ihn fest. '
        + 'Trag euren Schlüssel einmal unter „Grenzen anpassen“ ein: Er bleibt gespeichert und gilt auf allen deinen Geräten. Bis dahin: Beispielwerte.</p>')
      + '<div class="gr-reached" data-gr-reached-result></div><div data-gr-table></div>'
      + '<div class="gr-key-actions">'
      + '<button type="button" class="btn btn-sm ' + (_editKey ? 'btn-primary' : 'btn-secondary') + '" data-gr-editkey>' + (_editKey ? 'Fertig' : 'Grenzen anpassen') + '</button>'
      + (_editKey ? '<button type="button" class="btn btn-sm btn-ghost" data-gr-resetkey>Beispielwerte</button>' : '')
      + '<span class="gr-muted gr-key-status">' + (own ? 'Dein Schlüssel – gespeichert.' : 'Beispielwerte') + '</span></div>';
  }

  function updateSchluessel() {
    if (!_root) return;
    var max = parseFloat(String(_max).replace(',', '.'));
    var steps = currentSteps();
    var table = _root.querySelector('[data-gr-table]');
    var reachedBox = _root.querySelector('[data-gr-reached-result]');
    var punkte = _settings.keyScale === 'punkte';
    var points = function (pct) { return Math.ceil(max * pct / 100 * 2) / 2; };
    table.innerHTML = '<table class="gr-table"><thead><tr><th>' + (punkte ? 'Punkte' : 'Note') + '</th><th>ab %</th><th>Punkte</th></tr></thead><tbody>'
      + steps.map(function (step, index) {
        var pct = step[1];
        var from = max > 0 ? points(pct) : null;
        var upper = index > 0 && max > 0 ? points(steps[index - 1][1]) - 0.5 : (max > 0 ? max : null);
        return '<tr><td><strong>' + esc(step[0]) + '</strong></td>'
          + '<td>' + (_editKey && index < steps.length - 1 ? '<input class="gr-pct-input" type="number" min="0" max="100" step="0.5" inputmode="decimal" data-gr-step="' + index + '" value="' + esc(pct) + '" />' : esc(String(pct).replace('.', ','))) + '</td>'
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
      else if (btn.dataset.grWeight) {
        var preset = WEIGHTS.filter(function (w) { return w.id === btn.dataset.grWeight; })[0];
        if (preset && _settings.areas.length === 2) {
          _settings.areas[0].weight = preset.first;
          _settings.areas[1].weight = 100 - preset.first;
          saveSettings(); renderGrades();
        }
      }
      else if (btn.hasAttribute('data-gr-add')) addArea();
      else if (btn.dataset.grRemove) removeArea(btn.dataset.grRemove);
      else if (btn.hasAttribute('data-gr-equal')) { equalWeights(); saveSettings(); renderGrades(); }
      else if (btn.dataset.grKeyscale) { _settings.keyScale = btn.dataset.grKeyscale; saveSettings(); renderGrades(); }
      else if (btn.hasAttribute('data-gr-editkey')) { _editKey = !_editKey; renderGrades(); }
      else if (btn.hasAttribute('data-gr-resetkey')) {
        var scale = _settings.keyScale === 'punkte' ? 'punkte' : 'noten';
        _settings.keys[scale] = copySteps(EXAMPLE_KEYS[scale]);
        _settings.keysOwn[scale] = false;
        saveSettings(); renderGrades();
      } else if (btn.hasAttribute('data-gr-clear')) {
        _inputs = {};
        renderGrades();
        var first = _root.querySelector('[data-gr-input]');
        if (first) first.focus();
      }
    });
    _root.addEventListener('input', function (event) {
      var el = event.target;
      if (el.dataset.grInput) { _inputs[el.dataset.grInput] = el.value; updateZeugnis(); }
      else if (el.dataset.grW) setWeight(el.dataset.grW, el.value);
      else if (el.dataset.grName) {
        _settings.areas.forEach(function (a) { if (a.id === el.dataset.grName) a.name = el.value.slice(0, 40); });
        saveSettings();
      }
      else if (el.hasAttribute('data-gr-max')) { _max = el.value; updateSchluessel(); }
      else if (el.hasAttribute('data-gr-reached')) { _reached = el.value; updateSchluessel(); }
    });
    _root.addEventListener('change', function (event) {
      var el = event.target;
      if (el.dataset.grW) {   // tidy the shown number when leaving the field
        var area = _settings.areas.filter(function (a) { return a.id === el.dataset.grW; })[0];
        if (area) el.value = pctText(area.weight);
        return;
      }
      if (el.dataset.grStep !== undefined) {
        var scale = _settings.keyScale === 'punkte' ? 'punkte' : 'noten';
        var steps = _settings.keys[scale];
        var index = Number(el.dataset.grStep);
        var value = Math.min(100, Math.max(0, parseFloat(String(el.value).replace(',', '.')) || 0));
        // keep the order: a better grade needs at least as much as the next one
        var lower = index < steps.length - 1 ? steps[index + 1][1] : 0;
        var upper = index > 0 ? steps[index - 1][1] : 100;
        steps[index][1] = Math.min(upper, Math.max(lower, value));
        _settings.keysOwn[scale] = true;
        saveSettings();
        updateSchluessel();
        var status = _root.querySelector('.gr-key-status');
        if (status) status.textContent = 'Dein Schlüssel – gespeichert.';
      }
    });
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
