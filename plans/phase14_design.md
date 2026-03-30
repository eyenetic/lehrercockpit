# Lehrercockpit — Phase 14 Design Document

**Status:** Draft · **Author:** Architect · **Target:** Implementation Agent

---

## Section 1: Feature Summary

Every working day, a Berlin teacher opens a browser and has to visit five or six different tools to figure out what the day looks like — WebUntis for the schedule, itslearning for student messages, a PDF somewhere for the Orgaplan, a bookmark for the school portal, another one for Nextcloud. The Lehrercockpit already pulls these together into a single login, but the experience still feels like a collection of separate pages rather than a unified daily workspace.

This phase delivers **one authoritative Today view** that answers the three questions every teacher has the moment they sit down: *What does my day look like? What needs my attention right now? Where do I need to go?* The Today view shows the personal timetable, a curated list of important school events from the school calendar, all relevant quick-access links in one compact launchpad, and an inbox that clearly separates official school mail from itslearning notifications — all above or one scroll away from the fold.

Teachers who want to simplify their Today view can hide optional modules through a single "Heute anpassen" panel. Mandatory context (the daily briefing and the quick-access launchpad) cannot be removed. Every personalization choice is remembered per user.

Two plan views — the Orgaplan and the Klassenarbeitsplan — are promoted to first-class cards rather than buried in the Documents section, making it obvious at a glance whether there are upcoming tests or changes to the schedule.

Finally, an admin can configure the application title (e.g., the school name) and the school event calendar URL from the existing admin panel, so the cockpit feels like *their school's* tool rather than a generic product.

---

## Section 2: Current-State Assessment Summary

### Frontend Structure

The frontend is a single-page vanilla-JS application with no build step. [`index.html`](../index.html) is a ~707-line static shell that renders all seven sections simultaneously in the DOM; navigation shows/hides them via the `hidden` attribute driven by `state.activeSection` inside [`src/app.js`](../src/app.js). The monolithic `bootstrapApp()` IIFE in `src/app.js` (~2895 lines) owns all render logic and delegates to seven feature modules in [`src/features/`](../src/features/). Layout personalization is already partially implemented: [`src/modules/dashboard-manager.js`](../src/modules/dashboard-manager.js) fetches `GET /api/v2/dashboard/layout`, exposes `isModuleVisible(moduleId)`, and dispatches a `dashboard-layout-changed` event that the rest of the app listens to. This is the gating mechanism any new module card must hook into.

### Backend & Data Layer

The backend is Flask 3.x on Python 3.11. The v2 API layer uses four blueprints; the dashboard blueprint lives in [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py). The critical function for this phase is `_fetch_base_data()`, which already reads `schoolportal_url`, `orgaplan_pdf_url`, `itslearning_base_url`, and `school_name` from the `system_settings` KV table. The parallel module-fetch pattern using `ThreadPoolExecutor` in `get_dashboard_data()` provides the exact hook needed to add a `wichtige-termine` backend fetcher. The `PUT /api/v2/dashboard/layout` endpoint already exists in `dashboard_routes.py` and handles both `sort_order` and `is_visible` updates, so no new persistence endpoint is needed for personalization.

### Module System & Constraints

The `modules` table (seeded in [`backend/migrations.py`](../backend/migrations.py)) drives which modules exist; `user_modules` stores per-user visibility and sort order. The seed uses `ON CONFLICT DO NOTHING`, which means three new rows are needed for `tagesbriefing`, `zugaenge`, and `wichtige-termine`. The `modules` seed also makes new modules appear in each user's layout via `initialize_user_modules()` in [`backend/modules/module_registry.py`](../backend/modules/module_registry.py). All schema changes must follow the existing idempotency pattern (`ADD COLUMN IF NOT EXISTS`, `INSERT … ON CONFLICT DO NOTHING`, wrapped in `try/except`). These constraints shape every migration and seed decision below.

---

## Section 3: UX Design

### 3.1 Today Landing Experience

When a teacher opens the cockpit and lands on the **Heute** section (the renamed `overview` nav item), they see — above the fold on a standard 1280 px laptop — the following vertical stack:

