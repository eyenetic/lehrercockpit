from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from .config import load_settings
from .document_monitor import MonitoredDocument, build_document_monitor
from .itslearning_adapter import fetch_itslearning_sync
from .mail_adapter import fetch_mail_sync
from .plan_digest import build_plan_digest
from .webuntis_adapter import fetch_webuntis_sync


def build_dashboard_payload(mock_path: Path, monitor_state_path: Path, classwork_cache_path: Path | None = None) -> dict[str, Any]:
    payload = _load_mock_payload(mock_path)
    settings = load_settings()
    now = datetime.now().astimezone()
    mail_sync = fetch_mail_sync(settings.mail, now)
    itslearning_sync = fetch_itslearning_sync(settings.itslearning, now)
    webuntis_sync = fetch_webuntis_sync(settings.webuntis_base_url, settings.webuntis_ical_url, now)
    document_monitor = build_document_monitor(_monitored_documents(settings), monitor_state_path, now)
    plan_digest = build_plan_digest(settings.orgaplan_pdf_url, settings.classwork_plan_url, settings.classwork_gsheets_csv_url, now)

    # Overlay classwork data using priority chain:
    # 1. Google Sheets CSV (live, via plan_digest) — if already ok, keep it
    # 2. Playwright cache (data/classwork-cache.json) — if plan_digest blocked
    # 3. mock-dashboard.json snapshot — if no cache either (e.g. Render cold start)
    if classwork_cache_path is not None:
        plan_digest["classwork"] = _merge_classwork_cache(plan_digest["classwork"], classwork_cache_path, mock_path)

    payload["generatedAt"] = now.isoformat()
    payload["teacher"]["name"] = settings.teacher_name
    payload["teacher"]["school"] = settings.school_name
    payload["workspace"] = _build_workspace(settings)
    payload["meta"] = _build_meta(settings, mail_sync, itslearning_sync, webuntis_sync, now)
    payload["quickLinks"] = _build_quick_links(settings)
    payload["berlinFocus"] = _build_berlin_focus(settings)
    payload["documentMonitor"] = document_monitor
    payload["webuntisCenter"] = _build_webuntis_center(settings, webuntis_sync, now)
    payload["planDigest"] = plan_digest

    payload["messages"] = _filter_placeholder_messages(payload["messages"], settings)
    payload["priorities"] = _filter_placeholder_priorities(payload["priorities"])
    payload["documents"] = _filter_placeholder_documents(payload["documents"])
    payload["sources"] = _apply_source_configuration(payload["sources"], settings)
    payload["sources"] = _merge_source(payload["sources"], mail_sync.source)
    payload["sources"] = _merge_source(payload["sources"], itslearning_sync.source)
    payload["sources"] = _merge_source(payload["sources"], webuntis_sync.source)
    payload["sources"] = _apply_source_configuration(payload["sources"], settings)
    payload["documents"] = _apply_document_configuration(payload["documents"], settings)
    payload["priorities"] = _apply_monitor_priorities(payload["priorities"], document_monitor)
    payload["documents"] = _apply_plan_digest_documents(payload["documents"], plan_digest)
    payload["priorities"] = _merge_priorities(_build_plan_digest_priorities(plan_digest), payload["priorities"])

    if mail_sync.messages:
        payload["messages"] = mail_sync.messages + [message for message in payload["messages"] if message["channel"] != "mail"]
        payload["priorities"] = _merge_priorities(mail_sync.priorities, payload["priorities"])
    else:
        payload["sources"] = _set_source_detail(payload["sources"], "mail", mail_sync.source)
        payload["messages"] = [message for message in payload["messages"] if message["channel"] != "mail"]
        payload["priorities"] = [priority for priority in payload["priorities"] if priority["source"] != "Dienstmail"]

    if itslearning_sync.messages:
        payload["messages"] = itslearning_sync.messages + [message for message in payload["messages"] if message["channel"] != "itslearning"]
        payload["priorities"] = _merge_priorities(itslearning_sync.priorities, payload["priorities"])
    else:
        payload["sources"] = _set_source_detail(payload["sources"], "itslearning", itslearning_sync.source)
        payload["messages"] = [message for message in payload["messages"] if message["channel"] != "itslearning"]
        payload["priorities"] = [priority for priority in payload["priorities"] if priority["source"] != "itslearning"]

    if webuntis_sync.schedule:
        payload["schedule"] = webuntis_sync.schedule

    payload["priorities"] = _merge_priorities(webuntis_sync.priorities, payload["priorities"])

    return payload


