/**
 * LehrerGrades — minimaler Notenrechner
 *
 * Bewusst kein Notenbuch:
 * - keine Klassen
 * - keine Speicherung von Schuelerdaten
 * - keine Notizen
 * - keine Backend-Abhaengigkeit
 *
 * Fokus:
 * - gewichtete Teilnoten
 * - haeufige Presets (1/3 : 2/3, 50/50, 25/25/50)
 * - sofort sichtbares Ergebnis
 */
(function () {
  'use strict';

  var _elements = null;
  var _callbacks = {};
  var _activePreset = 'one-third';
  var _rows = [];

  var PRESETS = {
    'one-third': [
      { label: 'Teilnote 1', value: '', weight: '33,33' },
      { label: 'Teilnote 2', value: '', weight: '66,67' },
    ],
    'half-half': [
      { label: 'Teilnote 1', value: '', weight: '50' },
      { label: 'Teilnote 2', value: '', weight: '50' },
    ],
    'quarters': [
      { label: 'Teilnote 1', value: '', weight: '25' },
      { label: 'Teilnote 2', value: '', weight: '25' },
      { label: 'Teilnote 3', value: '', weight: '50' },
    ],
    'custom': [
      { label: 'Teilnote 1', value: '', weight: '' },
      { label: 'Teilnote 2', value: '', weight: '' },
    ],
  };

  function init(_state, elements, callbacks) {
    _elements = elements;
    _callbacks = callbacks || {};
    if (!_rows.length) {
      _rows = clonePreset(_activePreset);
    }
    bindUi();
  }

  function bindUi() {
    if (!_elements) return;

    if (_elements.gradesAddRow && !_elements.gradesAddRow.dataset.bound) {
      _elements.gradesAddRow.dataset.bound = 'true';
      _elements.gradesAddRow.addEventListener('click', function () {
        syncRowsFromDom();
        _rows.push({
          label: 'Teilnote ' + (_rows.length + 1),
          value: '',
          weight: '',
        });
        renderGrades();
      });
    }

    if (_elements.gradesReset && !_elements.gradesReset.dataset.bound) {
      _elements.gradesReset.dataset.bound = 'true';
      _elements.gradesReset.addEventListener('click', function () {
        applyPreset(_activePreset);
      });
    }

    if (_elements.gradesPresetButtons && !_elements.gradesPresetButtons.dataset.bound) {
      _elements.gradesPresetButtons.dataset.bound = 'true';
      _elements.gradesPresetButtons.addEventListener('click', function (event) {
        var button = event.target.closest('[data-grade-preset]');
        if (!button) return;
        applyPreset(button.dataset.gradePreset);
      });
    }

    if (_elements.gradesRows && !_elements.gradesRows.dataset.bound) {
      _elements.gradesRows.dataset.bound = 'true';
      _elements.gradesRows.addEventListener('input', function () {
        syncRowsFromDom();
        renderResult();
      });
      _elements.gradesRows.addEventListener('click', function (event) {
        var removeButton = event.target.closest('[data-grade-remove]');
        if (!removeButton) return;
        syncRowsFromDom();
        var index = Number(removeButton.dataset.gradeRemove);
        if (isFinite(index)) {
          _rows.splice(index, 1);
          if (!_rows.length) {
            _rows = clonePreset(_activePreset);
          }
          renderGrades();
        }
      });
    }
  }

  function clonePreset(presetId) {
    var preset = PRESETS[presetId] || PRESETS['one-third'];
    return preset.map(function (row) {
      return {
        label: row.label,
        value: row.value,
        weight: row.weight,
      };
    });
  }

  function applyPreset(presetId) {
    _activePreset = PRESETS[presetId] ? presetId : 'one-third';
    _rows = clonePreset(_activePreset);
    renderGrades();
    setFeedback('');
  }

  function syncRowsFromDom() {
    if (!_elements || !_elements.gradesRows) return;
    var rows = Array.from(_elements.gradesRows.querySelectorAll('[data-grade-row]'));
    _rows = rows.map(function (row, index) {
      var labelInput = row.querySelector('[data-grade-field="label"]');
      var valueInput = row.querySelector('[data-grade-field="value"]');
      var weightInput = row.querySelector('[data-grade-field="weight"]');
      return {
        label: (labelInput && labelInput.value.trim()) || ('Teilnote ' + (index + 1)),
        value: (valueInput && valueInput.value.trim()) || '',
        weight: (weightInput && weightInput.value.trim()) || '',
      };
    });
  }

  function parseGradeValue(value) {
    var token = String(value || '').trim();
    if (!token) return NaN;
    var mapping = {
      '1+': 0.7, '1': 1, '1-': 1.3,
      '2+': 1.7, '2': 2, '2-': 2.3,
      '3+': 2.7, '3': 3, '3-': 3.3,
      '4+': 3.7, '4': 4, '4-': 4.3,
      '5+': 4.7, '5': 5, '5-': 5.3,
      '6': 6,
    };
    if (mapping[token] !== undefined) return mapping[token];
    var numeric = Number(token.replace(',', '.'));
    return isFinite(numeric) ? numeric : NaN;
  }

  function parseWeight(value) {
    var token = String(value || '').trim();
    if (!token) return NaN;
    var numeric = Number(token.replace('%', '').replace(',', '.'));
    return isFinite(numeric) ? numeric : NaN;
  }

  function formatNumber(value) {
    return String(value).replace('.', ',');
  }

  function formatGrade(value) {
    if (!isFinite(value)) return '-';
    return value.toFixed(2).replace('.', ',');
  }

  function approximateGradeLabel(value) {
    if (!isFinite(value)) return '-';
    var bands = [
      { max: 0.85, label: '1+' },
      { max: 1.15, label: '1' },
      { max: 1.5, label: '1-' },
      { max: 1.85, label: '2+' },
      { max: 2.15, label: '2' },
      { max: 2.5, label: '2-' },
      { max: 2.85, label: '3+' },
      { max: 3.15, label: '3' },
      { max: 3.5, label: '3-' },
      { max: 3.85, label: '4+' },
      { max: 4.15, label: '4' },
      { max: 4.5, label: '4-' },
      { max: 4.85, label: '5+' },
      { max: 5.15, label: '5' },
      { max: 5.5, label: '5-' },
      { max: Infinity, label: '6' },
    ];
    for (var i = 0; i < bands.length; i += 1) {
      if (value <= bands[i].max) return bands[i].label;
    }
    return '-';
  }

  function buildCalculation() {
    var validRows = _rows
      .map(function (row) {
        return {
          label: row.label,
          grade: parseGradeValue(row.value),
          rawGrade: row.value,
          weight: parseWeight(row.weight),
          rawWeight: row.weight,
        };
      })
      .filter(function (row) {
        return isFinite(row.grade) && isFinite(row.weight) && row.weight > 0;
      });

    if (!validRows.length) {
      return {
        usedCount: 0,
        totalWeight: 0,
        weightedAverage: NaN,
        rows: [],
      };
    }

    var totalWeight = validRows.reduce(function (sum, row) { return sum + row.weight; }, 0);
    var weightedAverage = validRows.reduce(function (sum, row) {
      return sum + row.grade * row.weight;
    }, 0) / totalWeight;

    return {
      usedCount: validRows.length,
      totalWeight: totalWeight,
      weightedAverage: weightedAverage,
      rows: validRows.map(function (row) {
        return {
          label: row.label,
          rawGrade: row.rawGrade,
          rawWeight: row.rawWeight,
          contribution: totalWeight > 0 ? (row.grade * row.weight) / totalWeight : 0,
        };
      }),
    };
  }

  function renderRows() {
    if (!_elements || !_elements.gradesRows) return;
    _elements.gradesRows.innerHTML = _rows.map(function (row, index) {
      return (
        '<div class="grades-row" data-grade-row>' +
          '<label class="connect-field">' +
            '<span>Bezeichnung</span>' +
            '<input type="text" data-grade-field="label" value="' + escapeHtml(row.label) + '" placeholder="z. B. Klausur" autocomplete="off" />' +
          '</label>' +
          '<label class="connect-field">' +
            '<span>Note</span>' +
            '<input type="text" data-grade-field="value" value="' + escapeHtml(row.value) + '" placeholder="z. B. 2-" autocomplete="off" />' +
          '</label>' +
          '<label class="connect-field">' +
            '<span>Gewichtung in %</span>' +
            '<input type="text" data-grade-field="weight" value="' + escapeHtml(row.weight) + '" placeholder="z. B. 66,67" autocomplete="off" />' +
          '</label>' +
          '<button class="filter-button grades-row__remove" type="button" data-grade-remove="' + index + '"' + (_rows.length <= 1 ? ' disabled' : '') + '>Entfernen</button>' +
        '</div>'
      );
    }).join('');
  }

  function renderPresetState() {
    if (!_elements || !_elements.gradesPresetButtons) return;
    _elements.gradesPresetButtons.querySelectorAll('[data-grade-preset]').forEach(function (button) {
      button.classList.toggle('active', button.dataset.gradePreset === _activePreset);
    });
  }

  function renderResult() {
    if (!_elements) return;
    var result = buildCalculation();

    if (_elements.gradesSummaryCount) {
      _elements.gradesSummaryCount.textContent = String(result.usedCount);
    }
    if (_elements.gradesSummaryRisk) {
      _elements.gradesSummaryRisk.textContent = formatNumber(result.totalWeight.toFixed(2)).replace(',00', '') + '%';
    }
    if (_elements.gradesSummaryAverage) {
      _elements.gradesSummaryAverage.textContent = isFinite(result.weightedAverage)
        ? approximateGradeLabel(result.weightedAverage) + ' · ' + formatGrade(result.weightedAverage)
        : '-';
    }

    if (_elements.gradesList) {
      if (!result.rows.length) {
        _elements.gradesList.innerHTML = '<div class="empty-state">Trage mindestens eine gueltige Teilnote mit Gewichtung ein.</div>';
        return;
      }

      _elements.gradesList.innerHTML =
        '<article class="today-mini-card">' +
          '<strong>Gesamt</strong>' +
          '<p>Rechnerisch ergibt sich aktuell die Note <strong>' + approximateGradeLabel(result.weightedAverage) + '</strong> bei einem Schnitt von ' + formatGrade(result.weightedAverage) + '.</p>' +
          '<span class="meta-tag low">Gewichtung gesamt: ' + formatNumber(result.totalWeight.toFixed(2)).replace(',00', '') + '%</span>' +
        '</article>' +
        result.rows.map(function (row) {
          return (
            '<article class="today-mini-card">' +
              '<strong>' + escapeHtml(row.label) + '</strong>' +
              '<p>Note ' + escapeHtml(row.rawGrade || '-') + ' bei ' + escapeHtml(row.rawWeight || '-') + '% Gewichtung.</p>' +
              '<span class="meta-tag low">Beitrag: ' + formatGrade(row.contribution) + '</span>' +
            '</article>'
          );
        }).join('');
    }
  }

  function setFeedback(message, kind) {
    if (!_elements || !_elements.gradesFeedback) return;
    _elements.gradesFeedback.textContent = message || '';
    _elements.gradesFeedback.className = 'connect-feedback' + (kind ? ' ' + kind : '');
  }

  function renderGrades() {
    if (!_elements || !_elements.gradesRows) return;
    renderPresetState();
    renderRows();
    renderResult();
  }

  async function saveGradeEntry() {
    syncRowsFromDom();
    var result = buildCalculation();
    if (!result.rows.length) {
      setFeedback('Bitte mindestens eine gueltige Teilnote und Gewichtung eintragen.', 'warning');
      renderResult();
      return;
    }
    setFeedback('Berechnung aktualisiert.', 'success');
    renderResult();
  }

  async function loadGradebook() {
    renderGrades();
  }

  async function loadNotes() {
    if (_callbacks.renderNavSignals) {
      _callbacks.renderNavSignals();
    }
  }

  async function deleteGradeEntry() {
    return;
  }

  async function saveClassNote() {
    return;
  }

  async function clearClassNote() {
    return;
  }

  function getGradebookData() {
    return {
      status: 'ok',
      detail: 'Lokaler Notenrechner aktiv.',
      updatedAt: '',
      entries: [],
      classes: [],
    };
  }

  function getNotesData() {
    return {
      status: 'ok',
      detail: '',
      updatedAt: '',
      notes: [],
      classes: [],
    };
  }

  function getGradeClasses() {
    return [];
  }

  function summarizeGrades(entries) {
    var numericGrades = (entries || [])
      .map(function (entry) { return parseGradeValue(entry.gradeValue); })
      .filter(function (value) { return isFinite(value) && !isNaN(value); });
    if (!numericGrades.length) {
      return { averageLabel: '-', riskCount: 0 };
    }
    var average = numericGrades.reduce(function (sum, value) { return sum + value; }, 0) / numericGrades.length;
    var riskCount = numericGrades.filter(function (value) { return value >= 4; }).length;
    return {
      averageLabel: formatGrade(average),
      riskCount: riskCount,
    };
  }

  function renderClassNotes() {
    return;
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  window.LehrerGrades = {
    init: init,
    loadGradebook: loadGradebook,
    loadNotes: loadNotes,
    saveGradeEntry: saveGradeEntry,
    deleteGradeEntry: deleteGradeEntry,
    saveClassNote: saveClassNote,
    clearClassNote: clearClassNote,
    getGradebookData: getGradebookData,
    getNotesData: getNotesData,
    getGradeClasses: getGradeClasses,
    summarizeGrades: summarizeGrades,
    renderGrades: renderGrades,
    renderClassNotes: renderClassNotes,
  };
})();