1. **Page header row** — App title (configurable, default "Lehrercockpit") + greeting + current date (e.g., "Montag, 31. März 2026").
2. **Tagesbriefing card** (full width, mandatory) — Today's timetable summary: period list for today pulled from WebUntis (or a "Kein Stundenplan konfiguriert" placeholder). This is the primary above-the-fold content because a teacher's first question is always about their own lessons.
3. **Wichtige Termine card** (full width, optional) — Upcoming events from the school calendar ICS feed. Appears directly below Tagesbriefing.
4. **Two-column row**: **Zugänge** card (left, fixed width ~40 %) + **Inbox** card (right, ~60 %). Zugänge is mandatory; Inbox is optional.

Below the fold (one scroll):
5. **Orgaplan card** — full width or half width
6. **Klassenarbeitsplan card** — full width or half width

Visual hierarchy uses card elevation (subtle `box-shadow`) and a clear typographic scale: section heading (`h2`, 1.25 rem, semibold) > card title (`h3`, 1 rem, medium) > body text (0.875 rem, normal). Status badges (green dot = ok, amber = warning, red = error) appear in every card header.

### 3.2 Fixed vs Optional Module Rules

| Module | Mandatory on Today? | Reason |
|---|---|---|
| Tagesbriefing (WebUntis summary) | **Yes** | Core daily context |
| Zugänge | **Yes** | Navigation can never be hidden |
| Wichtige Termine | No (optional) | Useful but not every school uses the ICS feed |
| Inbox | No (optional) | Requires individual credential config |
| Orgaplan | No (optional) | Central but some users may not need it |
| Klassenarbeitsplan | No (optional) | Central but same rationale |
| Noten | No (optional, belongs to dedicated section) | Not a Today card |

Mandatory modules are shown in the "Heute anpassen" panel with a **lock icon** and the label "Immer sichtbar" instead of a toggle. They appear first in the list and cannot be dragged below optional modules (or drag is simply disabled for them). If all optional modules are hidden, the Today view still shows Tagesbriefing and Zugänge with a small info note: "Alle optionalen Module ausgeblendet. Über 'Heute anpassen' wieder einblenden."

### 3.3 `Heute anpassen` Flow

**Trigger:** A subtle `⚙ Heute anpassen` text-button appears in the top-right of the Today page header row (not inside any card). It is always visible on the Today section only.

**Panel:** Clicking the button opens a right-side drawer overlay (not a full modal) with:
- Header: "Heute anpassen" + ✕ close button
- Section "Immer sichtbar" → lists Tagesbriefing and Zugänge as locked rows (lock icon, no toggle)
- Section "Optionale Module" → lists remaining Today-eligible modules as draggable rows, each with:
  - Drag handle (⠿) on the left
  - Module name
  - Toggle switch (on/off) on the right
- Footer: "Speichern" primary button + "Abbrechen" link

**Save behavior:** On "Speichern", a single `PUT /api/v2/dashboard/layout` call is made with the updated `modules` array (module_id + sort_order + is_visible). The drawer closes and the Today view re-renders immediately from the updated layout without a page reload. Mandatory modules always receive `is_visible: true` in the payload regardless of UI state.

**Auto-save alternative (simpler):** Individual toggle changes can also fire immediately (debounced 500 ms) via `PUT /api/v2/dashboard/layout/<module_id>/visibility`. The reorder save only fires on explicit "Speichern". This matches the pattern already used by the existing layout panel.

### 3.4 Module Shell Structure

Every module card uses a consistent three-part shell:

```
┌─────────────────────────────────────────────┐
│ [Icon] Card Title          [● Status] [→]   │  ← Header
├─────────────────────────────────────────────┤
│                                             │
│  Content area                               │  ← Body
│                                             │
├─────────────────────────────────────────────┤
│ Zuletzt aktualisiert: 14:32    [Öffnen ↗]  │  ← Footer
└─────────────────────────────────────────────┘
```

**Loading state:** Body replaced with three grey skeleton shimmer bars. Header title and status remain visible.

**Empty state:** Body shows a centred icon + short explanation text (e.g., "Heute keine Termine.") + optional CTA link.

**Error state:** Body shows amber warning icon + short error message (e.g., "Konnte nicht geladen werden.") + "Erneut versuchen" link. Status badge in header turns red.

**Not configured state:** Body shows info icon + "Nicht konfiguriert — Einstellungen öffnen" link that navigates to the module's config screen.

### 3.5 Zugänge Layout

Zugänge is a compact launchpad card. Links shown (in order):

