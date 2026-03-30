# Lehrercockpit — Consistency Audit
Date: 2026-03-30

---

## 1. Systemübersicht

**Lehrercockpit** ist ein multi-user SaaS-fähiges Lehrer-Dashboard.

| Schicht | Technologie | Status |
|---|---|---|
| Frontend | Vanilla HTML/CSS/JS, kein Framework, kein Bundler | Produktiv, Netlify |
| Backend | Python 3.11, Flask 3.x, gunicorn | Produktiv, Render/Docker |
| Datenbank | PostgreSQL via psycopg3 | Produktiv, Render |
| Auth | Session-Cookie (`lc_session`), Argon2-Hash, Access-Code | Aktiv, MULTIUSER_ENABLED=true |
| Deployment | Frontend: Netlify static, Backend: Render Docker | Produktiv |

**Aktueller Code-Stand:** Phase 14 Today-First Refactor vollständig integriert. 418 Tests bestanden, 110 übersprungen (DB-abhängig), 0 Fehler.

---

## 2. Architekturkarte

### Frontend-Module (Ladereihenfolge, index.html:714–726)
```
data/mock-dashboard.js      ← Fallback-Daten
src/api-client.js           ← window.LehrerAPI
src/modules/dashboard-manager.js  ← window.DashboardManager
src/features/grades.js      ← window.LehrerGrades
src/features/webuntis.js    ← window.LehrerWebUntis
src/features/itslearning.js ← window.LehrerItslearning
src/features/nextcloud.js   ← window.LehrerNextcloud
src/features/documents.js   ← window.LehrerDocuments
src/features/classwork.js   ← window.LehrerClasswork
src/features/inbox.js       ← window.LehrerInbox
src/features/zugaenge.js    ← window.LehrerZugaenge
src/features/wichtige-termine.js ← window.LehrerWichtigeTermine
src/app.js                  ← bootstrapApp() IIFE (Hauptorchestrator)
```

### Backend-Blueprints (app.py:517–528)
```
/api/v2/auth/*       → auth_routes.py (auth_bp)
/api/v2/dashboard/*  → dashboard_routes.py (dashboard_bp)
/api/v2/modules/*    → module_routes.py (module_bp)
/api/v2/admin/*      → admin_routes.py (admin_bp)
/api/*               → Legacy v1 Endpunkte in app.py (DEPRECATED)
```

### Datenbank-Tabellen
`users`, `user_access_codes`, `sessions`, `modules`, `user_modules`, `user_module_configs`, `system_settings`, `grades`, `class_notes`, `app_state`, `audit_log`

### Dashboard-Datenfluss (v2, MULTIUSER_ENABLED=true)
```
checkAuth() → GET /api/v2/auth/me
            → GET /api/v2/dashboard/onboarding-status
DashboardManager.init() → GET /api/v2/dashboard (Layout)
loadDashboard() → GET /api/v2/dashboard/data (Alle Moduldaten + Base)
               → normalizeV2Dashboard()
               → renderAll()
```

---

## 3. Inkonsistenzen

---

### [I-001] Zwei konkurrierende Panel-Systeme: `#layout-panel-overlay` vs. `#heute-anpassen-panel`
- **Bereich:** frontend / layout
- **Symptom:** `index.html` enthält beide Panels (Zeilen 639–655 und 657–670). Nur das neue `#heute-anpassen-panel` ist aktiv verdrahtet. Das alte `#layout-panel-overlay` ist im HTML präsent, wird aber nie geöffnet.
- **Ursache:** Phase 14 hat ein neues Panel eingeführt, ohne das alte zu entfernen. `_wireSettingsButton()` in [`dashboard-manager.js:337`](src/modules/dashboard-manager.js:337) würde `#layout-panel-overlay` öffnen, wird aber **nirgends aufgerufen**. [`initHeuteAnpassen()`](src/app.js:2041) verdrahtet `#settings-button` mit `#heute-anpassen-panel`.
- **Betroffene Dateien:**
  - [`index.html:98`](index.html:98) — `#settings-button` (der Button)
  - [`index.html:639`](index.html:639) — `#layout-panel-overlay` (altes Panel, nie geöffnet)
  - [`index.html:657`](index.html:657) — `#heute-anpassen-panel` (neues Panel, aktiv)
  - [`src/modules/dashboard-manager.js:337`](src/modules/dashboard-manager.js:337) — `_wireSettingsButton()` (dead function)
  - [`src/app.js:2041`](src/app.js:2041) — `initHeuteAnpassen()` (aktive Verdrahtung)
- **Auswirkung:** `#layout-panel-overlay` ist toter HTML-Code; `_wireSettingsButton()` ist eine tote Funktion. Kein visueller Fehler, aber erhebliche kognitive Last beim Code-Lesen. Das alte Panel mit seinem komplexen Drag-and-Drop-Mechanismus (`_renderLayoutPanelContent()`, `_saveLayout()`) ist vollständig inaktiv.
- **Schweregrad:** P2

---

