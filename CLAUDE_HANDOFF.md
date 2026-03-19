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
http://127.0.0.1:4173
```

## Aktueller Stand

- Lokale Python-App ohne externe Dependencies
- Frontend in `index.html`, `styles.css`, `src/app.js`
- API in `server.py`
- Dashboard-Zusammenbau in `backend/dashboard.py`
- Dokumentenmonitor in `backend/document_monitor.py`
- Mailadapter in `backend/mail_adapter.py`
- Konfiguration ueber `.env.local`

## Bereits konfigurierte echte Quellen

- `SCHOOLPORTAL_URL=https://schulportal.berlin.de`
- `WEBUNTIS_BASE_URL=https://hermann-ehlers-os.webuntis.com`
- `ITSLEARNING_BASE_URL=https://berlin.itslearning.com`
- `ORGAPLAN_PDF_URL=https://hermann-ehlers-schule.de/wp-content/uploads/2026/02/Orgaplan-2025_26-ab-Maerz-2.pdf`
- `CLASSWORK_PLAN_URL=<OneDrive-Link>`

## Was funktioniert

- Berlin-Quick-Links im UI
- Berliner Fokus-/Kontextkarten im UI
- Quellenstatus fuer die realen URLs
- Dokumentenmonitor mit lokalem Zustand in `data/document-monitor-state.json`
- Orgaplan wird erfolgreich beobachtet und als `tracked` gemeldet
- Klassenarbeitsplan ist verlinkt, aber automatischer Abruf ist durch OneDrive blockiert

## Bekannte Einschraenkungen

- Berliner Dienstmail derzeit nicht sinnvoll per IMAP integrierbar; im Projekt nur vorbereitet
- WebUntis ist als Quelle konfiguriert, aber noch ohne Session-/Datenabruf
- itslearning ist als Quelle konfiguriert, aber noch ohne Session-/Datenabruf
- OneDrive-Link fuer Klassenarbeitsplan liefert fuer automatisierte Abrufe aktuell keine robuste offene Datei

## Beste naechste Schritte

1. WebUntis-Session oder offiziellen Abrufweg pruefen und `Heute`/Vertretungen real befuellen
2. itslearning-Ansichten identifizieren und read-only anbinden
3. Orgaplan-Aenderungserkennung im UI noch aggressiver hervorheben
4. Klassenarbeitsplan auf besseren Export-/Direktlink umstellen
5. Weitere Schul-PDFs oder Rundschreiben in den Dokumentenmonitor aufnehmen

## Deployment Status (Stand: 2026-03-19)

### Netlify Frontend (Primary)

- **URL:** `https://dainty-empanada-5ab04b.netlify.app` — Live ✅
- **Hosting:** Statisches Hosting (kein Build-Step, kostenlos, kein Team-Membership nötig)
- **Config:** `netlify.toml` + `.netlifyignore`
- **API-URL in `index.html`:** `window.RAILWAY_API_URL = "https://lehrercockpit.onrender.com"`

### Render Backend (Primary)

- **URL:** `https://lehrercockpit.onrender.com` — Live ✅
- **Hinweis:** Render Free Tier — 30s Kaltstart nach 15min Inaktivität
- **Start-Befehl:** `python3 server_test.py`
- **PORT:** aus `$PORT` Env-Variable
- **CORS:** `CORS_ORIGIN` Env-Variable (Default: `*`)

### Railway Backend (Legacy)

- **URL:** `https://lehrercockpit-production.up.railway.app` — Nicht mehr primärer Hoster
- **Hinweis:** Railway wird nicht mehr als primärer Backend-Hoster verwendet. Render ist jetzt der primäre Hoster.
- **Config:** `railway.json` + `Procfile` (noch im Repo, aber nicht aktiv genutzt)

### Vercel Frontend (Legacy)

- **URL:** `https://lehrercockpit.vercel.app` — Nicht mehr primärer Hoster
- **Hinweis:** Vercel wird nicht mehr als primärer Frontend-Hoster verwendet. Netlify ist jetzt der primäre Hoster.
- **Config:** `vercel.json` + `.vercelignore` (noch im Repo, aber nicht aktiv genutzt)

