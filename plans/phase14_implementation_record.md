# Phase 14 Implementation Record
## Title: Today-First Refactor — All Slices

**Date:** 2026-03-30  
**Status:** ✅ Complete (Slices 1–4)  
**Design document:** [`plans/phase14_design.md`](phase14_design.md)

---

## Objective

Deliver a unified **Today view** that answers the three daily questions every teacher has at the start of the day: *What does my schedule look like? What needs my attention? Where do I need to go?*

Phase 14 spans four implementation slices, each leaving the application in a fully runnable state.

---

## Slice 1: Today Shell + Module Orchestration + Personalization

**Date:** 2026-03-30  
**Goal:** The overview section becomes heute; the "Heute anpassen" drawer works end-to-end; mandatory module enforcement in place.

### Files Changed

| File | Change |
|---|---|
| [`index.html`](../index.html) | Added `id="app-title-display"` on brand title; added "Heute anpassen" drawer HTML; added "Heute anpassen" trigger button; added `#heute-zugaenge-container` and `#heute-wichtige-termine-container` slots in overview grid |
| [`src/modules/dashboard-manager.js`](../src/modules/dashboard-manager.js) | Added `MANDATORY_MODULES` constant; added `isMandatoryModule(id)` method; `isModuleVisible()` hard-returns `true` for mandatory modules; added `getTodayModuleOrder()` method |
| [`src/app.js`](../src/app.js) | Updated `state.activeSection` default; added drawer open/close listeners; added `openHeuteAnpassenDrawer()`, `closeHeuteAnpassenDrawer()`, `renderHeuteAnpassenDrawer()`, `saveHeuteLayout()`; `renderTodayModuleLayout()` gated on `DashboardManager` |
| [`backend/migrations.py`](../backend/migrations.py) | Added `tagesbriefing`, `zugaenge`, `wichtige-termine` rows to `modules_seed` |
| [`backend/admin/bootstrap.py`](../backend/admin/bootstrap.py) | Seeded `app_title` key in `system_settings` |
| Script version bump | `?v=44` on all `<script>` tags in `index.html` |

---

## Slice 2: Zugänge Module Card + Wichtige Termine Module

**Date:** 2026-03-30  
**Goal:** Both new Today module cards render with real data; ICS fetcher works server-side.

### New Files

| File | Purpose |
|---|---|
| [`backend/wichtige_termine_adapter.py`](../backend/wichtige_termine_adapter.py) | `fetch_wichtige_termine(ical_url, now) -> WichtigeTermineResult` — parses iCal feed server-side |
| [`src/features/wichtige-termine.js`](../src/features/wichtige-termine.js) | `renderWichtigeTermine(container, data)` — handles loading/error/empty/data states |
| [`src/features/zugaenge.js`](../src/features/zugaenge.js) | `renderZugaenge(container, links)` — pill-based launchpad card |

### Files Changed

| File | Change |
|---|---|
| [`requirements.txt`](../requirements.txt) | Added `icalendar>=5.0` |
| [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py) | Added `_fetch_wichtige_termine_data()`; wired into `module_fetchers`; extended `_fetch_base_data()` to read `fehlzeiten_11_url`, `fehlzeiten_12_url`, `klassenarbeitsplan_url`, `webuntis_url` from `system_settings` |
| [`index.html`](../index.html) | Added `<div id="heute-zugaenge-container">` and `<div id="heute-wichtige-termine-container">` inside the overview grid; added `<script>` tags for new feature files |
| [`src/app.js`](../src/app.js) | Added `renderHeuteZugaenge()` and `renderHeuteWichtigeTermine()` calls in `renderAll()` |
| Script version bump | `?v=45` on all `<script>` tags in `index.html` |

---

## Slice 3: Inbox Split + Pläne Split

**Date:** 2026-03-30  
**Goal:** Inbox has two clearly separated source tabs; Orgaplan and Klassenarbeitsplan appear as separated sub-sections in Dokumente.

### Files Changed

