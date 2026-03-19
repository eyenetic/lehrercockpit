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