| Label | URL Source | Group |
|---|---|---|
| WebUntis | `webuntis` user config `base_url` | Mein Unterricht |
| Dienstmail (Berlin) | Static: `https://securemailer.berlin.de` | Mein Unterricht |
| itslearning | `system_settings.itslearning_base_url` | Mein Unterricht |
| Berliner Schulportal | `system_settings.schoolportal_url` | Berlin-Dienste |
| Nextcloud | `nextcloud` user config `url` | Berlin-Dienste |
| Orgaplan (PDF) | `system_settings.orgaplan_pdf_url` | Schule |
| Klassenarbeitsplan | `system_settings.klassenarbeitsplan_url` | Schule |
| Fehlzeiten 11. Klasse | Static or `system_settings.fehlzeiten_11_url` | Schule |
| Fehlzeiten 12. Klasse | Static or `system_settings.fehlzeiten_12_url` | Schule |

Visual grouping: Three visually distinct pill-groups separated by a small label heading. Each link is a rounded pill button with an icon + label. All links open in a new tab (`target="_blank" rel="noopener"`). The card has no body content beyond the pill grid — it is intentionally compact (no footer needed).

URLs that have no configured value are rendered as a greyed-out disabled pill with a ⚙ icon linking to admin settings (visible only to admins) or hidden entirely for teachers.

### 3.6 Wichtige Termine Display Logic

**When today has events:**
- Show a "Heute" section header followed by event rows.
- Each row: coloured left-border strip (blue for timed, grey for all-day) + time range (or "Ganztags") + title + optional location.
- All-day events are shown first, then timed events sorted by start time.

**When no events today:**
- Show next upcoming event(s): "Nächste Termine" section with up to 3 entries.
- Each entry shows: date label ("Morgen", "Fr 3. Apr.", etc.) + title.

**If no upcoming events at all:**
- Empty state: "Keine anstehenden Termine gefunden."

**Loading state:** Skeleton shimmer in card body.

**Error state:** "Schulkalender konnte nicht geladen werden." + retry link.

**ICS not configured:** "Schulkalender-URL nicht konfiguriert." + admin link (admin-only).

### 3.7 Stundenplan Navigation Behavior

The **Stundenplan** section (nav item `schedule`) remains its own dedicated full-page section with enhanced navigation. Layout:

- **Day/Week switcher:** Two toggle buttons "Tag" / "Woche" in the card header. Default: Day view.
- **Navigation row:** `‹ Zurück` button + current date/week label + `Weiter ›` button + `Heute` jump button.
- **Jump to today:** Always visible button that resets to today's date; disabled/greyed when already on today.
- **WebUntis external link:** "In WebUntis öffnen ↗" text-link in the card footer. The URL is constructed from `webuntis` user module config `base_url`. If not configured, the link is hidden.
- **Data:** The existing `_fetch_webuntis_data()` returns a full data structure. The frontend `src/features/webuntis.js` already parses this; the navigation state (selected date, day/week mode) is maintained in a local `state` object within the feature module and triggers a re-render — no new API call is needed for navigation (data is already fetched for the current week; client-side filtering by selected day).

### 3.8 Inbox Source Split

The **Posteingang** section (nav item `inbox`) splits into two clearly separated sources:

**Tab bar:** Two tabs at the top of the inbox section: `Dienstmail` and `itslearning`. Active tab highlighted with a bottom border accent color. The unread count badge appears on each tab label when there are unread items.

**Per-message display (both sources):**
- Sender name / avatar initial
- Subject line (bold if unread)
- Snippet (first ~100 chars of body, greyed text)
- Relative timestamp ("Vor 2 Std.", "Gestern", or absolute date if older than 7 days)
- Unread indicator: left border accent or bold font weight

**Dienstmail tab:** Renders mail messages from the existing `inbox.js` data where `channel === "mail"` (or the mail adapter data). Each message has an "Öffnen" link pointing to `securemailer.berlin.de`.

**itslearning tab:** Renders notifications from `channel === "itslearning"`. Each notification has an "In itslearning öffnen ↗" link using `itslearning_base_url`.

**Empty state per tab:** "Keine neuen Nachrichten in [source]."

### 3.9 Plans Separation

Orgaplan and Klassenarbeitsplan are promoted from "buried in Documents" to **first-class Today module cards** and also retain their own dedicated sub-sections within the existing **Dokumente** nav section.

**Orgaplan card (Today):** Compact card showing `highlights` (top 3 items from digest) + "Mehr anzeigen" footer link that navigates to the full Dokumente > Orgaplan view. PDF link button in card header.