### [I-002] `overlayV2ModuleData()` ist tote Funktion
- **Bereich:** frontend / data flow
- **Symptom:** Die Funktion [`overlayV2ModuleData()`](src/app.js:393) ist in `app.js` definiert, wird aber im Produktions-Codepfad nie aufgerufen.
- **Ursache:** In Phase 11d wurde `overlayV2ModuleData()` für den v1-Fallback-Pfad eingeführt. In Phase 12 übernahm `normalizeV2Dashboard()` die vollständige v2-Normalisierung (einschließlich Overlay-Logik). Der v1-Fallback-Pfad in [`loadDashboard()`](src/app.js:280–314) ruft `overlayV2ModuleData()` nicht auf. Da `MULTIUSER_ENABLED=true` und `LehrerAPI` immer vorhanden ist, wird der v1-Pfad im Produktionsbetrieb nie erreicht.
- **Betroffene Dateien:**
  - [`src/app.js:393`](src/app.js:393) — `overlayV2ModuleData()` (never called in production)
  - [`src/app.js:266`](src/app.js:266) — `loadDashboard()` v2-Pfad (nutzt `normalizeV2Dashboard()` direkt)
- **Auswirkung:** ~50 Zeilen toter Code. Keine Fehler. Die private Overlay-Logik in `_applyWebuntisV2Data()`, `_applyItslearningV2Data()`, etc. ist funktional, wird aber über `normalizeV2Dashboard()` genutzt, nicht über `overlayV2ModuleData()`.
- **Schweregrad:** P3

---

### [I-003] `triggerClassworkUpload()` ist tote Funktion mit ungültigen Element-Referenzen
- **Bereich:** frontend / classwork
- **Symptom:** [`triggerClassworkUpload()`](src/app.js:2445) referenziert `elements.classworkUploadLabelText` und `elements.classworkUploadLabel` — weder im `elements`-Objekt ([`src/app.js:72`](src/app.js:72)) noch in [`index.html`](index.html) existieren diese IDs.
- **Ursache:** Überbleibsel eines älteren Upload-Mechanismus. Der aktive Pfad nutzt [`uploadClassworkFile()`](src/app.js:1881), verdrahtet durch den Event-Handler bei [`src/app.js:1643`](src/app.js:1643). `triggerClassworkUpload()` wird nirgendwo aufgerufen.
- **Betroffene Dateien:**
  - [`src/app.js:2445`](src/app.js:2445) — `triggerClassworkUpload()` (dead function, invalid element refs)
  - [`src/app.js:1643`](src/app.js:1643) — aktiver Upload-Eventhandler (ruft `uploadClassworkFile()` auf)
- **Auswirkung:** Kein visueller Fehler. Würde bei Aufruf jedoch `undefined.textContent` werfen. Konfusion beim Code-Lesen.
- **Schweregrad:** P3

---

### [I-004] `admin_service.get_user_overview()` berechnet `is_admin` aus dem `role`-Feld statt aus der `is_admin`-Spalte
- **Bereich:** backend / auth / admin
- **Symptom:** [`admin_service.py:370`](backend/admin/admin_service.py:370): `"is_admin": row[3] == "admin"` — nutzt die `role`-Spalte zur Berechnung, nicht die persistierte `is_admin`-Boolean-Spalte.
- **Ursache:** Phase 13 hat `is_admin` als separate DB-Spalte eingeführt. Das `get_user_overview()`-SQL-Query (Zeile 339) selektiert nur `id, first_name, last_name, role, is_active, created_at, updated_at, module_count, has_access_code` — die `is_admin`-Spalte fehlt im SELECT. Das daraus berechnete `"is_admin"` ist daher nur korrekt für Legacy-User (role='admin'). User mit `role='teacher'` + `is_admin=True` (kanonische Phase-13-Form) erscheinen im Admin-Dashboard als **nicht-admin**.
- **Betroffene Dateien:**
  - [`backend/admin/admin_service.py:339`](backend/admin/admin_service.py:339) — SQL fehlt `u.is_admin`
  - [`backend/admin/admin_service.py:370`](backend/admin/admin_service.py:370) — falsche Ableitung
  - [`backend/users/user_store.py:60`](backend/users/user_store.py:60) — `to_dict()` korrekt (nutzt `self.is_admin`)
- **Auswirkung:** Admin-UI zeigt Admins, die mit der kanonischen Phase-13-Form angelegt wurden, als normale Teacher. Da Bootstrap-Admin mit `role='teacher'`+`is_admin=True` angelegt wird ([`backend/admin/bootstrap.py:46`](backend/admin/bootstrap.py:46)), ist **der erste Bootstrap-Admin in der Übersicht als nicht-admin sichtbar**. Die `require_admin`-Middleware und Zugriffskontrolle sind davon NICHT betroffen (nutzen `user.is_admin` korrekt).
- **Schweregrad:** P1

---

### [I-005] `admin_service.create_teacher()` Wrapper akzeptiert keinen `is_admin`-Parameter
- **Bereich:** backend / admin
- **Symptom:** Der Wrapper [`admin_service.create_teacher()`](backend/admin/admin_service.py:296) akzeptiert keinen `is_admin`-Parameter und übergibt ihn nicht an `_create_teacher()`. Der kanonische `is_admin`-Pfad ist damit über diesen Wrapper nicht nutzbar.
- **Ursache:** Phase-13-Erweiterung hat `is_admin` zu `user_service.create_teacher()` hinzugefügt, aber den Admin-Service-Wrapper nicht aktualisiert.
- **Betroffene Dateien:**
  - [`backend/admin/admin_service.py:296`](backend/admin/admin_service.py:296) — fehlender `is_admin` Parameter
  - [`backend/api/admin_routes.py:116`](backend/api/admin_routes.py:116) — importiert korrekt `user_service.create_teacher` direkt (nicht den Wrapper)
  - [`backend/admin/bootstrap.py:46`](backend/admin/bootstrap.py:46) — importiert ebenfalls `user_service.create_teacher` direkt
