# Architektur fuer echte Schulquellen

## Zielbild

Das Lehrer-Cockpit sollte spaeter aus drei Schichten bestehen:

1. `Collector Layer`: einzelne Adapter fuer Mail, itslearning, WebUntis, Website und PDF-Quellen.
2. `Normalization Layer`: alle Meldungen werden in ein gemeinsames Format fuer Nachrichten, Termine, Dokumente und Aufgaben ueberfuehrt.
3. `Experience Layer`: Dashboard, Suche, Tagesbriefing und spaetere KI-Funktionen greifen nur noch auf das vereinheitlichte Datenmodell zu.

## Gemeinsames Datenmodell

Ein vereinfachtes Zielschema:

```js
{
  source: "webuntis",
  entityType: "event",
  title: "Raumwechsel 8b",
  body: "Mathematik wechselt in Raum C112.",
  startsAt: "2026-03-15T09:35:00+01:00",
  priority: "high",
  audience: ["8b"],
  rawUrl: "https://...",
  syncedAt: "2026-03-15T06:58:00+01:00"
}
```

## Integrationsstrategie

- `Dienstmail`: bevorzugt ueber Microsoft Graph, alternativ IMAP. Neue Mails werden klassifiziert und nur relevante Inhalte ins Dashboard gespiegelt.
- `WebUntis`: wenn eine offizielle API oder ein stabiler Login-Fluss vorhanden ist, werden Stundenplan, Vertretung und Raeume regelmaessig synchronisiert.
- `itslearning`: Kursmeldungen, Aufgaben und Fristen in einen Feed uebernehmen.
- `Schulwebsite`: Seiten oder PDFs auf Aenderungen pruefen und neue Inhalte extrahieren.
- `PDF-Ablage`: Dateiuploads, OCR oder Textextraktion und anschliessendes Tagging fuer Klassen, Termine und Rollen.

## Backend-Skizze

- Scheduler fuer zyklische Syncs
- kleine Datenbank fuer letzte Aenderungen und historische Vergleiche
- Queue fuer PDF-Verarbeitung und spaetere KI-Zusammenfassungen
- API fuer Frontend-Abfragen wie `today`, `inbox`, `documents`, `search`

## Produktlogik

- Dubletten zusammenfuehren, wenn dieselbe Info in Mail und PDF auftaucht
- Aenderungen hervorheben statt alles neu anzuzeigen
- Prioritaet aus Quelle, Datum, Klasse und persoenlicher Rolle ableiten
- spaeter eine persoenliche Fragen-Antwort-Suche auf den normalisierten Daten aufsetzen