**Klassenarbeitsplan card (Today):** Compact card showing `previewRows` (next 5 test entries) + class filter if multiple classes present. "Mehr anzeigen" footer link navigates to Dokumente > Klassenarbeitsplan view.

**Dokumente section:** The existing `documents` nav section retains both full-detail views as two clearly separated sub-sections (tabbed or stacked). The current nav label "Dokumente" remains unchanged. The `documents` section in `index.html` gains two sub-panels: `#orgaplan-detail` and `#klassenarbeitsplan-detail`.

### 3.10 Admin App Title Config

**Location in `admin.html`:** The "Einstellungen" tab (4th tab, already exists). A new form group is added at the **top** of the settings form, before existing URL fields.

**Field:** Text input, label "App-Titel / Schulname", placeholder "Lehrercockpit", `id="setting-app-title"`, `data-key="app_title"`. Below the field: helper text "Wird in der Navigationsleiste und im Browser-Tab angezeigt. Leer lassen für den Standard 'Lehrercockpit'."

**Fallback:** If `app_title` is empty string, null, or not set in `system_settings`, the frontend defaults to `"Lehrercockpit"`.

**Display locations in cockpit:**
1. `<title>` element in `index.html` — updated dynamically on load via `document.title = appTitle`.
2. The sidebar/nav area header (currently has a static "Lehrercockpit" text element in `index.html`) — replaced with a `<span id="app-title-display">` that is populated from the dashboard payload.
3. PWA manifest `name` / `short_name` cannot be dynamic; they remain "Lehrercockpit" in [`manifest.json`](../manifest.json).

**Backend:** `app_title` is read in `_fetch_base_data()` alongside the existing `school_name` key and included in the `workspace` object of the `base` section in the `GET /api/v2/dashboard/data` response.

---

## Section 4: Architecture / Technical Design

### 4.1 Today Shell & Module Orchestration

**Section rename:** The `overview` nav section in [`index.html`](../index.html) is renamed to `heute` — the `data-section-target="overview"` attribute on the sidebar button and the corresponding section `id="overview"` both change to `heute`. The `state.activeSection` default changes accordingly in [`src/app.js`](../src/app.js).

**`DashboardManager` changes ([`src/modules/dashboard-manager.js`](../src/modules/dashboard-manager.js)):**
- Add a `MANDATORY_MODULES = ['tagesbriefing', 'zugaenge']` constant.
- Add `isMandatoryModule(moduleId)` method that checks against this constant.
- `isModuleVisible(moduleId)` continues to use the layout data; mandatory modules always return `true` regardless of stored visibility (enforce client-side).
- Add `getTodayModuleOrder()` method that returns the sorted list of Today-eligible module IDs.

**Mandatory module enforcement:** `PUT /api/v2/dashboard/layout` on the backend does **not** enforce mandatory modules — the backend stays simple and accepts any visibility value. Enforcement is purely front-end: the "Heute anpassen" drawer never renders a toggle for mandatory modules; the `PUT` payload always sends `is_visible: true` for `tagesbriefing` and `zugaenge`.

**Personalization persistence:** Uses the existing `PUT /api/v2/dashboard/layout` endpoint (body: `{"modules": [{module_id, sort_order, is_visible}, ...]}`). No new endpoint needed.

### 4.2 `Wichtige Termine` Module

**Fetch location:** Server-side. Justification: The ICS URL is a school-wide central resource (not per-user); fetching it from the backend avoids CORS issues with `https://hermann-ehlers-schule.de/events/liste/?ical=1`; the existing parallel `ThreadPoolExecutor` pattern in `get_dashboard_data()` provides the right hook; and caching (same pattern as Orgaplan) is trivially added server-side.

**New backend module:** `backend/wichtige_termine_adapter.py`
- Function: `fetch_wichtige_termine(ical_url: str, now: datetime) -> dict`
- ICS parsing library: **`icalendar`** (already in the Python ecosystem; add to `requirements.txt`). Stdlib `urllib.request` for fetching.
- Returns: `{"events_today": [...], "events_upcoming": [...], "fetched_at": ISO}`
- Each event: `{"uid": str, "title": str, "start": ISO date/datetime, "end": ISO date/datetime, "all_day": bool, "location": str|null}`

