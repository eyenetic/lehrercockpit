"""Berliner Schulferien und Feiertage für den Server (Kalender-Abo).

Dieselbe Tabelle wie src/features/schoolyear.js – beim Ergänzen eines
Schuljahres beide Dateien ändern. Ferien: KMK-Ferienkalender, Stand 09.10.2025
(erster und letzter Ferientag). Feiertage in Berlin werden berechnet.
"""
from __future__ import annotations

from datetime import date, timedelta

BREAKS = [
    ("Herbstferien", "2026-10-19", "2026-10-31"),
    ("Weihnachtsferien", "2026-12-23", "2027-01-02"),
    ("Winterferien", "2027-02-01", "2027-02-06"),
    ("Osterferien", "2027-03-22", "2027-04-02"),
    ("Unterrichtsfrei nach Himmelfahrt", "2027-05-07", "2027-05-07"),
    ("Pfingstferien", "2027-05-18", "2027-05-19"),
    ("Sommerferien", "2027-07-01", "2027-08-14"),
    ("Herbstferien", "2027-10-11", "2027-10-23"),
    ("Weihnachtsferien", "2027-12-22", "2027-12-31"),
    ("Winterferien", "2028-01-31", "2028-02-05"),
    ("Osterferien", "2028-04-10", "2028-04-22"),
    ("Unterrichtsfrei nach Himmelfahrt", "2028-05-26", "2028-05-26"),
    ("Pfingstferien", "2028-06-01", "2028-06-02"),
    ("Sommerferien", "2028-07-01", "2028-08-12"),
]


def easter(year: int) -> date:
    """Ostersonntag (Gauß/Anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def public_holidays(year: int) -> list[tuple[str, date]]:
    fixed = [("Neujahr", 1, 1), ("Frauentag", 3, 8), ("Tag der Arbeit", 5, 1), ("Tag der Deutschen Einheit", 10, 3),
             ("1. Weihnachtstag", 12, 25), ("2. Weihnachtstag", 12, 26)]
    sunday = easter(year)
    moving = [("Karfreitag", -2), ("Ostermontag", 1), ("Christi Himmelfahrt", 39), ("Pfingstmontag", 50)]
    return sorted([(name, date(year, month, day)) for name, month, day in fixed]
                  + [(name, sunday + timedelta(days=offset)) for name, offset in moving], key=lambda h: h[1])


def free_days_between(start: date, end: date) -> list[dict]:
    """Ferien and Feiertage overlapping [start, end]: [{"name", "start", "end"}] with inclusive dates."""
    out = []
    for name, first, last in BREAKS:
        first_day, last_day = date.fromisoformat(first), date.fromisoformat(last)
        if first_day <= end and last_day >= start:
            out.append({"name": name, "start": first_day, "end": last_day})
    for year in range(start.year, end.year + 1):
        for name, day in public_holidays(year):
            if start <= day <= end:
                out.append({"name": name, "start": day, "end": day})
    return sorted(out, key=lambda b: b["start"])