| File | Change |
|---|---|
| [`src/features/inbox.js`](../src/features/inbox.js) | Added `initInboxTabs()` tab-switching logic; added `renderBadges()` for per-tab unread counts; added `renderItslearningTab()` sub-renderer |
| [`src/features/documents.js`](../src/features/documents.js) | Updated render logic to use two sub-panels `#plans-block-orgaplan` and `#plans-block-klassenarbeitsplan` |
| [`index.html`](../index.html) | Added tab bar (`Dienstmail` / `itslearning`) to `#inbox-section`; added `#inbox-tab-mail` and `#inbox-tab-itslearning` panels; added `#plans-block-orgaplan` and `#plans-block-klassenarbeitsplan` sub-panels to `#documents-section` |
| [`src/app.js`](../src/app.js) | Calls `LehrerInbox.initInboxTabs()` and `LehrerInbox.renderBadges()` after `renderAll()` |
| Script version bump | `?v=45` on all `<script>` tags in `index.html` |

---

## Slice 4: Admin App Title + New Settings Fields + Nav Clarification

**Date:** 2026-03-30  
**Goal:** Admin can set app title; cockpit reflects it; admin UI has clean settings fields for all new URL settings; nav labels match spec.

### Files Changed

#### `backend/api/dashboard_routes.py`

- **`_fetch_base_data()`**: Added `app_title = _safe_str(get_system_setting(conn, "app_title", ""))` alongside the existing URL reads.
- **`workspace` dict**: Added `"app_title": app_title or "Lehrercockpit"` to the workspace sub-section.
- **`_fetch_base_data()` return dict**: Added `"app_title": app_title or "Lehrercockpit"` at the top-level `data` dict for direct access.
- **`base_section` in `get_dashboard_data()`**: Passes `app_title` through from `base_data` into the API response at `base.app_title`.

#### `index.html`

- **`id="app-title-display"`** added to `<strong class="brand-title">` in sidebar brand block so JS can update it dynamically.
- **Nav label fixed**: `data-section-target="inbox"` button label changed from `"Inbox"` → `"Posteingang"` (all other labels were already correct per spec).
- **WebUntis external link**: Added `<a id="webuntis-open-btn" class="secondary-link webuntis-external-link" href="#" target="_blank" rel="noopener noreferrer" hidden>In WebUntis öffnen ↗</a>` inside the `[data-view-section="schedule"]` toolbar actions.
- **Script version**: All `?v=45` bumped to `?v=46`.

#### `src/app.js`

- **`applyAppTitle()`** new function: reads `state.data?.base?.app_title`, falls back to `'Lehrercockpit'`; sets `document.title` and updates `#app-title-display` text content.
- **`updateWebUntisExternalLink()`** new function: reads `state.data?.base?.webuntis_url`; shows/hides `#webuntis-open-btn` and sets its `href`.
- Both functions called in **`refreshDashboard()`** after `renderAll()`, covering both the success path and the fallback path.

#### `admin.html`

- **Einstellungen form — new fields added (top to bottom)**:
  1. `s-app-title` — Anwendungstitel (`app_title`), text input, maxlength 60, with helper text
  2. `s-webuntis-url` — WebUntis URL (`webuntis_url`), url input
  3. `s-fehlzeiten-11` — Fehlzeiten 11. Klasse URL (`fehlzeiten_11_url`), url input
  4. `s-fehlzeiten-12` — Fehlzeiten 12. Klasse URL (`fehlzeiten_12_url`), url input
  5. `s-wichtige-termine-ical` — Wichtige Termine iCal URL (`wichtige_termine_ical_url`), url input
- **`loadSettings()`**: Extended to populate all five new input fields from the `GET /api/v2/admin/settings` response.
- **Settings form `submit` handler**: Extended payload to include `app_title`, `webuntis_url`, `fehlzeiten_11_url`, `fehlzeiten_12_url`, `wichtige_termine_ical_url`. All keys saved via existing `PUT /api/v2/admin/settings` endpoint (no new endpoint needed — backend is already generic KV store).

---

## Nav Label Audit (Part C)

| `data-section-target` | Label found | Label required | Changed? |
|---|---|---|---|
| `overview` | `Heute` | **Heute** | No |
| `schedule` | `Stundenplan` | **Stundenplan** | No |
| `inbox` | `Inbox` | **Posteingang** | **Yes** |
| `documents` | `Pläne` | **Pläne** | No |
| `access` | `Zugänge` | **Zugänge** | No |
| `assistant` | `Assistenz` | **Assistenz** | No |

---

## `app_title` End-to-End Wire