**New fetcher function in [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py):**
```
def _fetch_wichtige_termine_data() -> dict
```
- Reads `wichtige_termine_ical_url` from `system_settings`
- Falls back to hardcoded HES URL if not set (school-specific default, overridable in admin)
- Calls `fetch_wichtige_termine(url, now)`
- Returns `{"ok": True, "data": {...}, "configured": True}` or error dict

**Wired into `module_fetchers` dict** in `get_dashboard_data()` when `"wichtige-termine" in active_module_ids`.

**`modules` table row:**
```
("wichtige-termine", "Wichtige Termine", "Schulkalender-Ereignisse", "central", True, True, 15, False)
```
`requires_config = False` because the URL is a system setting, not per-user.

**Frontend:** New file `src/features/wichtige-termine.js`
- Exports: `renderWichtigeTermine(container, data)`
- Handles loading / error / empty states per Section 3.4 / 3.6 spec
- `app.js` wires it: after dashboard data loads, if `data.modules['wichtige-termine']` exists, call `renderWichtigeTermine(document.getElementById('heute-wichtige-termine'), data.modules['wichtige-termine'].data)`

### 4.3 `Zugänge` Module

**Current location:** The `access` section in `index.html` (`data-section-target="access"`) renders a version of quick links today. This remains as-is for the dedicated Zugänge nav section.

**Today card:** A new `<div id="heute-zugaenge" class="module-card">` is added to the `#heute` section in `index.html`. It is rendered by a new `renderZugaenge(container, data)` function — either in an extended `src/features/zugaenge.js` (new file) or added to the existing access section logic.

**Link URL sources:**
- `itslearning_base_url` — from `base.quick_links` (already in dashboard data response)
- `schoolportal_url` — from `base.quick_links`
- `orgaplan_pdf_url` — from `base.quick_links`
- `webuntis base_url` — from user module config (available in dashboard layout response)
- `nextcloud url` — from user module config
- `fehlzeiten_11_url`, `fehlzeiten_12_url` — new `system_settings` keys (optional, if empty the pills are hidden)
- `klassenarbeitsplan_url` — from `system_settings` (already read for plan digest)

**Backend change:** `_fetch_base_data()` extended to also read `fehlzeiten_11_url`, `fehlzeiten_12_url`, and `klassenarbeitsplan_url` from `system_settings`, including them in the `quick_links` array under a `group` field (e.g., `"group": "schule"`).

**No new endpoint needed.** Zugänge is entirely assembled client-side from data already present in the dashboard payload.

**`modules` table row:**
```
("zugaenge", "Zugänge", "Schnellzugriffe", "central", True, True, 5, False)
```

### 4.4 Personalization Persistence

**Storage:** `user_modules` table. Columns `is_visible` and `sort_order` are sufficient. No schema change needed.

**Module IDs for mandatory modules:** `tagesbriefing` and `zugaenge`. Both need rows in `modules` table (see 4.9).

**`tagesbriefing` module:** This is a UI shell concept (the Today WebUntis summary card) rather than a separate data fetcher — it maps onto the existing `webuntis` data. Its module row in `modules` table sets `module_type = 'individual'` and `requires_config = True` (since it needs WebUntis config). Visibility: always `True` enforced client-side.

**API:** `PUT /api/v2/dashboard/layout` already exists in [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py) (lines 104–153). No changes needed to this endpoint. The frontend sends the full module array on save.

### 4.5 Inbox Split

**No backend change.** The existing inbox data already has source separation (mail adapter vs itslearning adapter).

**Frontend changes to [`src/features/inbox.js`](../src/features/inbox.js):**
- Split `renderInbox(container, data)` into two sub-renderers: `renderMailTab(container, messages)` and `renderItslearningTab(container, messages)`.
- Filter messages: `messages.filter(m => m.channel === 'mail')` and `messages.filter(m => m.channel === 'itslearning')` (or equivalent source field in actual data shape).
- Tab switching: add `data-tab` attribute to tab buttons; on click, toggle `hidden` on the two sub-panels.
- Unread count badge: count messages where `m.read === false` per source.

**`index.html` changes to `#inbox` section:**
- Add tab bar: two `<button class="tab-btn" data-tab="mail">Dienstmail <span class="badge" id="badge-mail"></span></button>` and `<button class="tab-btn" data-tab="itslearning">itslearning <span class="badge" id="badge-itsl"></span></button>`
- Add two `<div class="tab-panel" id="inbox-tab-mail">` and `<div class="tab-panel" id="inbox-tab-itslearning">` containers.

