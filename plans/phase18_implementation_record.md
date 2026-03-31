# Phase 18 Implementation Record
## Title: Orgaplan live-PDF + Heute/Woche Darstellung

**Date:** 2026-03-31
**Status:** ✅ Complete
**Commits:** `b621f27` (Feature), `7f95051` (Bugfix)

---

## Objective

Den Orgaplan der Hermann-Ehlers-Schule live aus der PDF lesen und benutzerfreundlich anzeigen:
- **Tagesbriefing:** kurzer Hinweis auf heutige Orgaplan-Einträge
- **Pläne → Orgaplan:** Heute-Karte + Wochenübersicht + aufklappbare Gesamtliste

---

## Dateien geändert

| Datei | Änderung |
|---|---|
| [`backend/plan_digest.py`](../backend/plan_digest.py) | `_berlin_today()`, `isoDate` in `_serialize_entry()`, alle upcoming-Einträge ohne Limit |
| [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py) | HES-PDF-Fallback-URL, `_slice_by_date()` für zeitzonenkorrektes Filtern |
| [`src/features/classwork.js`](../src/features/classwork.js) | `renderOrgaplanTodayCard()`, `renderOrgaplanWeekSection()`, `renderPlanDigest()` erweitert |
| [`index.html`](../index.html) | Drei-Ebenen-Orgaplan-Block; v=53 |
| [`src/app.js`](../src/app.js) | `_applyOrgaplanV2Data()`, `pickOrgaplanBriefing()`, `renderSectionFocus()` Divider-Fix |
| [`styles.css`](../styles.css) | CSS für today/week-Blöcke |
| [`CLAUDE_HANDOFF.md`](../CLAUDE_HANDOFF.md) | Phase 18 dokumentiert |

---

## Backend-Änderungen

### `backend/plan_digest.py`

**`_berlin_today(now)`** — neue Hilfsfunktion:
```python
def _berlin_today(now: datetime) -> date:
    try:
        import zoneinfo
        berlin = zoneinfo.ZoneInfo("Europe/Berlin")
        return datetime.now(berlin).date()
    except Exception:
        berlin_offset = timedelta(hours=2)
        return (now.replace(tzinfo=timezone.utc) + berlin_offset).date()
```

**`_serialize_entry()`** — liefert jetzt `isoDate`:
```python
{"dateLabel": "01.04.", "isoDate": "2026-04-01", "title": "...", ...}
```

**`_build_orgaplan_digest()`** — `upcoming` enthält alle zukünftigen Einträge (kein 8er-Limit), kein `today_entries`/`week_entries` mehr in der Digest-Speicherung (werden immer frisch berechnet).

### `backend/api/dashboard_routes.py`

**HES-Fallback-URL:**
```python
_HES_ORGAPLAN_PDF_URL = "https://hermann-ehlers-schule.de/wp-content/uploads/2026/03/Orgaplan-2025_26-ab-April.pdf"
effective_url = pdf_url or orgaplan_url or _HES_ORGAPLAN_PDF_URL
```

**`_slice_by_date()`** — berechnet bei jedem Request frisch:
```python
def _slice_by_date(all_upcoming: list) -> tuple:
    today_local = _get_berlin_today(now)
    week_end = today_local + _td(days=6)
    t_entries, w_entries = [], []
    for entry in sorted(all_upcoming, key=lambda e: e.get("isoDate", "")):
        d = _date.fromisoformat(entry.get("isoDate", ""))
        if d == today_local: t_entries.append(entry)
        if today_local <= d <= week_end: w_entries.append(entry)
    return t_entries, w_entries
```

Wird sowohl für Cache-Hit als auch für frisch geparste Daten aufgerufen.

---

## Frontend-Änderungen

### `src/features/classwork.js`

