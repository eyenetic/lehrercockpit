# Claude Handoff

## Projektziel

Ein lokales Lehrer-Cockpit fuer den Berliner Schulalltag, das mehrere Quellen an einem Ort sichtbar macht:

- Berliner Schulportal
- WebUntis
- itslearning
- Orgaplan
- Klassenarbeitsplan
- spaeter weitere Dokumente, ggf. Berliner Kommunikationsdienste

## Starten

```bash
python3 server.py
```

Dann im Browser:

```text
http://127.0.0.1:8080
```

## Aktueller Stand (2026-03-21)

- Lokale Python-App ohne externe Dependencies (ausser openpyxl, pypdf, playwright optional)
- Frontend in `index.html`, `styles.css`, `src/app.js`
- API in `server.py` (lokal) + `server_test.py` (Render, delegiert an server.py)
- Dashboard-Zusammenbau in `backend/dashboard.py`
- Dokumentenmonitor in `backend/document_monitor.py`
- Mailadapter in `backend/mail_adapter.py`
- Konfiguration ueber `.env.local`

## Bereits konfigurierte echte Quellen

- `SCHOOLPORTAL_URL=https://schulportal.berlin.de`
- `WEBUNTIS_BASE_URL=https://hermann-ehlers-os.webuntis.com`
- `ITSLEARNING_BASE_URL=https://berlin.itslearning.com`
- `ORGAPLAN_PDF_URL=https://hermann-ehlers-schule.de/wp-content/uploads/2026/02/Orgaplan-2025_26-ab-Maerz-2.pdf`
- `CLASSWORK_PLAN_URL=<OneDrive-Link>` (blockiert, nur als Fallback)
- `CLASSWORK_GSHEETS_CSV_URL=https://docs.google.com/spreadsheets/d/e/2PACX-1vSbtq5XRitB38-o_yPg-IvKGRHEcjFkcWZSFsdtHPb_NeDfEYUdLdKLcmBexLfH4h6jX-ZnUPjHGEBg/pub?output=csv`

## Was funktioniert

- Berlin-Quick-Links im UI
- Berliner Fokus-/Kontextkarten im UI
- Quellenstatus fuer die realen URLs
- Dokumentenmonitor mit lokalem Zustand in `data/document-monitor-state.json`
- Orgaplan wird erfolgreich beobachtet und als `tracked` gemeldet
- **Klassenarbeitsplan** vollstaendig live:
  - Google Sheets CSV als primaere Live-Quelle (kein Login noetig)
  - XLS/XLSX Upload-Button im UI (`📂 Hochladen`) → parst alle Sheets
  - Monats-Tab-Selektor im UI (autom. aktueller Monat)
  - Leere Spalten werden automatisch ausgeblendet
  - Fallback-Kette: Google Sheets → Playwright-Cache → mock-dashboard.json

## Klassenarbeitsplan-Datenfluss (Prioritaeten)

1. **Google Sheets CSV** (live, oeffentlich, kein Login) — `CLASSWORK_GSHEETS_CSV_URL`
2. **XLS/XLSX Upload** via `POST /api/classwork/upload` → gespeichert in `data/classwork-cache.json`
3. **Playwright-Scrape** via `POST /api/classwork/scrape` → gespeichert in `data/classwork-cache.json`
4. **`data/mock-dashboard.json`** Snapshot (Render cold-start Fallback, immer im Repo)

## Bekannte Einschraenkungen

- Berliner Dienstmail derzeit nicht sinnvoll per IMAP integrierbar; im Projekt nur vorbereitet
- WebUntis ist als Quelle konfiguriert, aber noch ohne Session-/Datenabruf (iCal fehlt)
- itslearning ist als Quelle konfiguriert, aber noch ohne Session-/Datenabruf
- Playwright-Scrape funktioniert nur lokal (Render hat kein Chromium ohne Build-Step)
- Render-Umgebungsvariable `CLASSWORK_GSHEETS_CSV_URL` muss manuell gesetzt werden

## Beste naechste Schritte

1. **WebUntis iCal verbinden**: `WEBUNTIS_ICAL_URL` in `.env.local` setzen → live Stundenplan sofort
2. **itslearning credentials setzen**: `ITSLEARNING_USERNAME` + `ITSLEARNING_PASSWORD` in `.env.local`
3. **Render env var setzen**: `CLASSWORK_GSHEETS_CSV_URL` im Render-Dashboard hinterlegen
4. **Orgaplan-Aenderungserkennung** im UI noch aggressiver hervorheben (Badge auf Nav-Item)
5. **Playwright auf Render**: Build-Befehl um `playwright install chromium` ergaenzen
6. **Weitere Schul-PDFs** oder Rundschreiben in den Dokumentenmonitor aufnehmen