- **Auswirkung:** Gering — der Wrapper wird in `admin_routes.py` und `bootstrap.py` nicht verwendet, beide nutzen `user_service.create_teacher` direkt. Kein aktiver Fehler. Jedoch irreführend und ein Risiko bei zukünftiger Nutzung des Wrappers.
- **Schweregrad:** P2

---

### [I-006] `#today-quick-link-grid` ist hidden, aber `renderQuickLinks()` schreibt weiterhin hinein
- **Bereich:** frontend / heute / layout
- **Symptom:** `index.html:128` markiert `#today-quick-link-grid` explizit als `hidden`. [`renderQuickLinks()`](src/app.js:1108) schreibt trotzdem HTML in dieses Element (Zeilen 1128–1143).
- **Ursache:** Phase 14 ersetzte das alte `#today-quick-link-grid` durch `#heute-zugaenge-container` (via `LehrerZugaenge`). Das alte Element wurde aus Kompatibilitätsgründen im HTML behalten (laut Kommentar: "kept hidden for JS compatibility"), ist aber für den User nie sichtbar.
- **Betroffene Dateien:**
  - [`index.html:127`](index.html:127) — Kommentar + `<div id="today-quick-link-grid" hidden>`
  - [`src/app.js:1128`](src/app.js:1128) — Rendering in hidden element
  - [`index.html:130`](index.html:130) — `#heute-zugaenge-container` (aktiver Ersatz)
- **Auswirkung:** Kein visueller Fehler. Leicht verwirrend — `renderQuickLinks()` leistet für Today-Ansicht Arbeit, die nie angezeigt wird. Das eigentliche Zugänge-Rendering erfolgt über `renderHeuteZugaenge()` → `LehrerZugaenge.render()`.
- **Schweregrad:** P3

---

### [I-007] Doppeltes Inbox-System: Tab-UI plus alter Channel-Filter-Buttons (hidden)
- **Bereich:** frontend / inbox
- **Symptom:** Zwei parallele Systeme steuern die Inbox-Anzeige: (1) neues Tab-UI in `index.html:201–220` (Slice 3) mit `renderItslearningTab()`, (2) altes `renderChannelFilters()` / `renderMessages()` mit `_state.selectedChannel`.
- **Ursache:** Der alte Kanal-Filter-Mechanismus (`#channel-filters` mit `data-channel`-Buttons) wurde nicht entfernt. `renderMessages()` rendert in `#message-list` basierend auf `_state.selectedChannel`. Das neue Tab-UI aktiviert `_activateTab()` was direkt `renderItslearningTab()` für `#message-list-itslearning` aufruft. Die `#channel-filters`-Div ist in index.html hidden (`<div id="channel-filters" class="filter-row" hidden>`).
- **Betroffene Dateien:**
  - [`index.html:196`](index.html:196) — `#channel-filters` (hidden, old system)
  - [`index.html:201`](index.html:201) — `.inbox-tabs` (new tab system)
  - [`src/features/inbox.js:123`](src/features/inbox.js:123) — `renderChannelFilters()` (schreibt in hidden Element)
  - [`src/features/inbox.js:155`](src/features/inbox.js:155) — `renderMessages()` (gefilterter Kanal-Mechanismus, weiterhin für `#message-list` aktiv)
  - [`src/features/inbox.js:309`](src/features/inbox.js:309) — `initInboxTabs()` (neues Tab-System)
- **Auswirkung:** `renderChannelFilters()` schreibt in ein hidden Element — kein visueller Effekt. `renderMessages()` rendert für `#message-list` korrekt (Mail-Tab). Die itslearning-Nachrichten werden korrekt in `#message-list-itslearning` gerendert. Funktionstüchtig, aber zwei sich überlappende Konzepte erhöhen die Komplexität.
- **Schweregrad:** P2

---

### [I-008] `_wireSettingsButton()` in DashboardManager ist tote Funktion
- **Bereich:** frontend / dashboard-manager
- **Symptom:** [`dashboard-manager.js:337`](src/modules/dashboard-manager.js:337) definiert `_wireSettingsButton()`, die `#settings-button` mit dem **alten** `#layout-panel-overlay` verdrahtet. Diese Funktion wird nirgendwo aufgerufen.
- **Ursache:** Phase 14 hat die Panel-Verdrahtung in [`initHeuteAnpassen()`](src/app.js:2041) in `app.js` verschoben. `_wireSettingsButton()` wurde in `_initAsync()` entfernt aber nicht gelöscht. Der Kommentar bei [`dashboard-manager.js:199`](src/modules/dashboard-manager.js:199) bestätigt die Absicht: "Note: #settings-button (old panel trigger) is intentionally kept hidden."
- **Betroffene Dateien:**
  - [`src/modules/dashboard-manager.js:337`](src/modules/dashboard-manager.js:337) — dead function
  - [`src/modules/dashboard-manager.js:199`](src/modules/dashboard-manager.js:199) — erläuternder Kommentar
- **Auswirkung:** Toter Code. `#settings-button` ist korrekt mit genau EINEM Panel verdrahtet (dem neuen `#heute-anpassen-panel`). Kein Fehler.
- **Schweregrad:** P3

---