| Layer | Location | What it does |
|---|---|---|
| DB | `system_settings` table, key `app_title` | Stored as string value |
| Backend read | `_fetch_base_data()` in `dashboard_routes.py` | Reads from DB, falls back to `""`, includes in `workspace.app_title` and top-level `data.app_title` |
| API response | `GET /api/v2/dashboard/data` → `base.app_title` | String, default `"Lehrercockpit"` |
| Frontend normalization | `normalizeV2Dashboard()` in `app.js` | `data.base = v2.base` preserves `app_title` at `state.data.base.app_title` |
| Frontend display | `applyAppTitle()` in `app.js` | Sets `document.title` + `#app-title-display` text content |
| Admin write | `admin.html` settings form | `PUT /api/v2/admin/settings` with `key=app_title, value=<string>` |
| Admin read | `loadSettings()` in `admin.html` | Populates `#s-app-title` input from `GET /api/v2/admin/settings` |

---

## Deferred / Out of Scope

| Item | Reason |
|---|---|
| Slice 5 (Stundenplan day/week toggle + multi-week navigation) | Deferred — requires additional frontend state machine in `webuntis.js` |
| PWA manifest `name` / `short_name` dynamic update | Not possible — manifest must be static; remains `"Lehrercockpit"` |
| `base.documents` in v2 response | Still returns `null` — requires `document_monitor` pipeline (deferred since Phase 12) |
| `app_title` seeded as default in migrations | No seed value — empty by default; frontend/backend both fall back to `"Lehrercockpit"` |

---

## Known Limitations

- `applyAppTitle()` and `updateWebUntisExternalLink()` are only called when the v2 primary path succeeds (or fallback data is present). In the v1 fallback path (local runtime), `app_title` and `webuntis_url` are not available; the defaults (`"Lehrercockpit"`, button hidden) apply.
- The `PUT /api/v2/admin/settings` endpoint accepts the entire settings payload as a single object. The backend currently saves all keys in a single call using the bulk `PUT /settings` route. Per-key `PUT /settings/<key>` is also available but not used here — no behavioral difference.
- `webuntis_url` in `base_section` is the *system-level* WebUntis URL configured by admin. The per-user `base_url` in WebUntis module config (used by `webuntis.js` for the iCal link) remains separate.

---

## Verification

```
python3 -m py_compile backend/api/dashboard_routes.py  → OK
python3 -m pytest tests/ → all passed (no new failures)
```

Script version on all `<script>` tags in `index.html`: `?v=46`

---

## Section 7: Edge Cases

### 7.1 No optional modules enabled

If the user has toggled off every optional module via "Heute anpassen", [`src/modules/dashboard-manager.js`](../src/modules/dashboard-manager.js) still hard-returns `true` from `isMandatoryModule()` for `tagesbriefing` and `zugaenge`. The `renderTodayModuleLayout()` path in [`src/app.js`](../src/app.js) always injects these two cards regardless of the user's stored layout. The Today view therefore always shows at least the Tagesbriefing and Zugänge cards. No empty-section error occurs. A small info note ("Alle optionalen Module ausgeblendet") is rendered below the mandatory cards to indicate the state.

### 7.2 Legacy users with no saved Today layout

Users who existed before Slice 1 have no `user_modules` rows for `tagesbriefing`, `zugaenge`, or `wichtige-termine`. The `_inject_mandatory_modules()` helper in [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py) detects this by checking whether the mandatory module IDs are already present in the fetched layout. If they are absent, it prepends them with `is_visible: true` and a sort order of `0` / `1` before returning the layout to the frontend. This ensures legacy users immediately see a well-formed Today view on their first page load after the migration, without any database write at read-time.

### 7.3 Failure to fetch ICS (Wichtige Termine)

If `fetch_wichtige_termine()` in [`backend/wichtige_termine_adapter.py`](../backend/wichtige_termine_adapter.py) cannot reach the ICS URL (network error, timeout, HTTP error), it returns `WichtigeTermineResult(ok=False, error="…")`. The `_fetch_wichtige_termine_data()` function in [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py) passes this result through to the module payload with `"ok": false`. On the frontend, [`src/features/wichtige-termine.js`](../src/features/wichtige-termine.js) detects `data.ok === false` and renders the card's error-state shell — a red status badge and a human-readable error message — instead of the event list. The card shell (header/footer) is still shown so the section doesn't collapse.

### 7.4 Malformed ICS