## Deployment Status (Stand: 2026-03-21)

### Netlify Frontend (Primary)

- **URL:** `https://dainty-empanada-5ab04b.netlify.app` — Live ✅
- **Hosting:** Statisches Hosting (kein Build-Step, kostenlos)
- **API-URL in `index.html`:** `window.BACKEND_API_URL = "https://lehrercockpit.onrender.com"`
- **Auto-Deploy:** Jeder Push auf `main` → Netlify deployt automatisch

### Render Backend (Primary)

- **URL:** `https://lehrercockpit.onrender.com` — Live ✅
- **Hinweis:** Render Free Tier — 30s Kaltstart nach 15min Inaktivitaet
- **Start-Befehl:** `python3 server_test.py` (delegiert an `server.py`)
- **PORT:** aus `$PORT` Env-Variable
- **CORS:** `CORS_ORIGIN` Env-Variable (Default: `*`)
- **Wichtig:** `CLASSWORK_GSHEETS_CSV_URL` muss manuell im Render-Dashboard gesetzt werden

### GitHub Repo

- **URL:** `https://github.com/eyenetic/lehrercockpit` (branch: `main`)
- **Git-Committer:** `eyenetic@users.noreply.github.com`

### Wichtige Hinweise

- **Primaeres Frontend:** Netlify (`https://dainty-empanada-5ab04b.netlify.app`)
- `server_test.py` delegiert vollstaendig an `server.py` (kein eigener Handler-Code mehr)
- Lokaler Dev-Server: `python3 server.py` → `http://localhost:8080`
- CORS ist auf `*` gesetzt, sodass sowohl Netlify als auch Vercel als Origins erlaubt sind
- **API POST-Calls** (scrape, upload, settings) nutzen `getBackendApiBase()` → immer Render-URL, nicht Netlify-Origin

## API-Endpunkte (server.py)

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| GET | `/api/health` | Healthcheck |
| GET | `/api/dashboard` | Dashboard-Payload (inkl. Klassenarbeitsplan aus Google Sheets oder Cache) |
| GET | `/api/classwork` | Aktueller classwork-cache.json Inhalt |
| POST | `/api/classwork/scrape` | Playwright-Scrape im Hintergrund starten |
| GET | `/api/classwork/scrape/progress` | SSE-Stream fuer Scrape-Fortschritt |
| POST | `/api/classwork/upload` | XLS/XLSX/CSV hochladen, alle Sheets parsen, Cache speichern |
| POST | `/api/local-settings/itslearning` | itslearning-Zugangsdaten lokal speichern |

## Commit-Historie (Session 2026-03-21)

| Commit | Beschreibung |
|--------|-------------|
| `5705c29` | Wire Playwright classwork cache into /api/dashboard planDigest |
| `329cfa6` | Upgrade server_test.py + embed classwork data in mock-dashboard |
| `ffb1597` | Fix Render: use mock-dashboard.json classwork snapshot as fallback |
| `f8f58f3` | Use Google Sheets CSV as primary live source for Klassenarbeitsplan |
| `acbfdb6` | Add XLS/XLSX/CSV upload for Klassenarbeitsplan |
| `28b0702` | Fix 404: use getBackendApiBase() for all API POST calls |
| `f09fc54` | Rename 'Datei oeffnen' to 'Plan online im Viewer öffnen' |
| `aea3101` | Fix Excel upload: read all sheets + clean newlines from headers |
| `53614aa` | Add month tab selector to Klassenarbeitsplan table |

---

## Arifs Beiträge (arifulu) — Stand 2026-03-19

### Git-Identität

- **GitHub:** `arifulu`
- **Email:** `arifulu@users.noreply.github.com`
- **Rolle:** Collaborator am `eyenetic/lehrercockpit`-Repository

### Zusammenfassung

Arif hat das Projekt initial importiert, die WebUntis-Integration (`webuntis_adapter.py`) und den Orgaplan-Digest (`plan_digest.py`) als neue Backend-Module hinzugefuegt, einen aktuellen Fallback-Snapshot erstellt, und die Deployment-Pipeline fuer Netlify, Vercel und Railway konfiguriert.