### 4.6 Plans Split

**Both `orgaplan` and `klassenarbeitsplan` already have separate module IDs** and separate fetchers in `dashboard_routes.py`.

**`index.html` changes:**
- The `#documents` section gains two sub-panels with a tab strip or stacked layout: `#documents-orgaplan` and `#documents-klassenarbeitsplan`.
- The existing documents render logic in [`src/features/documents.js`](../src/features/documents.js) is extended to route data to the correct sub-panel.

**Today cards in `#heute` section:**
- `<div id="heute-orgaplan" class="module-card">` — compact Orgaplan card
- `<div id="heute-klassenarbeitsplan" class="module-card">` — compact Klassenarbeitsplan card
- Both rendered by new `renderOrgaplanCard(container, data)` and `renderKlassenarbeitsplanCard(container, data)` functions, either added to existing feature files or extracted.

**Nav label:** "Dokumente" remains unchanged.

### 4.7 Admin App Title

**`system_settings` key:** `app_title` (string value, e.g., `"Hermann-Ehlers-Schule Cockpit"`).

**Backend read location:** `_fetch_base_data()` in [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py). Add:
```python
app_title = _safe_str(get_system_setting(conn, "app_title", ""))
```
Include in `workspace` dict: `"app_title": app_title or "Lehrercockpit"`.

**Frontend render:** In [`src/app.js`](../src/app.js), after dashboard data loads, read `data.base.workspace.app_title` and:
1. Set `document.title = appTitle`
2. Set `document.getElementById('app-title-display').textContent = appTitle`

**`index.html`:** Replace static "Lehrercockpit" text in nav header with `<span id="app-title-display">Lehrercockpit</span>`.

**`admin.html`:** In the Einstellungen tab, add a new form group at the top (before existing URL fields). The existing `PUT /api/v2/admin/settings/<key>` endpoint already handles arbitrary keys — no backend change needed. The admin JS uses the same `saveSetting('app_title', value)` pattern already in place.

**Fallback:** Empty string → `"Lehrercockpit"` applied both in backend response builder and in frontend render.

### 4.8 Stundenplan Improvements

**`index.html` `#schedule` section changes:**
- Add nav row: `<div class="schedule-nav">` containing back/forward buttons, date label, today button, day/week toggle.
- Add external link in card footer: `<a id="webuntis-external-link" href="#" target="_blank" rel="noopener">In WebUntis öffnen ↗</a>`.

**[`src/features/webuntis.js`](../src/features/webuntis.js) changes:**
- Add local state: `{ viewMode: 'day', selectedDate: today }`.
- Add `renderScheduleNav(state)` function that updates the nav row DOM.
- Add event listeners for nav buttons (back/forward/today/toggle) that update local state and call `rerenderSchedule()`.
- Day mode: filter events for `selectedDate` from the already-loaded week data.
- Week mode: render 5-column week grid (Mon–Fri).
- `webuntis-external-link` href: set from `config.base_url` (already available from dashboard data).

**What is out of scope for Stundenplan in this phase:** Multi-week navigation (fetching a different week requires a new API call — left for a future phase). Only current-week data is available; back/forward navigation is constrained to days within the current fetched week, with a disabled-state indicator at week boundaries.

### 4.9 DB / Schema Changes

**New `modules` table rows** (idempotent `INSERT … ON CONFLICT DO NOTHING` in `run_migrations()`):

| id | display_name | module_type | default_visible | default_order | requires_config |
|---|---|---|---|---|---|
| `tagesbriefing` | Tagesbriefing | `individual` | True | 1 | True |
| `zugaenge` | Zugänge | `central` | True | 5 | False |
| `wichtige-termine` | Wichtige Termine | `central` | True | 15 | False |

**New `system_settings` keys** (no schema change — KV store; set by admin UI or migration seed):

| Key | Default | Purpose |
|---|---|---|
| `app_title` | `""` | Configurable cockpit/school name |
| `wichtige_termine_ical_url` | `""` | School event calendar ICS URL |
| `fehlzeiten_11_url` | `""` | Absence form URL for class 11 |
| `fehlzeiten_12_url` | `""` | Absence form URL for class 12 |

**Migration pattern:** New module rows appended to `modules_seed` list in [`backend/migrations.py`](../backend/migrations.py). No new SQL `CREATE TABLE` statements. Existing tables are untouched.