### GitHub Repo

- **URL:** `https://github.com/eyenetic/lehrercockpit` (branch: `main`)
- **Git-Committer:** `eyenetic@users.noreply.github.com`

### Wichtige Hinweise

- **Primäres Frontend:** Netlify (`https://dainty-empanada-5ab04b.netlify.app`)
- `server_test.py` ist der Railway-Produktionsserver; `server.py` ist fuer lokale Entwicklung
- Lokaler Dev-Server: `python3 server.py` → `http://localhost:4173`
- CORS ist auf `*` gesetzt, sodass sowohl Netlify als auch Vercel als Origins erlaubt sind

---

## Arifs Beiträge (arifulu) — Stand 2026-03-19

### Git-Identität

- **GitHub:** `arifulu`
- **Email:** `arifulu@users.noreply.github.com`
- **Rolle:** Collaborator am `eyenetic/lehrercockpit`-Repository

### Commit-Übersicht (8 Commits am 2026-03-19)

| Commit | Beschreibung |
|--------|-------------|
| `e617ac1` | Initial import of Lehrer-Cockpit — Erstimport des gesamten Projekts |
| `aa4eae6` | Merge remote main into local Lehrer-Cockpit state |
| `d33fff2` | Add live WebUntis hub and Orgaplan digest — Neue Module + Frontend-Erweiterungen |
| `8c40389` | Merge remote-tracking branch 'origin/main' |
| `d724e90` | Configure deploy targets for Vercel and Railway |
| `cdae5e5` | Merge remote-tracking branch 'origin/main' |
| `e8c9e5d` | Publish fresh WebUntis snapshot fallback |
| `2f7dcc4` | Re-enable Netlify auto deploys — `ignore = "exit 1"` aus `netlify.toml` entfernt |

### Was Arif implementiert/geändert hat

#### Neue Dateien (Added)
- **`backend/plan_digest.py`** — Neues Modul für Orgaplan-Digest-Funktionalität (PDF-Parsing und Zusammenfassung)
- **`backend/webuntis_adapter.py`** — Neuer WebUntis-Adapter für Stundenplan- und Vertretungsdaten
- **`data/mock-dashboard.js`** — JavaScript-basierter Fallback-Snapshot mit aktuellen WebUntis-Daten
- **`requirements.txt`** — Python-Dependencies für das Backend

#### Geänderte Dateien (Modified)
- **`netlify.toml`** — Netlify Auto-Deploy Blocker entfernt (`ignore = "exit 1"` entfernt), damit Pushes automatisch deployt werden
- **`data/mock-dashboard.json`** — Aktualisierter Fallback-Snapshot mit frischen WebUntis-Daten
- **`index.html`** — Frontend-Erweiterungen für WebUntis-Hub-Anzeige und Deploy-Target-Konfiguration
- **`src/app.js`** — JavaScript-Logik für WebUntis-Daten-Rendering im Dashboard
- **`styles.css`** — Styling-Anpassungen für neue UI-Komponenten
- **`backend/config.py`** — Konfiguration um WebUntis- und Orgaplan-Parameter erweitert
- **`backend/dashboard.py`** — Dashboard-Zusammenbau um neue Datenquellen erweitert
- **`config/mail.env.example`** — Beispiel-Konfiguration aktualisiert
- **`README.md`** — Dokumentation aktualisiert
- **`Procfile`** — Railway-Startbefehl angepasst
- **`railway.json`** — Railway-Deploy-Konfiguration angepasst

### Zusammenfassung

Arif hat das Projekt initial importiert, die WebUntis-Integration (`webuntis_adapter.py`) und den Orgaplan-Digest (`plan_digest.py`) als neue Backend-Module hinzugefügt, einen aktuellen Fallback-Snapshot erstellt, und die Deployment-Pipeline für Netlify, Vercel und Railway konfiguriert. Sein letzter Commit hat die Netlify-Auto-Deploys wieder aktiviert, sodass jeder Push auf `main` automatisch live geht.