**`renderOrgaplanTodayCard(todayEntries)`:**
- Leerer Zustand: „Heute keine Orgaplan-Hinweise ✓"
- Einträge: Card mit Badge „Heute" + Allgemein/Mittelstufe/Oberstufe-Zeilen

**`renderOrgaplanWeekSection(weekEntries)`:**
- Gruppiert nach `isoDate`
- Jeder Tag als eigene `<section>` mit Datums-Kopfzeile
- Einträge mit Linksrand-Styling

**`renderPlanDigest()`** — befüllt neue DOM-Targets:
```javascript
if (_elements.orgaplanTodayList) {
  _elements.orgaplanTodayList.innerHTML = renderOrgaplanTodayCard(orgaplan.today_entries || []);
}
if (_elements.orgaplanWeekList) {
  _elements.orgaplanWeekList.innerHTML = renderOrgaplanWeekSection(orgaplan.week_entries || []);
}
```

### `index.html` (v=53)

Orgaplan-Block mit drei Ebenen:
```html
<!-- Heute -->
<div class="orgaplan-today-section">
  <div class="orgaplan-section-label"><span class="card-kicker">Heute</span></div>
  <div id="orgaplan-today-list" class="orgaplan-today-list"></div>
</div>

<!-- Diese Woche -->
<div class="orgaplan-week-section">
  <div class="orgaplan-section-label"><span class="card-kicker">Diese Woche</span></div>
  <div id="orgaplan-week-list" class="orgaplan-week-list stack-list compact-list"></div>
</div>

<!-- Alle weiteren (eingeklappt) -->
<details class="orgaplan-upcoming-details">
  <summary class="orgaplan-upcoming-summary">Alle weiteren Einträge</summary>
  <div id="orgaplan-upcoming-list" class="stack-list compact-list"></div>
</details>
```

### `src/app.js`

**`_applyOrgaplanV2Data()`** — überträgt neue Felder:
```javascript
data.planDigest.orgaplan = Object.assign({}, data.planDigest.orgaplan, digest, {
  today_entries: digest.today_entries || [],
  week_entries: digest.week_entries || [],
});
```

**`pickOrgaplanBriefing()`** — bevorzugt `today_entries`:
```javascript
const todayEntries = orgaplan.today_entries || [];
if (todayEntries.length) {
  const item = todayEntries[0];
  return { label: item.dateLabel || "Heute", copy: item.general || item.text };
}
// Fallback: Suche in upcoming per dateLabel-String
```

**`renderSectionFocus()`** — Divider-Fix:
```javascript
elements.viewDividers.forEach((divider) => {
  const targetSection = divider.dataset.dividerFor || "";
  divider.hidden = !targetSection || !isSectionEnabled(targetSection);
});
```

---

## Bug-Fixes

| Bug | Ursache | Fix |
|---|---|---|
| Falsches Datum | `now.date()` nutzte UTC statt Europe/Berlin | `_berlin_today()` mit zoneinfo |
| Veraltete today/week aus Cache | Wurden aus gecachtem Digest gelesen | `_slice_by_date()` bei jedem Request neu berechnet |
| Reihenfolge falsch | 8er-Limit + keine Sortierung | Alle Einträge, aufsteigend nach `isoDate` sortiert |
| Divider blind versteckt | `divider.hidden = true` für alle | Filter per `dataset.dividerFor` |

---

## Test-Ergebnis

```
412 passed, 116 deselected, 109 warnings in 2.42s
```

---

## Bekannte Einschränkungen

- Orgaplan-Cache hat 60-Minuten-TTL — bei Änderung an der PDF: Cache invalidieren via Render-Restart oder Admin-Einstellung `orgaplan_cache_ts` löschen
- Wenn kein `orgaplan_pdf_url` in Admin-Settings gesetzt: HES-URL wird als Fallback genutzt (hardcodiert für `Orgaplan-2025_26-ab-April.pdf`)
- Schuljahreswechsel: URL muss in Admin-Einstellungen aktualisiert werden