### 4.10 API Changes Summary

| Method | Path | Auth | Change Type | Notes |
|---|---|---|---|---|
| `GET` | `/api/v2/dashboard/data` | session | **Modified** | `base.workspace` gains `app_title`; `modules` gains `wichtige-termine` key when module active; `base.quick_links` gains `fehlzeiten_11`, `fehlzeiten_12`, `klassenarbeitsplan` entries |
| `GET` | `/api/v2/dashboard/layout` | session | No change | Already returns all module rows including new ones once seeded |
| `PUT` | `/api/v2/dashboard/layout` | session | No change | Already handles sort_order + is_visible for any module_id |
| `PUT` | `/api/v2/dashboard/layout/<module_id>/visibility` | session | No change | Already exists |
| `GET` | `/api/v2/admin/settings` | admin | No change | Will return new keys once set |
| `PUT` | `/api/v2/admin/settings/<key>` | admin | No change | `app_title`, `wichtige_termine_ical_url`, `fehlzeiten_11_url`, `fehlzeiten_12_url` are valid keys already |

**Net new endpoints: zero.** All required functionality is achievable with the existing API surface.

---

## Section 5: Implementation Plan

Each slice leaves the application in a fully runnable state. No slice breaks existing functionality.

---

### Slice 1: Today Shell + Module Orchestration + Personalization

**Goal:** The `overview` section becomes `heute`; the "Heute anpassen" drawer works end-to-end; mandatory module enforcement is in place.

**Files to change:**
- [`index.html`](../index.html) — rename `id="overview"` → `id="heute"`; rename nav button `data-section-target="overview"` → `data-section-target="heute"`; add `id="app-title-display"` span in nav header; add "Heute anpassen" trigger button in Today section header; add the `Heute anpassen` drawer HTML (hidden by default)
- [`src/app.js`](../src/app.js) — update `state.activeSection` default; update all references to `'overview'`; add drawer open/close event listeners; add `saveLayout(moduleUpdates)` function that calls `PUT /api/v2/dashboard/layout`; set `document.title` and `#app-title-display` from `data.base.workspace.app_title` after load
- [`src/modules/dashboard-manager.js`](../src/modules/dashboard-manager.js) — add `MANDATORY_MODULES` constant; add `isMandatoryModule(id)` method; modify `isModuleVisible()` to hard-return `true` for mandatory modules; add `getTodayModuleOrder()` method

**Functions to add/modify:**
- `src/app.js`: add `openHeuteAnpassenDrawer()`, `closeHeuteAnpassenDrawer()`, `renderHeuteAnpassenDrawer(modules)`, `saveHeuteLayout(modules)`
- `src/modules/dashboard-manager.js`: add `isMandatoryModule()`, `getTodayModuleOrder()`

**DB migration changes:**
- [`backend/migrations.py`](../backend/migrations.py): append `tagesbriefing`, `zugaenge`, `wichtige-termine` rows to `modules_seed` list

**Backend changes:**
- [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py): in `_fetch_base_data()`, read `app_title` from `system_settings`, add to `workspace` dict

**Version bump:** Increment `?v=` query strings on all `<script>` tags in [`index.html`](../index.html) to `?v=44`

**Expected result:** App loads, Today section opens by default, "Heute anpassen" drawer opens and saves layout changes, app title reflects admin-configured value, mandatory modules cannot be toggled off.

---

### Slice 2: Zugänge Module Card + Wichtige Termine Module

**Goal:** Both new Today module cards render with real data; ICS fetcher works server-side.

**New files:**
- `backend/wichtige_termine_adapter.py` — `fetch_wichtige_termine(ical_url, now) -> dict`
- `src/features/wichtige-termine.js` — `renderWichtigeTermine(container, data)`
- `src/features/zugaenge.js` — `renderZugaenge(container, links)`

**Files to change:**
- [`requirements.txt`](../requirements.txt) — add `icalendar>=5.0`
- [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py) — add `_fetch_wichtige_termine_data()` function; wire into `module_fetchers` dict in `get_dashboard_data()`; extend `_fetch_base_data()` to read `fehlzeiten_11_url`, `fehlzeiten_12_url`, `klassenarbeitsplan_url` and add to `quick_links` with `group` field
- [`index.html`](../index.html) — add `<div id="heute-wichtige-termine" class="module-card">` and `<div id="heute-zugaenge" class="module-card">` to `#heute` section; add `<script src="src/features/wichtige-termine.js?v=44">` and `<script src="src/features/zugaenge.js?v=44">` in correct load order
- [`src/app.js`](../src/app.js) — after data load, call `renderWichtigeTermine()` and `renderZugaenge()` with appropriate data slices