### [I-009] `modules`-Seed fehlen `tagesbriefing` und `zugaenge` in Phase-1-Seed; beide werden in Phase-14-Migration nachgepflegt
- **Bereich:** backend / data / migrations
- **Symptom:** Die Phase-1-Seed-Daten in [`migrations.py:120`](backend/migrations.py:120) enthalten `itslearning`, `nextcloud`, `webuntis`, `orgaplan`, `klassenarbeitsplan`, `noten`, `mail` — aber NICHT `tagesbriefing`, `zugaenge`, `wichtige-termine`. Diese werden in `_migrate_seed_today_modules()` ([`migrations.py:248`](backend/migrations.py:248)) nachträglich geseedet.
- **Ursache:** Phase 14 hat neue zentrale Module eingeführt, was eine separate Migration erforderte. `run_all_migrations()` ruft beide Funktionen auf, ist also korrekt.
- **Betroffene Dateien:**
  - [`backend/migrations.py:120`](backend/migrations.py:120) — Phase-1-Seed (7 Module)
  - [`backend/migrations.py:248`](backend/migrations.py:248) — Phase-14-Seed (3 neue Module)
- **Auswirkung:** Kein Fehler bei normaler Migration. Problematisch nur wenn jemand `run_migrations()` ohne `_migrate_seed_today_modules()` aufruft — `tagesbriefing` und `zugaenge` fehlen dann. Da `run_all_migrations()` beide aufruft, ist das in der Praxis kein Problem.
- **Schweregrad:** P3

---

### [I-010] `wichtige-termine` hat `default_visible = FALSE` im Seed, aber `_MANDATORY_MODULE_DEFAULTS` in `dashboard_routes.py` behandelt es nicht als Mandatory
- **Bereich:** backend / frontend / module-system
- **Symptom:** `wichtige-termine` ist in der DB mit `default_visible = FALSE` ([`migrations.py:258`](backend/migrations.py:258)) geseedet. Im Frontend gibt `isModuleVisible('wichtige-termine')` `true` zurück, wenn das Modul im `_modules`-Array fehlt (vor `_layoutReady`). Nach dem Layout-Load ist der Wert korrekt `false` für nicht-aktivierte User.
- **Ursache:** Korrekt designed — `wichtige-termine` ist optional. Durch `_layoutReady` wird das Flash-of-visibility verhindert. Kein echter Bug.
- **Betroffene Dateien:**
  - [`backend/migrations.py:258`](backend/migrations.py:258) — `default_visible = FALSE`
  - [`src/modules/dashboard-manager.js:489`](src/modules/dashboard-manager.js:489) — `isModuleVisible()` default-true vor Layout-Load
  - [`src/app.js:1740`](src/app.js:1740) — `renderHeuteWichtigeTermine()` prüft `isModuleVisible('wichtige-termine')`
- **Auswirkung:** Keine. Das Design ist korrekt — `wichtige-termine` erscheint nicht bis der User es aktiviert.
- **Schweregrad:** P3 (informell)

---

### [I-011] `normalizeV2Dashboard()` propagiert nicht `v2.base.workspace.app_title` in `data.workspace`
- **Bereich:** frontend / data flow
- **Symptom:** `_fetch_base_data()` gibt `workspace.app_title` als Teil des workspace-Dicts zurück. `normalizeV2Dashboard()` mappt `v2.base.workspace` → `data.workspace`. `applyAppTitle()` liest jedoch `state.data.base.app_title` (nicht `state.data.workspace.app_title`).
- **Ursache:** Zwei verschiedene Lese-Pfade für `app_title`. Funktioniert weil `data.base = v2.base` explizit gesetzt wird ([`src/app.js:530`](src/app.js:530)).
- **Betroffene Dateien:**
  - [`src/app.js:530`](src/app.js:530) — `data.base = v2.base` (korrekt)
  - [`src/app.js:1790`](src/app.js:1790) — `applyAppTitle()` liest `state.data.base.app_title`
  - [`backend/api/dashboard_routes.py:491`](backend/api/dashboard_routes.py:491) — `workspace` enthält `app_title`
  - [`backend/api/dashboard_routes.py:534`](backend/api/dashboard_routes.py:534) — `app_title` auch direkt in `base_data` root-level
- **Auswirkung:** Keiner — `state.data.base.app_title` ist der korrekte Pfad und wird konsistent genutzt. Leichte Redundanz: `app_title` ist sowohl in `base.app_title` als auch in `base.workspace.app_title`.
- **Schweregrad:** P3 (informell)

---

### [I-012] CSS-Klassen `.heute-anpassen-bar` und `.heute-anpassen-trigger` sind orphaned
- **Bereich:** frontend / CSS
- **Symptom:** [`styles.css:3003`](styles.css:3003) definiert `.heute-anpassen-bar` und `.heute-anpassen-trigger`. Diese CSS-Klassen existieren in keinem HTML-Element in `index.html` oder anderen Seiten.
- **Ursache:** Frühe Phase-14-Implementation hat diese Klassen für eine geplante Bar-Variante des Heute-Anpassen-Triggers definiert. Der finale Design verwendet `#settings-button` mit `.secondary-link`-Klasse stattdessen.
- **Betroffene Dateien:**
  - [`styles.css:3003`](styles.css:3003) — `.heute-anpassen-bar` (orphaned)
  - [`styles.css:3010`](styles.css:3010) — `.heute-anpassen-trigger` (orphaned)
- **Auswirkung:** Kein visueller Fehler. ~25 Zeilen ungenutzter CSS.
- **Schweregrad:** P3

---

### [I-013] `module_routes.py` und `dashboard_routes.py` bieten BEIDE `/api/v2/dashboard/module-config/<id>` und `/api/v2/modules/<id>/config` — Doppelregistrierung
- **Bereich:** backend / api
- **Symptom:** Zwei separate Endpunkte implementieren dasselbe Modul-Konfigurations-Speichern:
  - `dashboard_routes.py`: `PUT /api/v2/dashboard/module-config/<module_id>` ([`dashboard_routes.py:291`](backend/api/dashboard_routes.py:291))
  - `module_routes.py`: `PUT /api/v2/modules/<module_id>/config` ([`module_routes.py:88`](backend/api/module_routes.py:88))
