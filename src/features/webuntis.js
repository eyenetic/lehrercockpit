/**
 * LehrerWebUntis — WebUntis Stundenplan feature module (Phase 10c)
 *
 * Extracted from src/app.js to separate the WebUntis rendering, picker,
 * watchlist, plan strip, and schedule logic into an isolated module.
 *
 * WHAT THIS FILE DOES:
 *   - renderWebUntisControls()    — view-switch buttons, "Heute" link
 *   - renderWebUntisPicker()      — full picker overlay (search, categories, favorites)
 *   - renderWebUntisWatchlist()   — watchlist panel (Radar)
 *   - renderWebUntisPlanStrip()   — pinned plan chips
 *   - renderWebUntisSchedule()    — schedule router (day/week/next-week)
 *   - renderWeekSchedule()        — week board with columns
 *   - renderAgendaGroups()        — day agenda groups wrapper
 *   - renderAgendaGroup()         — single agenda group
 *   - renderDayGroup()            — day group (day view)
 *   - renderDayEvent()            — individual day-view event card
 *   - renderWeekEvent()           — individual week-view event chip
 *   - getWebUntisEvents()         — filter events by current view window
 *   - normalizeLocalWebUntisState() — reset shortcuts/favorites on init
 *
 * PUBLIC API:
 *   window.LehrerWebUntis.init(state, elements, callbacks)
 *   window.LehrerWebUntis.renderWebUntisControls()
 *   window.LehrerWebUntis.renderWebUntisPicker()
 *   window.LehrerWebUntis.renderWebUntisWatchlist()
 *   window.LehrerWebUntis.renderWebUntisPlanStrip()
 *   window.LehrerWebUntis.renderWebUntisSchedule()
 *   window.LehrerWebUntis.getWebUntisEvents()
 *   window.LehrerWebUntis.normalizeLocalWebUntisState()
 *   window.LehrerWebUntis.loadSavedShortcuts()
 *   window.LehrerWebUntis.loadWebUntisFavorites()
 *
 * DEPENDS ON:
 *   - callbacks.getData()         — returns current dashboard data
 *   - callbacks.renderAll()       — full re-render (called after plan select)
 *   - callbacks.formatDate()      — date formatter
 *   - callbacks.formatTime()      — time formatter
 *   - callbacks.weekdayLabel()    — day-of-week label
 *   - callbacks.isSameDay()       — date comparison
 *   - callbacks.startOfWeek()     — get Monday of a week
 *   - callbacks.isoWeekNumber()   — ISO week number
 *   - callbacks.bindExternalLink() — set href + visibility on <a> element
 */
