/**
 * LehrerCalendar — „Alle“ unter Termine: alle Quellen in einem Kalender.
 *
 * Monat (Überblick, bis zu fünf Einträge pro Tag), Woche (Zeitleiste mit dem
 * Stundenplan im Hintergrund) und Liste (Tag für Tag, am Handy Standard).
 * Quellen: Orgaplan, Klassenarbeiten der eigenen Klassen, Schultermine,
 * itslearning; Ferien und Feiertage als Hintergrund. Alles, was das Cockpit
 * ohnehin geladen hat – nichts geht dafür an den Server.
 *
 * Exports (window.LehrerCalendar): init, render
 */
var LehrerCalendar = (function () {
  'use strict';

  var SOURCES = [
    { id: 'org', label: 'Orgaplan', tab: 'orgaplan' },
    { id: 'ka', label: 'Klassenarbeiten', tab: 'klassenarbeitsplan' },
    { id: 'sch', label: 'Schultermine', tab: 'termine' },
    { id: 'its', label: 'itslearning', tab: 'itslearning' },
    { id: 'lessons', label: 'Stundenplan', tab: '' },
  ];
  var MAX_PER_DAY = 5;
  var HOUR_PX = 44;
  var VIEW_KEY = 'lc.calendarView';
  var OFF_KEY = 'lc.calendarOff';
  var WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

  var _h = null;           // helpers from app.js
  var _root = null;
  var _view = null;        // month | week | list
  var _anchor = null;      // first day of the shown range
  var _selected = null;    // ISO day shown below the month grid
  var _off = {};           // hidden sources
  var _events = [];
  var _byId = {};

  // ── Helpers ────────────────────────────────────────────────────────────────
  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function iso(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function fromIso(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ''));
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }
  function addDays(d, n) { var x = new Date(d.getFullYear(), d.getMonth(), d.getDate()); x.setDate(x.getDate() + n); return x; }
  function monday(d) { return addDays(d, -((d.getDay() + 6) % 7)); }
  function isoWeek(d) {
    var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
    return Math.ceil(((t - new Date(Date.UTC(t.getUTCFullYear(), 0, 1))) / 86400000 + 1) / 7);
  }
  function hhmm(d) { return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); }
  function todayIso() { return iso(new Date()); }
  function store(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* ignore */ } }
  function load(key) { try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) { return null; } }
  function narrow() { return window.matchMedia && window.matchMedia('(max-width: 640px)').matches; }
  function breakOn(d) { return window.LehrerSchoolYear ? window.LehrerSchoolYear.breakOn(d) : null; }

  // ── Events from all sources ────────────────────────────────────────────────
  /** {id, src, title, sub, day, endDay, allDay, time, endTime, startMs, endMs, raw} */
  function when(start, end, allDay) {
    var dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(String(start || ''));
    var s = dateOnly ? fromIso(start) : new Date(start);
    if (!s || isNaN(s.getTime())) return null;
    var e = end ? (/^\d{4}-\d{2}-\d{2}$/.test(String(end)) ? fromIso(end) : new Date(end)) : null;
    if (e && isNaN(e.getTime())) e = null;
    var whole = !!allDay || dateOnly;
    var endDay = e ? iso(e) : iso(s);
    if (endDay < iso(s)) endDay = iso(s);
    return {
      day: iso(s), endDay: endDay, allDay: whole,
      time: whole ? '' : hhmm(s), endTime: !whole && e && iso(e) === iso(s) ? hhmm(e) : '',
      startMs: s.getTime(), endMs: e ? e.getTime() : s.getTime() + 3600000,
    };
  }

  function collect() {
    var data = _h.getData() || {};
    var list = [];
    function push(src, key, title, sub, w, raw) {
      if (!w || !title) return;
      var ev = { id: src + ':' + key, src: src, title: String(title), sub: sub || '', raw: raw || {} };
      Object.keys(w).forEach(function (k) { ev[k] = w[k]; });
      list.push(ev);
    }

    var orgaplan = (data.planDigest || {}).orgaplan || {};
    var seenOrg = {};
    (orgaplan.today_entries || []).concat(orgaplan.upcoming || []).forEach(function (entry) {
      if (!entry || !entry.isoDate) return;
      (_h.orgaplanParts(entry) || []).forEach(function (part, i) {
        var key = entry.isoDate + '|' + part.text;
        if (!part.text || seenOrg[key]) return;
        seenOrg[key] = true;
        push('org', key + i, part.text, part.tag && part.tag !== 'Alle' ? part.tag : '', when(entry.isoDate, null, true), entry);
      });
    });

    var classwork = (data.planDigest || {}).classwork || {};
    var all = (classwork.classes || []).filter(Boolean);
    var mine = _h.selectedClasses ? _h.selectedClasses(all, classwork.defaultClass || '') : all;
    var filtered = mine.length && mine.length < all.length;
    (classwork.entries || []).forEach(function (entry, i) {
      if (!entry.isoDate || (filtered && mine.indexOf(entry.classLabel) === -1)) return;
      var short = { 'Klassenarbeit': 'KA', 'LEK': 'LEK', 'Klausur': 'Klausur', 'Test': 'Test', 'VERA': 'VERA' }[entry.kind] || '';
      var title = String(entry.title || entry.summary || '');
      var prefix = entry.classLabel + (short && !new RegExp('\\b' + short + '\\b', 'i').test(title) ? ' ' + short : '');
      push('ka', i, prefix + ': ' + title, entry.kind === 'Termin' ? 'Termin' : '', when(entry.isoDate, null, true), entry);
    });

    ((data.schoolCalendar || {}).events || []).forEach(function (event, i) {
      push('sch', event.uid || i, event.title, event.location || '', when(event.start, event.end, event.all_day), event);
    });

    ((data.itslearningCalendar || {}).events || []).forEach(function (event, i) {
      push('its', event.id || i, (event.kind === 'todo' ? 'Abgabe: ' : '') + event.title, event.location || '',
           when(event.start, event.end, event.allDay), event);
    });

    list.sort(function (a, b) {
      return a.day.localeCompare(b.day)
        || (b.endDay > b.day) - (a.endDay > a.day)          // multi-day first (bars)
        || (b.allDay - a.allDay)
        || a.startMs - b.startMs
        || order(a.src) - order(b.src);
    });
    _events = list;
    _byId = {};
    list.forEach(function (ev) { _byId[ev.id] = ev; });
  }

  function order(src) { for (var i = 0; i < SOURCES.length; i++) if (SOURCES[i].id === src) return i; return 9; }
  function label(src) { for (var i = 0; i < SOURCES.length; i++) if (SOURCES[i].id === src) return SOURCES[i].label; return ''; }

  /** Shown in the week's time grid (else in the all-day row): one day, between 6 and 20 o'clock. */
  function inGrid(ev) {
    if (ev.allDay || ev.endDay !== ev.day) return false;
    var hour = new Date(ev.startMs).getHours();
    return hour >= 6 && hour < 20;
  }

  function eventsOn(dayIso) {
    return _events.filter(function (ev) { return !_off[ev.src] && ev.day <= dayIso && dayIso <= ev.endDay; });
  }

  /** Lessons of the week (Stundenplan), double lessons merged. */
  function lessonsBetween(fromIso, toIso) {
    var data = _h.getData() || {};
    var raw = ((data.webuntisCenter || {}).events || []).filter(function (e) {
      var d = String(e.startsAt || '').slice(0, 10);
      return d >= fromIso && d <= toIso;
    }).sort(function (a, b) { return String(a.startsAt).localeCompare(String(b.startsAt)); });
    var out = [];
    raw.forEach(function (e) {
      var prev = out[out.length - 1];
      var start = new Date(e.startsAt);
      if (prev && prev.title === e.title && prev.location === e.location && !!prev.cancelled === !!e.cancelled
          && start - new Date(prev.endsAt) <= 10 * 60000 && start >= new Date(prev.endsAt)) {
        prev.endsAt = e.endsAt;
        return;
      }
      out.push({ title: e.title, location: e.location, startsAt: e.startsAt, endsAt: e.endsAt, cancelled: e.cancelled, src: e });
    });
    return out;
  }

  // ── Rendering ──────────────────────────────────────────────────────────────
  function render() {
    if (!_root || !_h) return;
    collect();
    if (!_view) _view = load(VIEW_KEY) || (narrow() ? 'list' : 'month');
    if (!_anchor) goToday(false);
    var body = _view === 'week' ? weekHtml() : _view === 'list' ? listHtml() : monthHtml();
    _root.innerHTML = headHtml() + chipsHtml() + body;
    if (_view === 'week') scrollWeek();
  }

  function goToday(rerender) {
    var now = new Date();
    _selected = iso(now);
    _anchor = _view === 'month' ? new Date(now.getFullYear(), now.getMonth(), 1) : monday(now);
    if (rerender) render();
  }

  function shift(step) {
    if (_view === 'month') {
      _anchor = new Date(_anchor.getFullYear(), _anchor.getMonth() + step, 1);
      var t = new Date();
      _selected = t.getFullYear() === _anchor.getFullYear() && t.getMonth() === _anchor.getMonth() ? iso(t) : iso(_anchor);
    } else {
      _anchor = addDays(_anchor, step * (_view === 'week' ? 7 : 28));
    }
    render();
  }

  function setView(view) {
    if (view === _view) return;
    var ref = fromIso(_selected) || _anchor || new Date();
    _view = view;
    store(VIEW_KEY, view);
    _anchor = view === 'month' ? new Date(ref.getFullYear(), ref.getMonth(), 1) : monday(ref);
    render();
  }

  function title() {
    if (_view === 'month') return _anchor.toLocaleDateString('de-DE', { month: 'long', year: 'numeric' });
    var end = addDays(_anchor, _view === 'week' ? 6 : 27);
    var sameMonth = end.getMonth() === _anchor.getMonth();
    var range = _anchor.getDate() + '.' + (sameMonth ? '' : ' ' + _anchor.toLocaleDateString('de-DE', { month: 'short' }))
      + '–' + end.getDate() + '. ' + end.toLocaleDateString('de-DE', { month: 'long', year: 'numeric' });
    return (_view === 'week' ? 'KW ' + isoWeek(_anchor) + ' · ' : '') + range;
  }

  function headHtml() {
    var views = [['month', 'Monat'], ['week', 'Woche'], ['list', 'Liste']];
    return '<div class="cal-head">'
      + '<div class="cal-nav">'
      + '<button class="cal-icon-btn" type="button" data-cal="prev" aria-label="Zurück">‹</button>'
      + '<h3 class="cal-title">' + esc(title()) + '</h3>'
      + '<button class="cal-icon-btn" type="button" data-cal="next" aria-label="Weiter">›</button>'
      + '<button class="cal-today-btn" type="button" data-cal="today">Heute</button>'
      + '</div>'
      + '<div class="cal-views" role="tablist" aria-label="Ansicht">'
      + views.map(function (v) {
        return '<button type="button" role="tab" aria-selected="' + (v[0] === _view) + '" class="' + (v[0] === _view ? 'is-active' : '') + '" data-cal-view="' + v[0] + '">' + v[1] + '</button>';
      }).join('')
      + '</div></div>';
  }

  function chipsHtml() {
    var have = {};
    _events.forEach(function (ev) { have[ev.src] = true; });
    if (_view === 'week' && ((_h.getData() || {}).webuntisCenter || {}).events) have.lessons = true;
    var chips = SOURCES.filter(function (s) { return have[s.id]; }).map(function (s) {
      return '<button type="button" class="cal-chip src-' + s.id + (_off[s.id] ? ' is-off' : '') + '" data-cal-src="' + s.id + '" aria-pressed="' + !_off[s.id] + '">'
        + '<span class="cal-dot" aria-hidden="true"></span>' + esc(s.label) + '</button>';
    });
    if (!chips.length) {
      return '<div class="empty-state">Noch keine Termine. Verbinde Orgaplan, Klassenarbeitsplan, Schultermine oder itslearning – '
        + 'dann erscheinen hier alle zusammen.</div>';
    }
    return '<div class="cal-chips">' + chips.join('') + '</div>';
  }

  function evButton(ev, dayIso, extraClass) {
    var multi = ev.endDay > ev.day;
    var cls = 'cal-ev src-' + ev.src + (multi ? ' is-multi' : '') + (multi && dayIso > ev.day ? ' is-cont' : '')
      + (multi && dayIso < ev.endDay ? ' is-goes-on' : '') + (extraClass || '');
    var showText = !multi || dayIso === ev.day || (fromIso(dayIso).getDay() === 1);
    return '<button type="button" class="' + cls + '" data-cal-ev="' + esc(ev.id) + '" title="' + esc((ev.time ? ev.time + ' ' : '') + ev.title) + '">'
      + (showText ? (ev.time ? '<span class="cal-ev-time">' + esc(ev.time) + '</span> ' : '') + esc(ev.title) : '&nbsp;')
      + '</button>';
  }

  // Monat
  function monthHtml() {
    var first = _anchor;
    var start = monday(first);
    var last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
    var end = addDays(monday(last), 6);
    var today = todayIso();
    var html = '<div class="cal-month"><div class="cal-month-head"><span class="cal-kw-head">KW</span>'
      + WEEKDAYS.map(function (d, i) { return '<span class="' + (i > 4 ? 'is-weekend' : '') + '">' + d + '</span>'; }).join('') + '</div>';
    for (var w = start; w <= end; w = addDays(w, 7)) {
      html += '<div class="cal-month-row"><span class="cal-kw">' + isoWeek(w) + '</span>';
      for (var i = 0; i < 7; i++) {
        var d = addDays(w, i);
        var dIso = iso(d);
        var evs = eventsOn(dIso);
        var br = breakOn(d);
        var cls = 'cal-day' + (i > 4 ? ' is-weekend' : '') + (d.getMonth() !== first.getMonth() ? ' is-outside' : '')
          + (dIso === today ? ' is-today' : '') + (dIso === _selected ? ' is-selected' : '') + (br ? ' is-break' : '');
        html += '<div class="' + cls + '" data-cal-day="' + dIso + '">'
          + '<div class="cal-day-top"><span class="cal-day-num">' + d.getDate() + '</span>'
          + (br && i < 5 ? '<span class="cal-break-label" title="' + esc(br.name) + '">' + esc(br.name) + '</span>' : '') + '</div>'
          + evs.slice(0, MAX_PER_DAY).map(function (ev) { return evButton(ev, dIso); }).join('')
          + (evs.length > MAX_PER_DAY ? '<button type="button" class="cal-more" data-cal-day-more="' + dIso + '">+' + (evs.length - MAX_PER_DAY) + ' weitere</button>' : '')
          + '</div>';
      }
      html += '</div>';
    }
    return html + '</div>' + dayPanelHtml(_selected);
  }

  function dayPanelHtml(dayIso) {
    var d = fromIso(dayIso);
    if (!d) return '';
    var evs = eventsOn(dayIso);
    var br = breakOn(d);
    return '<section class="cal-daypanel" aria-label="Termine am ausgewählten Tag">'
      + '<h4 class="cal-daypanel-title">' + esc(d.toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long' }))
      + (br ? ' <span class="cal-break-tag">' + esc(br.name) + '</span>' : '') + '</h4>'
      + (evs.length ? evs.map(rowHtml).join('') : '<p class="cal-empty">Keine Termine.</p>')
      + '</section>';
  }

  function rowHtml(ev) {
    var whenText = ev.time ? ev.time + (ev.endTime ? '–' + ev.endTime : '') : (ev.endDay > ev.day ? 'mehrtägig' : 'ganztägig');
    return '<button type="button" class="cal-row src-' + ev.src + '" data-cal-ev="' + esc(ev.id) + '">'
      + '<span class="cal-dot" aria-hidden="true"></span>'
      + '<span class="cal-row-when">' + esc(whenText) + '</span>'
      + '<span class="cal-row-title">' + esc(ev.title) + (ev.sub ? ' <span class="cal-row-sub">' + esc(ev.sub) + '</span>' : '') + '</span>'
      + '<span class="cal-row-src">' + esc(label(ev.src)) + '</span>'
      + '</button>';
  }

  // Woche
  function weekHtml() {
    var days = [];
    for (var i = 0; i < 7; i++) days.push(addDays(_anchor, i));
    var fromD = iso(days[0]), toD = iso(days[6]);
    var today = todayIso();
    var lessons = _off.lessons ? [] : lessonsBetween(fromD, toD);
    var timed = _events.filter(function (ev) { return !_off[ev.src] && inGrid(ev) && ev.day >= fromD && ev.day <= toD; });

    // visible hours: 7–17, widened to fit lessons and events
    var minH = 7, maxH = 17;
    timed.concat(lessons.map(function (l) { return { startMs: new Date(l.startsAt).getTime(), endMs: new Date(l.endsAt).getTime() }; }))
      .forEach(function (x) {
        var s = new Date(x.startMs), e = new Date(x.endMs);
        minH = Math.min(minH, s.getHours());
        maxH = Math.max(maxH, e.getHours() + (e.getMinutes() ? 1 : 0));
      });
    minH = Math.max(0, minH); maxH = Math.min(24, Math.max(maxH, minH + 1));
    var height = (maxH - minH) * HOUR_PX;

    var head = '<div class="cal-week-head"><span></span>' + days.map(function (d, i) {
      var br = breakOn(d);
      return '<button type="button" class="cal-week-day' + (iso(d) === today ? ' is-today' : '') + (i > 4 ? ' is-weekend' : '') + (br ? ' is-break' : '') + '" data-cal-day-more="' + iso(d) + '">'
        + '<span class="cal-week-dow">' + WEEKDAYS[i] + '</span><span class="cal-week-num">' + d.getDate() + '</span>'
        + (br && i < 5 ? '<span class="cal-break-label">' + esc(br.name) + '</span>' : '') + '</button>';
    }).join('') + '</div>';

    var allDayRow = '<div class="cal-week-allday"><span class="cal-week-axis">ganztägig</span>' + days.map(function (d, i) {
      var dIso = iso(d);
      var evs = eventsOn(dIso).filter(function (ev) { return !inGrid(ev); });
      return '<div class="cal-week-cell' + (i > 4 ? ' is-weekend' : '') + '">'
        + evs.slice(0, MAX_PER_DAY).map(function (ev) { return evButton(ev, dIso); }).join('')
        + (evs.length > MAX_PER_DAY ? '<button type="button" class="cal-more" data-cal-day-more="' + dIso + '">+' + (evs.length - MAX_PER_DAY) + ' weitere</button>' : '')
        + '</div>';
    }).join('') + '</div>';

    var axis = '<div class="cal-week-axis cal-week-hours" style="height:' + height + 'px">';
    for (var h = minH; h < maxH; h++) axis += '<span style="top:' + ((h - minH) * HOUR_PX) + 'px">' + String(h).padStart(2, '0') + ':00</span>';
    axis += '</div>';

    function top(ms) { var d = new Date(ms); return ((d.getHours() - minH) * 60 + d.getMinutes()) / 60 * HOUR_PX; }

    var cols = days.map(function (d, i) {
      var dIso = iso(d);
      var html = '';
      lessons.filter(function (l) { return l.startsAt.slice(0, 10) === dIso; }).forEach(function (l) {
        var s = new Date(l.startsAt).getTime(), e = new Date(l.endsAt).getTime();
        var p = _h.lessonParts ? _h.lessonParts(l.src) : { main: l.title, sub: '', room: l.location };
        html += '<div class="cal-lesson' + (l.cancelled ? ' is-cancelled' : '') + (p.duty ? ' is-duty' : '') + '" style="top:' + top(s) + 'px;height:' + Math.max(18, top(e) - top(s) - 2) + 'px"'
          + ' title="' + esc(hhmm(new Date(s)) + ' ' + p.main + (p.sub ? ' · ' + p.sub : '') + (p.room ? ' · ' + p.room : '') + (l.cancelled ? ' · entfällt' : '')) + '">'
          + '<strong>' + esc(p.main) + '</strong>' + (p.sub ? ' ' + esc(p.sub) : '') + (p.room ? '<span>' + esc(p.room) + '</span>' : '') + '</div>';
      });
      var mine = timed.filter(function (ev) { return ev.day === dIso; });
      lanes(mine).forEach(function (x) {
        var ev = x.ev;
        var t = top(ev.startMs);
        var bottom = ev.endDay === ev.day ? top(ev.endMs) : height;
        html += '<button type="button" class="cal-ev cal-ev-timed src-' + ev.src + '" data-cal-ev="' + esc(ev.id) + '"'
          + ' style="top:' + t + 'px;height:' + Math.max(20, bottom - t - 2) + 'px;left:calc(' + (x.lane / x.of * 100) + '% + 2px);width:calc(' + (100 / x.of) + '% - 4px)"'
          + ' title="' + esc(ev.time + ' ' + ev.title) + '"><span class="cal-ev-time">' + esc(ev.time) + '</span> ' + esc(ev.title) + '</button>';
      });
      if (dIso === today) {
        var now = new Date();
        var nowTop = top(now.getTime());
        if (nowTop >= 0 && nowTop <= height) html += '<span class="cal-now" style="top:' + nowTop + 'px" aria-hidden="true"></span>';
      }
      return '<div class="cal-week-col' + (i > 4 ? ' is-weekend' : '') + (dIso === today ? ' is-today' : '') + (breakOn(d) ? ' is-break' : '') + '" style="height:' + height + 'px">' + html + '</div>';
    }).join('');

    var lines = '';
    for (var k = 1; k < maxH - minH; k++) lines += '<span style="top:' + (k * HOUR_PX) + 'px"></span>';

    return '<div class="cal-week-scroll"><div class="cal-week">' + head + allDayRow
      + '<div class="cal-week-body">' + axis + '<div class="cal-week-grid"><div class="cal-week-lines" aria-hidden="true">' + lines + '</div>' + cols + '</div></div>'
      + '</div></div>'
      + (lessons.length || _off.lessons ? '' : '<p class="cal-hint">Den Stundenplan zeigt die Woche, sobald WebUntis verbunden ist.</p>');
  }

  /** Side-by-side columns for overlapping timed events. */
  function lanes(evs) {
    var out = [];
    var group = [];
    var groupEnd = -1;
    function flush() {
      var laneEnds = [];
      group.forEach(function (x) {
        var lane = laneEnds.findIndex(function (end) { return end <= x.ev.startMs; });
        if (lane === -1) { lane = laneEnds.length; laneEnds.push(0); }
        laneEnds[lane] = x.ev.endMs;
        x.lane = lane;
      });
      group.forEach(function (x) { x.of = laneEnds.length; out.push(x); });
      group = [];
    }
    evs.slice().sort(function (a, b) { return a.startMs - b.startMs; }).forEach(function (ev) {
      if (group.length && ev.startMs >= groupEnd) flush();
      group.push({ ev: ev });
      groupEnd = Math.max(groupEnd, ev.endMs);
    });
    if (group.length) flush();
    return out;
  }

  function scrollWeek() {
    var scroller = _root.querySelector('.cal-week-scroll');
    var today = _root.querySelector('.cal-week-col.is-today');
    if (scroller && today && scroller.scrollWidth > scroller.clientWidth) {
      scroller.scrollLeft = Math.max(0, today.offsetLeft - 60);
    }
  }

  // Liste
  function listHtml() {
    var html = '<div class="cal-list">';
    var any = false;
    var today = todayIso();
    for (var w = 0; w < 4; w++) {
      var weekStart = addDays(_anchor, w * 7);
      var dayBlocks = '';
      for (var i = 0; i < 7; i++) {
        var d = addDays(weekStart, i);
        var dIso = iso(d);
        if (dIso < today && _anchor <= new Date()) continue; // past days of the running week
        var evs = eventsOn(dIso);
        var br = breakOn(d);
        var startsBreak = br && (br.start === dIso || i === 0 || dIso === today);
        if (!evs.length && !startsBreak) continue;
        dayBlocks += '<div class="cal-list-day' + (dIso === today ? ' is-today' : '') + '">'
          + '<div class="cal-list-date"><strong>' + d.getDate() + '</strong><span>' + WEEKDAYS[i] + '</span></div>'
          + '<div class="cal-list-items">'
          + (startsBreak ? '<p class="cal-break-line">' + esc(br.name) + (br.end > br.start ? ' bis ' + esc(fromIso(br.end).toLocaleDateString('de-DE', { day: 'numeric', month: 'short' })) : '') + '</p>' : '')
          + evs.map(rowHtml).join('') + '</div></div>';
      }
      if (!dayBlocks) continue;
      any = true;
      var end = addDays(weekStart, 6);
      html += '<section class="cal-list-week"><h4 class="cal-list-week-title">KW ' + isoWeek(weekStart) + ' <span>'
        + esc(weekStart.getDate() + '.' + (weekStart.getMonth() + 1) + '. – ' + end.getDate() + '.' + (end.getMonth() + 1) + '.') + '</span></h4>'
        + dayBlocks + '</section>';
    }
    return html + (any ? '' : '<p class="cal-empty">Keine Termine in diesen vier Wochen.</p>') + '</div>';
  }

  // ── Details ────────────────────────────────────────────────────────────────
  function openDetail(ev) {
    var raw = ev.raw || {};
    var d = fromIso(ev.day);
    var dateText = ev.endDay > ev.day
      ? d.toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'long' }) + ' – '
        + fromIso(ev.endDay).toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'long' })
      : d.toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    var timeText = ev.time ? ev.time + (ev.endTime ? '–' + ev.endTime + ' Uhr' : ' Uhr') : 'ganztägig';
    var body = '';
    var A = window.LehrerAttachments;
    if (ev.src === 'sch' && A) {
      body = A.detailHtml(raw.description, raw.description_html) + A.attachmentsHtml(raw.attachments);
    } else if (ev.src === 'its' && A) {
      var data = _h.getData() || {};
      var viaServer = !!data.itslearningMode && data.itslearningMode !== 'calendar';
      body = A.detailHtml(raw.detail, raw.detailHtml) + A.attachmentsHtml(raw.attachments, { viaServer: viaServer });
    } else if (ev.src === 'ka') {
      body = '<p class="cal-detail-note">Klasse ' + esc(raw.classLabel) + ' · ' + esc(raw.kind || '') + '</p>';
    } else if (ev.src === 'org' && ev.sub) {
      body = '<p class="cal-detail-note">' + esc(ev.sub) + '</p>';
    }
    var src = SOURCES[order(ev.src)] || {};
    var actions = (raw.url ? '<a class="btn btn-secondary btn-sm" href="' + esc(raw.url) + '" target="_blank" rel="noopener noreferrer">In der Quelle öffnen ↗</a>' : '')
      + (src.tab ? '<button class="btn btn-secondary btn-sm" type="button" data-cal-goto="' + src.tab + '">Im Reiter ' + esc(src.label) + '</button>' : '');

    closeDetail();
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay cal-detail-overlay';
    overlay.innerHTML = '<div class="modal cal-detail src-' + ev.src + '" role="dialog" aria-modal="true" aria-labelledby="cal-detail-title">'
      + '<div class="modal-header"><span class="cal-detail-src"><span class="cal-dot" aria-hidden="true"></span>' + esc(label(ev.src)) + '</span>'
      + '<button class="modal-close" type="button" data-cal-close aria-label="Schließen">✕</button></div>'
      + '<h3 class="cal-detail-title" id="cal-detail-title">' + esc(ev.title) + '</h3>'
      + '<p class="cal-detail-when">' + esc(dateText) + ' · ' + esc(timeText) + '</p>'
      + (ev.src !== 'ka' && ev.src !== 'org' && ev.sub ? '<p class="cal-detail-note">' + esc(ev.sub) + '</p>' : '')
      + body
      + (actions ? '<div class="modal-actions cal-detail-actions">' + actions + '</div>' : '')
      + '</div>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay || e.target.closest('[data-cal-close]')) { closeDetail(); return; }
      var go = e.target.closest('[data-cal-goto]');
      if (go) {
        closeDetail();
        var tab = document.querySelector('.plans-tab-btn[data-plans-tab="' + go.dataset.calGoto + '"]');
        if (tab) tab.click();
      }
    });
    var close = overlay.querySelector('[data-cal-close]');
    if (close) close.focus();
  }

  function closeDetail() {
    var open = document.querySelector('.cal-detail-overlay');
    if (open) open.remove();
  }

  // ── Events ─────────────────────────────────────────────────────────────────
  function onClick(e) {
    var t = e.target;
    var ev = t.closest('[data-cal-ev]');
    if (ev) { if (_byId[ev.dataset.calEv]) openDetail(_byId[ev.dataset.calEv]); return; }
    var more = t.closest('[data-cal-day-more]');
    if (more) {
      // the whole day: in the month view below the grid, elsewhere in the month view
      _selected = more.dataset.calDayMore;
      if (_view !== 'month') {
        var d = fromIso(_selected);
        _view = 'month';
        store(VIEW_KEY, 'month');
        _anchor = new Date(d.getFullYear(), d.getMonth(), 1);
      }
      render();
      var panel = _root.querySelector('.cal-daypanel');
      if (panel && panel.scrollIntoView) panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      return;
    }
    var day = t.closest('[data-cal-day]');
    if (day) { _selected = day.dataset.calDay; render(); return; }
    var view = t.closest('[data-cal-view]');
    if (view) { setView(view.dataset.calView); return; }
    var src = t.closest('[data-cal-src]');
    if (src) {
      var id = src.dataset.calSrc;
      if (_off[id]) delete _off[id]; else _off[id] = true;
      store(OFF_KEY, _off);
      render();
      return;
    }
    var nav = t.closest('[data-cal]');
    if (nav) {
      if (nav.dataset.cal === 'prev') shift(-1);
      else if (nav.dataset.cal === 'next') shift(1);
      else goToday(true);
    }
  }

  function init(helpers) {
    _h = helpers;
    _root = document.getElementById('calendar-root');
    if (!_root || _root.dataset.bound) return;
    _root.dataset.bound = '1';
    _off = load(OFF_KEY) || {};
    _root.addEventListener('click', onClick);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && document.querySelector('.cal-detail-overlay')) closeDetail();
    });
  }

  return { init: init, render: render };
})();

if (typeof window !== 'undefined') window.LehrerCalendar = LehrerCalendar;