- **Ursache:** Organisches Wachstum — `dashboard_routes.py` hatte ursprünglich alle Config-Endpunkte, dann wurde `module_routes.py` eingeführt.
- **Betroffene Dateien:**
  - [`backend/api/dashboard_routes.py:291`](backend/api/dashboard_routes.py:291) — Duplizierter Endpunkt
  - [`backend/api/module_routes.py:88`](backend/api/module_routes.py:88) — Kanonischer Endpunkt
  - [`src/modules/dashboard-manager.js:312`](src/modules/dashboard-manager.js:312) — `_submitConfigForm()` nutzt `/api/v2/dashboard/module-config/<id>`
  - [`src/api-client.js:47`](src/api-client.js:47) — `saveModuleConfig` nutzt `/api/v2/modules/<id>/config`
- **Auswirkung:** Beide Endpunkte funktionieren. `dashboard-manager.js`-Inline-Config-Form nutzt den alten Pfad; alle Feature-Module nutzen den kanonischen neuen Pfad. Kein Fehler, aber zwei aktive Pfade für dieselbe Operation.
- **Schweregrad:** P2

---

### [I-014] `isSectionEnabled('grades')` hat keine Null-Guard für `DashboardManager`
- **Bereich:** frontend / module visibility
- **Symptom:** [`src/app.js:244`](src/app.js:244): `return DashboardManager.isModuleVisible('noten');` — direkte Referenz auf `DashboardManager` ohne Prüfung ob es null ist.
- **Ursache:** `DashboardManager` ist die erste JS-Datei nach `api-client.js`. Im Normalfall ist `window.DashboardManager` immer gesetzt bevor `app.js` läuft. Es gibt jedoch kein defensives Fallback.
- **Betroffene Dateien:**
  - [`src/app.js:244`](src/app.js:244) — fehlendes `DashboardManager &&`
  - [`src/app.js:212`](src/app.js:212) — `isModuleVisible()` hat korrekten Guard
- **Auswirkung:** Würde `TypeError` werfen wenn `dashboard-manager.js` nicht geladen hat. In der Praxis unwahrscheinlich (alle Skripte synchron geladen). Vergleiche: `isModuleVisible()` hat korrekte Guard-Logik bei Zeile 212.
- **Schweregrad:** P2

---

### [I-015] `app.js:saveItslearningCredentials()` (Fallback) ist dead code, da `LehrerItslearning` immer initialisiert
- **Bereich:** frontend / itslearning
- **Symptom:** [`src/app.js:1836`](src/app.js:1836): `async function saveItslearningCredentials()` hat einen Fallback-Body für den Fall, dass `LehrerItslearning` nicht verfügbar ist. Da `itslearning.js` immer geladen wird, ist dieser Code nie aktiv.
- **Ursache:** Phased extraction pattern — Fallbacks wurden bei der Extraktion eingefügt und nie bereinigt. Analog dazu: `renderItslearningConnector()`, `renderNextcloudConnector()`, etc. sind reine Delegierungs-Stubs.
- **Betroffene Dateien:**
  - [`src/app.js:1836`](src/app.js:1836) — `saveItslearningCredentials()` mit totem Fallback-Body
  - [`src/app.js:1198`](src/app.js:1198) — `renderItslearningConnector()` (sauberer Stub)
- **Auswirkung:** Der Fallback-Body enthält direkten API-Call-Code der mit dem v2-API-Pfad übereinstimmt — kein funktionaler Fehler, aber toter Code.
- **Schweregrad:** P3

---

### [I-016] `orgaplan_url` vs. `orgaplan_pdf_url` — inkonsistente Schlüssel-Nutzung
- **Bereich:** backend / system_settings
- **Symptom:** `_fetch_orgaplan_data()` liest beide `orgaplan_url` UND `orgaplan_pdf_url` aus system_settings. Die Admin-Konfiguration stellt `orgaplan_pdf_url` bereit. In `LehrerZugaenge.STATIC_LINKS` ist der configKey `orgaplan_pdf_url`. Aber `_fetch_base_data()` liest `orgaplan_pdf_url` für quick_links und Zugänge, während `_fetch_orgaplan_data()` einen Fallback zwischen beiden baut.
- **Ursache:** `orgaplan_pdf_url` ist der primäre Schlüssel; `orgaplan_url` ist ein potenzieller Alias ohne klare Dokumentation wann welcher zu setzen ist.
- **Betroffene Dateien:**
  - [`backend/api/dashboard_routes.py:606`](backend/api/dashboard_routes.py:606) — `orgaplan_url` und `orgaplan_pdf_url` gelesen
  - [`backend/api/dashboard_routes.py:441`](backend/api/dashboard_routes.py:441) — nur `orgaplan_pdf_url` für base_data
  - [`src/features/zugaenge.js:20`](src/features/zugaenge.js:20) — `configKey: 'orgaplan_pdf_url'`
- **Auswirkung:** Wenn Admin `orgaplan_url` setzt (ohne `_pdf_`), wird Orgaplan für den Digest geladen, aber Zugänge-Karte und Quick-Links zeigen keinen Link (weil `orgaplan_pdf_url` leer ist). Konfigurationsverwirrung.
- **Schweregrad:** P2