The `_build_event()` helper in [`backend/wichtige_termine_adapter.py`](../backend/wichtige_termine_adapter.py) wraps each VEVENT component in a `try/except`. Any event that is missing required fields (e.g., `DTSTART`, `SUMMARY`) or has an unparseable date format is silently skipped. The adapter accumulates all successfully parsed events and returns them. If zero events parse successfully, `WichtigeTermineResult(ok=True, today_events=[], upcoming_events=[])` is returned. This is treated as the "no events" empty state rather than an error.

### 7.5 No events today (Wichtige Termine)

When `today_events` is an empty list but `upcoming_events` may still contain future items, [`src/features/wichtige-termine.js`](../src/features/wichtige-termine.js) renders the today-events sub-section with the empty-state message "Heute keine besonderen Termine" and then renders the upcoming events list normally beneath it. The module is not hidden; the card remains visible to signal that the calendar is connected and no events are scheduled for today.

### 7.6 Multiple all-day and timed events on same day

The [`backend/wichtige_termine_adapter.py`](../backend/wichtige_termine_adapter.py) distinguishes all-day events (those whose `DTSTART` is a `date` instance, not `datetime`) from timed events. Both types are included in `today_events` and `upcoming_events`. The [`src/features/wichtige-termine.js`](../src/features/wichtige-termine.js) renderer applies an `"all-day"` CSS class and an "Ganztägig" badge to all-day entries, and renders the start time (formatted as `HH:MM`) for timed events. Multiple events of both types on the same day are all rendered in sequence with their respective badges.

### 7.7 Partially configured integrations (Zugänge)

[`src/features/zugaenge.js`](../src/features/zugaenge.js) receives the `links` object from `base` in the dashboard response. Any link whose URL value is `null`, `undefined`, or an empty string is rendered as a muted, non-clickable `<span>` element with a "Nicht konfiguriert" style rather than an `<a>` anchor. Configured links are rendered as active pill anchors. This allows the Zugänge card to remain useful even when only some integrations are set up, while making the unconfigured state visually obvious.

### 7.8 Source items missing deep links (inbox messages)

If an inbox message from itslearning or Dienstmail does not carry a per-message deep-link URL, [`src/features/inbox.js`](../src/features/inbox.js) falls back to the source base URL: `itslearning_base_url` from `base` for itslearning items, and the default Dienstmail host for mail items. The "Öffnen" action on the message card points to the root of the source system rather than the specific message. This is noted as a known limitation (see Section 9.4).

### 7.9 External systems unavailable

When a module fetcher (e.g., WebUntis, itslearning) returns `ok: false` due to an unreachable external system, the dashboard response still carries the module's data payload, set to `{"ok": false, "error": "…", "mode": "error"}`. The frontend feature renderer (e.g., [`src/features/webuntis.js`](../src/features/webuntis.js), [`src/features/wichtige-termine.js`](../src/features/wichtige-termine.js)) checks `data.ok` first and renders the card's error-state template — a status badge in red and the error message — rather than the data template. Other modules on the page are unaffected.

### 7.10 Admin title unset or blank

In [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py), `_fetch_base_data()` reads `app_title` from `system_settings` and applies `app_title or "Lehrercockpit"` before writing it to the response dict, so a `null` or empty DB value is always replaced with the default. On the frontend, [`src/app.js`](../src/app.js) `applyAppTitle()` reads `state.data?.base?.app_title` and applies `|| 'Lehrercockpit'` as a second guard, so even if the API value somehow arrives empty, `document.title` and `#app-title-display` always display the fallback string.

### 7.11 Viewport / mobile constraints

Today modules stack vertically via CSS `flex-direction: column` on small viewports. The Zugänge pill grid wraps to multiple rows via `flex-wrap: wrap`. The "Heute anpassen" panel is rendered as a fixed-position drawer with a hard-coded width of `320px`. On viewports narrower than ~360 px, the panel may overflow or require horizontal scroll. **This is a known limitation** — no responsive breakpoint was added for the panel in this phase (see Section 9.2).

### 7.12 `webuntis_url` not configured

The `<a id="webuntis-open-btn">` element in [`index.html`](../index.html) is rendered with the `hidden` attribute by default. [`src/app.js`](../src/app.js) `updateWebUntisExternalLink()` checks `state.data?.base?.webuntis_url`: if the value is falsy, the button remains hidden and its `href` is not set. Only when a non-empty URL is returned from the backend is the `hidden` attribute removed and the `href` assigned. This prevents a broken link from appearing in the Stundenplan toolbar.

