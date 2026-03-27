/**
 * LehrerGrades — Grades & Notes feature module (Phase 9e → Phase 15)
 *
 * Phase 9e: extracted data-fetching and mutation functions from src/app.js.
 * Phase 15: extracted all grades rendering functions from src/app.js.
 *
 * WHAT THIS FILE DOES:
 *   Data loading / mutation (Phase 9e):
 *   - loadGradebook()    — fetches from GET /api/v2/modules/noten/data
 *   - loadNotes()        — fetches from GET /api/v2/modules/noten/data (same endpoint)
 *   - saveGradeEntry()   — POST /api/v2/modules/noten/grades
 *   - deleteGradeEntry() — DELETE /api/v2/modules/noten/grades/<id>
 *   - saveClassNote()    — POST /api/v2/modules/noten/notes
 *   - clearClassNote()   — DELETE /api/v2/modules/noten/notes/<class>
 *
 *   State accessors (Phase 15):
 *   - getGradebookData()           — returns state.gradesData (with defaults)
 *   - getNotesData()               — returns state.notesData (with defaults)
 *   - getGradeClasses()            — union of grade + classwork classes, sorted
 *   - summarizeGrades(entries)     — { averageLabel, riskCount }
 *
 *   Rendering (Phase 15):
 *   - renderGrades()               — full grades panel render
 *   - renderClassNotes(cls, hint)  — full notes panel render
 *
 * v1 FALLBACK:
 *   When MULTIUSER_ENABLED is false (local runtime), falls back to legacy v1 endpoints.
 *
 * DATA SHAPE MAPPING (v2 ↔ v1):
 *   The v2 backend stores: { id, class_name, subject, grade_value, grade_date, note }
 *   The v1 UI expects:     { id, classLabel, type, studentName, title, gradeValue, date, comment }
 *   We pack UI fields into the v2 schema:
 *     subject  = "type | studentName | title"  (pipe-delimited)
 *     note     = comment
 *
 * PUBLIC API:
 *   window.LehrerGrades.init(state, elements, callbacks)
 *   window.LehrerGrades.loadGradebook()
 *   window.LehrerGrades.loadNotes()
 *   window.LehrerGrades.saveGradeEntry()
 *   window.LehrerGrades.deleteGradeEntry(entryId)
 *   window.LehrerGrades.saveClassNote()
 *   window.LehrerGrades.clearClassNote()
 *   window.LehrerGrades.renderGrades()
 *   window.LehrerGrades.renderClassNotes(classes, suggestedClass)
 *   window.LehrerGrades.getGradebookData()
 *   window.LehrerGrades.getNotesData()
 *   window.LehrerGrades.getGradeClasses()
 *   window.LehrerGrades.summarizeGrades(entries)
 *
 * DEPENDS ON:
 *   - window.LehrerAPI    (src/api-client.js loaded before this file)
 *   - window.MULTIUSER_ENABLED
 */