---

### [I-017] `wichtige-termine` hat keine `is_admin`-Prüfung für die Admin-konfigurierbare `wichtige_termine_ical_url`
- **Bereich:** backend / system_settings
- **Symptom:** `_fetch_wichtige_termine_data()` liest `wichtige_termine_ical_url` aus system_settings via `get_system_setting()`. Es gibt keinen Admin-seitigen Endpunkt in `admin_routes.py`, der diesen Schlüssel explizit dokumentiert oder exposes.
- **Ursache:** Neue system_setting-Schlüssel für Phase 14. Der Admin kann den Wert über `PUT /api/v2/admin/settings/wichtige_termine_ical_url` setzen (generischer Settings-Endpunkt), aber der Schlüssel wird nirgendwo in der Admin-UI explizit aufgeführt.
- **Betroffene Dateien:**
  - [`backend/api/dashboard_routes.py:548`](backend/api/dashboard_routes.py:548) — Liest `wichtige_termine_ical_url`
  - [`backend/api/admin_routes.py:470`](backend/api/admin_routes.py:470) — Generischer Settings-Endpunkt (setzt beliebige Keys)
- **Auswirkung:** Wenn Admin den iCal-Feed nicht kennt, bleibt der Default-HES-URL aktiv. Kein Fehler, aber der Key ist für Admins nicht auffindbar ohne Code-Lesen.
- **Schweregrad:** P3

---

### [I-018] `#sources-section` und `#stats-grid` in `index.html` sind tote HTML-Elemente
- **Bereich:** frontend / HTML
- **Symptom:**
  - `index.html:446-468`: `<section id="sources-section" hidden>` — mit `hidden`, enthält Source-List und Monitor-List. Wird mit `hidden` initialisiert; in `app.js` gibt es kein `renderSectionFocus`-Handling dafür.
  - `elements.statsGrid` in [`src/app.js:91`](src/app.js:91) referenziert `#stats-grid` — dieses Element existiert **nicht** in `index.html`.
- **Ursache:** `#sources-section` ist ein Überbleibsel aus Pre-Phase-12-Zeiten als Quellenstatus noch sichtbar war. `#stats-grid` war ebenfalls ein früheres Element. [`renderStats()`](src/app.js:754) prüft `if (!elements.statsGrid) return;` und returniert sofort — safe guard vorhanden.
- **Betroffene Dateien:**
  - [`index.html:446`](index.html:446) — `#sources-section` (immer hidden, nie angezeigt)
  - [`src/app.js:91`](src/app.js:91) — `elements.statsGrid = document.querySelector("#stats-grid")` (null, weil Element fehlt)
  - [`src/app.js:754`](src/app.js:754) — `renderStats()` (safe guard vorhanden)
- **Auswirkung:** `#sources-section` ist toter HTML-Code. `elements.statsGrid` ist immer `null`, `renderStats()` tut daher nichts. Kein Fehler.
- **Schweregrad:** P2

---

### [I-019] `app.js` enthält WebUntis-Picker-Hilfsfunktionen als tote Stubs neben vollständiger Implementierung in `webuntis.js`
- **Bereich:** frontend / webuntis / dead code
- **Symptom:** `app.js` enthält volle Implementierungen von: `getWebUntisPlans()`, `getPinnedPlans()`, `getActivePlan()`, `getActiveFinderEntity()`, `isPlanChipActive()`, `getPickerEntities()`, `getFavoriteEntities()`, `getGlobalPickerResults()`, `isEntityActive()`, `renderPickerItem()`, `bindPickerActions()`, `selectPlanById()`, `toggleFavorite()`, `closePicker()` — alle als eigenständige Funktionen (nicht nur Delegierungs-Stubs).
- **Ursache:** Phase 10c hat WebUntis in `webuntis.js` extrahiert. Die Original-Implementierungen in `app.js` wurden nicht entfernt, nur Delegierungs-Stubs wurden hinzugefügt. Die Stubs bei `renderWeekSchedule()`, `getWebUntisEvents()` etc. sind korrekte Stubs. Die Picker-Funktionen sind vollständige Doppelungen.
- **Betroffene Dateien:**
  - [`src/app.js:2561`](src/app.js:2561) — `getWebUntisPlans()` (toter Doppelgänger)
  - [`src/app.js:2577`](src/app.js:2577) — `getPinnedPlans()` (toter Doppelgänger)
  - und weitere Picker-Funktionen bis Zeile 2884
- **Auswirkung:** ~300 Zeilen toter Code. Die Stubs in `app.js` für `renderWebUntisControls()` etc. rufen korrekt `window.LehrerWebUntis.*` auf. Die Picker-Funktionen werden nicht aufgerufen (der Event-Handler in `app.js:1544-1580` verwendet den Stub-Pfad, der zu `LehrerWebUntis` delegiert).
- **Schweregrad:** P2

---

## 4. Priorisierte Probleme (P0/P1/P2/P3)

### P0 — Kritisch (Produktionsbruch oder Datenverlust)
*Keine P0-Probleme gefunden.*

### P1 — Hoch (Funktional falsch, Nutzer betroffen)

| ID | Titel |
|---|---|
| [I-004] | `get_user_overview()` berechnet `is_admin` aus `role`-Feld — Admin-Dashboard zeigt kanonische Admins falsch |

### P2 — Mittel (Inkonsistenz, potentielles Problem bei Weiterentwicklung)