---

## Section 8: Acceptance Criteria

### Today Screen

| ID | Description — Expected behavior |
|---|---|
| AC-TODAY-1 | When a logged-in user navigates to the Heute section, the Tagesbriefing card is always visible regardless of the user's saved layout. |
| AC-TODAY-2 | When a logged-in user navigates to the Heute section, the Zugänge card is always visible regardless of the user's saved layout. |
| AC-TODAY-3 | When a logged-in user has optional modules (e.g., Wichtige Termine) enabled, those cards appear below the mandatory cards in the configured sort order. |
| AC-TODAY-4 | When a user saves a layout change via "Heute anpassen", the new layout is reflected immediately on the Today view without a page reload. |
| AC-TODAY-5 | When all optional modules are disabled, the Today view still renders with Tagesbriefing and Zugänge and shows the "Alle optionalen Module ausgeblendet" info note. |

### Heute Anpassen Panel

| ID | Description — Expected behavior |
|---|---|
| AC-HEUTE-1 | Clicking the "Heute anpassen" button opens the right-side drawer panel; clicking ✕ or "Abbrechen" closes it without saving changes. |
| AC-HEUTE-2 | Mandatory modules (Tagesbriefing, Zugänge) appear in the panel with a lock icon and "Immer sichtbar" label; their toggles are absent or disabled. |
| AC-HEUTE-3 | Clicking "Speichern" in the panel fires `PUT /api/v2/dashboard/heute-layout`; the drawer closes and the Today layout re-renders from the server response. |
| AC-HEUTE-4 | The saved layout persists across page reloads — re-opening the cockpit shows the same module configuration the user last saved. |

### Zugänge

| ID | Description — Expected behavior |
|---|---|
| AC-ZUGAENGE-1 | The Zugänge card renders all configured quick-access links as active pill anchors that open in a new tab. |
| AC-ZUGAENGE-2 | Links are grouped by category (e.g., Schule, Tools, Dokumente) with a visible group label. |
| AC-ZUGAENGE-3 | A link whose URL is not configured in admin settings is rendered as a muted, non-clickable span rather than a broken anchor. |

### Wichtige Termine

| ID | Description — Expected behavior |
|---|---|
| AC-TERMINE-1 | When `wichtige_termine_ical_url` is set and the ICS feed is reachable, the card renders today's events and the next upcoming events. |
| AC-TERMINE-2 | All-day events display a "Ganztägig" badge; timed events display their start time (HH:MM format). |
| AC-TERMINE-3 | When the ICS feed is unreachable or returns an HTTP error, the card renders an error state with a descriptive message; other cards are unaffected. |
| AC-TERMINE-4 | When today has no events, the card renders the "Heute keine besonderen Termine" empty-state message and still shows upcoming events if present. |
| AC-TERMINE-5 | When no ICS URL is configured, the Wichtige Termine module is not fetched; the card renders a "Nicht konfiguriert" placeholder. |

### Navigation

| ID | Description — Expected behavior |
|---|---|
| AC-NAV-1 | The sidebar navigation item that shows/hides the inbox section is labelled "Posteingang" (not "Inbox"). |
| AC-NAV-2 | All other nav labels match the spec: Heute, Stundenplan, Pläne, Zugänge, Assistenz. |
| AC-NAV-3 | Clicking every nav item correctly switches to the intended section (existing `data-section-target` + `data-view-section` wiring remains functional). |

### Inbox

| ID | Description — Expected behavior |
|---|---|
| AC-INBOX-1 | The inbox section displays two tabs: "Dienstmail" and "itslearning"; clicking each tab switches the visible panel without a page reload. |
| AC-INBOX-2 | Each tab label shows an unread-count badge when the respective source has unread items; the badge disappears when count is zero. |
| AC-INBOX-3 | The Dienstmail tab renders mail messages from `base.mail` with sender, subject, and date. |
| AC-INBOX-4 | The itslearning tab renders notifications from `base.itslearning` with title, course context, and a link to the source. |

### Pläne

| ID | Description — Expected behavior |
|---|---|
| AC-PLAENE-1 | The documents section renders Orgaplan and Klassenarbeitsplan as separate, independently styled sub-panel cards (`#plans-block-orgaplan`, `#plans-block-klassenarbeitsplan`). |
| AC-PLAENE-2 | Existing DOM IDs and `data-view-section` attributes in the documents section are preserved so that any existing deep-links or tests continue to work. |

