/**
 * LehrerGrades — Grades & Notes feature module (Phase 9e)
 *
 * Extracted from src/app.js to migrate data-fetching and mutation functions
 * from v1 endpoints to v2 per-user endpoints.
 *
 * WHAT THIS FILE DOES:
 *   - loadGradebook()    — fetches from GET /api/v2/modules/noten/data
 *   - loadNotes()        — fetches from GET /api/v2/modules/noten/data (same endpoint)
 *   - saveGradeEntry()   — calls LehrerAPI.saveGrade()  → POST /api/v2/modules/noten/grades
 *   - deleteGradeEntry() — calls LehrerAPI.deleteGrade() → DELETE /api/v2/modules/noten/grades/<id>
 *   - saveClassNote()    — calls LehrerAPI.saveNote()   → POST /api/v2/modules/noten/notes
 *   - clearClassNote()   — calls LehrerAPI.deleteNote() → DELETE /api/v2/modules/noten/notes/<class>
 *
 * v1 FALLBACK:
 *   When MULTIUSER_ENABLED is false (local runtime), falls back to legacy v1 endpoints
 *   so that local development continues to work unchanged.
 *
 * DATA SHAPE MAPPING:
 *   The v2 backend stores: { id, class_name, subject, grade_value, grade_date, note }
 *   The v1 UI expects:     { id, classLabel, type, studentName, title, gradeValue, date, comment }
 *
 *   We pack UI fields into the v2 schema:
 *     subject  = "type | studentName | title"  (pipe-delimited)
 *     note     = comment
 *   And unpack on load (normalizeV2Grade).
 *
 * PUBLIC API:
 *   window.LehrerGrades.init(state, elements, callbacks)
 *   window.LehrerGrades.loadGradebook()
 *   window.LehrerGrades.loadNotes()
 *   window.LehrerGrades.saveGradeEntry()
 *   window.LehrerGrades.deleteGradeEntry(entryId)
 *   window.LehrerGrades.saveClassNote()
 *   window.LehrerGrades.clearClassNote()
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

  // ── Data shape helpers ───────────────────────────────────────────────────────

  /**
   * Normalize a v2 grade entry to the shape expected by renderGrades() in app.js.
   * v2 stores: { id, class_name, subject, grade_value, grade_date, note }
   * v1 expects: { id, classLabel, type, studentName, title, gradeValue, date, comment, createdAt }
   */
  function _normalizeV2Grade(g) {
    // subject is packed as "type | studentName | title"
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
   * Normalize a v2 note entry to the shape expected by renderClassNotes() in app.js.
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
   * Allows existing renderGrades() in app.js to consume v2 data unchanged.
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
   * Allows existing renderClassNotes() in app.js to consume v2 data unchanged.
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

  // ── Callbacks ────────────────────────────────────────────────────────────────

  function _renderGrades() {
    if (_callbacks.renderGrades) _callbacks.renderGrades();
  }

  function _renderClassNotes() {
    var classes = _callbacks.getGradeClasses ? _callbacks.getGradeClasses() : [];
    var selected = _state ? _state.notesSelectedClass : '';
    if (_callbacks.renderClassNotes) _callbacks.renderClassNotes(classes, selected);
  }

  function _renderNavSignals() {
    if (_callbacks.renderNavSignals) _callbacks.renderNavSignals();
  }

  // ── Core API functions ───────────────────────────────────────────────────────

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
        // v1 fallback (local runtime)
        var response = await window.LehrerAPI.legacy.getGrades();
        if (!response.ok) return;
        _state.gradesData = await response.json();
      }
      _renderGrades();
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
        // v1 fallback (local runtime)
        var response = await window.LehrerAPI.legacy.getNotes();
        if (!response.ok) return;
        _state.notesData = await response.json();
      }
      _renderClassNotes();
      _renderNavSignals();
    } catch (_err) {
      // fail silently
    }
  }

  /**
   * Save a grade entry via v2 API (POST /api/v2/modules/noten/grades).
   * Falls back to v1 (POST /api/local-settings/grades) on local runtime.
   * Reads form values from elements.*, updates state.*, triggers renderGrades().
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
      _renderGrades();
      return;
    }

    _state.gradesFeedback = 'Speichere Noteneintrag ...';
    _state.gradesFeedbackKind = '';
    _renderGrades();

    try {
      if (_isV2()) {
        // v2 API: pack multi-field data into subject and note
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
        // Reload all grades from v2 to keep state in sync
        var dataResp = await window.LehrerAPI.getNotesData();
        if (dataResp.ok) {
          var dataJson = await dataResp.json();
          _state.gradesData = _buildV1GradesShape(dataJson.grades || []);
        }
        _state.gradesSelectedClass = classLabel;
        _state.gradesFeedback = 'Note gespeichert.';
        _state.gradesFeedbackKind = 'success';
      } else {
        // v1 fallback (local runtime)
        var v1Payload = {
          classLabel: classLabel,
          type: type,
          studentName: studentName,
          title: title,
          gradeValue: gradeValue,
          date: date,
          comment: comment,
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
      _renderGrades();
    } catch (err) {
      _state.gradesFeedback = (err && err.message) || 'Noteneintrag konnte nicht gespeichert werden.';
      _state.gradesFeedbackKind = 'warning';
      _renderGrades();
    }
  }

  /**
   * Delete a grade entry via v2 API (DELETE /api/v2/modules/noten/grades/<id>).
   * Falls back to v1 on local runtime.
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
        // Reload grades from v2
        var dataResp = await window.LehrerAPI.getNotesData();
        if (dataResp.ok) {
          var dataJson = await dataResp.json();
          _state.gradesData = _buildV1GradesShape(dataJson.grades || []);
        }
        _state.gradesFeedback = 'Eintrag entfernt.';
        _state.gradesFeedbackKind = 'success';
      } else {
        // v1 fallback (local runtime)
        var v1Resp = await window.LehrerAPI.legacy.saveGrade({ mode: 'delete', id: entryId });
        var v1Result = await v1Resp.json();
        if (!v1Resp.ok) {
          throw new Error(v1Result.detail || 'Eintrag konnte nicht entfernt werden.');
        }
        _state.gradesData = v1Result;
        _state.gradesFeedback = v1Result.detail || 'Eintrag entfernt.';
        _state.gradesFeedbackKind = 'success';
      }
      _renderGrades();
    } catch (err) {
      _state.gradesFeedback = (err && err.message) || 'Eintrag konnte nicht entfernt werden.';
      _state.gradesFeedbackKind = 'warning';
      _renderGrades();
    }
  }

  /**
   * Save a class note via v2 API (POST /api/v2/modules/noten/notes).
   * Falls back to v1 on local runtime.
   */
  async function saveClassNote() {
    if (!_state || !_elements) return;

    var classLabel = (_elements.notesClassFilter && _elements.notesClassFilter.value.trim())
      || _state.notesSelectedClass
      || _state.gradesSelectedClass
      || '';
    var text = (_elements.notesInput && _elements.notesInput.value.trim()) || '';

    if (!classLabel) {
      _state.notesFeedback = 'Bitte zuerst eine Klasse waehlen.';
      _state.notesFeedbackKind = 'warning';
      _renderClassNotes();
      return;
    }

    _state.notesFeedback = 'Speichere Klassen-Notiz ...';
    _state.notesFeedbackKind = '';
    _renderClassNotes();

    try {
      if (_isV2()) {
        var payload = { class_name: classLabel, note_text: text };
        var resp = await window.LehrerAPI.saveNote(payload);
        var result = await resp.json();
        if (!resp.ok) {
          throw new Error(result.error || result.detail || 'Notiz konnte nicht gespeichert werden.');
        }
        // Reload notes from v2
        var dataResp = await window.LehrerAPI.getNotesData();
        if (dataResp.ok) {
          var dataJson = await dataResp.json();
          _state.notesData = _buildV1NotesShape(dataJson.notes || []);
        }
        _state.notesSelectedClass = classLabel;
        _state.notesFeedback = 'Notiz gespeichert.';
        _state.notesFeedbackKind = 'success';
      } else {
        // v1 fallback (local runtime)
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
      _renderClassNotes();
      _renderNavSignals();
    } catch (err) {
      _state.notesFeedback = (err && err.message) || 'Notiz konnte nicht gespeichert werden.';
      _state.notesFeedbackKind = 'warning';
      _renderClassNotes();
    }
  }

  /**
   * Delete a class note via v2 API (DELETE /api/v2/modules/noten/notes/<class>).
   * Falls back to v1 on local runtime.
   */
  async function clearClassNote() {
    if (!_state || !_elements) return;

    var classLabel = (_elements.notesClassFilter && _elements.notesClassFilter.value.trim())
      || _state.notesSelectedClass
      || '';
    if (!classLabel) return;

    try {
      if (_isV2()) {
        var resp = await window.LehrerAPI.deleteNote(classLabel);
        if (!resp.ok) {
          var errData = await resp.json().catch(function () { return {}; });
          throw new Error(errData.error || errData.detail || 'Notiz konnte nicht entfernt werden.');
        }
        // Reload notes from v2
        var dataResp = await window.LehrerAPI.getNotesData();
        if (dataResp.ok) {
          var dataJson = await dataResp.json();
          _state.notesData = _buildV1NotesShape(dataJson.notes || []);
        }
        _state.notesFeedback = 'Notiz entfernt.';
        _state.notesFeedbackKind = 'success';
        if (_elements.notesInput) _elements.notesInput.value = '';
      } else {
        // v1 fallback (local runtime)
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
      _renderClassNotes();
      _renderNavSignals();
    } catch (err) {
      _state.notesFeedback = (err && err.message) || 'Notiz konnte nicht entfernt werden.';
      _state.notesFeedbackKind = 'warning';
      _renderClassNotes();
    }
  }

  // ── Public API ───────────────────────────────────────────────────────────────

  /**
   * Initialize the grades module with shared state, DOM element references,
   * and render callbacks from the parent app.js IIFE.
   *
   * @param {object} state    - The shared `state` object from app.js
   * @param {object} elements - The shared `elements` object from app.js
   * @param {object} cbs      - Render callbacks: { renderGrades, renderClassNotes,
   *                            renderNavSignals, getGradeClasses }
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
    loadGradebook: loadGradebook,
    loadNotes: loadNotes,
    saveGradeEntry: saveGradeEntry,
    deleteGradeEntry: deleteGradeEntry,
    saveClassNote: saveClassNote,
    clearClassNote: clearClassNote,
  };

})();