| ID | Titel |
|---|---|
| [I-001] | Zwei Panel-Systeme im HTML — altes `#layout-panel-overlay` nie geöffnet |
| [I-005] | `admin_service.create_teacher()` Wrapper ohne `is_admin`-Parameter |
| [I-007] | Doppeltes Inbox-System: Tab-UI + alter Channel-Filter (hidden) |
| [I-013] | Zwei API-Pfade für Modul-Konfig: `/dashboard/module-config/` und `/modules/<id>/config` |
| [I-014] | `isSectionEnabled('grades')` ohne Null-Guard für `DashboardManager` |
| [I-016] | `orgaplan_url` vs. `orgaplan_pdf_url` — inkonsistente Schlüssel |
| [I-018] | `#sources-section` immer hidden; `#stats-grid` fehlt in HTML |
| [I-019] | WebUntis-Picker-Funktionen als Doppelungen in `app.js` (~300 Zeilen) |

### P3 — Niedrig (Toter Code, CSS-Orphans, minimales Risiko)

| ID | Titel |
|---|---|
| [I-002] | `overlayV2ModuleData()` nie aufgerufen |
| [I-003] | `triggerClassworkUpload()` nie aufgerufen, ungültige Element-Referenzen |
| [I-006] | `renderQuickLinks()` schreibt in hidden `#today-quick-link-grid` |
| [I-008] | `_wireSettingsButton()` in DashboardManager ist dead function |
| [I-009] | `modules`-Seed aufgeteilt auf zwei Migrations-Funktionen |
| [I-010] | `wichtige-termine` default_visible=FALSE — korrekt designed |
| [I-011] | `app_title` redundant in `base.workspace.app_title` und `base.app_title` |
| [I-012] | CSS `.heute-anpassen-bar` und `.heute-anpassen-trigger` orphaned |
| [I-015] | `saveItslearningCredentials()` Fallback-Body nie erreicht |
| [I-017] | `wichtige_termine_ical_url` System-Setting nicht in Admin-UI exponiert |

---

## 5. Root-Cause-Muster

### Muster A: Additive Phase-Entwicklung ohne Bereinigung
Die Phasen 8–14 haben Features durch Extraktion und Ergänzung entwickelt, ohne systematisch toten Code zu entfernen. Dies betrifft:
- Extrahierte Feature-Funktionen verbleiben als Vollimplementierungen in `app.js` (WebUntis-Picker, Zeilen ~2560–2884)
- Delegierungs-Stubs koexistieren mit alten Fallback-Implementierungen
- Phase-14-Panel-Wechsel ließ altes Panel und tote `_wireSettingsButton()`-Funktion zurück

### Muster B: Phase-13-Migration nicht vollständig propagiert
Der `is_admin`-Boolean-Spalten-Wechsel (Phase 13) wurde nicht in alle Stellen propagiert:
- `admin_service.get_user_overview()` nutzt immer noch `role == "admin"` statt die `is_admin`-Spalte
- `admin_service.create_teacher()` Wrapper wurde nicht erweitert

### Muster C: Zwei API-Pfade für dieselbe Operation
Organisches Wachstum führte zu zwei gültigen API-Endpunkten für Modul-Konfiguration. Verschiedene Aufrufer nutzen verschiedene Pfade.

### Muster D: System-Settings ohne zentrales Schema
`system_settings`-Schlüssel (`orgaplan_url`, `orgaplan_pdf_url`, `wichtige_termine_ical_url`, `app_title`, etc.) sind nicht in einer zentralen Konstanten-Definition dokumentiert. Admin kann generische PUT-Endpunkte nutzen, kennt aber die gültigen Keys nicht.

---

## 6. Empfohlene Bereinigungsschritte

### Bereinigung 1: `get_user_overview()` — `is_admin` korrekt lesen (I-004)
In `backend/admin/admin_service.py:339`: `u.is_admin` zur SQL-Query hinzufügen und `row[9]` als `is_admin` nutzen.

### Bereinigung 2: Altes Panel-System entfernen (I-001, I-008)
- `#layout-panel-overlay` aus `index.html:639–655` entfernen
- `_wireSettingsButton()`, `openLayoutPanel()`, `_renderLayoutPanelContent()`, `_saveLayout()`, `_getDragAfterElement()` aus `dashboard-manager.js` entfernen
- Korrespondierendes `.layout-panel*`-CSS aus `styles.css` prüfen und entfernen

### Bereinigung 3: Tote `app.js`-Funktionen entfernen (I-002, I-003, I-019)
- `overlayV2ModuleData()` (Zeilen 393–443) entfernen
- `triggerClassworkUpload()` (Zeilen 2445–2475) entfernen
- WebUntis-Picker-Doppelungen (Zeilen ~2561–2884) entfernen — Stubs bleiben

### Bereinigung 4: Inbox-System vereinheitlichen (I-007)
- `renderChannelFilters()` deaktivieren oder entfernen
- `#channel-filters`-Div aus `index.html:196` entfernen
- `_state.selectedChannel` nur noch intern für `renderMessages()` bei mail-Tab nutzen

### Bereinigung 5: CSS-Orphans entfernen (I-012)
- `.heute-anpassen-bar` und `.heute-anpassen-trigger` aus `styles.css` entfernen (~25 Zeilen)

### Bereinigung 6: Orgaplan-Key konsolidieren (I-016)
- `orgaplan_url`-Schlüssel in `_fetch_orgaplan_data()` auf `orgaplan_pdf_url` als einzigen kanonischen Schlüssel vereinfachen
- Dokumentation im Admin-Panel ergänzen

