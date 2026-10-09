/**
 * src/features/classwork.js — "Pläne": Orgaplan, Klassenarbeitsplan, Schultermine
 *
 * Each plan shows a source bar first (file, stand, last check, where it comes
 * from) so a stale source is visible at once, then the entries from today on.
 *
 * Data (state.data, see normalizeV2Dashboard in app.js):
 *   planDigest.orgaplan   backend/orgaplan.py build_digest()
 *   planDigest.classwork  backend/classwork_sync.py plan_view() (entries from today, planStatus)
 *   classworkSync         OneDrive sync status
 *   schoolCalendar        backend/school_calendar.py (events of the next weeks)
 *
 * Initialization:
 *   window.LehrerClasswork.init(state, elements, {
 *     getData, bindExternalLink, isModuleVisible, getVisiblePanelItems,
 *     setExpandableMeta, weekdayLabel, getSelectedClassworkClasses, refreshDashboard
 *   })
 *
 * Exports (window.LehrerClasswork):
 *   init, renderPlanDigest, renderClassworkList, renderClassworkCalendar,
 *   renderOrgaplanItem, getActiveClassworkClass, truncateText, checkClassworkNow
 */
var LehrerClasswork = (function () {
  'use strict';

  var _state = null;
  var _elements = null;
  var _getData = null;
  var _isModuleVisible = null;
  var _getVisiblePanelItems = null;
  var _setExpandableMeta = null;
  var _weekdayLabel = null;
  var _getSelectedClassworkClasses = null;
  var _setSelectedClassworkClasses = null;
  var _toggleClassworkClass = null;
  var _renderClassPills = null;
  var _refreshDashboard = null;
  var _busy = { orgaplan: false, classwork: false };

  var ORGAPLAN_LEVEL_KEY = 'lc.orgaplanLevel';
  var LEVELS = [
    { id: 'all', label: 'Alle' },
    { id: 'middle', label: 'Mittelstufe' },
    { id: 'upper', label: 'Oberstufe' },
  ];

  function init(state, elements, callbacks) {
    _state = state;
    _elements = elements;
    _getData = callbacks.getData;
    _isModuleVisible = callbacks.isModuleVisible;
    _getVisiblePanelItems = callbacks.getVisiblePanelItems;
    _setExpandableMeta = callbacks.setExpandableMeta;
    _weekdayLabel = callbacks.weekdayLabel;
    _getSelectedClassworkClasses = callbacks.getSelectedClassworkClasses;
    _setSelectedClassworkClasses = callbacks.setSelectedClassworkClasses;
    _toggleClassworkClass = callbacks.toggleClassworkClass;
    _renderClassPills = callbacks.renderClassPills;
    _refreshDashboard = callbacks.refreshDashboard || null;

    _elements.orgaplanSourceBar = document.querySelector('#orgaplan-source-bar');
    _elements.orgaplanLevelFilter = document.querySelector('#orgaplan-level-filter');
    _elements.classworkSourceBar = document.querySelector('#classwork-source-bar');
    _elements.classworkClassPills = document.querySelector('#classwork-class-pills');
    _elements.classworkPillSection = document.querySelector('#classwork-pill-section');
    _elements.termineSourceBar = document.querySelector('#termine-source-bar');
    _elements.schoolCalendarList = document.querySelector('#school-calendar-list');

    document.addEventListener('click', function (event) {
      var action = event.target.closest('[data-plan-action]');
      if (!action) return;
      var name = action.getAttribute('data-plan-action');
      if (name === 'orgaplan-refresh') checkOrgaplanNow(action);
      if (name === 'classwork-refresh') checkClassworkNow(action);
    });
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function truncateText(value, maxLength) {
    var clean = String(value || '').replace(/\s+/g, ' ').trim();
    if (clean.length <= maxLength) return clean;
    return clean.slice(0, maxLength - 1).trimEnd() + '…';
  }

  function relTime(iso) {
    if (window.LehrerConnections && window.LehrerConnections.relTime) return window.LehrerConnections.relTime(iso);
    return iso ? new Date(iso).toLocaleString('de-DE') : '';
  }

  function deDate(value) {
    var match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
    return match ? match[3] + '.' + match[2] + '.' + match[1] : String(value || '');
  }

  function host(url) {
    try { return new URL(url).host.replace(/^www\./, ''); } catch (e) { return ''; }
  }

  function isAdmin() {
    var user = window.CURRENT_USER || {};
    return user.is_admin === true || user.role === 'admin';
  }

  function sourceBar(kind, label, parts, actions, note) {
    return '<div class="plan-source-main">' +
      '<span class="pill ' + ({ ok: 'pill-live', warn: 'pill-attention', error: 'pill-danger' }[kind] || '') + '">' + esc(label) + '</span>' +
      '<span class="plan-source-text">' + parts.filter(Boolean).join(' <span aria-hidden="true">·</span> ') + '</span>' +
      '</div>' +
      (actions ? '<div class="plan-source-actions">' + actions + '</div>' : '') +
      (note ? '<div class="plan-source-note is-' + kind + '">' + note + '</div>' : '');
  }

  function weekKey(iso) {
    var day = new Date(iso + 'T00:00:00');
    var monday = new Date(day);
    monday.setDate(day.getDate() - ((day.getDay() + 6) % 7));
    return monday;
  }

  function weekHeading(monday) {
    var sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    var now = new Date();
    var thisMonday = weekKey(now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0'));
    var diff = Math.round((monday - thisMonday) / (7 * 86400000));
    var label = diff === 0 ? 'Diese Woche' : diff === 1 ? 'Nächste Woche' : 'KW ' + isoWeek(monday);
    var range = monday.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) + '–' +
      sunday.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
    return '<h3 class="plan-week-heading">' + esc(label) + ' <span>' + esc(range) + '</span></h3>';
  }

  function isoWeek(date) {
    var d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    var dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    var yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  }

  // „neu“ / „geändert“ from app.js (per-teacher state on the server).
  function newMark(source, date, title) {
    return window.LehrerNewMarks ? window.LehrerNewMarks.html(source, date, title) : '';
  }

  // ── Orgaplan ────────────────────────────────────────────────────────────────

  function joinOrgaplanSection(primary, notes) {
    if (!primary && !notes) return '';
    if (primary && notes) return primary + ' (' + notes + ')';
    return primary || notes;
  }

  function _orgaplanLevel() {
    try { return localStorage.getItem(ORGAPLAN_LEVEL_KEY) || 'all'; } catch (e) { return 'all'; }
  }

  function _sectionsFor(item, level) {
    var sections = [
      { id: 'general', label: 'Allgemein', value: item.general },
      { id: 'middle', label: 'Mittelstufe', value: joinOrgaplanSection(item.middle, item.middleNotes) },
      { id: 'upper', label: 'Oberstufe', value: joinOrgaplanSection(item.upper, item.upperNotes) },
    ].filter(function (s) { return s.value; });
    if (level === 'middle') sections = sections.filter(function (s) { return s.id !== 'upper'; });
    if (level === 'upper') sections = sections.filter(function (s) { return s.id !== 'middle'; });
    return sections;
  }

  function _levelClass(label) {
    return { Allgemein: 'orgaplan-label--allgemein', Mittelstufe: 'orgaplan-label--mittelstufe', Oberstufe: 'orgaplan-label--oberstufe' }[label] || '';
  }

  function renderOrgaplanItem(item, level) {
    var sections = _sectionsFor(item, level || 'all');
    var today = new Date().toISOString().slice(0, 10);
    var weekday = item.weekday || (item.isoDate ? new Date(item.isoDate + 'T00:00:00').toLocaleDateString('de-DE', { weekday: 'short' }).replace('.', '') : '');
    var body = sections.length
      ? sections.map(function (s) {
          return '<div class="orgaplan-row">' +
            '<span class="orgaplan-label ' + _levelClass(s.label) + '">' + esc(s.label) + '</span>' +
            '<p>' + esc(truncateText(s.value, 260)) + '</p></div>';
        }).join('')
      : '<p class="orgaplan-text">' + esc(truncateText(item.detail || item.text || '', 260)) + '</p>';
    return '<article class="orgaplan-entry' + (item.isoDate === today ? ' is-today' : '') + '">' +
      '<div class="orgaplan-entry-head">' +
      '<strong class="orgaplan-entry-date">' + esc(weekday ? weekday + ' ' : '') + esc(item.dateLabel || '') + '</strong>' +
      (item.isoDate === today ? '<span class="pill pill-live">heute</span>' : '') +
      '</div>' +
      '<div class="orgaplan-entry-copy">' + body + '</div></article>';
  }

  function renderOrgaplanSourceBar(orgaplan) {
    var el = _elements.orgaplanSourceBar;
    if (!el) return;
    var status = orgaplan.status || 'pending';
    var kind = status === 'ok' ? 'ok' : status === 'pending' ? '' : status === 'error' ? 'error' : 'warn';
    var label = { ok: 'aktuell', outdated: 'veraltet', error: 'Fehler', pending: 'wird geladen' }[status] || 'unbekannt';
    var fileLabel = orgaplan.schoolYear ? 'Orgaplan ' + orgaplan.schoolYear : (orgaplan.sourceName || 'Orgaplan');
    var parts = [
      '<strong>' + esc(fileLabel) + '</strong>',
      orgaplan.stand ? 'Stand ' + esc(orgaplan.stand) : '',
      orgaplan.mode === 'fixed' ? 'feste PDF' : (orgaplan.site ? 'automatisch von ' + esc(host(orgaplan.site)) : ''),
      orgaplan.checkedAt ? 'geprüft ' + esc(relTime(orgaplan.checkedAt)) : '',
    ];
    var actions =
      (orgaplan.sourceUrl ? '<a class="secondary-link" href="' + esc(orgaplan.sourceUrl) + '" target="_blank" rel="noopener noreferrer">PDF öffnen ↗</a>' : '') +
      '<button class="secondary-link" type="button" data-plan-action="orgaplan-refresh">' + (_busy.orgaplan ? 'Aktualisiere …' : 'Aktualisieren') + '</button>' +
      (window.MULTIUSER_ENABLED ? '<button class="secondary-link" type="button" data-open-connections="orgaplan">Quelle' + (isAdmin() ? ' ändern' : '') + '</button>' : '');
    var note = '';
    if (status === 'outdated' || status === 'error') note = esc(orgaplan.detail || orgaplan.error || '');
    else if (orgaplan.error) note = 'Letzte Prüfung fehlgeschlagen: ' + esc(orgaplan.error) + ' Angezeigt wird der zuletzt gelesene Plan.';
    el.innerHTML = sourceBar(note && status === 'ok' ? 'warn' : kind, label, parts, actions, note);
  }

  function renderOrgaplanLevelFilter() {
    var el = _elements.orgaplanLevelFilter;
    if (!el) return;
    var level = _orgaplanLevel();
    el.innerHTML = LEVELS.map(function (option) {
      return '<button class="filter-button' + (option.id === level ? ' active' : '') + '" type="button" data-orgaplan-level="' + option.id + '">' + esc(option.label) + '</button>';
    }).join('');
    el.querySelectorAll('[data-orgaplan-level]').forEach(function (button) {
      button.addEventListener('click', function () {
        try { localStorage.setItem(ORGAPLAN_LEVEL_KEY, button.getAttribute('data-orgaplan-level')); } catch (e) { /* private mode */ }
        renderPlanDigest();
      });
    });
  }

  // ── Orgaplan as a compact agenda ────────────────────────────────────────────
  // One row per day, small level tags, and items that run over several school
  // days (class trips …) shown once with "bis …".

  var LEVEL_TAGS = {
    general: { label: 'Allg.', title: 'Allgemein – für alle' },
    middle: { label: 'MS', title: 'Mittelstufe' },
    upper: { label: 'OS', title: 'Oberstufe' },
  };
  var WEEKDAYS_SHORT = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
  var OPEN_WEEKS = 2;
  var _showAllWeeks = false;

  function isoLocal(date) {
    return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
  }

  function _dayItems(entry, level) {
    var parts = [];
    if (entry.general) parts.push(['general', entry.general]);
    var middle = joinOrgaplanSection(entry.middle, entry.middleNotes);
    var upper = joinOrgaplanSection(entry.upper, entry.upperNotes);
    if (middle && level !== 'upper') parts.push(['middle', middle]);
    if (upper && level !== 'middle') parts.push(['upper', upper]);
    var items = [];
    parts.forEach(function (part) {
      part[1].split(' · ').forEach(function (text) {
        text = text.trim();
        if (text) items.push({ level: part[0], text: text });
      });
    });
    return items;
  }

  // Next school day: the following day, or Monday after a Friday.
  function _continues(previousIso, iso) {
    var previous = new Date(previousIso + 'T00:00:00');
    var next = new Date(iso + 'T00:00:00');
    var gap = Math.round((next - previous) / 86400000);
    return gap === 1 || (gap === 3 && previous.getDay() === 5);
  }

  function orgaplanAgenda(entries, level) {
    var days = [];
    var running = {};
    entries.forEach(function (entry) {
      var fresh = [];
      _dayItems(entry, level).forEach(function (item) {
        var key = item.level + '|' + item.text.toLowerCase();
        var open = running[key];
        if (open && _continues(open.lastIso, entry.isoDate)) {
          open.until = entry.isoDate;
          open.lastIso = entry.isoDate;
          return;
        }
        running[key] = { level: item.level, text: item.text, until: '', lastIso: entry.isoDate };
        fresh.push(running[key]);
      });
      if (fresh.length) days.push({ iso: entry.isoDate, items: fresh });
    });
    return days;
  }

  function _agendaDay(day, today) {
    var date = new Date(day.iso + 'T00:00:00');
    return '<div class="og-day' + (day.iso === today ? ' is-today' : '') + '">' +
      '<div class="og-date"><strong>' + WEEKDAYS_SHORT[date.getDay()] + '</strong> ' +
      String(date.getDate()).padStart(2, '0') + '.' + String(date.getMonth() + 1).padStart(2, '0') + '.' +
      (day.iso === today ? '<span class="og-today">heute</span>' : '') + newMark('orgaplan', day.iso) + '</div>' +
      '<ul class="og-items">' + day.items.map(function (item) {
        var tag = LEVEL_TAGS[item.level];
        var until = '';
        if (item.until) {
          var end = new Date(item.until + 'T00:00:00');
          until = '<span class="og-until">bis ' + WEEKDAYS_SHORT[end.getDay()] + ' ' +
            String(end.getDate()).padStart(2, '0') + '.' + String(end.getMonth() + 1).padStart(2, '0') + '.</span>';
        }
        return '<li><span class="og-level og-level--' + item.level + '" title="' + esc(tag.title) + '">' + esc(tag.label) + '</span>' +
          '<span class="og-text">' + esc(item.text) + until + '</span></li>';
      }).join('') + '</ul></div>';
  }

  function renderOrgaplanList(orgaplan) {
    var list = _elements.orgaplanUpcomingList;
    if (!list) return;
    var level = _orgaplanLevel();
    var days = orgaplanAgenda(orgaplan.upcoming || [], level);
    if (_elements.orgaplanDigestDetail) {
      var count = days.reduce(function (sum, day) { return sum + day.items.length; }, 0);
      _elements.orgaplanDigestDetail.textContent = days.length
        ? count + ' Termine in den nächsten sechs Wochen' + (level === 'all' ? '' : ' · ' + (level === 'middle' ? 'Mittelstufe' : 'Oberstufe') + ' und Allgemein')
        : '';
    }
    if (!days.length) {
      var empty = orgaplan.status === 'pending' ? 'Der Orgaplan wird geladen …'
        : orgaplan.status === 'ok' ? 'In den nächsten sechs Wochen stehen keine Termine im Orgaplan.'
        : 'Keine aktuellen Orgaplan-Termine.';
      list.innerHTML = '<div class="empty-state">' + esc(empty) + '</div>';
      return;
    }
    var today = isoLocal(new Date());
    var weeks = [];
    days.forEach(function (day) {
      var monday = weekKey(day.iso);
      var key = isoLocal(monday);
      if (!weeks.length || weeks[weeks.length - 1].key !== key) weeks.push({ key: key, monday: monday, days: [] });
      weeks[weeks.length - 1].days.push(day);
    });
    var visible = _showAllWeeks ? weeks : weeks.slice(0, OPEN_WEEKS);
    list.innerHTML = '<div class="og-agenda">' + visible.map(function (week) {
      return '<section class="og-week">' + weekHeading(week.monday) +
        week.days.map(function (day) { return _agendaDay(day, today); }).join('') + '</section>';
    }).join('') + '</div>' +
      (weeks.length > OPEN_WEEKS
        ? '<button class="section-toggle og-more" type="button" data-orgaplan-weeks>' +
          (_showAllWeeks ? 'Weniger anzeigen' : 'Weitere ' + (weeks.length - OPEN_WEEKS) + ' Wochen anzeigen') + '</button>'
        : '');
    var more = list.querySelector('[data-orgaplan-weeks]');
    if (more) more.addEventListener('click', function () { _showAllWeeks = !_showAllWeeks; renderOrgaplanList(orgaplan); });
  }

  function checkOrgaplanNow(button) {
    if (_busy.orgaplan) return;
    _busy.orgaplan = true;
    if (button) { button.disabled = true; button.textContent = 'Aktualisiere …'; }
    fetch((window.BACKEND_API_URL || '') + '/api/v2/modules/orgaplan/refresh', { method: 'POST', credentials: 'include' })
      .then(function (resp) { return resp.json().catch(function () { return {}; }); })
      .then(function () { return _refreshDashboard ? _refreshDashboard(true) : null; })
      .catch(function () { /* the source bar shows the state after the reload */ })
      .finally(function () { _busy.orgaplan = false; renderPlanDigest(); });
  }

  // ── Klassenarbeitsplan ──────────────────────────────────────────────────────

  function _classworkSourceLabel(source) {
    return { onedrive: 'von OneDrive', 'onedrive-browser': 'von OneDrive (über einen Browser)', upload: 'hochgeladen', auto: 'automatisch abgerufen' }[source] || '';
  }

  function renderClassworkSourceBar(classwork, sync, url) {
    var el = _elements.classworkSourceBar;
    if (!el) return;
    var plan = classwork.planStatus || {};
    sync = sync || {};
    // A new link that never loaded: the stored plan still belongs to the previous link.
    var previousLink = sync.onedrive && !sync.last_success && /^onedrive/.test(plan.source || '');
    var outdated = plan.state === 'outdated';
    var syncProblem = sync.onedrive && (sync.last_result === 'error' || sync.last_result === 'blocked') && sync.needs_browser;
    var kind = previousLink || outdated || syncProblem ? 'warn' : (plan.state === 'ok' ? 'ok' : '');
    var label = previousLink ? 'neuer Link' : outdated ? 'veraltet' : syncProblem ? 'Abruf gestört'
      : (plan.state === 'ok' ? 'aktuell' : (url ? 'wird geladen' : 'kein Plan'));
    var parts = [
      plan.fileName ? '<strong>' + esc(plan.fileName) + '</strong>' : '<strong>Klassenarbeitsplan</strong>',
      plan.fileModified ? 'geändert am ' + esc(deDate(plan.fileModified)) : '',
      sync.last_success ? 'geprüft ' + esc(relTime(sync.last_success)) : (plan.storedAt ? 'übernommen ' + esc(plan.storedAt) : ''),
      _classworkSourceLabel(plan.source),
    ];
    var actions =
      (url ? '<button class="secondary-link" type="button" data-plan-action="classwork-refresh">' + (_busy.classwork ? 'Aktualisiere …' : 'Aktualisieren') + '</button>' : '') +
      (url ? '<a class="secondary-link" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">Auf OneDrive öffnen ↗</a>' : '') +
      (window.MULTIUSER_ENABLED ? '<button class="secondary-link" type="button" data-open-connections="klassenarbeitsplan">' + (isAdmin() ? 'Link ändern' : 'Details') + '</button>' : '');
    var note = '';
    if (previousLink) {
      note = (sync.last_error
        ? 'Der eingetragene Link konnte noch nicht geladen werden: ' + esc(sync.last_error)
        : 'Der eingetragene Link wird gerade geladen.') + ' Angezeigt wird noch der Plan vom vorherigen Link.';
    } else if (outdated) {
      note = esc(plan.message) + ' ' + (isAdmin()
        ? 'Trag unter „Verbindungen“ den Link zum aktuellen Plan ein – am besten den Link zum OneDrive-Ordner, dann findet das Cockpit neue Dateien selbst.'
        : 'Bitte gib der Person Bescheid, die das Cockpit an eurer Schule verwaltet.');
    } else if (syncProblem && sync.last_error) {
      note = 'Letzter Abruf fehlgeschlagen: ' + esc(sync.last_error);
    } else if (!url && plan.state !== 'ok') {
      note = 'Noch kein Klassenarbeitsplan hinterlegt. Du kannst die Excel-Datei hochladen' + (isAdmin() ? ' oder unter „Verbindungen“ den OneDrive-Link eintragen.' : '.');
    }
    el.innerHTML = sourceBar(kind, label, parts, actions, note);
  }

  function checkClassworkNow(button) {
    if (_busy.classwork) return;
    _busy.classwork = true;
    if (button) { button.disabled = true; button.textContent = 'Aktualisiere …'; }
    var data = _getData() || {};
    var url = (data.base || {}).klassenarbeitsplan_url || '';
    var api = (window.BACKEND_API_URL || '') + '/api/v2/modules/klassenarbeitsplan/fetch';
    fetch(api, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: '{}' })
      .then(function (resp) { return resp.json().catch(function () { return {}; }); })
      .then(function (result) {
        if (result.result === 'ok' || result.result === 'unchanged') {
          return result.result === 'ok' ? 'Neuer Stand geladen.' : 'Geprüft – die Datei auf OneDrive ist unverändert.';
        }
        if (result.sync && result.sync.needs_browser && window.LehrerOneDriveSync && url) {
          return window.LehrerOneDriveSync.syncNow(url, result.sync.etag || '').then(function (sync) {
            return sync.state === 'ok' ? 'Neuer Stand über deinen Browser geladen.' : 'Geprüft – die Datei ist unverändert.';
          });
        }
        throw new Error(result.error || 'Der Plan konnte nicht geprüft werden.');
      })
      .then(function (message) {
        _state.classworkUploadFeedback = message;
        _state.classworkUploadFeedbackKind = 'success';
        return _refreshDashboard ? _refreshDashboard(true) : null;
      })
      .catch(function (err) {
        _state.classworkUploadFeedback = err.message;
        _state.classworkUploadFeedbackKind = 'warning';
      })
      .finally(function () { _busy.classwork = false; renderPlanDigest(); });
  }

  // ── Classwork class selection ────────────────────────────────────────────────

  function getSelectedClasses(classes, defaultClass) {
    if (_getSelectedClassworkClasses) return _getSelectedClassworkClasses(classes, defaultClass);
    return classes.slice();
  }

  function renderClassworkSelector(classes, defaultClass) {
    var pillContainer = _elements.classworkClassPills;
    var pillSection = _elements.classworkPillSection;
    if (!pillContainer) return;
    if (!classes.length) {
      if (pillSection) pillSection.hidden = true;
      return;
    }
    if (pillSection) pillSection.hidden = false;

    pillContainer.innerHTML = _renderClassPills(classes, 'data-classwork-class');
    pillContainer.querySelectorAll('[data-classwork-class]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var label = btn.dataset.classworkClass;
        if (label === '*') _setSelectedClassworkClasses([]);
        else _toggleClassworkClass(label, classes);
      });
    });
  }

  function renderClassworkViewSwitch() {
    if (!_elements.classworkViewSwitch) return;
    var options = [
      { id: 'list', label: 'Liste' },
      { id: 'calendar', label: 'Nach Tagen' },
    ];
    _elements.classworkViewSwitch.innerHTML = options.map(function (option) {
      return '<button class="filter-button ' + (_state.classworkView === option.id ? 'active' : '') + '" type="button" data-classwork-view="' + option.id + '">' + option.label + '</button>';
    }).join('');
    _elements.classworkViewSwitch.querySelectorAll('[data-classwork-view]').forEach(function (button) {
      button.addEventListener('click', function () {
        _state.classworkView = button.dataset.classworkView;
        renderPlanDigest();
      });
    });
  }

  function _dayLabel(entry) {
    var weekday = entry.isoDate
      ? new Date(entry.isoDate + 'T00:00:00').toLocaleDateString('de-DE', { weekday: 'short' }).replace('.', '')
      : _weekdayLabel(entry.weekdayLabel).slice(0, 2);
    return weekday + ' ' + entry.dateLabel;
  }

  function renderClassworkList(entries) {
    return '<div class="cw-table">'
      + '<div class="cw-table-head">'
      + '<span>Datum</span><span>Klasse</span><span>Art</span><span>Bezeichnung</span>'
      + '</div>'
      + entries.map(function (entry) {
          return '<div class="cw-row">'
            + '<span class="cw-row-date">' + esc(_dayLabel(entry)) + '</span>'
            + '<span class="cw-row-class"><span class="meta-tag">' + esc(entry.classLabel) + '</span></span>'
            + '<span class="cw-row-kind"><span class="meta-tag low">' + esc(entry.kind) + '</span></span>'
            + '<span class="cw-row-title">' + esc(entry.summary || entry.title)
            + newMark('klassenarbeitsplan', entry.isoDate, entry.classLabel + ': ' + (entry.summary || entry.title)) + '</span>'
            + '</div>';
        }).join('')
      + '</div>';
  }

  function renderClassworkCalendar(entries) {
    var grouped = [];
    entries.forEach(function (entry) {
      var last = grouped[grouped.length - 1];
      if (!last || last.iso !== entry.isoDate) grouped.push({ iso: entry.isoDate, label: _dayLabel(entry), items: [] });
      grouped[grouped.length - 1].items.push(entry);
    });
    return '<div class="cw-days">' + grouped.map(function (day) {
      return '<section class="cw-day"><h4>' + esc(day.label) + '</h4>' +
        day.items.map(function (entry) {
          return '<p><span class="meta-tag">' + esc(entry.classLabel) + '</span> ' + esc(entry.summary || entry.title)
            + newMark('klassenarbeitsplan', entry.isoDate, entry.classLabel + ': ' + (entry.summary || entry.title)) + '</p>';
        }).join('') + '</section>';
    }).join('') + '</div>';
  }

  function renderClassworkPanel(classwork, sync, url) {
    renderClassworkSourceBar(classwork, sync, url);
    var classes = classwork.classes || [];
    var entries = classwork.entries || [];
    var plan = classwork.planStatus || {};
    renderClassworkSelector(classes, classwork.defaultClass || '');
    renderClassworkViewSwitch();

    var feedback = _elements.classworkUploadFeedback;
    if (feedback) {
      feedback.textContent = _state.classworkUploadFeedback || '';
      feedback.className = 'connect-feedback' + (_state.classworkUploadFeedbackKind ? ' ' + _state.classworkUploadFeedbackKind : '');
    }

    var activeClasses = getSelectedClasses(classes, classwork.defaultClass || '');
    var showingAll = !activeClasses.length || activeClasses.length === classes.length;
    var classEntries = entries
      .filter(function (entry) { return showingAll || activeClasses.includes(entry.classLabel); })
      .sort(function (left, right) { return (left.isoDate || '').localeCompare(right.isoDate || ''); });
    var visible = _getVisiblePanelItems(classEntries, 'classwork');

    if (_elements.classworkDigestDetail) {
      _elements.classworkDigestDetail.textContent = classEntries.length
        ? classEntries.length + ' kommende Arbeiten' + (showingAll ? ' (alle Klassen).' : ' für ' + activeClasses.join(', ') + '.')
        : '';
    }
    _setExpandableMeta(_elements.classworkPreviewList, classEntries.length, visible.length);
    var empty = plan.state === 'outdated'
      ? 'Keine kommenden Arbeiten – der hinterlegte Plan ist veraltet (siehe oben).'
      : plan.state === 'ok' ? 'Für diese Auswahl stehen keine kommenden Arbeiten im Plan.'
      : 'Noch kein Klassenarbeitsplan geladen.';
    _elements.classworkPreviewList.innerHTML = classEntries.length
      ? (_state.classworkView === 'calendar' ? renderClassworkCalendar(visible) : renderClassworkList(visible))
      : '<div class="empty-state">' + esc(empty) + '</div>';
  }

  // ── Schultermine ────────────────────────────────────────────────────────────

  var WEEKDAYS = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];

  function _shortDay(iso) {
    return iso.slice(8, 10) + '.' + iso.slice(5, 7) + '.';
  }

  function _eventWhen(event) {
    var start = event.start.slice(0, 10);
    var end = event.end ? event.end.slice(0, 10) : start;
    if (end !== start) return _shortDay(start) + '–' + _shortDay(end);
    return WEEKDAYS[new Date(start + 'T00:00:00').getDay()] + ' ' + _shortDay(start);
  }

  function renderSchoolCalendar(calendar) {
    var bar = _elements.termineSourceBar;
    var list = _elements.schoolCalendarList;
    if (!bar || !list) return;
    if (!calendar) {
      bar.innerHTML = sourceBar('', 'aus', ['<strong>Schultermine</strong>', 'für dich ausgeblendet'], '', '');
      list.innerHTML = '';
      return;
    }
    var events = calendar.events || [];
    var ok = !calendar.error;
    bar.innerHTML = sourceBar(ok ? 'ok' : 'error', ok ? 'aktuell' : 'Fehler',
      ['<strong>Kalender der Schulwebseite</strong>', calendar.feed_url ? esc(host(calendar.feed_url)) : '',
       calendar.fetched_at ? 'geprüft ' + esc(relTime(calendar.fetched_at)) : ''],
      (window.MULTIUSER_ENABLED ? '<button class="secondary-link" type="button" data-open-connections="termine">Quelle</button>' : ''),
      ok ? '' : esc(calendar.error));
    if (!events.length) {
      list.innerHTML = '<div class="empty-state">' + (ok ? 'Keine Schultermine in den nächsten sechs Wochen.' : '') + '</div>';
      return;
    }
    var today = new Date().toISOString().slice(0, 10);
    list.innerHTML = events.map(function (event) {
      var running = event.start.slice(0, 10) <= today && (event.end || event.start).slice(0, 10) >= today;
      var title = event.url
        ? '<a href="' + esc(event.url) + '" target="_blank" rel="noopener noreferrer">' + esc(event.title) + '</a>'
        : esc(event.title);
      return '<article class="calendar-item' + (running ? ' is-today' : '') + '">'
        + '<div class="calendar-item-when"><strong>' + esc(_eventWhen(event)) + '</strong>'
        + '<span>' + esc(event.all_day ? (running ? 'läuft' : 'ganztägig') : (event.time_label || '')) + '</span></div>'
        + '<div class="calendar-item-body"><p class="calendar-item-title">' + title + newMark('termine', event.start, event.title) + '</p>'
        + (event.location ? '<p class="message-snippet">' + esc(event.location) + '</p>' : '')
        + '</div></article>';
    }).join('');
  }

  // ── Orchestration ───────────────────────────────────────────────────────────

  function renderPlanDigest() {
    if (!_elements || !_state) return;
    var data = _getData();
    var digest = data.planDigest || {};
    var orgaplan = digest.orgaplan || {};
    var classwork = digest.classwork || {};
    var showOrgaplan = _isModuleVisible('orgaplan');
    var showClasswork = _isModuleVisible('klassenarbeitsplan');
    var showCalendar = _isModuleVisible('wichtige-termine');

    _toggleTab('orgaplan', showOrgaplan);
    _toggleTab('klassenarbeitsplan', showClasswork);
    _toggleTab('termine', showCalendar || !!data.schoolCalendar);

    if (showOrgaplan) {
      renderOrgaplanSourceBar(orgaplan);
      renderOrgaplanLevelFilter();
      renderOrgaplanList(orgaplan);
    }
    if (showClasswork) {
      renderClassworkPanel(classwork, data.classworkSync, (data.base || {}).klassenarbeitsplan_url || '');
    }
    renderSchoolCalendar(data.schoolCalendar);
  }

  function _toggleTab(id, visible) {
    var tab = document.querySelector('[data-plans-tab="' + id + '"]');
    if (tab) tab.hidden = !visible;
    if (!visible && tab && tab.classList.contains('is-active')) {
      var first = document.querySelector('.plans-tab-btn:not([hidden])');
      if (first) first.click();
    }
  }

  return {
    init: init,
    renderPlanDigest: renderPlanDigest,
    renderClassworkList: renderClassworkList,
    renderClassworkCalendar: renderClassworkCalendar,
    renderOrgaplanItem: renderOrgaplanItem,
    getActiveClassworkClass: function (classes, defaultClass) {
      return getSelectedClasses(classes, defaultClass)[0] || '';
    },
    truncateText: truncateText,
    checkClassworkNow: checkClassworkNow,
  };
})();

window.LehrerClasswork = LehrerClasswork;
