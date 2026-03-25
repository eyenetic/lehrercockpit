# Lehrer-Cockpit

Ein persoenliches Dashboard fuer den Berliner Schulalltag: WebUntis, itslearning, Orgaplan, Klassenarbeitsplan und Dienstmail an einem Ort.

**Deployment:** Frontend auf Netlify (statisch), Backend auf Render (Flask + gunicorn).

Fuer Deployments ist das Frontend so vorbereitet, dass es zuerst ein gleiches Origin (`/api`) versucht und danach auf konfigurierte externe Backend-URLs zurueckfallen kann. Damit laesst sich ein Wechsel zwischen Plattformen ohne Umbau der App-Logik abfedern.

## Was schon drin ist

- `Heute`-Briefing mit Reload aus einer lokalen JSON-API
- `Berlin-Quick-Links` fuer Schulportal, WebUntis, itslearning und Dokumente
- `Dokumentenmonitor` fuer Orgaplan und geteilte Planlinks
- `Plan-Digest` fuer Orgaplan und Klassenarbeitsplan
- spaltenbewusster `Orgaplan`-Digest fuer Allgemein, Mittelstufe und Oberstufe
- zentrale Inbox fuer Demo-Daten oder live geladene Dienstmails
- Wochenuebersicht fuer Termine, Fristen und Aufsichten
- Dokumentencenter mit Suche ueber PDFs und Plaene
- Quellenkarten mit Live- oder Demo-Status
- IMAP-Mailadapter ohne externe Python-Abhaengigkeiten
- lokale Apple-Mail-Vorschau als read-only Inbox-Quelle auf dem Mac
- WebUntis-iCal-Adapter fuer persoenliche Stundenplantermine aus dem Account

## Projektstruktur

- `index.html` — App-Struktur
- `styles.css` — visuelles System, responsives Layout
- `src/app.js` — Frontend (Daten laden, rendern, Events)
- `app.py` — **Produktions-Backend** (Flask, laeuft auf Render via gunicorn)
- `server.py` — Lokaler Dev-Server (stdlib `ThreadingHTTPServer`, kein gunicorn noetig)
- `dev_runner.py` — Startskript fuer `server.py` lokal (ersetzt das irrefuehrend benannte `server_test.py`)
- `backend/` — Konfiguration, Adapter, Dashboard-Building, Persistenz
- `backend/file_utils.py` — Geteilte Parsing-Hilfsfunktionen (multipart, XLSX), kein Duplikat mehr
- `backend/persistence.py` — Persistenz-Abstraktion: JsonFileStore lokal, DbStore (PostgreSQL) in Produktion
- `data/mock-dashboard.json` — Fallback Demo-Daten
- `tests/` — Automatisierte Tests (pytest)
- `config/mail.env.example` — Umgebungsvariablen-Vorlage
- `requirements.txt` — Python-Abhaengigkeiten inkl. pytest

## Lokal starten

Die App laeuft ohne Build-Schritt:

```bash
python3 -m pip install -r requirements.txt
python3 server.py
# oder gleichwertig:
python3 dev_runner.py
```

Danach im Browser `http://localhost:8080` aufrufen.

Wenn kein lokaler Server laeuft und `index.html` direkt geoeffnet wird, zeigt die App trotzdem eingebaute Demo-Daten an. Fuer echte API-Daten sollte `python3 server.py` laufen.

## Tests ausfuehren

```bash
pytest tests/ -v
```

Getestet werden: `grades_store`, `notes_store`, `classwork_cache`, Persistenz-Abstraktion und die wichtigsten Flask-API-Endpunkte.

DB-Integration-Tests (erfordern `TEST_DATABASE_URL`):

```bash
TEST_DATABASE_URL="postgresql://..." pytest tests/test_persistence.py -v -m db
```

## Quellen vorbereiten

Beispielkonfiguration:

```bash
cp config/mail.env.example .env.local
python3 server.py
```

`server.py` liest `.env.local` automatisch ein. Die benoetigten Variablen stehen in `config/mail.env.example`.
`.env.local` ist absichtlich in `.gitignore` eingetragen, damit Zugangsdaten lokal bleiben.