### Bereinigung 7: `admin_service.create_teacher()` Wrapper aktualisieren (I-005)
- `is_admin`-Parameter hinzufügen oder Wrapper entfernen (da er nicht von Admin-Routes genutzt wird)

---

## 7. Sofortmaßnahmen

### Sofortmaßnahme 1 (sicher, gering, klar begründet): `get_user_overview()` — `is_admin`-Fix (I-004)

**Problem:** Admin-Dashboard zeigt `is_admin=false` für Admins, die mit kanonischer Phase-13-Form (role='teacher', is_admin=True) angelegt wurden.

**Fix:** In [`backend/admin/admin_service.py`](backend/admin/admin_service.py) SQL-Query um `u.is_admin` erweitern:

```sql
-- Vorher (Zeile 339):
SELECT u.id, u.first_name, u.last_name, u.role, u.is_active,
       u.created_at, u.updated_at,
       COUNT(um.id) FILTER (WHERE um.is_configured = TRUE) AS module_count,
       (uac.user_id IS NOT NULL) AS has_access_code

-- Nachher:
SELECT u.id, u.first_name, u.last_name, u.role, u.is_active,
       u.created_at, u.updated_at,
       COUNT(um.id) FILTER (WHERE um.is_configured = TRUE) AS module_count,
       (uac.user_id IS NOT NULL) AS has_access_code,
       u.is_admin
```

Und bei Zeile 370: `"is_admin": bool(row[9])` statt `row[3] == "admin"`.

---

Alle weiteren Bereinigungsschritte (I-001, I-002, I-003, I-007, etc.) sind safe, aber erfordern Regressionstests nach der Änderung. Keine weiteren Sofortmaßnahmen ohne Testabsicherung empfohlen.

---

## 8. Validierung (Testergebnisse)

Ausgeführt am 2026-03-30:

```
python3 -m pytest tests/ --tb=short -q
```

**Ergebnis:** `418 passed, 110 skipped, 0 errors` in 2,41s

- 110 übersprungene Tests sind DB-abhängig (psycopg3 + PostgreSQL nicht lokal verfügbar) — normal und erwartet
- Keine Regression durch Audit-Untersuchung: alle 418 bestehenden Tests weiterhin grün

---

## 9. Offene Fragen

**F1: `#layout-panel-overlay` — Entfernen oder absichtlich behalten?**
Das alte Panel ist vollständig im HTML + CSS + JS vorhanden (inkl. Drag-and-Drop). Wenn Phase 15+ dieses Panel reaktivieren soll (z.B. für vollständige Modul-Umordnung über alle Sektionen), wäre es ein Fehler es jetzt zu löschen. Wenn nicht: sofortiger Bereinigungskandidat.

**F2: `wichtige_termine_ical_url` — Schulspezifisch oder neutral?**
[`backend/wichtige_termine_adapter.py:14`](backend/wichtige_termine_adapter.py:14) enthält als Fallback-Hardcode die HES-URL (`https://hermann-ehlers-schule.de/events/liste/?ical=1`). Für eine echte Multi-School-SaaS-Nutzung müsste dieser Default entfernt oder auf einen leeren String gesetzt werden, sodass das Modul ohne Admin-Konfiguration nicht anzeigt.

**F3: `orgaplan_url` vs `orgaplan_pdf_url` — Veralteter Schlüssel oder geplante Unterscheidung?**
Ist `orgaplan_url` der HTML-/Detailseiten-Link und `orgaplan_pdf_url` der direkte PDF-Link? Wenn ja: die Unterscheidung ist sinnvoll und sollte in Admin-UI dokumentiert werden. Wenn nein: einer der Schlüssel kann entfernt werden.

**F4: Kann ein nicht-authentifizierter User `onboarding.html` direkt aufrufen?**
Der Auth-Check in [`index.html:676`](index.html:676) (`checkAuth()`) leitet nicht-authentifizierte User zu `login.html` weiter. `onboarding.html` ist eine statische Seite auf Netlify — falls sie keinen eigenen `checkAuth()`-Block enthält, kann die Seite ohne Login geladen werden. Alle API-Calls würden 401 zurückgeben, aber die Seite selbst wäre für unauthentifizierte Nutzer zugänglich (nur UI-Shell, keine echten Daten).

**F5: `webuntis_url` in system_settings — Wann und von wem gesetzt?**
`_fetch_base_data()` liest `webuntis_url` aus system_settings ([`dashboard_routes.py:447`](backend/api/dashboard_routes.py:447)) und gibt ihn an die Zugänge-Karte weiter. In [`zugaenge.js:17`](src/features/zugaenge.js:17) ist `configKey: 'webuntis_url'` definiert. Es ist unklar ob dieser Key über die Admin-Settings-UI gesetzt wird oder nur über die per-user WebUntis-Modulkonfiguration (`ical_url` + `base_url`). Wenn kein Admin `webuntis_url` in system_settings setzt, bleibt der Zugänge-WebUntis-Link leer für alle User.

**F6: `mail`-Modul — Was ist dessen Rendering-Rolle?**
Das `mail`-Modul ist in der DB mit `module_type='local'`, `default_visible=FALSE` geseedet ([`migrations.py:128`](backend/migrations.py:128)). Im Frontend gibt es kein `isModuleVisible('mail')`-gegatetes Rendering — Mail-Messages kommen immer über `data.messages` mit `channel='mail'` (v1-Daten-Pfad). Soll das `mail`-Modul zukünftig die Inbox-Section steuern (Section ein/aus basierend auf `is_visible`)? Aktuell hat die Inbox-Section kein Modul-Gating.