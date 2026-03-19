# Lehrer-Cockpit

Dieses Projekt ist jetzt eine lokale Web-App mit Python-Backend. Das Cockpit fuehrt Nachrichten, Vertretungen, Termine und PDFs in einer einzigen Tagesoberflaeche zusammen und kann erste echte Quellen wie WebUntis bereits als konfigurierte Basis aufnehmen.

## Was schon drin ist

- `Heute`-Briefing mit Reload aus einer lokalen JSON-API
- `Berlin-Quick-Links` fuer Schulportal, WebUntis, itslearning und Dokumente
- `Dokumentenmonitor` fuer Orgaplan und geteilte Planlinks
- zentrale Inbox fuer Demo-Daten oder live geladene Dienstmails
- Wochenuebersicht fuer Termine, Fristen und Aufsichten
- Dokumentencenter mit Suche ueber PDFs und Plaene
- Quellenkarten mit Live- oder Demo-Status
- IMAP-Mailadapter ohne externe Python-Abhaengigkeiten

## Projektstruktur

- `index.html` enthaelt die App-Struktur
- `styles.css` definiert das visuelle System und das responsive Layout
- `data/mock-dashboard.json` ist der Fallback fuer Demo-Daten
- `data/document-monitor-state.json` speichert den letzten beobachteten Dokumentenstand
- `src/app.js` laedt die API-Daten und rendert Dashboard, Filter, Suche und den Assistenten
- `server.py` liefert die statischen Dateien und die API-Endpunkte aus
- `backend/` enthaelt Konfiguration, Mailadapter und Dashboard-Building
- `config/mail.env.example` zeigt, welche Umgebungsvariablen fuer WebUntis, itslearning und Mail gesetzt werden koennen
- `docs/architecture.md` beschreibt, wie echte Quellen nachgezogen werden koennen

## Lokal starten

Die App laeuft ohne Build-Schritt:

```bash
python3 server.py
```

Danach im Browser `http://localhost:4173` aufrufen.

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
- `ITSLEARNING_BASE_URL`
- `ORGAPLAN_PDF_URL`
- `CLASSWORK_PLAN_URL`
- Mail-Variablen fuer Umgebungen, in denen IMAP erlaubt ist

## Sinnvolle naechste Schritte

1. WebUntis-Loginweg pruefen und eine sichere Session-Anbindung fuer Stundenplan und Vertretungen bauen.
2. itslearning-URL hinterlegen und die relevanten Ansichten/Feeds identifizieren.
3. PDFs automatisch einsammeln, textlich auslesen und mit Klassen/Terminen taggen.
4. Spaeter Sync-Historie und persoenliche Regeln pro Lehrkraft speichern.