(function () {
  'use strict';

  // ── Internal state references (set via init) ─────────────────────────────────

  var _state = null;
  var _elements = null;
  var _callbacks = {};

  // ── Private helpers — delegate to callbacks ──────────────────────────────────

  function _getData() {
    return _callbacks.getData ? _callbacks.getData() : (_state && _state.data) || {};
  }

  function _getVisiblePanelItems(items, panelKey) {
    if (_callbacks.getVisiblePanelItems) return _callbacks.getVisiblePanelItems(items, panelKey);
    return Array.isArray(items) ? items : [];
  }

  function _setExpandableMeta(element, totalCount, visibleCount) {
    if (_callbacks.setExpandableMeta) _callbacks.setExpandableMeta(element, totalCount, visibleCount);
  }

  function _renderNavSignals() {
    if (_callbacks.renderNavSignals) _callbacks.renderNavSignals();
  }

  // ── Data shape helpers ───────────────────────────────────────────────────────

  /**
   * Normalize a v2 grade entry to the shape expected by renderGrades().
   * v2 stores: { id, class_name, subject, grade_value, grade_date, note }
   * v1 expects: { id, classLabel, type, studentName, title, gradeValue, date, comment, createdAt }
   */
  function _normalizeV2Grade(g) {
    var subjectParts = (g.subject || '').split(' | ');
    var type = subjectParts[0] || 'Sonstiges';
    var studentName = subjectParts[1] || '';
    var title = subjectParts[2] || subjectParts[0] || '';
    return {
      id: g.id,
      classLabel: g.class_name || '',
      type: type,
      studentName: studentName,
      title: title,
      gradeValue: g.grade_value || '',
      points: '',
      date: g.grade_date || '',
      comment: g.note || '',
      createdAt: g.created_at || '',
    };
  }

  /**
   * Normalize a v2 note entry to the shape expected by renderClassNotes().
   * v2 stores: { id, class_name, note_text, updated_at }
   * v1 expects: { classLabel, text, updatedAt }
   */
  function _normalizeV2Note(n) {
    return {
      classLabel: n.class_name || '',
      text: n.note_text || '',
      updatedAt: n.updated_at || '',
    };
  }

  /**
   * Build v1-compatible gradesData shape from v2 response.
   */
  function _buildV1GradesShape(v2Grades) {
    var entries = (v2Grades || []).map(_normalizeV2Grade);
    var classSet = {};
    entries.forEach(function (e) { if (e.classLabel) classSet[e.classLabel] = true; });
    var classes = Object.keys(classSet).sort();
    return {
      status: 'ok',
      detail: entries.length + ' Einträge',
      updatedAt: new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }),
      entries: entries,
      classes: classes,
    };
  }

  /**
   * Build v1-compatible notesData shape from v2 response.
   */
  function _buildV1NotesShape(v2Notes) {
    var notes = (v2Notes || []).map(_normalizeV2Note);
    var classSet = {};
    notes.forEach(function (n) { if (n.classLabel) classSet[n.classLabel] = true; });
    var classes = Object.keys(classSet).sort();
    return {
      status: 'ok',
      detail: notes.length + ' Notizen',
      updatedAt: new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }),
      notes: notes,
      classes: classes,
    };
  }

  // ── API helpers ──────────────────────────────────────────────────────────────

  var _USE_V2 = typeof window !== 'undefined' && window.MULTIUSER_ENABLED;

  function _isV2() {
    return _USE_V2 && window.LehrerAPI && typeof window.LehrerAPI.getNotesData === 'function';
  }

  // ── State accessors ──────────────────────────────────────────────────────────

  /**
   * Returns the current gradesData, with safe defaults.
   */
  function getGradebookData() {
    return (
      (_state && _state.gradesData) || {
        status: 'empty',
        detail: 'Noch keine lokalen Noten erfasst.',
        updatedAt: '',
        entries: [],
        classes: [],
      }
    );
  }

  /**
   * Returns the current notesData, with safe defaults.
   */
  function getNotesData() {
    return (
      (_state && _state.notesData) || {
        status: 'empty',
        detail: 'Noch keine Klassen-Notizen erfasst.',
        updatedAt: '',
        notes: [],
        classes: [],
      }
    );
  }

  /**
   * Returns the union of grade classes and classwork classes, sorted.
   * Reads getData().planDigest.classwork.classes for classwork class names.
   */
  function getGradeClasses() {
    var gradeClasses = getGradebookData().classes || [];
    var data = _getData();
    var classworkClasses =
      (data.planDigest && data.planDigest.classwork && data.planDigest.classwork.classes) || [];
    var all = gradeClasses.concat(classworkClasses);
    var seen = {};
    var result = [];
    all.forEach(function (c) {
      if (c && !seen[c]) { seen[c] = true; result.push(c); }
    });
    return result.sort();
  }

  /**
   * Returns the union of note classes and grade classes, sorted.
   */
  function _getNoteClasses() {
    var notesClasses = getNotesData().classes || [];
    var gradeClasses = getGradeClasses();
    var all = gradeClasses.concat(notesClasses);
    var seen = {};
    var result = [];
    all.forEach(function (c) {
      if (c && !seen[c]) { seen[c] = true; result.push(c); }
    });
    return result.sort();
  }

  function _getActiveGradeClass(classes) {
    if (!classes.length) {
      if (_state) _state.gradesSelectedClass = '';
      return '';
    }
    if (_state && _state.gradesSelectedClass && classes.indexOf(_state.gradesSelectedClass) !== -1) {
      return _state.gradesSelectedClass;
    }
    if (_state) _state.gradesSelectedClass = classes[0];
    return classes[0];
  }

  function _getActiveNoteClass(classes, suggestedClass) {
    if (!classes.length) {
      if (_state) _state.notesSelectedClass = '';
      return '';
    }
    if (_state && _state.notesSelectedClass && classes.indexOf(_state.notesSelectedClass) !== -1) {
      return _state.notesSelectedClass;
    }
    if (suggestedClass && classes.indexOf(suggestedClass) !== -1) {
      if (_state) _state.notesSelectedClass = suggestedClass;
      return suggestedClass;
    }
    if (_state) _state.notesSelectedClass = classes[0];
    return classes[0];
  }

  // ── Grade computation helpers ────────────────────────────────────────────────

  /**
   * Compute average and risk count from a grade entries array.
   * @returns {{ averageLabel: string, riskCount: number }}
   */
  function summarizeGrades(entries) {
    var numericGrades = (entries || [])
      .map(function (entry) { return _parseGradeValue(entry.gradeValue); })
      .filter(function (value) { return isFinite(value) && !isNaN(value); });
    var average = numericGrades.length
      ? numericGrades.reduce(function (sum, value) { return sum + value; }, 0) / numericGrades.length
      : null;
    var riskCount = numericGrades.filter(function (value) { return value >= 4; }).length;
    return {
      averageLabel: average ? average.toFixed(2).replace('.', ',') : '-',
      riskCount: riskCount,
    };
  }

  function _parseGradeValue(value) {
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

  // ── Format helpers ───────────────────────────────────────────────────────────

  function _formatGradeDate(value) {
    if (!value) return 'ohne Datum';
    try {
      var date = new Date(value + 'T00:00:00');
      return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch (_error) {
      return value;
    }
  }

  function _formatNoteTimestamp(value) {
    if (!value) return 'ohne Zeitstempel';
    try {
      var date = new Date(value);
      return 'zuletzt aktualisiert ' +
        date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) +
        ' \u00b7 ' +
        date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    } catch (_error) {
      return value;
    }
  }

  // ── Render helpers ───────────────────────────────────────────────────────────

  function _renderGradeItem(entry) {
    return (
      '<article class="grade-item">' +
      '<div class="grade-item-top">' +
      '<div>' +
      '<strong>' + (entry.studentName || '') + '</strong>' +
      '<p class="message-snippet">' +
        (entry.classLabel || '') + ' \u00b7 ' + (entry.type || '') + ' \u00b7 ' + _formatGradeDate(entry.date) +
      '</p>' +
      '</div>' +
      '<div class="grade-item-actions">' +
      '<span class="meta-tag low">' + (entry.gradeValue || '-') + '</span>' +
      '<button class="filter-button" type="button" data-grade-delete="' + entry.id + '">Entfernen</button>' +
      '</div>' +
      '</div>' +
      '<p class="classwork-entry-title">' + (entry.title || '') + '</p>' +
      '<div class="meta-row">' +
      (entry.points ? '<span class="meta-tag">' + entry.points + '</span>' : '') +
      (entry.comment ? '<span class="meta-tag">' + entry.comment + '</span>' : '') +
      '</div>' +
      '</article>'
    );
  }

  function _renderGradeClassOptions(element, classes, activeClass, includePlaceholder) {
    if (!element) return;
    if (!classes.length) {
      element.innerHTML = includePlaceholder
        ? '<option value="">Klasse waehlen</option>'
        : '<option value="">Keine Klasse</option>';
      element.disabled = !includePlaceholder;
      return;
    }
    element.disabled = false;
    element.innerHTML = (includePlaceholder ? '<option value="">Klasse waehlen</option>' : '') +
      classes.map(function (classLabel) {
        return '<option value="' + classLabel + '"' +
          (classLabel === activeClass ? ' selected' : '') + '>' + classLabel + '</option>';
      }).join('');
  }

  // ── Rendering: grades panel ──────────────────────────────────────────────────

  /**
   * Render the full grades panel: stat summary, class filter, grade list, notes.
   */
  function renderGrades() {
    if (!_elements || !_elements.gradesList) return;

    var gradebook = getGradebookData();
    var classes = getGradeClasses();
    var activeClass = _getActiveGradeClass(classes);
    var entries = (gradebook.entries || [])
      .filter(function (entry) { return !activeClass || entry.classLabel === activeClass; })
      .sort(function (left, right) { return (right.date || '').localeCompare(left.date || ''); });
    var visibleEntries = _getVisiblePanelItems(entries, 'grades');
    var summary = summarizeGrades(entries);

    if (_elements.gradesDetail) {
      _elements.gradesDetail.textContent = gradebook.updatedAt
        ? gradebook.detail + ' Letzter lokaler Stand: ' + gradebook.updatedAt + '.'
        : gradebook.detail;
    }
    if (_elements.gradesSummaryClass) {
      _elements.gradesSummaryClass.textContent = activeClass || 'Keine Klasse';
    }
    if (_elements.gradesSummaryCount) {
      _elements.gradesSummaryCount.textContent = String(entries.length);
    }
    if (_elements.gradesSummaryAverage) {
      _elements.gradesSummaryAverage.textContent = summary.averageLabel;
    }
    if (_elements.gradesSummaryRisk) {
      _elements.gradesSummaryRisk.textContent = String(summary.riskCount);
      var riskCard = _elements.gradesSummaryRisk.closest
        ? _elements.gradesSummaryRisk.closest('.grades-stat-card')
        : null;
      if (riskCard) riskCard.classList.toggle('has-risk', summary.riskCount > 0);
    }
    if (_elements.gradesFeedback) {
      _elements.gradesFeedback.textContent = (_state && _state.gradesFeedback) || '';
      _elements.gradesFeedback.className = 'connect-feedback' +
        ((_state && _state.gradesFeedbackKind) ? ' ' + _state.gradesFeedbackKind : '');
    }

    _renderGradeClassOptions(_elements.gradesClassInput, classes, activeClass, true);
    _renderGradeClassOptions(_elements.gradesClassFilter, classes, activeClass, false);
    renderClassNotes(classes, activeClass);

    if (_elements.gradesDateInput && !_elements.gradesDateInput.value) {
      _elements.gradesDateInput.value = new Date().toISOString().slice(0, 10);
    }

    _setExpandableMeta(_elements.gradesList, entries.length, visibleEntries.length);
    _elements.gradesList.innerHTML = entries.length
      ? visibleEntries.map(function (entry) { return _renderGradeItem(entry); }).join('')
      : '<div class="empty-state">Noch keine lokalen Noten fuer diese Klasse erfasst.</div>';
  }

  // ── Rendering: class notes panel ─────────────────────────────────────────────

  /**
   * Render the full class notes panel.
   * @param {string[]} [classes]       - pre-computed class list (optional; recalculated if omitted)
   * @param {string}   [suggestedClass] - class to pre-select if notesSelectedClass not set
   */
  function renderClassNotes(classes, suggestedClass) {
    if (!_elements || !_elements.notesList) return;

    var notesData = getNotesData();
    var noteClasses = _getNoteClasses();
    var activeClass = _getActiveNoteClass(noteClasses, suggestedClass);
    var notes = (notesData.notes || [])
      .slice()
      .sort(function (left, right) {
        return String(right.updatedAt || '').localeCompare(String(left.updatedAt || ''));
      });
    var currentNote = null;
    for (var i = 0; i < notes.length; i++) {
      if (notes[i].classLabel === activeClass) { currentNote = notes[i]; break; }
    }

    _renderGradeClassOptions(_elements.notesClassFilter, noteClasses, activeClass, false);
    if (_elements.notesInput && !_elements.notesInput.matches(':focus')) {
      _elements.notesInput.value = (currentNote && currentNote.text) || '';
    }

    if (_elements.notesFeedback) {
      _elements.notesFeedback.textContent = (_state && _state.notesFeedback) || '';
      _elements.notesFeedback.className = 'connect-feedback' +
        ((_state && _state.notesFeedbackKind) ? ' ' + _state.notesFeedbackKind : '');
    }

    var prioritizedNotes = currentNote
      ? [currentNote].concat(notes.filter(function (item) { return item.classLabel !== activeClass; }))
      : notes.slice();
    var visibleNotes = _getVisiblePanelItems(prioritizedNotes, 'notes');
    _setExpandableMeta(_elements.notesList, prioritizedNotes.length, visibleNotes.length);

    _elements.notesList.innerHTML = visibleNotes.length
      ? visibleNotes.map(function (note) {
          return (
            '<article class="grade-item note-item ' + (note.classLabel === activeClass ? 'active' : '') + '">' +
            '<div class="grade-item-top">' +
            '<div>' +
            '<strong>' + note.classLabel + '</strong>' +
            '<p class="message-snippet">' + _formatNoteTimestamp(note.updatedAt) + '</p>' +
            '</div>' +
            '<span class="meta-tag low">' + (note.classLabel === activeClass ? 'aktiv' : 'notiz') + '</span>' +
            '</div>' +
            '<p class="classwork-entry-title">' + note.text + '</p>' +
            '</article>'
          );
        }).join('')
      : '<div class="empty-state">Noch keine Klassen-Notizen erfasst.</div>';
  }

  // ── Core API functions (data loading / mutation) ─────────────────────────────

  /**
   * Load grades from v2 endpoint (GET /api/v2/modules/noten/data).
   * Falls back to v1 (GET /api/grades) when MULTIUSER_ENABLED is false.
   * Sets state.gradesData and triggers renderGrades().
   */
  async function loadGradebook() {
    if (!_state) return;
    try {
      if (_isV2()) {
        var resp = await window.LehrerAPI.getNotesData();
        if (!resp.ok) return;
        var json = await resp.json();
        _state.gradesData = _buildV1GradesShape(json.grades || []);
      } else {
        var response = await window.LehrerAPI.legacy.getGrades();
        if (!response.ok) return;
        _state.gradesData = await response.json();
      }
      renderGrades();
    } catch (_err) {
      // fail silently — grades are optional
    }
  }

  /**
   * Load class notes from v2 endpoint (GET /api/v2/modules/noten/data).
   * Falls back to v1 (GET /api/notes) when MULTIUSER_ENABLED is false.
   * Sets state.notesData and triggers renderClassNotes() + renderNavSignals().
   */
  async function loadNotes() {
    if (!_state) return;
    try {
      if (_isV2()) {
        var resp = await window.LehrerAPI.getNotesData();
        if (!resp.ok) return;
        var json = await resp.json();
        _state.notesData = _buildV1NotesShape(json.notes || []);
      } else {
        var response = await window.LehrerAPI.legacy.getNotes();
        if (!response.ok) return;
        _state.notesData = await response.json();
      }
      var classes = getGradeClasses();
      renderClassNotes(classes, _state && _state.notesSelectedClass);
      _renderNavSignals();
    } catch (_err) {
      // fail silently
    }
  }

  /**
   * Save a grade entry via v2 API (POST /api/v2/modules/noten/grades).
   * Falls back to v1 (POST /api/local-settings/grades) on local runtime.
   */
  async function saveGradeEntry() {
    if (!_state || !_elements) return;

    var classLabel = (_elements.gradesClassInput && _elements.gradesClassInput.value.trim()) || '';
    var type = (_elements.gradesTypeInput && _elements.gradesTypeInput.value.trim()) || 'Sonstiges';
    var studentName = (_elements.gradesStudentInput && _elements.gradesStudentInput.value.trim()) || '';
    var title = (_elements.gradesTitleInput && _elements.gradesTitleInput.value.trim()) || '';
    var gradeValue = (_elements.gradesValueInput && _elements.gradesValueInput.value.trim()) || '';
    var date = (_elements.gradesDateInput && _elements.gradesDateInput.value) || '';
    var comment = (_elements.gradesCommentInput && _elements.gradesCommentInput.value.trim()) || '';

    if (!classLabel || !studentName || !title) {
      _state.gradesFeedback = 'Klasse, Schueler:in und Titel werden benoetigt.';
      _state.gradesFeedbackKind = 'warning';
      renderGrades();
      return;
    }

    _state.gradesFeedback = 'Speichere Noteneintrag ...';
    _state.gradesFeedbackKind = '';
    renderGrades();

    try {
      if (_isV2()) {
        var payload = {
          class_name: classLabel,
          subject: [type, studentName, title].filter(Boolean).join(' | '),
          grade_value: gradeValue,
          grade_date: date || null,
          note: comment,
        };
        var resp = await window.LehrerAPI.saveGrade(payload);
        var result = await resp.json();
        if (!resp.ok) {
          throw new Error(result.error || result.detail || 'Noteneintrag konnte nicht gespeichert werden.');
        }
        var dataResp = await window.LehrerAPI.getNotesData();
        if (dataResp.ok) {
          var dataJson = await dataResp.json();
          _state.gradesData = _buildV1GradesShape(dataJson.grades || []);
        }
        _state.gradesSelectedClass = classLabel;
        _state.gradesFeedback = 'Note gespeichert.';
        _state.gradesFeedbackKind = 'success';
      } else {
        var v1Payload = {
          classLabel: classLabel, type: type, studentName: studentName,
          title: title, gradeValue: gradeValue, date: date, comment: comment,
        };
        var v1Resp = await window.LehrerAPI.legacy.saveGrade(v1Payload);
        var v1Result = await v1Resp.json();
        if (!v1Resp.ok) {
          throw new Error(v1Result.detail || 'Noteneintrag konnte nicht gespeichert werden.');
        }
        _state.gradesData = v1Result;
        _state.gradesSelectedClass = classLabel;
        _state.gradesFeedback = v1Result.detail || 'Note lokal gespeichert.';
        _state.gradesFeedbackKind = 'success';
      }
      if (_elements.gradesForm) _elements.gradesForm.reset();
      if (_elements.gradesDateInput) {
        _elements.gradesDateInput.value = new Date().toISOString().slice(0, 10);
      }
      renderGrades();
    } catch (err) {
      _state.gradesFeedback = (err && err.message) || 'Noteneintrag konnte nicht gespeichert werden.';
      _state.gradesFeedbackKind = 'warning';
      renderGrades();
    }
  }

  /**
   * Delete a grade entry via v2 API (DELETE /api/v2/modules/noten/grades/<id>).
   */
  async function deleteGradeEntry(entryId) {
    if (!entryId || !_state) return;
    try {
      if (_isV2()) {
        var resp = await window.LehrerAPI.deleteGrade(entryId);
        if (!resp.ok) {
          var errData = await resp.json().catch(function () { return {}; });
          throw new Error(errData.error || errData.detail || 'Eintrag konnte nicht entfernt werden.');
        }
        var dataResp = await window.LehrerAPI.getNotesData();
        if (dataResp.ok) {
          var dataJson = await dataResp.json();
          _state.gradesData = _buildV1GradesShape(dataJson.grades || []);
        }
        _state.gradesFeedback = 'Eintrag entfernt.';
        _state.gradesFeedbackKind = 'success';
      } else {
        var v1Resp = await window.LehrerAPI.legacy.saveGrade({ mode: 'delete', id: entryId });
        var v1Result = await v1Resp.json();
        if (!v1Resp.ok) {
          throw new Error(v1Result.detail || 'Eintrag konnte nicht entfernt werden.');
        }
        _state.gradesData = v1Result;
        _state.gradesFeedback = v1Result.detail || 'Eintrag entfernt.';
        _state.gradesFeedbackKind = 'success';
      }
      renderGrades();
    } catch (err) {
      _state.gradesFeedback = (err && err.message) || 'Eintrag konnte nicht entfernt werden.';
      _state.gradesFeedbackKind = 'warning';
      renderGrades();
    }
  }

  /**
   * Save a class note via v2 API (POST /api/v2/modules/noten/notes).
   */
  async function saveClassNote() {
    if (!_state || !_elements) return;

    var classLabel = (_elements.notesClassFilter && _elements.notesClassFilter.value.trim())
      || (_state && _state.notesSelectedClass)
      || (_state && _state.gradesSelectedClass)
      || '';
    var text = (_elements.notesInput && _elements.notesInput.value.trim()) || '';

    if (!classLabel) {
      _state.notesFeedback = 'Bitte zuerst eine Klasse waehlen.';
      _state.notesFeedbackKind = 'warning';
      renderClassNotes();
      return;
    }

    _state.notesFeedback = 'Speichere Klassen-Notiz ...';
    _state.notesFeedbackKind = '';
    renderClassNotes();

    try {
      if (_isV2()) {
        var payload = { class_name: classLabel, note_text: text };
        var resp = await window.LehrerAPI.saveNote(payload);
        var result = await resp.json();
        if (!resp.ok) {
          throw new Error(result.error || result.detail || 'Notiz konnte nicht gespeichert werden.');
        }
        var dataResp = await window.LehrerAPI.getNotesData();
        if (dataResp.ok) {
          var dataJson = await dataResp.json();
          _state.notesData = _buildV1NotesShape(dataJson.notes || []);
        }
        _state.notesSelectedClass = classLabel;
        _state.notesFeedback = 'Notiz gespeichert.';
        _state.notesFeedbackKind = 'success';
      } else {
        var v1Resp = await window.LehrerAPI.legacy.saveNote({ classLabel: classLabel, text: text });
        var v1Result = await v1Resp.json();
        if (!v1Resp.ok) {
          throw new Error(v1Result.detail || 'Notiz konnte nicht gespeichert werden.');
        }
        _state.notesData = v1Result;
        _state.notesSelectedClass = classLabel;
        _state.notesFeedback = v1Result.detail || 'Notiz lokal gespeichert.';
        _state.notesFeedbackKind = 'success';
      }
      renderClassNotes();
      _renderNavSignals();
    } catch (err) {
      _state.notesFeedback = (err && err.message) || 'Notiz konnte nicht gespeichert werden.';
      _state.notesFeedbackKind = 'warning';
      renderClassNotes();
    }
  }

  /**
   * Delete a class note via v2 API (DELETE /api/v2/modules/noten/notes/<class>).
   */
  async function clearClassNote() {
    if (!_state || !_elements) return;

    var classLabel = (_elements.notesClassFilter && _elements.notesClassFilter.value.trim())
      || (_state && _state.notesSelectedClass)
      || '';
    if (!classLabel) return;

    try {
      if (_isV2()) {
        var resp = await window.LehrerAPI.deleteNote(classLabel);
        if (!resp.ok) {
          var errData = await resp.json().catch(function () { return {}; });
          throw new Error(errData.error || errData.detail || 'Notiz konnte nicht entfernt werden.');
        }
        var dataResp = await window.LehrerAPI.getNotesData();
        if (dataResp.ok) {
          var dataJson = await dataResp.json();
          _state.notesData = _buildV1NotesShape(dataJson.notes || []);
        }
        _state.notesFeedback = 'Notiz entfernt.';
        _state.notesFeedbackKind = 'success';
        if (_elements.notesInput) _elements.notesInput.value = '';
      } else {
        var v1Resp = await window.LehrerAPI.legacy.saveNote({ mode: 'delete', classLabel: classLabel });
        var v1Result = await v1Resp.json();
        if (!v1Resp.ok) {
          throw new Error(v1Result.detail || 'Notiz konnte nicht entfernt werden.');
        }
        _state.notesData = v1Result;
        _state.notesFeedback = v1Result.detail || 'Notiz entfernt.';
        _state.notesFeedbackKind = 'success';
        if (_elements.notesInput) _elements.notesInput.value = '';
      }
      renderClassNotes();
      _renderNavSignals();
    } catch (err) {
      _state.notesFeedback = (err && err.message) || 'Notiz konnte nicht entfernt werden.';
      _state.notesFeedbackKind = 'warning';
      renderClassNotes();
    }
  }

  // ── Public API ───────────────────────────────────────────────────────────────

  /**
   * Initialize the grades module with shared state, DOM element references,
   * and render callbacks from the parent app.js IIFE.
   *
   * @param {object} state    - The shared `state` object from app.js
   * @param {object} elements - The shared `elements` object from app.js
   * @param {object} cbs      - Render callbacks: {
   *   getData, getVisiblePanelItems, setExpandableMeta, renderNavSignals
   * }
   */
  function init(state, elements, cbs) {
    _state = state;
    _elements = elements;
    _callbacks = cbs || {};
    // Re-evaluate v2 availability after init (MULTIUSER_ENABLED may be set after load)
    _USE_V2 = typeof window !== 'undefined' && !!window.MULTIUSER_ENABLED;
  }

  window.LehrerGrades = {
    init: init,
    // Data loading / mutation
    loadGradebook: loadGradebook,
    loadNotes: loadNotes,
    saveGradeEntry: saveGradeEntry,
    deleteGradeEntry: deleteGradeEntry,
    saveClassNote: saveClassNote,
    clearClassNote: clearClassNote,
    // State accessors
    getGradebookData: getGradebookData,
    getNotesData: getNotesData,
    getGradeClasses: getGradeClasses,
    summarizeGrades: summarizeGrades,
    // Rendering
    renderGrades: renderGrades,
    renderClassNotes: renderClassNotes,
  };

})();
