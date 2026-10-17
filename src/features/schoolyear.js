/**
 * LehrerSchoolYear — Berliner Schulferien und Feiertage.
 *
 * Ferien: KMK-Ferienkalender, Stand 09.10.2025 (erster und letzter Ferientag),
 * https://www.kmk.org/service/ferienregelung/ferienkalender.html
 * Feiertage in Berlin: Neujahr, Frauentag (8.3.), Karfreitag, Ostermontag,
 * 1. Mai, Himmelfahrt, Pfingstmontag, 3. Oktober, 1./2. Weihnachtstag.
 * Additional days from the school calendar (title with „Ferien“/„unterrichtsfrei“)
 * are merged in by the caller via setExtraBreaks().
 *
 * Exports (window.LehrerSchoolYear): breakOn, nextBreak, schoolDaysBetween,
 * isSchoolDay, schoolYear, setExtraBreaks
 */
var LehrerSchoolYear = (function () {
  'use strict';

  // Schuljahr → [Name, erster Tag, letzter Tag]
  var BREAKS = [
    ['Herbstferien', '2026-10-19', '2026-10-31'],
    ['Weihnachtsferien', '2026-12-23', '2027-01-02'],
    ['Winterferien', '2027-02-01', '2027-02-06'],
    ['Osterferien', '2027-03-22', '2027-04-02'],
    ['Unterrichtsfrei nach Himmelfahrt', '2027-05-07', '2027-05-07'],
    ['Pfingstferien', '2027-05-18', '2027-05-19'],
    ['Sommerferien', '2027-07-01', '2027-08-14'],
    ['Herbstferien', '2027-10-11', '2027-10-23'],
    ['Weihnachtsferien', '2027-12-22', '2027-12-31'],
    ['Winterferien', '2028-01-31', '2028-02-05'],
    ['Osterferien', '2028-04-10', '2028-04-22'],
    ['Unterrichtsfrei nach Himmelfahrt', '2028-05-26', '2028-05-26'],
    ['Pfingstferien', '2028-06-01', '2028-06-02'],
    ['Sommerferien', '2028-07-01', '2028-08-12'],
  ].map(function (b) { return { name: b[0], start: b[1], end: b[2] }; });

  var _extra = [];

  function iso(date) {
    return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
  }

  function fromIso(value) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value || '');
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }

  function addDays(date, n) {
    var d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    d.setDate(d.getDate() + n);
    return d;
  }

  // Ostersonntag (Gauß/Anonymous Gregorian algorithm)
  function easter(year) {
    var a = year % 19, b = Math.floor(year / 100), c = year % 100, d = Math.floor(b / 4), e = b % 4;
    var f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30;
    var i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
    var month = Math.floor((h + l - 7 * m + 114) / 31), day = ((h + l - 7 * m + 114) % 31) + 1;
    return new Date(year, month - 1, day);
  }

  var _holidayCache = {};
  function publicHolidays(year) {
    if (_holidayCache[year]) return _holidayCache[year];
    var e = easter(year);
    var days = {};
    [['01-01', 'Neujahr'], ['03-08', 'Frauentag'], ['05-01', 'Tag der Arbeit'], ['10-03', 'Tag der Deutschen Einheit'],
     ['12-25', '1. Weihnachtstag'], ['12-26', '2. Weihnachtstag']].forEach(function (f) { days[year + '-' + f[0]] = f[1]; });
    [[-2, 'Karfreitag'], [1, 'Ostermontag'], [39, 'Christi Himmelfahrt'], [50, 'Pfingstmontag']].forEach(function (f) {
      days[iso(addDays(e, f[0]))] = f[1];
    });
    _holidayCache[year] = days;
    return days;
  }

  function allBreaks() {
    return BREAKS.concat(_extra).sort(function (a, b) { return a.start.localeCompare(b.start); });
  }

  /** The break (Ferien or Feiertag) covering this day, or null. */
  function breakOn(date) {
    var day = iso(date);
    var hit = allBreaks().find(function (b) { return b.start <= day && day <= b.end; });
    if (hit) return hit;
    var name = publicHolidays(date.getFullYear())[day];
    return name ? { name: name, start: day, end: day, holiday: true } : null;
  }

  function isSchoolDay(date) {
    var dow = date.getDay();
    return dow !== 0 && dow !== 6 && !breakOn(date);
  }

  /** Next Ferien period that starts after today (single Feiertage are not „Ferien“). */
  function nextBreak(today) {
    var day = iso(today);
    return allBreaks().find(function (b) { return b.start > day && (b.end > b.start || /ferien/i.test(b.name)); }) || null;
  }

  /** School days from `from` (inclusive) to `to` (exclusive). */
  function schoolDaysBetween(from, to) {
    var n = 0;
    for (var d = addDays(from, 0); d < to; d = addDays(d, 1)) if (isSchoolDay(d)) n++;
    return n;
  }

  /** Breaks of the school year containing `date` (1 August – 31 July). */
  function schoolYear(date) {
    var y = date.getMonth() >= 7 ? date.getFullYear() : date.getFullYear() - 1;
    var start = y + '-08-01', end = (y + 1) + '-07-31';
    return {
      label: y + '/' + String((y + 1) % 100).padStart(2, '0'),
      start: start, end: end,
      breaks: allBreaks().filter(function (b) { return b.start >= start && b.start <= end; }),
      known: BREAKS.some(function (b) { return b.start >= start && b.start <= end; }),
    };
  }

  /** Extra free days from the school calendar ([{name, start, end}] with ISO dates). */
  function setExtraBreaks(list) {
    _extra = (list || []).filter(function (b) {
      // only what the KMK table does not already cover
      return b && b.start && b.end && !BREAKS.some(function (k) { return k.start <= b.start && b.end <= k.end; });
    });
  }

  return { breakOn: breakOn, nextBreak: nextBreak, schoolDaysBetween: schoolDaysBetween, isSchoolDay: isSchoolDay,
           schoolYear: schoolYear, setExtraBreaks: setExtraBreaks, iso: iso, fromIso: fromIso, addDays: addDays };
})();

if (typeof window !== 'undefined') window.LehrerSchoolYear = LehrerSchoolYear;