### Admin Settings

| ID | Description — Expected behavior |
|---|---|
| AC-ADMIN-1 | An admin who enters a school name in the "Anwendungstitel" field and saves it sees that name appear in the cockpit sidebar brand and browser tab on next load. |
| AC-ADMIN-2 | The admin settings form loads all five new fields (`app_title`, `webuntis_url`, `fehlzeiten_11_url`, `fehlzeiten_12_url`, `wichtige_termine_ical_url`) pre-populated from the stored values on page open. |
| AC-ADMIN-3 | Saving the settings form persists all five new fields via `PUT /api/v2/admin/settings`; a subsequent page reload of the cockpit reflects the saved values. |
| AC-ADMIN-4 | Leaving "Anwendungstitel" blank results in the cockpit displaying the fallback label "Lehrercockpit" rather than an empty title. |

### Stundenplan

| ID | Description — Expected behavior |
|---|---|
| AC-STUNDENPLAN-1 | When `webuntis_url` is set in admin settings, the "In WebUntis öffnen ↗" button appears in the Stundenplan toolbar; when it is unset, the button is hidden. |

---

## Section 9: Post-Implementation Review

### 9.1 What Was Completed (Shipped)

All four implementation slices were completed on 2026-03-30:

**Slice 1 — Today Shell + Module Orchestration + Personalization**
- `MANDATORY_MODULE_IDS` constant, `isMandatoryModule()`, `getModules()`, and `saveHeuteLayout()` added to [`src/modules/dashboard-manager.js`](../src/modules/dashboard-manager.js)
- `_inject_mandatory_modules()` and `PUT /api/v2/dashboard/heute-layout` added to [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py)
- Migration seed for `tagesbriefing`, `zugaenge`, `wichtige-termine` in [`backend/migrations.py`](../backend/migrations.py)
- `initHeuteAnpassen()` open/close/save/render drawer logic in [`src/app.js`](../src/app.js)
- `#heute-anpassen-btn` + `#heute-anpassen-panel` HTML in [`index.html`](../index.html)
- Heute anpassen panel CSS in [`styles.css`](../styles.css)

**Slice 2 — Zugänge + Wichtige Termine**
- New file [`src/features/zugaenge.js`](../src/features/zugaenge.js) — `window.LehrerZugaenge` pill-based launchpad
- New file [`src/features/wichtige-termine.js`](../src/features/wichtige-termine.js) — `window.LehrerWichtigeTermine` calendar module
- New file [`backend/wichtige_termine_adapter.py`](../backend/wichtige_termine_adapter.py) — stdlib iCal parser, no external dependencies
- `_fetch_wichtige_termine_data()` wired into `module_fetchers` in [`backend/api/dashboard_routes.py`](../backend/api/dashboard_routes.py)
- `renderHeuteZugaenge()` and `renderHeuteWichtigeTermine()` added to [`src/app.js`](../src/app.js)
- Module card shell CSS, Zugänge pill grid CSS, Wichtige Termine event CSS added to [`styles.css`](../styles.css)

**Slice 3 — Inbox Split + Pläne Split**
- `initInboxTabs()`, `renderBadges()`, `renderItslearningTab()` added to [`src/features/inbox.js`](../src/features/inbox.js)
- Inbox tab bar (Dienstmail / itslearning) and dual tab panels added to [`index.html`](../index.html)
- `#plans-block-orgaplan` and `#plans-block-klassenarbeitsplan` sub-panels added to [`index.html`](../index.html)
- Inbox tab CSS and plans-block CSS added to [`styles.css`](../styles.css)

**Slice 4 — Admin App Title + Nav Clarification**
- `app_title` read from `system_settings` in `_fetch_base_data()` and surfaced at `base.app_title` in the API response
- `applyAppTitle()` and `updateWebUntisExternalLink()` added to [`src/app.js`](../src/app.js)
- Five new settings fields added to [`admin.html`](../admin.html) with `loadSettings()` and save handler extended
- "Inbox" → "Posteingang" nav label fixed in [`index.html`](../index.html)
- `#webuntis-open-btn` external link added to the Stundenplan toolbar in [`index.html`](../index.html)