def _load_mock_payload(mock_path: Path) -> dict[str, Any]:
    with mock_path.open("r", encoding="utf-8") as handle:
        return deepcopy(json.load(handle))


def _merge_source(existing_sources: list[dict[str, Any]], source_update: dict[str, Any]) -> list[dict[str, Any]]:
    merged = []
    replaced = False
    for source in existing_sources:
        if source["id"] == source_update["id"]:
            merged.append(source_update)
            replaced = True
        else:
            merged.append(source)

    if not replaced:
        merged.insert(0, source_update)
    return merged


def _set_source_detail(existing_sources: list[dict[str, Any]], source_id: str, source_update: dict[str, Any]) -> list[dict[str, Any]]:
    return [source_update if source["id"] == source_id else source for source in existing_sources]


def _merge_priorities(incoming: list[dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    incoming_sources = {priority["source"] for priority in incoming}
    combined = incoming + [priority for priority in existing if priority["source"] not in incoming_sources]
    return combined[:4]


def _build_meta(settings: Any, mail_sync: Any, itslearning_sync: Any, webuntis_sync: Any, now: datetime) -> dict[str, str]:
    notes = []
    live_modes = set()

    if webuntis_sync.mode == "live-webuntis":
        notes.append(webuntis_sync.note)
        live_modes.add(webuntis_sync.mode)
    elif settings.webuntis_base_url:
        notes.append("WebUntis ist als Schulzugang hinterlegt, aber noch nicht vollstaendig live.")

    if settings.itslearning_base_url:
        notes.append(itslearning_sync.note)

    if mail_sync.mode == "live-mail":
        notes.append(mail_sync.note)
        live_modes.add(mail_sync.mode)
    else:
        notes.append("Dienstmail bleibt vorerst Link- oder Hinweis-Modul.")

    return {
        "mode": "live" if live_modes else "mixed",
        "note": " ".join(notes),
        "lastUpdatedLabel": now.strftime("%H:%M"),
    }


def _filter_placeholder_messages(messages: list[dict[str, Any]], settings: Any) -> list[dict[str, Any]]:
    blocked_channels = {"mail", "webuntis"}
    if settings.itslearning_base_url:
        blocked_channels.add("itslearning")

    return [message for message in messages if message["channel"] not in blocked_channels]


def _filter_placeholder_priorities(priorities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocked_sources = {"Dienstmail", "WebUntis"}
    return [priority for priority in priorities if priority["source"] not in blocked_sources]


def _filter_placeholder_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocked_sources = {"Dienstmail", "WebUntis"}
    return [document for document in documents if document["source"] not in blocked_sources]


def _apply_source_configuration(existing_sources: list[dict[str, Any]], settings: Any) -> list[dict[str, Any]]:
    configured_sources = []
    for source in existing_sources:
        updated = dict(source)

        if source["id"] == "webuntis" and settings.webuntis_base_url and not settings.webuntis_ical_url:
            updated["status"] = "ok"
            updated["lastSync"] = "konfiguriert"
            updated["cadence"] = "naechster Schritt: persoenlichen iCal verbinden"
            updated["nextStep"] = "Persoenlichen WebUntis-iCal hinterlegen oder spaeter Session-Cookie fuer Vertretungen pruefen"
            updated["detail"] = f"WebUntis-Basis gesetzt: {settings.webuntis_base_url}"

        if source["id"] == "website" and settings.orgaplan_pdf_url:
            updated["status"] = "ok"
            updated["lastSync"] = "konfiguriert"
            updated["cadence"] = "naechster Schritt: PDF-Aenderungen pruefen"
            updated["nextStep"] = "Orgaplan regelmaessig abrufen und Aenderungen gegen die letzte Version vergleichen"
            updated["detail"] = f"Orgaplan hinterlegt: {settings.orgaplan_pdf_url}"

        if source["id"] == "pdf" and settings.orgaplan_pdf_url:
            updated["status"] = "ok"
            updated["lastSync"] = "konfiguriert"
            updated["cadence"] = "naechster Schritt: PDF-Parsing"
            updated["nextStep"] = "Text aus dem Orgaplan extrahieren und Termine/Aufsichten taggen"
            updated["detail"] = "Ein konkreter Orgaplan-PDF-Link ist fuer spaetere Verarbeitung hinterlegt."

        if source["id"] == "pdf" and settings.classwork_plan_url:
            updated["status"] = "ok"
            updated["lastSync"] = "konfiguriert"
            updated["cadence"] = "naechster Schritt: XLSX-/Share-Link-Pruefung"
            updated["nextStep"] = "Freigabelink oder Export fuer den Klassenarbeitsplan in ein robustes Abrufformat ueberfuehren"
            updated["detail"] = "Klassenarbeitsplan-Link hinterlegt. OneDrive kann fuer automatisierte Abrufe zusaetzliche Freigaben verlangen."

        configured_sources.append(updated)

    return configured_sources


def _apply_document_configuration(existing_documents: list[dict[str, Any]], settings: Any) -> list[dict[str, Any]]:
    configured_documents = []
    for document in existing_documents:
        updated = dict(document)

        if document["id"] == "doc-1" and settings.orgaplan_pdf_url:
            updated["summary"] = (
                "Konkreter Orgaplan-PDF-Link hinterlegt und bereit fuer spaetere Aenderungserkennung: "
                f"{settings.orgaplan_pdf_url}"
            )
            updated["updatedAt"] = "konfiguriert"

        if document["id"] == "doc-2" and settings.classwork_plan_url:
            updated["summary"] = (
                "Konkreter Klassenarbeitsplan-Link hinterlegt. Der aktuelle OneDrive-Link liefert fuer automatisierte Abrufe "
                f"noch keinen direkten Dateizugriff: {settings.classwork_plan_url}"
            )
            updated["updatedAt"] = "konfiguriert"

        configured_documents.append(updated)

    return configured_documents


def _apply_plan_digest_documents(existing_documents: list[dict[str, Any]], plan_digest: dict[str, Any]) -> list[dict[str, Any]]:
    configured_documents = []
    orgaplan = plan_digest["orgaplan"]
    classwork = plan_digest["classwork"]

    for document in existing_documents:
        updated = dict(document)

        if document["id"] == "doc-1":
            updated["summary"] = orgaplan["detail"]
            updated["updatedAt"] = orgaplan["updatedAt"]
            updated["tags"] = ["Orgaplan", orgaplan["monthLabel"], "Live"]

        if document["id"] == "doc-2":
            updated["summary"] = classwork["detail"]
            updated["updatedAt"] = classwork["updatedAt"]
            updated["tags"] = ["Klassenarbeiten", "Plan", classwork["status"]]

        configured_documents.append(updated)

    return configured_documents


def _build_plan_digest_priorities(plan_digest: dict[str, Any]) -> list[dict[str, Any]]:
    priorities = []
    orgaplan = plan_digest["orgaplan"]
    classwork = plan_digest["classwork"]

    for index, item in enumerate(orgaplan["highlights"][:2], start=1):
        priorities.append(
            {
                "id": f"orgaplan-highlight-{index}",
                "title": f"Orgaplan: {item['title']}",
                "detail": item["detail"],
                "priority": "high",
                "source": "Orgaplan",
                "due": item["dateLabel"],
            }
        )

    if classwork["status"] != "ok":
        priorities.append(
            {
                "id": "classwork-status",
                "title": "Klassenarbeitsplan braucht robusteren Abruf",
                "detail": classwork["detail"],
                "priority": "medium",
                "source": "Klassenarbeitsplan",
                "due": "offen",
            }
        )

    return priorities[:3]


def _build_workspace(settings: Any) -> dict[str, str]:
    return {
        "eyebrow": "Berlin Lehrer-Cockpit",
        "title": f"Dein Tagesstart fuer {settings.school_name}",
        "description": (
            "Ein persoenliches Dashboard fuer Berliner Schulportal-Dienste, WebUntis, "
            "itslearning und eure wichtigsten Schul-Dokumente."
        ),
    }


def _build_quick_links(settings: Any) -> list[dict[str, str]]:
    links = [
        {
            "id": "schoolportal",
            "title": "Berliner Schulportal",
            "url": settings.schoolportal_url,
            "kind": "Portal",
            "note": "Zentraler Einstieg fuer Berliner Schuldienste",
        }
    ]

    optional_links = [
        ("webuntis", "WebUntis", settings.webuntis_base_url, "Planung", "Stundenplan, Vertretung und Heute"),
        ("itslearning", "itslearning", settings.itslearning_base_url, "Lernen", "Updates und Kursmeldungen"),
        ("orgaplan", "Orgaplan", settings.orgaplan_pdf_url, "PDF", "Aktueller Orgaplan fuer eure Schule"),
        (
            "classwork",
            "Klassenarbeitsplan",
            settings.classwork_plan_url,
            "Dokument",
            "Geteilter Planlink fuer Klassenarbeiten",
        ),
    ]

    for link_id, title, url, kind, note in optional_links:
        if url:
            links.append(
                {
                    "id": link_id,
                    "title": title,
                    "url": url,
                    "kind": kind,
                    "note": note,
                }
            )

    if "hermann-ehlers-schule.de" in settings.orgaplan_pdf_url:
        links.extend(
            [
                {
                    "id": "school-calendar",
                    "title": "Schulkalender",
                    "url": "https://hermann-ehlers-schule.de/events/",
                    "kind": "Website",
                    "note": "Kommende Termine direkt von der Schulwebsite",
                },
                {
                    "id": "school-hours",
                    "title": "Stunden- und Pausenzeiten",
                    "url": "https://hermann-ehlers-schule.de/1462-2/",
                    "kind": "Website",
                    "note": "Zeiten und Rhythmus des Schultags",
                },
                {
                    "id": "teacher-contact",
                    "title": "Kontakt Lehrkraefte",
                    "url": "https://hermann-ehlers-schule.de/e-mail-adressen-der-lehrkraefte/",
                    "kind": "Website",
                    "note": "Lehrkraefte-Kontakte, aktuell passwortgeschuetzt",
                },
            ]
        )

    return links


def _build_webuntis_center(settings: Any, webuntis_sync: Any, now: datetime) -> dict[str, Any]:
    base_url = settings.webuntis_base_url.rstrip("/")
    if base_url:
        today_url = f"{base_url}/today"
        start_url = base_url
    else:
        today_url = ""
        start_url = ""

    return {
        "status": webuntis_sync.source["status"],
        "note": webuntis_sync.note,
        "detail": webuntis_sync.source["detail"],
        "activePlan": "Mein WebUntis-Plan",
        "todayUrl": today_url,
        "startUrl": start_url,
        "currentDate": now.date().isoformat(),
        "currentWeekLabel": f"KW {now.isocalendar().week}",
        "events": webuntis_sync.events,
        "planTypes": [
            {"id": "teacher", "label": "Lehrkraft"},
            {"id": "class", "label": "Klasse"},
            {"id": "room", "label": "Raum"},
        ],
        "finder": _build_webuntis_finder(settings, webuntis_sync, start_url, today_url, now),
        "shortcutHint": (
            "Dein persoenlicher Plan kommt live ueber iCal. Fuer Kolleg:innen-, Klassen- und Raumplaene bereiten wir die Suche lokal vor und haengen sie als Naechstes an deine WebUntis-Sitzung."
        ),
    }


def _build_webuntis_finder(
    settings: Any,
    webuntis_sync: Any,
    start_url: str,
    today_url: str,
    now: datetime,
) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    has_named_teacher = _has_real_teacher_name(settings.teacher_name)

    def add_entity(entity_type: str, label: str, detail: str, *, url: str = "", live: bool = False) -> None:
        compact = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        entity_id = f"{entity_type}-{compact or 'eintrag'}"
        if entity_id in seen_ids:
            return
        seen_ids.add(entity_id)
        entities.append(
            {
                "id": entity_id,
                "type": entity_type,
                "label": label,
                "detail": detail,
                "url": url,
                "live": live,
            }
        )

    if start_url or today_url:
        add_entity(
            "teacher",
            settings.teacher_name if has_named_teacher else "Mein Plan",
            "Dein persoenlicher WebUntis-Plan ist live verbunden.",
            url=start_url or today_url,
            live=True,
        )

    for room in _extract_rooms(webuntis_sync.events):
        add_entity("room", room, "Aus deinem aktuellen Stundenplan erkannt. Fuer Live-Aenderungen ist die WebUntis-Sitzung noetig.")

    for school_class in _extract_classes(webuntis_sync.events):
        add_entity("class", school_class, "Aus deinem aktuellen Stundenplan erkannt. Klassenplaene werden spaeter direkt ueber die lokale Suche geladen.")

    finder_status = "warning"
    finder_note = "Aktuell suchbar: Klassen und Raeume aus deinem eigenen Plan. Kolleg:innen folgen erst mit lokaler WebUntis-Sitzung."
    if webuntis_sync.mode == "missing":
        finder_note = "WebUntis ist noch nicht verbunden. Fuer Planfinder zuerst den persoenlichen Zugang aktivieren."
    elif webuntis_sync.mode == "webuntis-error":
        finder_note = "WebUntis konnte gerade nicht geladen werden. Der Planfinder bleibt vorbereitet."
    elif len(entities) > 1:
        finder_status = "ok"

    return {
        "status": finder_status,
        "note": finder_note,
        "indexedAt": now.strftime("%H:%M"),
        "supportsSessionSearch": False,
        "searchPlaceholder": "Klasse oder Raum aus deinem Plan suchen",
        "availableTypes": [
            {"id": "teacher", "label": "Mein Plan"},
            {"id": "class", "label": "Klasse"},
            {"id": "room", "label": "Raum"},
        ],
        "entities": entities[:18],
        "watchlist": _build_webuntis_watchlist(webuntis_sync),
    }


def _build_webuntis_watchlist(webuntis_sync: Any) -> list[dict[str, str]]:
    items = []

    for priority in webuntis_sync.priorities[:3]:
        items.append(
            {
                "id": priority["id"],
                "title": priority["title"],
                "detail": priority["detail"],
                "status": "changed" if priority["priority"] in {"critical", "high"} else "watch",
            }
        )

    if not items:
        items.append(
            {
                "id": "watch-session",
                "title": "Aenderungsradar vorbereitet",
                "detail": "Sobald die lokale WebUntis-Suche gekoppelt ist, koennen wir Vertretungen, Raumwechsel und Ausfaelle fuer weitere Plaene verfolgen.",
                "status": "watch",
            }
        )

    return items


def _extract_rooms(events: list[dict[str, Any]]) -> list[str]:
    rooms = []
    seen = set()
    for event in events:
        room = (event.get("location") or "").strip()
        if room and room not in seen:
            seen.add(room)
            rooms.append(room)
    return rooms


def _extract_classes(events: list[dict[str, Any]]) -> list[str]:
    class_pattern = re.compile(r"\b(?:[5-9]\w?|1[0-3]\w?|Q\d(?:/Q\d)?|S\d)\b", re.IGNORECASE)
    classes = []
    seen = set()

    for event in events:
        for field in (event.get("detail") or "", event.get("description") or "", event.get("title") or ""):
            for match in class_pattern.findall(field):
                label = match.upper()
                if label not in seen:
                    seen.add(label)
                    classes.append(label)

    return classes


def _has_real_teacher_name(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return normalized not in {"", "herr mustermann", "mustermann", "frau mustermann"}


def _build_berlin_focus(settings: Any) -> list[dict[str, str]]:
    focus_items = [
        {
            "title": "SSO-Dienste zuerst",
            "detail": "WebUntis und itslearning sind bereits als echte Einstiegsquellen im Cockpit hinterlegt.",
        },
        {
            "title": "Dokumente bringen den Mehrwert",
            "detail": "Orgaplan und Klassenarbeitsplan bleiben besonders wichtig, weil PDFs und Share-Links im Alltag schnell verstreut sind.",
        },
        {
            "title": "Mail vorerst nur Portal-Logik",
            "detail": "Die Berliner Dienstmail bleibt ohne klassischen IMAP-Weg zunaechst ein Portal-/Hinweis-Modul.",
        },
    ]

    if settings.orgaplan_pdf_url:
        focus_items[1]["detail"] = "Der konkrete Orgaplan ist schon hinterlegt, sodass wir als Naechstes Aenderungen automatisch vergleichen koennen."

    if settings.classwork_plan_url:
        focus_items.append(
            {
                "title": "OneDrive-Freigabe im Blick",
                "detail": "Der Klassenarbeitsplan ist verlinkt, braucht fuer spaetere Automatisierung aber wahrscheinlich einen robusteren Export-Link.",
            }
        )

    return focus_items


def _monitored_documents(settings: Any) -> list[MonitoredDocument]:
    documents = []

    if settings.orgaplan_pdf_url:
        documents.append(
            MonitoredDocument(
                id="orgaplan",
                title="Orgaplan",
                url=settings.orgaplan_pdf_url,
                type="PDF",
                note="Orgaplan-Monitor aktiv.",
            )
        )

    if settings.classwork_plan_url:
        documents.append(
            MonitoredDocument(
                id="classwork",
                title="Klassenarbeitsplan",
                url=settings.classwork_plan_url,
                type="Share-Link",
                note="Klassenarbeitsplan-Monitor aktiv.",
            )
        )

    return documents


def _merge_classwork_cache(plan_classwork: dict[str, Any], cache_path: Path, mock_path: Path | None = None) -> dict[str, Any]:
    """Overlay Playwright-scraped cache (or mock-dashboard snapshot) onto plan_digest classwork.

    Priority:
    1. data/classwork-cache.json  — written by Playwright scraper (local/Render after first scrape)
    2. data/mock-dashboard.json   — embedded snapshot, always present in the repo
    3. plan_classwork             — live plan_digest result (often blocked by HTTP 4xx on OneDrive)
    """
    import json as _json

    def _is_good(data: dict) -> bool:
        return data.get("status") == "ok" and bool(data.get("structuredRows") or data.get("previewRows"))

    # If plan_digest already has live data (e.g. Google Sheets CSV), keep it — no override needed
    if _is_good(plan_classwork):
        return plan_classwork

    def _shape(cached: dict) -> dict:
        return {
            "status": "ok",
            "title": cached.get("title", "Klassenarbeitsplan"),
            "detail": cached.get("detail", ""),
            "updatedAt": cached.get("updatedAt", plan_classwork.get("updatedAt", "")),
            "previewRows": cached.get("previewRows", []),
            "structuredRows": cached.get("structuredRows", []),
            "sourceUrl": cached.get("sourceUrl", plan_classwork.get("sourceUrl", "")),
            "hasChanges": cached.get("hasChanges", False),
            "noChanges": cached.get("noChanges", False),
            "scrapeMode": cached.get("scrapeMode", "playwright"),
        }

    # 1. Playwright cache (local or Render after scrape)
    try:
        if cache_path.exists():
            cached = _json.loads(cache_path.read_text(encoding="utf-8"))
            if _is_good(cached):
                return _shape(cached)
    except Exception as exc:
        print(f"[dashboard] classwork cache read failed: {exc}", flush=True)

    # 2. Embedded snapshot from mock-dashboard.json (always in repo)
    if mock_path is not None:
        try:
            mock_data = _json.loads(mock_path.read_text(encoding="utf-8"))
            mock_cw = mock_data.get("planDigest", {}).get("classwork", {})
            if _is_good(mock_cw):
                print("[dashboard] classwork: using mock-dashboard.json snapshot as fallback", flush=True)
                return _shape(mock_cw)
        except Exception as exc:
            print(f"[dashboard] classwork mock fallback failed: {exc}", flush=True)

    return plan_classwork


def _apply_monitor_priorities(
    priorities: list[dict[str, Any]],
    document_monitor: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    monitor_priorities = []

    for item in document_monitor:
        if item["changed"]:
            monitor_priorities.append(
                {
                    "id": f"monitor-{item['id']}",
                    "title": f"{item['title']} hat sich geaendert",
                    "detail": item["detail"],
                    "priority": "high",
                    "source": "Dokumentenmonitor",
                    "due": "neu",
                }
            )

    return (monitor_priorities + priorities)[:4]
