from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .config import load_settings
from .document_monitor import MonitoredDocument, build_document_monitor
from .mail_adapter import fetch_mail_sync


def build_dashboard_payload(mock_path: Path, monitor_state_path: Path) -> dict[str, Any]:
    payload = _load_mock_payload(mock_path)
    settings = load_settings()
    now = datetime.now().astimezone()
    mail_sync = fetch_mail_sync(settings.mail, now)
    document_monitor = build_document_monitor(_monitored_documents(settings), monitor_state_path, now)

    payload["generatedAt"] = now.isoformat()
    payload["teacher"]["name"] = settings.teacher_name
    payload["teacher"]["school"] = settings.school_name
    payload["workspace"] = _build_workspace(settings)
    payload["meta"] = {
        "mode": mail_sync.mode,
        "note": mail_sync.note,
        "lastUpdatedLabel": now.strftime("%H:%M"),
    }
    payload["quickLinks"] = _build_quick_links(settings)
    payload["berlinFocus"] = _build_berlin_focus(settings)
    payload["documentMonitor"] = document_monitor

    payload["sources"] = _merge_source(payload["sources"], mail_sync.source)
    payload["sources"] = _apply_source_configuration(payload["sources"], settings)
    payload["documents"] = _apply_document_configuration(payload["documents"], settings)
    payload["priorities"] = _apply_monitor_priorities(payload["priorities"], document_monitor)

    if mail_sync.messages:
        payload["messages"] = mail_sync.messages + [message for message in payload["messages"] if message["channel"] != "mail"]
        payload["priorities"] = _merge_priorities(mail_sync.priorities, payload["priorities"])
    else:
        payload["sources"] = _set_source_detail(payload["sources"], "mail", mail_sync.source)

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
    combined = incoming + [priority for priority in existing if priority["source"] != "Dienstmail"]
    return combined[:4]


def _apply_source_configuration(existing_sources: list[dict[str, Any]], settings: Any) -> list[dict[str, Any]]:
    configured_sources = []
    for source in existing_sources:
        updated = dict(source)

        if source["id"] == "webuntis" and settings.webuntis_base_url:
            updated["status"] = "ok"
            updated["lastSync"] = "konfiguriert"
            updated["cadence"] = "naechster Schritt: Session-Login"
            updated["nextStep"] = "Session-Cookie oder offizieller API-Zugang fuer Stundenplan und Vertretung pruefen"
            updated["detail"] = f"WebUntis-Basis gesetzt: {settings.webuntis_base_url}"

        if source["id"] == "itslearning" and settings.itslearning_base_url:
            updated["status"] = "ok"
            updated["lastSync"] = "konfiguriert"
            updated["cadence"] = "naechster Schritt: Login-/Feed-Pruefung"
            updated["nextStep"] = "itslearning-Startpunkt pruefen und relevante Ansichten identifizieren"
            updated["detail"] = f"itslearning-Basis gesetzt: {settings.itslearning_base_url}"

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
        ("itslearning", "itslearning", settings.itslearning_base_url, "Lernen", "Kurse, Aufgaben und Kursmeldungen"),
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

    return links


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