**Expected result:** Today view shows Wichtige Termine card (events from school ICS or empty state) and Zugänge launchpad (quick-access pills). Admin can set `wichtige_termine_ical_url` in the Einstellungen tab.

---

### Slice 3: Inbox Split + Pläne Split

**Goal:** Inbox has two clearly separated source tabs; Orgaplan and Klassenarbeitsplan appear as Today cards AND as separated sub-sections in Dokumente.

**Files to change:**
- [`src/features/inbox.js`](../src/features/inbox.js) — split render into `renderMailTab()` and `renderItslearningTab()`; add tab switching logic; add unread badge counts
- [`src/features/documents.js`](../src/features/documents.js) — add `renderOrgaplanCard(container, data)` and `renderKlassenarbeitsplanCard(container, data)` compact card renderers; update full-detail section render to use two sub-panels
- [`index.html`](../index.html) — add tab bar to `#inbox` section; add tab panels `#inbox-tab-mail` and `#inbox-tab-itslearning`; add sub-panels `#documents-orgaplan` and `#documents-klassenarbeitsplan` to `#documents` section; add Today cards `#heute-orgaplan` and `#heute-klassenarbeitsplan` to `#heute` section
- [`src/app.js`](../src/app.js) — call compact card renderers for Today section after data load

**Expected result:** Inbox shows Dienstmail / itslearning tabs with per-source message lists. Dokumente section shows Orgaplan and Klassenarbeitsplan as distinct sub-sections. Today view shows compact plan cards.

---

### Slice 4: Admin App Title + Nav Clarification

**Goal:** Admin can set app title; cockpit reflects it; admin UI has clean, labeled settings fields.

**Files to change:**
- [`admin.html`](../admin.html) — add "App-Titel / Schulname" input field at top of Einstellungen tab; add fields for `wichtige_termine_ical_url`, `fehlzeiten_11_url`, `fehlzeiten_12_url` to Einstellungen tab

**Functions to add/modify:**
- [`admin.html`](../admin.html) inline JS or linked admin JS — extend settings save handler to include `app_title` and new URL keys using existing `PUT /api/v2/admin/settings/<key>` pattern

**No backend changes needed** (endpoint already generic).

**Expected result:** Admin sets a custom title (e.g., "HES Lehrercockpit"); nav header, browser tab, and PWA display name update on next cockpit load.

---

### Slice 5: Stundenplan UX Improvements

**Goal:** Stundenplan section has day/week toggle and forward/back navigation within the current week.

**Files to change:**
- [`index.html`](../index.html) — add navigation row HTML to `#schedule` section: back/forward buttons, date label, today button, day/week toggle buttons, external link in footer
- [`src/features/webuntis.js`](../src/features/webuntis.js) — add local view state (`viewMode`, `selectedDate`); add `renderScheduleNav()` function; add event listeners for nav controls; implement day-mode filter (filter events for `selectedDate`); implement week-mode grid (5-column Mon–Fri); set `#webuntis-external-link` href from `base_url` config

**Out of scope for this slice:**
- Multi-week data fetching (requires new API call; deferred to future phase)
- Navigation beyond current week boundaries (buttons disabled at boundaries)
- Mobile-specific schedule rendering optimizations

**Expected result:** Stundenplan section shows day/week toggle; teacher can navigate between days in the current week; "In WebUntis öffnen" link appears when `base_url` is configured.

---

## Implementation Order Recommendation

**Start with Slice 1.**

Slice 1 establishes the foundational `heute` shell and the personalization persistence mechanism that every subsequent slice depends on. Without it, the Today section does not exist as a stable target for the module cards added in Slices 2 and 3, and the drawer has no modules to manage. Slice 1 also introduces the three new `modules` table rows (`tagesbriefing`, `zugaenge`, `wichtige-termine`) that must exist before any of those module cards can be gated through `DashboardManager.isModuleVisible()`. It involves zero new files and zero new API endpoints, making it the safest starting point — the app remains fully runnable throughout and the change is reversible by reverting the section ID rename.