The implementation stays entirely within the existing architecture: vanilla JS with no build step, Flask 3.x blueprints, PostgreSQL with the existing KV `system_settings` pattern. The only new server-side file (`wichtige_termine_adapter.py`) uses only Python standard library (`urllib.request`, `datetime`, string parsing) — no new pip packages were introduced.

---

### 9.2 What Was Deferred (Not MVP)

| Item | Status |
|---|---|
| Stundenplan multi-week navigation | Deferred — within-week view only shipped; multi-week requires additional state machine in [`src/features/webuntis.js`](../src/features/webuntis.js) |
| Mobile / responsive optimization of Heute anpassen panel | Deferred — panel is fixed at 320 px width; may overflow on viewports narrower than ~360 px |
| Drag-and-drop reordering of optional modules | Deferred — "Heute anpassen" uses checkboxes only; no drag handle or reorder UX |
| Per-message deep-link "Öffnen" button in inbox | Deferred — message cards link to the source base URL, not the individual message |
| Grades section | Not shipped — `isSectionEnabled('grades')` returns `false`; section remains hidden |
| Service worker / offline support | Not in scope — no PWA offline capability added |

---

### 9.3 Architecture Respect

- **No new frameworks** — the frontend remains vanilla JS with no build toolchain; the backend remains Flask 3.x.
- **No new external dependencies** — `wichtige_termine_adapter.py` uses only Python stdlib (`urllib.request`, `datetime`). The `icalendar` entry added to `requirements.txt` was reverted in favour of the stdlib parser; no third-party iCal library is used.
- **Idempotent migrations** — all new `modules` seed rows use `INSERT … ON CONFLICT DO NOTHING`; `ADD COLUMN IF NOT EXISTS` pattern followed throughout [`backend/migrations.py`](../backend/migrations.py).
- **Script cache-busters maintained** — all `<script>` tags in [`index.html`](../index.html) end on `?v=46` after Slice 4.
- **No legacy v1 routes removed** — `GET /api/dashboard` (v1) and the existing v2 layout endpoints remain untouched.
- **Auth / CORS / session untouched** — no changes to [`backend/auth/`](../backend/auth/), [`backend/api/auth_routes.py`](../backend/api/auth_routes.py), or the session cookie mechanism.
- **`users.id` serial integer preserved** — no schema changes to the `users` table.

---

### 9.4 Technical Debt Not Addressed

| Item | Notes |
|---|---|
| `server.py` (local dev) still doesn't support v2 blueprints | Local dev falls back to v1 mock data; v2 routes only work via `app.py` / Gunicorn |
| `GET /api/dashboard` v1 fallback still called in `loadDashboard()` | [`src/app.js`](../src/app.js) still has the v1 fallback path; it is never the primary path in production but adds code noise |
| `base.documents` in v2 dashboard response still returns `null` | Deferred since Phase 12; requires `document_monitor` pipeline to be wired in |
| [`src/app.js`](../src/app.js) remains monolithic at ~3000 lines | Only additive changes were made in this phase; no extraction or decomposition was performed |
| No automated tests for the new frontend JS modules | `zugaenge.js`, `wichtige-termine.js`, and the Heute anpassen logic in `app.js` have no unit tests |

---

### 9.5 Follow-up Improvements (Outside MVP)

The following items are out of scope for Phase 14 but are good candidates for a follow-up phase:

- **Drag-to-reorder Today modules** — add drag handle and `PUT /api/v2/dashboard/heute-layout` sort-order persistence in the Heute anpassen panel.
- **Per-message deep links in inbox** — pass per-message `url` from adapters and render an "Öffnen" button on each inbox card.
- **Stundenplan multi-week navigation** — add previous/next week controls and a week-offset state to [`src/features/webuntis.js`](../src/features/webuntis.js).
- **Wichtige Termine month/category view** — expand the calendar card to support a monthly list view and event-type filtering.
- **Responsive Heute anpassen panel** — replace the fixed `320px` width with a responsive drawer that stacks full-width on narrow viewports.
- **`app.js` decomposition** — extract the Today-specific render functions into a dedicated `src/features/today.js` module as a first step toward breaking up the ~3000-line monolith.
- **Test coverage for `wichtige_termine_adapter.py`** — add pytest fixtures with sample ICS strings covering all-day events, timed events, multi-day events, and malformed VEVENT components.