Schon hinterlegbar sind:
- `WEBUNTIS_BASE_URL`
- `WEBUNTIS_ICAL_URL`
- `ITSLEARNING_BASE_URL`
- `ORGAPLAN_PDF_URL`
- `CLASSWORK_PLAN_URL`
- Mail-Variablen fuer Umgebungen, in denen IMAP erlaubt ist
- optional `MAIL_LOCAL_SOURCE=apple_mail` fuer eine lokale Inbox-Vorschau aus Apple Mail
- optional `MAIL_LOCAL_ACCOUNT=lehrkraft@schule.berlin.de`, um die Vorschau auf genau dieses Dienstkonto zu beschraenken
- optional `ITSLEARNING_USERNAME` und `ITSLEARNING_PASSWORD`, um lokal die neuesten itslearning-Updates zu laden

Wenn `MAIL_LOCAL_SOURCE=apple_mail` gesetzt ist, versucht das Backend lokal auf dem Mac eine read-only Vorschau aus Apple Mail zu laden. Das ist fuer den lokalen Lehrer-Cockpit-Modus gedacht und ersetzt keine vollwertige Mailclient-Integration.

Wenn `WEBUNTIS_ICAL_URL` gesetzt ist, ersetzt das Backend die bisherigen Platzhalter im Stundenplan durch echte WebUntis-Termine aus dem persoenlichen Kalenderexport. Der Link bleibt lokal in `.env.local` und wird nicht in Git eingecheckt.

Wenn `ITSLEARNING_USERNAME` und `ITSLEARNING_PASSWORD` gesetzt sind, versucht das Backend lokal den nativen itslearning-Login zu verwenden und daraus einen kompakten Updates-Feed fuer die Inbox zu lesen. Der Zugriff ist bewusst schlank gehalten: Das Cockpit soll nur die neuesten Updates zeigen, die weitere Arbeit bleibt in itslearning selbst.

Der `Orgaplan` wird bei jedem Refresh neu gelesen und als kompakter Digest im Cockpit zusammengefasst. Dabei versucht das Backend jetzt, die PDF-Spalten `Allgemein`, `Mittelstufe` und `Oberstufe` getrennt zu erkennen. Der `Klassenarbeitsplan` wird ebenfalls bei jedem Refresh neu versucht; solange OneDrive den automatischen Abruf blockiert, zeigt das Cockpit den Status transparent an.

## Persistenz

Das Backend nutzt eine Persistenz-Abstraktion in `backend/persistence.py`.
Der aktive Store wird beim Start geloggt.

### Lokal ohne Datenbank (Standard)

Wenn `DATABASE_URL` **nicht** gesetzt ist, werden Daten als JSON-Dateien
in `data/` gespeichert. Das funktioniert sofort ohne weitere Einrichtung.

```
[persistence] Using local file store (no DATABASE_URL set).
```

### Produktion mit PostgreSQL (Render)

Wenn `DATABASE_URL` gesetzt ist, werden alle Daten in PostgreSQL gespeichert
und ueberleben Redeploys/Neustarts.

```
[persistence] Using PostgreSQL store (DATABASE_URL is set). Data will survive Render redeploys.
```

**Tabellen:**

| Tabelle | Schluessel | Inhalt |
|---------|-----------|--------|
| `app_state` | `grades-local` | Noten-Eintraege |
| `app_state` | `class-notes-local` | Klassen-Notizen |
| `app_state` | `classwork-cache` | Klassenarbeitsplan-Upload-Cache |

Die Tabelle wird beim Start automatisch erstellt (`CREATE TABLE IF NOT EXISTS`).

**Einrichten auf Render:**
1. Render Dashboard → dein Service → Environment → `DATABASE_URL` setzen
   (z. B. aus einem Render PostgreSQL Add-on: `postgresql://user:pass@host/db`)
2. Redeployen — fertig.

### Render ohne DATABASE_URL

Wenn das Backend auf Render laeuft ohne `DATABASE_URL`, erscheint eine Warnung:
```
[persistence] WARNING: Using file store on Render — data is ephemeral.
```

## Sinnvolle naechste Schritte

1. WebUntis-iCal verbinden: `WEBUNTIS_ICAL_URL` in `.env.local` → live Stundenplan.
2. itslearning: `ITSLEARNING_USERNAME` + `ITSLEARNING_PASSWORD` in `.env.local`.
3. `DATABASE_URL` auf Render setzen → Persistenz ist sofort dauerhaft.
4. PDFs automatisch einsammeln, textlich auslesen und mit Klassen/Terminen taggen.
5. `src/app.js` weiter in Feature-Module aufteilen (inbox, grades, webuntis, ...).
