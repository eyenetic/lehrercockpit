# Claude Handoff

## Projektziel

Ein lokales Lehrer-Cockpit fuer den Berliner Schulalltag, das mehrere Quellen an einem Ort sichtbar macht:

- Berliner Schulportal
- WebUntis
- itslearning
- Orgaplan
- Klassenarbeitsplan
- spaeter weitere Dokumente, ggf. Berliner Kommunikationsdienste

## Starten (lokal)

```bash
python3 server.py
```

Dann im Browser: `http://127.0.0.1:8080`

## Aktueller Stand (2026-03-21)

- Lokale Python-App ohne externe Dependencies (ausser openpyxl, pypdf)
- Frontend in `index.html`, `styles.css`, `src/app.js`
- API in `server.py` (lokal) + `server_test.py` (Render, delegiert an server.py)
- Dashboard-Zusammenbau in `backend/dashboard.py`
- Dokumentenmonitor in `backend/document_monitor.py`
- Konfiguration ueber `.env.local`

## Klassenarbeitsplan — Workflow

### Datenfluss

1. **XLS/XLSX Upload** via `POST /api/classwork/upload` → gespeichert in `data/classwork-cache.json`
   - Alle Sheets (11 Monate) werden gelesen
   - Upload-Zeitstempel wird angezeigt ("Stand: TT.MM.JJJJ, HH:MM Uhr")
2. **`data/mock-dashboard.json`** Snapshot (immer im Repo, Fallback fuer Render-Kaltstart)

> **Hinweis:** OneDrive-Link-Monitoring und Google Sheets CSV-Anbindung wurden entfernt.
> Die einzige Live-Quelle ist jetzt der manuelle XLS/XLSX/CSV-Upload.

### UI-Bedienung

- **"📂 Hochladen"** Button im Klassenarbeitsplan-Bereich → XLS/XLSX/CSV auswaehlen
- Tabelle erscheint sofort mit Monats-Tab-Selektor (autom. aktueller Monat)
- Upload-Zeitstempel unterm Tabellenkopf
- Daten bleiben bis zum naechsten Render-Kaltstart erhalten

### Render Free Tier Hinweis

Render Free Tier setzt den Disk nach 15 Min Inaktivitaet zurueck → Upload-Daten weg.

## API-Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| GET | `/api/health` | Healthcheck |
| GET | `/api/dashboard` | Dashboard-Payload (inkl. Klassenarbeitsplan) |
| GET | `/api/classwork` | Persistierter Upload-Cache (`data/classwork-cache.json`) |
| POST | `/api/classwork/upload` | XLS/XLSX/CSV hochladen, alle Sheets parsen, Cache speichern |
| POST | `/api/local-settings/itslearning` | itslearning-Zugangsdaten lokal speichern |

## Deployment

### Netlify Frontend (Primary)

- **URL:** `https://dainty-empanada-5ab04b.netlify.app` — Live ✅
- **Auto-Deploy:** Jeder Push auf `main` → Netlify deployt automatisch
- **API-URL:** `window.BACKEND_API_URL = "https://lehrercockpit.onrender.com"` (in `index.html`)

### Render Backend (Primary)

- **URL:** `https://lehrercockpit.onrender.com` — Live ✅
- **Build:** Docker (`Dockerfile`) — sauber, kein Playwright mehr
- **Start:** `python3 server.py`
- **PORT:** aus `$PORT` Env-Variable
- **CORS:** `*`
- **Env-Variablen auf Render setzen:** (keine Pflicht-Variablen mehr fuer Klassenarbeitsplan)

### Dockerfile (Render Build)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data
EXPOSE 8080
CMD ["python3", "server.py"]
```

Kein Playwright, keine System-Deps mehr — Build schlaegt nicht mehr fehl.

### GitHub Repo

- **URL:** `https://github.com/eyenetic/lehrercockpit` (branch: `main`)

## Bereits konfigurierte echte Quellen

- `SCHOOLPORTAL_URL=https://schulportal.berlin.de`
- `WEBUNTIS_BASE_URL=https://hermann-ehlers-os.webuntis.com`
- `ITSLEARNING_BASE_URL=https://berlin.itslearning.com`
- `ORGAPLAN_PDF_URL=https://hermann-ehlers-schule.de/wp-content/uploads/2026/02/Orgaplan-2025_26-ab-Maerz-2.pdf`

## Bekannte Einschraenkungen

- Berliner Dienstmail derzeit nicht sinnvoll per IMAP integrierbar
- WebUntis ist konfiguriert, aber noch ohne iCal-Anbindung
- itslearning ist konfiguriert, aber noch ohne Credentials
- Render Free Tier: Disk nach 15 Min Inaktivitaet zurueck → Upload-Daten weg

## Beste naechste Schritte

1. **WebUntis iCal verbinden**: `WEBUNTIS_ICAL_URL` in `.env.local` → live Stundenplan sofort
2. **itslearning**: `ITSLEARNING_USERNAME` + `ITSLEARNING_PASSWORD` in `.env.local`
3. **Render Persistent Disk** (Starter-Plan $7/mo) → Upload-Daten ueberleben Kaltstarts
4. **Orgaplan-Aenderungserkennung** im UI aggressiver hervorheben (Badge auf Nav-Item)
5. **Weitere Schul-PDFs** in den Dokumentenmonitor aufnehmen

## Commit-Historie — Session 2026-03-21

| Commit | Beschreibung |
|--------|-------------|
| `5705c29` | Wire Playwright cache into /api/dashboard planDigest |
| `329cfa6` | Upgrade server_test.py; embed classwork in mock-dashboard.json |
| `ffb1597` | Fix Render: mock-dashboard.json fallback when cache absent |
| `f8f58f3` | Google Sheets CSV als primaere Live-Quelle |
| `acbfdb6` | XLS/XLSX/CSV Upload-Endpoint + UI-Button |
| `28b0702` | Fix 404: getBackendApiBase() fuer alle API POST-Calls |
| `f09fc54` | "Plan online im Viewer öffnen" Label |
| `aea3101` | Alle 11 Excel-Sheets lesen; Zeilenumbrueche in Headers cleanens |
| `53614aa` | Monats-Tab-Selektor; leere Spalten ausblenden |
| `148c6c4` | CLAUDE_HANDOFF.md aktualisiert |
| `4b01b0f` | Fix: leeren Playwright-Cache nicht ueber Dashboard-Daten schreiben |
| `37b72d4` | **Playwright komplett entfernt** — reiner Upload-Workflow |
| `83e47bd` | Upload-Zeitstempel anzeigen (Stand: TT.MM.JJJJ, HH:MM Uhr) |
| `2520fb6` | Empty-Cache-Placeholder-Text aktualisiert |
| `f476cfd` | **Dockerfile ohne Playwright** — Build-Fehler auf Render behoben |
| *(heute)* | **OneDrive + Google Sheets Verbindungen entfernt** — nur Upload-Workflow |