(function () {
  'use strict';

  // ── Constants (duplicated from app.js — must match exactly) ─────────────────
  var WEBUNTIS_SHORTCUTS_KEY   = 'lehrerCockpit.webuntis.shortcuts';
  var WEBUNTIS_FAVORITES_KEY   = 'lehrerCockpit.webuntis.favorites';
  var ACTIVE_WEBUNTIS_PLAN_KEY = 'lehrerCockpit.webuntis.activePlan';

  // ── Internal references (set via init) ──────────────────────────────────────
  var _state     = null;
  var _elements  = null;
  var _callbacks = {};

  // ── Private helpers — delegate to callbacks ──────────────────────────────────

  function _getData()                       { return _callbacks.getData ? _callbacks.getData() : {}; }
  function _renderAll()                     { if (_callbacks.renderAll) _callbacks.renderAll(); }
  function _formatDate(v)                   { return _callbacks.formatDate ? _callbacks.formatDate(v) : String(v); }
  function _weekdayLabel(v)                 { return _callbacks.weekdayLabel ? _callbacks.weekdayLabel(v) : String(v); }
  function _isSameDay(a, b)                 { return _callbacks.isSameDay ? _callbacks.isSameDay(a, b) : false; }
  function _startOfWeek(v)                  { return _callbacks.startOfWeek ? _callbacks.startOfWeek(v) : v; }
  function _isoWeekNumber(v)                { return _callbacks.isoWeekNumber ? _callbacks.isoWeekNumber(v) : 0; }
  function _bindExternalLink(el, url, lbl)  { if (_callbacks.bindExternalLink) _callbacks.bindExternalLink(el, url, lbl); }

  // ── localStorage helpers ─────────────────────────────────────────────────────

  function loadSavedShortcuts() {
    try {
      var raw = window.localStorage.getItem(WEBUNTIS_SHORTCUTS_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? _sanitizeShortcuts(parsed) : [];
    } catch (_e) {
      return [];
    }
  }

  function persistShortcuts() {
    try { window.localStorage.setItem(WEBUNTIS_SHORTCUTS_KEY, JSON.stringify(_state.shortcuts)); } catch (_e) {}
  }

  function loadWebUntisFavorites() {
    try {
      var raw = window.localStorage.getItem(WEBUNTIS_FAVORITES_KEY);
      var parsed = JSON.parse(raw || '[]');
      return Array.isArray(parsed) ? _sanitizeFavorites(parsed) : [];
    } catch (_e) {
      return [];
    }
  }

  function persistFavorites() {
    try { window.localStorage.setItem(WEBUNTIS_FAVORITES_KEY, JSON.stringify(_state.favorites)); } catch (_e) {}
  }

  function loadActiveShortcutId() {
    try { return window.localStorage.getItem(ACTIVE_WEBUNTIS_PLAN_KEY) || 'personal'; } catch (_e) { return 'personal'; }
  }

  function persistActiveShortcutId() {
    try { window.localStorage.setItem(ACTIVE_WEBUNTIS_PLAN_KEY, _state.activeShortcutId); } catch (_e) {}
  }

  // ── Sanitize helpers ─────────────────────────────────────────────────────────

  function _sanitizeShortcuts(entries) {
    return entries
      .filter(function (e) { return e && typeof e === 'object'; })
      .filter(function (e) { return e.id && e.label && e.type; })
      .filter(function (e) { return !_isPlaceholderTeacher(e.label); })
      .filter(function (e, i, arr) { return arr.findIndex(function (x) { return x.id === e.id; }) === i; });
  }

  function _sanitizeFavorites(entries) {
    return entries
      .filter(function (e) { return typeof e === 'string' && e; })
      .filter(function (e) { return !e.includes('mustermann'); })
      .filter(function (e, i, arr) { return arr.indexOf(e) === i; });
  }

  function _isPlaceholderTeacher(label) {
    var n = String(label || '').trim().toLowerCase();
    return n === 'herr mustermann' || n === 'frau mustermann' || n === 'mustermann';
  }

  // ── State reset on initialize ────────────────────────────────────────────────

  function normalizeLocalWebUntisState() {
    if (!_state) return;
    if (_state.shortcuts.length) {
      _state.shortcuts = [];
      persistShortcuts();
    }
    if (_state.favorites.length) {
      _state.favorites = [];
      persistFavorites();
    }
    _state.activeShortcutId = 'personal';
    _state.activeFinderEntityId = null;
    persistActiveShortcutId();
  }

  // ── Plan helpers ─────────────────────────────────────────────────────────────

  function _getWebUntisPlans(center) {
    var defaultPlans = [];
    if (center.startUrl || center.todayUrl) {
      defaultPlans.push({
        id: 'personal',
        type: 'teacher',
        label: center.activePlan || 'Mein Plan',
        url: center.startUrl || center.todayUrl,
        fixed: true,
      });
    }
    return defaultPlans.concat(_sanitizeShortcuts(_state.shortcuts));
  }

  function getPinnedPlans(center) {
    var basePlans = _getWebUntisPlans(center);
    var favoriteEntities = getFavoriteEntities(center, '');
    var merged = basePlans.slice();
    favoriteEntities.forEach(function (entity) {
      if (!merged.some(function (p) { return p.id === entity.id; })) {
        merged.push({
          id: entity.id,
          type: entity.type,
          label: entity.label,
          url: entity.url || '',
          fixed: false,
          localFilter: !entity.url,
        });
      }
    });
    return merged.slice(0, 6);
  }

  function getActivePlan(center) {
    var activeEntity = _getActiveFinderEntity(center);
    if (activeEntity && !activeEntity.url) {
      return {
        id: activeEntity.id,
        type: activeEntity.type,
        label: activeEntity.label,
        url: '',
        fixed: false,
        localFilter: true,
      };
    }
    var plans = _getWebUntisPlans(center);
    return (
      plans.find(function (p) { return p.id === _state.activeShortcutId; }) ||
      plans[0] || {
        id: 'personal',
        type: 'teacher',
        label: center.activePlan || 'Mein Plan',
        url: center.startUrl || center.todayUrl || '',
        fixed: true,
      }
    );
  }

  function _getActiveFinderEntity(center) {
    return (center.finder && center.finder.entities ? center.finder.entities : []).find(
      function (e) { return e.id === _state.activeFinderEntityId; }
    ) || null;
  }

  function isPlanChipActive(center, plan) {
    if (plan.localFilter) return _state.activeFinderEntityId === plan.id;
    if (plan.id === 'personal') return _state.activeShortcutId === 'personal' && !_state.activeFinderEntityId;
    return _state.activeShortcutId === plan.id;
  }

  function getPickerEntities(center, type, query) {
    var entities = ((center.finder && center.finder.entities) ? center.finder.entities : [])
      .filter(function (e) { return e.type === type; })
      .filter(function (e) {
        if (!query) return true;
        var haystack = (e.label + ' ' + e.detail + ' ' + e.type).toLowerCase();
        return haystack.indexOf(query) !== -1;
      });

    if (type !== 'teacher') return entities;

    var teacherEntries = [
      {
        id: 'personal',
        type: 'teacher',
        label: center.activePlan || 'Mein Stundenplan',
        detail: center.detail || center.note,
        url: center.startUrl || center.todayUrl || '',
        fixed: true,
      },
    ].concat(entities);

    return teacherEntries.filter(function (e, i, arr) {
      return arr.findIndex(function (x) { return x.id === e.id; }) === i;
    });
  }

  function getFavoriteEntities(center, query) {
    var allEntities = [
      {
        id: 'personal',
        type: 'teacher',
        label: center.activePlan || 'Mein Stundenplan',
        detail: center.detail || center.note,
        url: center.startUrl || center.todayUrl || '',
        fixed: true,
      },
    ].concat((center.finder && center.finder.entities) ? center.finder.entities : []);

    return allEntities
      .filter(function (e) { return _state.favorites.indexOf(e.id) !== -1; })
      .filter(function (e) {
        if (!query) return true;
        var haystack = (e.label + ' ' + (e.detail || '') + ' ' + e.type).toLowerCase();
        return haystack.indexOf(query) !== -1;
      });
  }

  function getGlobalPickerResults(center, query) {
    if (!query) return [];
    var combined = [
      {
        id: 'personal',
        type: 'teacher',
        label: center.activePlan || 'Mein Stundenplan',
        detail: center.detail || center.note,
        url: center.startUrl || center.todayUrl || '',
        fixed: true,
      },
    ].concat((center.finder && center.finder.entities) ? center.finder.entities : []);

    return combined
      .filter(function (e) {
        var haystack = ((e.label || '') + ' ' + (e.detail || '') + ' ' + (e.type || '')).toLowerCase();
        return haystack.indexOf(query) !== -1;
      })
      .filter(function (e, i, arr) {
        return arr.findIndex(function (x) { return x.id === e.id; }) === i;
      })
      .slice(0, 8);
  }

  function isEntityActive(center, entity) {
    if (entity.id === 'personal') {
      return _state.activeShortcutId === 'personal' && !_state.activeFinderEntityId;
    }
    if (entity.url) {
      return _state.activeShortcutId === entity.id || _state.activeShortcutId === ('picker-' + entity.id);
    }
    return _state.activeFinderEntityId === entity.id;
  }

  // ── Plan selection / picker actions ──────────────────────────────────────────

  function selectPlanById(center, planId) {
    var entity = planId === 'personal'
      ? {
          id: 'personal',
          type: 'teacher',
          label: center.activePlan || 'Mein Plan',
          url: center.startUrl || center.todayUrl || '',
        }
      : (((center.finder && center.finder.entities) ? center.finder.entities : []).find(
          function (x) { return x.id === planId; }) ||
        (_state.shortcuts ? _state.shortcuts.find(function (x) { return x.id === planId; }) : null));

    if (!entity) return;

    if (entity.id === 'personal') {
      _state.activeShortcutId = 'personal';
      _state.activeFinderEntityId = null;
    } else if (entity.url) {
      var shortcutId = entity.id.startsWith('shortcut-') ? entity.id : ('picker-' + entity.id);
      var existing = _state.shortcuts.find(function (s) { return s.id === shortcutId; });
      if (!existing) {
        _state.shortcuts.unshift({ id: shortcutId, type: entity.type, label: entity.label, url: entity.url });
        persistShortcuts();
      }
      _state.activeShortcutId = shortcutId;
      _state.activeFinderEntityId = null;
    } else {
      _state.activeShortcutId = 'personal';
      _state.activeFinderEntityId = entity.id;
    }

    persistActiveShortcutId();
    closePicker();
    _renderAll();
  }

  function toggleFavorite(entityId) {
    if (_state.favorites.indexOf(entityId) !== -1) {
      _state.favorites = _state.favorites.filter(function (id) { return id !== entityId; });
    } else {
      _state.favorites.unshift(entityId);
    }
    persistFavorites();
    renderWebUntisPicker();
    renderWebUntisPlanStrip();
  }

  function closePicker() {
    _state.webuntisPickerOpen = false;
    _state.webuntisPickerCategory = null;
    _state.webuntisPickerSearch = '';
    renderWebUntisPicker();
  }

  function bindPickerActions(center) {
    var zones = [
      _elements.webuntisPickerCurrent,
      _elements.webuntisPickerResults,
      _elements.webuntisPickerFavorites,
      _elements.webuntisPickerCategoryResults,
    ];
    zones.forEach(function (zone) {
      if (!zone) return;
      zone.querySelectorAll('[data-picker-select], [data-picker-favorite]').forEach(function (btn) {
        if (btn.dataset.pickerSelect) {
          btn.addEventListener('click', function () { selectPlanById(center, btn.dataset.pickerSelect); });
        }
        if (btn.dataset.pickerFavorite) {
          btn.addEventListener('click', function () { toggleFavorite(btn.dataset.pickerFavorite); });
        }
      });
    });
  }

  // ── Label / icon helpers ─────────────────────────────────────────────────────

  function shortcutTypeLabel(type) {
    return ({ teacher: 'Lehrkraft', class: 'Klasse', room: 'Raum' }[type] || type);
  }

  function pickerIcon(type) {
    return ({ teacher: 'L', class: 'K', room: 'R' }[type] || '•');
  }

  function watchStatusLabel(status) {
    return ({ changed: 'geaendert', watch: 'beobachten', synced: 'live' }[status] || status);
  }

  function watchStatusClass(status) {
    return ({ changed: 'high', watch: 'low', synced: 'low' }[status] || '');
  }

  // ── Event timing / state helpers ─────────────────────────────────────────────

  function getEventTimingClass(event) {
    var now = new Date();
    var start = new Date(event.startsAt);
    var end = new Date(event.endsAt);
    if (end < now) return 'is-past';
    if (start <= now && now < end) return 'is-current';
    return 'is-upcoming';
  }

  function isEventCurrent(event) {
    return getEventTimingClass(event) === 'is-current';
  }

  function isCancelledEvent(event) {
    var haystack = ((event.title || '') + ' ' + (event.description || '') + ' ' + (event.detail || '')).toLowerCase();
    return /(entf[aä]llt|ausfall|ausfaellt|fällt aus|faellt aus|cancelled|verlegt|vertretung)/i.test(haystack);
  }

  function eventStateLabel(event) {
    if (isCancelledEvent(event)) return 'entfaellt';
    var t = getEventTimingClass(event);
    if (t === 'is-past') return 'vorbei';
    if (t === 'is-current') return 'jetzt';
    return 'kommt';
  }

  function eventStateTagClass(event) {
    if (isCancelledEvent(event)) return 'critical';
    var t = getEventTimingClass(event);
    if (t === 'is-past') return 'low';
    if (t === 'is-current') return 'ok';
    return '';
  }

  function compactEventDetail(event) {
    var parts = [];
    if (event.location) parts.push('Ort ' + event.location);
    if (event.description) parts.push(event.description);
    return parts.join(' • ') || 'Persoenlicher WebUntis-Termin';
  }

  function extractClassLabels(event) {
    var haystack = ((event.title || '') + ' ' + (event.detail || '') + ' ' + (event.description || ''))
      .match(/\b(?:[5-9][A-Z]?|1[0-3][A-Z]?|Q\d(?:\/Q?\d)?)\b/gi);
    return haystack ? haystack.map(function (t) { return t.toUpperCase(); }) : [];
  }

  // ── Date / week helpers ──────────────────────────────────────────────────────

  function getWeekAnchorDate(currentDate, view) {
    var referenceDate = new Date(currentDate + 'T00:00:00');
    var weekStart = _startOfWeek(referenceDate);
    if (view === 'next-week') {
      var nextWeek = new Date(weekStart);
      nextWeek.setDate(nextWeek.getDate() + 7);
      return nextWeek;
    }
    return weekStart;
  }

  function nextWeekLabel(currentDate) {
    var nextWeek = getWeekAnchorDate(currentDate, 'next-week');
    var weekNumber = _isoWeekNumber(nextWeek);
    return 'Naechste KW ' + weekNumber;
  }

  function getWebUntisRangeLabel(center) {
    if (_state.webuntisView === 'day') return 'Heute';
    if (_state.webuntisView === 'next-week') return nextWeekLabel(center.currentDate);
    return center.currentWeekLabel || 'Diese Woche';
  }

  function groupEventsByDay(events) {
    var groups = new Map();
    events.forEach(function (event) {
      var date = new Date(event.startsAt);
      var key = date.toISOString().slice(0, 10);
      var label = _weekdayLabel(date) + ' ' + _formatDate(date);
      if (!groups.has(key)) groups.set(key, { key: key, label: label, events: [] });
      groups.get(key).events.push(event);
    });
    return Array.from(groups.values());
  }

  function buildWeekColumns(events, currentDate) {
    var weekStart = _startOfWeek(currentDate instanceof Date ? currentDate : new Date(currentDate + 'T00:00:00'));
    var byKey = new Map();
    events.forEach(function (event) {
      var date = new Date(event.startsAt);
      var key = date.toISOString().slice(0, 10);
      if (!byKey.has(key)) byKey.set(key, []);
      byKey.get(key).push(event);
    });
    var todayKey = new Date().toISOString().slice(0, 10);
    return Array.from({ length: 5 }, function (_, index) {
      var day = new Date(weekStart);
      day.setDate(weekStart.getDate() + index);
      var key = day.toISOString().slice(0, 10);
      return {
        key: key,
        weekday: day.toLocaleDateString('de-DE', { weekday: 'short' }),
        date: _formatDate(day),
        isoDate: key,
        isToday: key === todayKey,
        events: byKey.get(key) || [],
      };
    });
  }

  function findNextEventAfter(referenceIsoDate) {
    var events = (((_getData().webuntisCenter || {}).events) || [])
      .filter(function (e) { return e.startsAt; })
      .filter(function (e) { return e.startsAt.slice(0, 10) > referenceIsoDate; })
      .sort(function (a, b) { return new Date(a.startsAt) - new Date(b.startsAt); });
    return events[0] || null;
  }

  // ── Event data filter ────────────────────────────────────────────────────────

  function getWebUntisEvents() {
    var center = _getData().webuntisCenter || {};
    var referenceDate = new Date((center.currentDate || new Date().toISOString().slice(0, 10)) + 'T00:00:00');
    var events = (center.events || []).filter(function (e) { return e.startsAt; });

    if (!events.length) return [];

    if (_state.webuntisView === 'day') {
      return events.filter(function (e) { return _isSameDay(new Date(e.startsAt), referenceDate); });
    }

    var weekStart = getWeekAnchorDate(center.currentDate || new Date().toISOString().slice(0, 10), _state.webuntisView);
    var weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 7);

    return events.filter(function (e) {
      var startsAt = new Date(e.startsAt);
      return startsAt >= weekStart && startsAt < weekEnd;
    });
  }

  // ── Render functions ─────────────────────────────────────────────────────────

  function renderPickerItem(entity, options) {
    options = options || {};
    var active = options.active || false;
    var showFavorite = options.showFavorite !== false;
    var compact = options.compact || false;
    return '<article class="picker-item ' + (active ? 'active' : '') + ' ' + (compact ? 'compact' : '') + '">'
      + '<button class="picker-item-main" type="button" data-picker-select="' + entity.id + '">'
      + '<span class="picker-item-icon">' + pickerIcon(entity.type) + '</span>'
      + '<span class="picker-item-copy">'
      + '<strong>' + entity.label + '</strong>'
      + (entity.detail ? '<span>' + entity.detail + '</span>' : '')
      + '</span>'
      + '</button>'
      + (showFavorite
        ? '<button class="picker-star ' + (_state.favorites.indexOf(entity.id) !== -1 ? 'active' : '') + '" type="button" data-picker-favorite="' + entity.id + '" aria-label="Favorit umschalten">★</button>'
        : '')
      + '</article>';
  }

  function renderEmptyWeekColumn(column, hasAnyWeekEvents) {
    if (hasAnyWeekEvents) {
      return '<div class="webuntis-week-empty">Kein iCal-Eintrag fuer diesen Tag</div>';
    }
    var nextEvent = findNextEventAfter(column.isoDate);
    if (nextEvent) {
      return '<div class="webuntis-week-empty">Im iCal keine Termine. Naechster Eintrag am ' + _formatDate(new Date(nextEvent.startsAt)) + '.</div>';
    }
    return '<div class="webuntis-week-empty">Im iCal sind fuer diese Woche gerade keine Termine vorhanden.</div>';
  }

  function renderDayEvent(event) {
    var timingClass = getEventTimingClass(event);
    return '<article class="webuntis-event ' + timingClass + ' ' + (isCancelledEvent(event) ? 'is-cancelled' : '') + '">'
      + '<div class="webuntis-event-time">' + event.time + '</div>'
      + '<div>'
      + '<div class="webuntis-event-head">'
      + '<strong>' + event.title + '</strong>'
      + '<span class="meta-tag ' + eventStateTagClass(event) + '">' + eventStateLabel(event) + '</span>'
      + '</div>'
      + '<p class="webuntis-event-copy">' + compactEventDetail(event) + '</p>'
      + '<div class="meta-row">'
      + '<span class="meta-tag">' + event.category + '</span>'
      + (event.location ? '<span class="meta-tag">' + event.location + '</span>' : '')
      + (event.description ? '<span class="meta-tag">' + event.description + '</span>' : '')
      + '</div>'
      + '</div>'
      + '</article>';
  }

  function renderWeekEvent(event) {
    var timingClass = getEventTimingClass(event);
    return '<article class="webuntis-week-event ' + timingClass + ' ' + (isCancelledEvent(event) ? 'is-cancelled' : '') + '">'
      + '<div class="webuntis-week-time">' + event.time.replace(' - ', '–') + '</div>'
      + '<div class="webuntis-week-copy">'
      + '<div class="webuntis-week-head">'
      + '<strong>' + event.title + '</strong>'
      + '<span class="meta-tag ' + eventStateTagClass(event) + '">' + eventStateLabel(event) + '</span>'
      + '</div>'
      + (event.location ? '<div class="webuntis-week-meta">' + event.location + '</div>' : '')
      + (event.description ? '<div class="webuntis-week-meta">' + event.description + '</div>' : '')
      + '</div>'
      + '</article>';
  }

  function renderAgendaGroup(group) {
    return '<section class="webuntis-agenda-group">'
      + '<div class="webuntis-agenda-label">'
      + '<span>' + group.label + '</span>'
      + '<span>' + (group.events.length ? group.events.length + ' Termine' : 'frei') + '</span>'
      + '</div>'
      + '<div class="webuntis-agenda-items">'
      + (group.events.length
        ? group.events.map(renderWeekEvent).join('')
        : '<div class="webuntis-week-empty">Keine Termine</div>')
      + '</div>'
      + '</section>';
  }

  function renderAgendaGroups(groups, label) {
    return '<div class="webuntis-agenda">'
      + '<div class="webuntis-agenda-head">'
      + '<strong>' + label + '</strong>'
      + '<span>' + groups.reduce(function (sum, g) { return sum + g.events.length; }, 0) + ' Eintraege</span>'
      + '</div>'
      + groups.map(renderAgendaGroup).join('')
      + '</div>';
  }

  function renderDayGroup(group) {
    return '<section class="webuntis-day-group">'
      + '<div class="webuntis-day-label">'
      + '<span>' + group.label + '</span>'
      + '<span>' + group.events.length + ' Eintraege</span>'
      + '</div>'
      + group.events.map(renderDayEvent).join('')
      + '</section>';
  }

  function renderWeekSchedule(events, center) {
    var columns = buildWeekColumns(events, getWeekAnchorDate(center.currentDate, _state.webuntisView));
    var hasAnyWeekEvents = columns.some(function (c) { return c.events.length > 0; });
    var nextFutureEvent = findNextEventAfter((columns[columns.length - 1] || {}).isoDate || center.currentDate);
    var totalCount = columns.reduce(function (sum, c) { return sum + c.events.length; }, 0);
    var countLabel = hasAnyWeekEvents
      ? totalCount + ' Eintraege'
      : (nextFutureEvent
        ? 'Naechster bekannter Termin: ' + _formatDate(new Date(nextFutureEvent.startsAt))
        : 'keine Eintraege im iCal');
    return '<div class="webuntis-week-board">'
      + '<div class="webuntis-agenda-head">'
      + '<strong>' + getWebUntisRangeLabel(center) + '</strong>'
      + '<span>' + countLabel + '</span>'
      + '</div>'
      + '<div class="webuntis-week-columns">'
      + columns.map(function (column) {
        return '<section class="webuntis-week-column' + (column.isToday ? ' is-today' : '') + '">'
          + '<div class="webuntis-week-column-head">'
          + '<div class="webuntis-week-column-head-row">'
          + '<span class="webuntis-weekday' + (column.isToday ? ' is-today' : '') + '">' + column.weekday + '</span>'
          + (column.isToday ? '<span class="webuntis-today-chip" aria-label="Heute">Heute</span>' : '')
          + '</div>'
          + '<strong class="webuntis-week-column-date">' + column.date + '</strong>'
          + '</div>'
          + '<div class="webuntis-week-column-items">'
          + (column.events.length ? column.events.map(renderWeekEvent).join('') : renderEmptyWeekColumn(column, hasAnyWeekEvents))
          + '</div>'
          + '</section>';
      }).join('')
      + '</div>'
      + '</div>';
  }

  function renderWebUntisSchedule() {
    if (!_state || !_elements) return;
    var events = getWebUntisEvents();
    var center = _getData().webuntisCenter || {};

    if (!events.length) {
      if (_state.webuntisView === 'day') {
        _elements.scheduleList.innerHTML = '<div class="empty-state">Heute liegen im WebUntis-iCal keine Termine vor.</div>';
        return;
      }
      _elements.scheduleList.innerHTML = renderWeekSchedule([], center);
      return;
    }

    if (_state.webuntisView !== 'day') {
      _elements.scheduleList.innerHTML = renderWeekSchedule(events, center);
      return;
    }

    var grouped = groupEventsByDay(events);
    _elements.scheduleList.innerHTML = renderAgendaGroups(grouped, 'Heute');
  }

  function renderWebUntisControls() {
    if (!_state || !_elements) return;
    var center = _getData().webuntisCenter || {};
    var buttons = [
      { id: 'day', label: 'Heute' },
      { id: 'week', label: center.currentWeekLabel || 'Diese Woche' },
      { id: 'next-week', label: nextWeekLabel(center.currentDate || new Date().toISOString().slice(0, 10)) },
    ];

    _elements.webuntisViewSwitch.innerHTML = buttons.map(function (btn) {
      return '<button class="segment-button ' + (_state.webuntisView === btn.id ? 'active' : '') + '" type="button" data-webuntis-view="' + btn.id + '">'
        + btn.label
        + '</button>';
    }).join('');

    _elements.webuntisViewSwitch.querySelectorAll('[data-webuntis-view]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        _state.webuntisView = btn.dataset.webuntisView;
        renderWebUntisControls();
        renderWebUntisSchedule();
      });
    });

    _bindExternalLink(_elements.webuntisOpenToday, center.todayUrl, 'Heute in WebUntis');
    _bindExternalLink(_elements.webuntisOpenBase, center.startUrl || center.todayUrl, 'WebUntis oeffnen');

    if (_elements.webuntisActivePlan) _elements.webuntisActivePlan.textContent = 'Mein Stundenplan';
    if (_elements.webuntisDetail) _elements.webuntisDetail.textContent =
      'Persoenlicher Plan ueber WebUntis-iCal. Vergangene, laufende und kommende Stunden werden hier markiert. Ausfaelle erscheinen nur, wenn WebUntis sie im iCal mitsendet.';
    if (_elements.webuntisRangeLabel) _elements.webuntisRangeLabel.textContent = getWebUntisRangeLabel(center);
    if (_elements.webuntisPlanStrip) {
      _elements.webuntisPlanStrip.hidden = true;
      _elements.webuntisPlanStrip.innerHTML = '';
    }
  }

  function renderWebUntisWatchlist() {
    if (!_elements) return;
    var finder = ((_getData().webuntisCenter || {}).finder) || { watchlist: [] };
    _elements.webuntisWatchlist.innerHTML = (finder.watchlist || []).length
      ? finder.watchlist.map(function (item) {
          return '<article class="priority-item">'
            + '<div class="priority-top">'
            + '<strong>' + item.title + '</strong>'
            + '<span class="meta-tag ' + watchStatusClass(item.status) + '">' + watchStatusLabel(item.status) + '</span>'
            + '</div>'
            + '<p class="priority-copy">' + item.detail + '</p>'
            + '</article>';
        }).join('')
      : '<div class="empty-state">Noch keine geoeffneten Plaene im Radar.</div>';
  }

  function renderWebUntisPlanStrip() {
    if (!_elements) return;
    var center = _getData().webuntisCenter || {};
    var plans = getPinnedPlans(center);
    var visiblePlans = plans.filter(function (p) { return !(p.id === 'personal' && plans.length === 1); });

    _elements.webuntisPlanStrip.hidden = visiblePlans.length === 0;
    _elements.webuntisPlanStrip.innerHTML = visiblePlans.length
      ? visiblePlans.map(function (plan) {
          return '<button class="plan-chip ' + (isPlanChipActive(center, plan) ? 'active' : '') + '" type="button" data-plan-chip="' + plan.id + '">'
            + '<span class="plan-chip-type">' + shortcutTypeLabel(plan.type) + '</span>'
            + '<strong>' + plan.label + '</strong>'
            + '</button>';
        }).join('')
      : '<div class="empty-state">Noch keine Plaene gespeichert.</div>';

    _elements.webuntisPlanStrip.querySelectorAll('[data-plan-chip]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        selectPlanById(_getData().webuntisCenter || {}, btn.dataset.planChip);
      });
    });
  }

  function renderWebUntisPicker() {
    if (!_state || !_elements) return;
    var center = _getData().webuntisCenter || {};
    var finder = center.finder || {
      status: 'warning',
      note: 'Planfinder ist vorbereitet.',
      availableTypes: [
        { id: 'teacher', label: 'Mein Plan' },
        { id: 'class', label: 'Klasse' },
        { id: 'room', label: 'Raum' },
      ],
      entities: [],
      watchlist: [],
      searchPlaceholder: 'Klasse oder Raum aus deinem Plan suchen',
    };
    var query = (_state.webuntisPickerSearch || '').trim().toLowerCase();
    var currentPlan = {
      id: 'personal',
      type: 'teacher',
      label: center.activePlan || 'Mein Stundenplan',
      detail: center.detail || center.note,
      favorite: _state.favorites.indexOf('personal') !== -1,
    };
    var searchResults = getGlobalPickerResults(center, query);
    var categories = (finder.availableTypes || center.planTypes || []).map(function (cat) {
      return Object.assign({}, cat, { count: getPickerEntities(center, cat.id, query).length });
    });
    var activePlan = getActivePlan(center);

    _elements.webuntisPickerOverlay.hidden = !_state.webuntisPickerOpen;
    if (_elements.webuntisPickerSearch) {
      _elements.webuntisPickerSearch.value = _state.webuntisPickerSearch;
      _elements.webuntisPickerSearch.placeholder = finder.searchPlaceholder || 'Stundenplan suchen';
    }
    if (_elements.webuntisPickerEdit) {
      _elements.webuntisPickerEdit.textContent = activePlan.id === 'personal' ? 'Fertig' : 'Zuruecksetzen';
    }

    var favorites = getFavoriteEntities(center, query);
    if (_elements.webuntisPickerCurrent) {
      _elements.webuntisPickerCurrent.innerHTML = renderPickerItem(currentPlan, {
        active: !_state.activeFinderEntityId && _state.activeShortcutId === 'personal',
        compact: false,
        showFavorite: true,
        action: 'select',
      });
    }
    if (_elements.webuntisPickerResultsSection) _elements.webuntisPickerResultsSection.hidden = !query;
    if (_elements.webuntisPickerResultsLabel) {
      _elements.webuntisPickerResultsLabel.textContent = query ? 'Treffer fuer "' + _state.webuntisPickerSearch + '"' : 'Suche';
    }
    if (_elements.webuntisPickerResults) {
      _elements.webuntisPickerResults.innerHTML = query
        ? (searchResults.length
          ? searchResults.map(function (e) { return renderPickerItem(e, { active: isEntityActive(center, e), showFavorite: e.id !== 'personal' }); }).join('')
          : '<div class="empty-state">Keine passenden Plaene gefunden.</div>')
        : '';
    }
    if (_elements.webuntisPickerFavorites) {
      _elements.webuntisPickerFavorites.innerHTML = favorites.length
        ? favorites.map(function (e) { return renderPickerItem(e, { active: isEntityActive(center, e), showFavorite: true, action: 'select' }); }).join('')
        : '<div class="empty-state">Noch keine Favoriten gespeichert.</div>';
    }
    if (_elements.webuntisPickerCategories) {
      _elements.webuntisPickerCategories.innerHTML = categories.map(function (cat) {
        return '<button class="picker-category-item" type="button" data-picker-category="' + cat.id + '">'
          + '<span>' + cat.label + '</span>'
          + '<span>' + cat.count + '</span>'
          + '</button>';
      }).join('');
      _elements.webuntisPickerCategories.querySelectorAll('[data-picker-category]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          _state.webuntisPickerCategory = btn.dataset.pickerCategory;
          renderWebUntisPicker();
        });
      });
    }

    var showCategory = Boolean(_state.webuntisPickerCategory);
    if (_elements.webuntisPickerHome) _elements.webuntisPickerHome.hidden = showCategory;
    if (_elements.webuntisPickerCategoryView) _elements.webuntisPickerCategoryView.hidden = !showCategory;

    if (showCategory) {
      var category = categories.find(function (c) { return c.id === _state.webuntisPickerCategory; });
      var categoryItems = getPickerEntities(center, _state.webuntisPickerCategory, query);
      if (_elements.webuntisPickerCategoryKicker) _elements.webuntisPickerCategoryKicker.textContent = 'Stundenplaene';
      if (_elements.webuntisPickerCategoryTitle) _elements.webuntisPickerCategoryTitle.textContent = (category && category.label) ? category.label : 'Auswahl';
      if (_elements.webuntisPickerCategoryNote) {
        _elements.webuntisPickerCategoryNote.textContent = _state.webuntisPickerCategory === 'teacher'
          ? 'Kolleg:innen-Listen folgen erst mit echter WebUntis-Session. Aktuell bleibt dein persoenlicher Plan die stabile Basis.'
          : 'Auswaehlen wechselt die Anzeige im Cockpit. Klassen und Raeume stammen derzeit aus deinem persoenlichen Plan.';
      }
      if (_elements.webuntisPickerCategoryResults) {
        _elements.webuntisPickerCategoryResults.innerHTML = categoryItems.length
          ? categoryItems.map(function (e) {
              return renderPickerItem(e, { active: isEntityActive(center, e), showFavorite: e.id !== 'personal', action: 'select' });
            }).join('')
          : '<div class="empty-state">In dieser Kategorie gibt es aktuell keine weiteren Live-Eintraege.</div>';
      }
    }

    bindPickerActions(center);
  }

  // ── Public API ───────────────────────────────────────────────────────────────

  /**
   * Initialize the WebUntis module with shared state, DOM element references,
   * and utility callbacks from the parent app.js IIFE.
   *
   * @param {object} state    - The shared `state` object from app.js (by reference)
   * @param {object} elements - The shared `elements` object from app.js (by reference)
   * @param {object} cbs      - Utility callbacks: {
   *   getData, renderAll, formatDate, formatTime, weekdayLabel,
   *   isSameDay, startOfWeek, isoWeekNumber, bindExternalLink
   * }
   */
  function init(state, elements, cbs) {
    _state     = state;
    _elements  = elements;
    _callbacks = cbs || {};
  }

  window.LehrerWebUntis = {
    init: init,
    // Core render functions
    renderWebUntisControls:   renderWebUntisControls,
    renderWebUntisPicker:     renderWebUntisPicker,
    renderWebUntisWatchlist:  renderWebUntisWatchlist,
    renderWebUntisPlanStrip:  renderWebUntisPlanStrip,
    renderWebUntisSchedule:   renderWebUntisSchedule,
    renderWeekSchedule:       renderWeekSchedule,
    renderAgendaGroups:       renderAgendaGroups,
    renderAgendaGroup:        renderAgendaGroup,
    renderDayGroup:           renderDayGroup,
    renderDayEvent:           renderDayEvent,
    renderWeekEvent:          renderWeekEvent,
    // Data helpers
    getWebUntisEvents:        getWebUntisEvents,
    getWebUntisRangeLabel:    getWebUntisRangeLabel,
    getWeekAnchorDate:        getWeekAnchorDate,
    nextWeekLabel:            nextWeekLabel,
    groupEventsByDay:         groupEventsByDay,
    buildWeekColumns:         buildWeekColumns,
    findNextEventAfter:       findNextEventAfter,
    extractClassLabels:       extractClassLabels,
    renderEmptyWeekColumn:    renderEmptyWeekColumn,
    // Picker helpers
    getActivePlan:            getActivePlan,
    getPinnedPlans:           getPinnedPlans,
    isEntityActive:           isEntityActive,
    selectPlanById:           selectPlanById,
    closePicker:              closePicker,
    isPlanChipActive:         isPlanChipActive,
    shortcutTypeLabel:        shortcutTypeLabel,
    watchStatusClass:         watchStatusClass,
    watchStatusLabel:         watchStatusLabel,
    // Event state helpers
    getEventTimingClass:      getEventTimingClass,
    isEventCurrent:           isEventCurrent,
    isCancelledEvent:         isCancelledEvent,
    eventStateLabel:          eventStateLabel,
    eventStateTagClass:       eventStateTagClass,
    compactEventDetail:       compactEventDetail,
    // State management
    normalizeLocalWebUntisState: normalizeLocalWebUntisState,
    loadSavedShortcuts:       loadSavedShortcuts,
    loadWebUntisFavorites:    loadWebUntisFavorites,
  };

})();
