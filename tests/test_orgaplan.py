"""Tests für backend/orgaplan.py – Quelle finden, Monatsseiten lesen, Zwischenstand."""
import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from backend import orgaplan as og

NOW = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)  # Mo 08:00 Berlin

# One month page as pdfplumber returns it (layout 2026/27: KW | Tag | …).
SEPTEMBER = [
    ["", "", "", "", "", "", "", ""],
    ["KW", "Tag", "allgemeine Termine", "Mittelstufe", "Bemerkungen", "Oberstufe", "Bemerkungen", ""],
    ["36.", "1", "", "", "", "", "Kursfahrt Q3 London + Kopenhagen", ""],
    ["", "2", "Workshop Leitbild SuS, Sl, Mo", "", "", "", "Workshop Leitbild SuS, Sl, Mo", ""],
    ["", "3", "", "Zentraler Elternabend 19 h Sek I", "", "Q1/Q3: 18 h Aula, Elternabend", "", ""],
    ["", "5", "", "", "", "", "", ""],
    ["", "11", "", "", "", "Q3: 5.PK - Deadline Genehmigung Thema\ndurch Lehrkraft", "", ""],
    ["", "17", "Juniorwahl\n1. Schulkonferenz 18.30 h", "", "", "", "", ""],
    ["40.", "28", "Klassenfahrt Bilbao", "", "Klassenfahrt 10a + 10c", "", "", ""],
    ["", "31", "gibt es nicht", "", "", "", "", ""],
]

# Older layout (2025/26): no KW column, the day column has no header.
OLD_LAYOUT = [
    ["", "allgemeine Termine", "Mittelstufe", "Bemerkungen", "Oberstufe", "Bemerkungen"],
    ["1", "", "", "", "", ""],
    ["2", "SV Wahl", "", "", "Q3: Abgabe Anträge 5.PK", ""],
    ["13", "", "", "", "Q1/3: Klausur LK 1", "Vorlage Kurshefte"],
]


def test_entries_follow_the_table_rows():
    entries = og.entries_from_table(SEPTEMBER, 2026, 9)
    by_day = {e["isoDate"]: e for e in entries}
    assert list(by_day) == ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-11", "2026-09-17", "2026-09-28"]
    # Remarks column carries the item when the level column is empty
    assert by_day["2026-09-01"]["upper"] == "Kursfahrt Q3 London + Kopenhagen"
    # Same text for everyone and for a level: shown once, as "Allgemein"
    assert by_day["2026-09-02"]["general"] == "Workshop Leitbild SuS, Sl, Mo"
    assert by_day["2026-09-02"]["upper"] == ""
    # Wrapped line joins with a space, separate items with " · "
    assert by_day["2026-09-11"]["upper"] == "Q3: 5.PK - Deadline Genehmigung Thema durch Lehrkraft"
    assert by_day["2026-09-17"]["general"] == "Juniorwahl · 1. Schulkonferenz 18.30 h"
    assert by_day["2026-09-17"]["title"] == "Juniorwahl"
    assert by_day["2026-09-28"]["middle"] == "Klassenfahrt 10a + 10c"
    assert by_day["2026-09-28"]["weekday"] == "Mo"
    assert by_day["2026-09-03"]["text"] == (
        "Mittelstufe: Zentraler Elternabend 19 h Sek I | Oberstufe: Q1/Q3: 18 h Aula, Elternabend")


def test_older_layout_without_day_header():
    entries = og.entries_from_table(OLD_LAYOUT, 2025, 9)
    assert [e["isoDate"] for e in entries] == ["2025-09-02", "2025-09-13"]
    assert entries[1]["upper"] == "Q1/3: Klausur LK 1" and entries[1]["upperNotes"] == "Vorlage Kurshefte"


def test_pages_without_plan_table_are_ignored():
    assert og.entries_from_table([["Anlage: Vorbereitung 5. PK"], ["Text"]], 2026, 9) == []


@pytest.mark.parametrize("line,expected", [
    ("Q1: n u r Klausur", "Q1: nur Klausur"),
    ("Integrationsfahrt 7a + 7b", "Integrationsfahrt 7a + 7b"),
])
def test_letter_spacing_is_removed(line, expected):
    assert og.join_cell(line) == expected


def test_cell_continuation_rules():
    assert og.join_cell("Klausuren LK-Schiene 1 (außer\nPh, Cs Q3)") == "Klausuren LK-Schiene 1 (außer Ph, Cs Q3)"
    assert og.join_cell("Abgabe dezentrale\nAufgabenvorschläge") == "Abgabe dezentrale Aufgabenvorschläge"
    assert og.join_cell("Q3: Klausur alle LK, ab\n8. Stde, R402") == "Q3: Klausur alle LK, ab 8. Stde, R402"
    assert og.join_cell("Integrationsfahrt 7a + 7b + 7c\nPersonalversammlung 12-14 h FU\nHenry-Ford-Bau") == \
        "Integrationsfahrt 7a + 7b + 7c · Personalversammlung 12-14 h FU Henry-Ford-Bau"
    assert og.join_cell(None) == ""


def test_school_year_decides_the_year_of_each_month():
    school_year = og.school_year_of("Organisationsplan 2026/27")
    assert school_year == (2026, 2027)
    assert og.page_month("September Stand 31.08.2026", school_year) == (2026, 9, "31.08.2026")
    assert og.page_month("JanuarStand 31.08.2026 September", school_year) == (2027, 1, "31.08.2026")


def test_without_school_year_the_stand_date_is_used_sensibly():
    assert og.page_month("Januar Stand 15.12.2025", None)[0] == 2026
    assert og.page_month("Februar Stand 03.03.2026", None)[0] == 2026
    assert og.page_month("Kein Monat hier", None) is None


def test_parse_pdf_rejects_non_pdf():
    with pytest.raises(og.OrgaplanError, match="keine PDF"):
        og.parse_pdf(b"<html>")


# ── Source settings ──────────────────────────────────────────────────────────

def test_old_wordpress_pdf_link_becomes_automatic():
    source = og.normalize_source(None, {
        "orgaplan_pdf_url": "https://hermann-ehlers-schule.de/wp-content/uploads/2026/03/Orgaplan-2025_26-ab-April.pdf"})
    assert source == {"mode": "auto", "site": "https://hermann-ehlers-schule.de", "query": "Orgaplan"}


def test_other_legacy_values():
    assert og.normalize_source(None, {"orgaplan_url": "https://schule.de/termine"})["site"] == "https://schule.de/termine"
    assert og.normalize_source(None, {"orgaplan_pdf_url": "https://cloud.de/plan.pdf"}) == \
        {"mode": "fixed", "pdf_url": "https://cloud.de/plan.pdf"}
    assert og.normalize_source({"mode": "fixed", "pdf_url": ""})["mode"] == "auto"


def test_validate_source():
    assert og.validate_source({"mode": "auto", "site": "https://schule.de", "query": ""}) == \
        {"mode": "auto", "site": "https://schule.de", "query": "Orgaplan"}
    with pytest.raises(og.OrgaplanError):
        og.validate_source({"mode": "fixed", "pdf_url": "http://schule.de/a.pdf"})
    with pytest.raises(og.OrgaplanError):
        og.validate_source({"mode": "anders"})


# ── Discovery ────────────────────────────────────────────────────────────────

def _fake_get(responses):
    def fake(url, **_kwargs):
        for prefix, (body, headers) in responses.items():
            if url.startswith(prefix):
                if isinstance(body, Exception):
                    raise body
                return body, headers
        raise og.OrgaplanError("HTTP 404")
    return fake


def test_wordpress_media_search_picks_the_newest_pdf():
    media = [
        {"date": "2026-09-03T07:22:09", "mime_type": "application/pdf", "slug": "orgaplan-2026_27",
         "source_url": "https://schule.de/wp-content/uploads/2026/09/Orgaplan-2026_27-31.08.2026.pdf",
         "title": {"rendered": "Orgaplan 2026_27"}},
        {"date": "2026-05-29T12:22:48", "mime_type": "application/pdf", "slug": "orgaplan-2025_26",
         "source_url": "https://schule.de/wp-content/uploads/2026/05/Orgaplan-2025_26-Mai_Juni.pdf",
         "title": {"rendered": "Orgaplan"}},
    ]
    fake = _fake_get({"https://schule.de/wp-json/": (json.dumps(media).encode(), {"content-type": "application/json"})})
    with patch.object(og, "_get", side_effect=fake):
        found = og.discover_latest_pdf("https://schule.de", "Orgaplan")
    assert found["url"].endswith("Orgaplan-2026_27-31.08.2026.pdf")
    assert found["published"] == "2026-09-03T07:22:09" and found["via"] == "wordpress"


def test_web_page_links_are_the_fallback():
    html = b"""<a href="/files/Orgaplan-2025_26.pdf">Orgaplan alt</a>
               <a href="/wp-content/uploads/2026/09/Orgaplan-2026_27.pdf">Orgaplan</a>
               <a href="/files/Speiseplan.pdf">Speiseplan</a>"""
    fake = _fake_get({"https://schule.de/wp-json/": (og.OrgaplanError("HTTP 404"), {}),
                      "https://schule.de/service": (html, {"content-type": "text/html; charset=utf-8"})})
    with patch.object(og, "_get", side_effect=fake):
        found = og.discover_latest_pdf("https://schule.de/service", "Orgaplan")
    assert found["url"] == "https://schule.de/wp-content/uploads/2026/09/Orgaplan-2026_27.pdf"
    assert found["via"] == "webseite"


def test_nothing_found_is_explained():
    fake = _fake_get({"https://schule.de/wp-json/": (b"[]", {"content-type": "application/json"}),
                      "https://schule.de": (b"<p>keine Links</p>", {"content-type": "text/html"})})
    with patch.object(og, "_get", side_effect=fake):
        with pytest.raises(og.OrgaplanError, match="keine PDF"):
            og.discover_latest_pdf("https://schule.de", "Orgaplan")


# ── Digest and refresh ───────────────────────────────────────────────────────

ENTRIES = [
    {"isoDate": "2026-09-10", "dateLabel": "10.09.", "title": "SV Wahl", "text": "Allgemein: SV Wahl"},
    {"isoDate": "2026-09-28", "dateLabel": "28.09.", "title": "Klassenfahrt", "text": "Allgemein: Klassenfahrt"},
    {"isoDate": "2026-10-01", "dateLabel": "01.10.", "title": "Konferenz", "text": "Allgemein: Gesamtkonferenz"},
    {"isoDate": "2026-12-01", "dateLabel": "01.12.", "title": "Später", "text": "Allgemein: Später"},
]
AUTO = {"mode": "auto", "site": "https://schule.de", "query": "Orgaplan"}


def test_digest_windows():
    digest = og.build_digest({"entries": ENTRIES, "school_year": "2026/27", "stand": "31.08.2026",
                              "pdf_url": "https://schule.de/o.pdf"}, AUTO, NOW)
    assert digest["status"] == "ok"
    assert [e["isoDate"] for e in digest["upcoming"]] == ["2026-09-28", "2026-10-01"]
    assert [e["isoDate"] for e in digest["today_entries"]] == ["2026-09-28"]
    assert [e["isoDate"] for e in digest["week_entries"]] == ["2026-09-28", "2026-10-01"]
    assert digest["highlights"][0]["title"] == "Konferenz"
    assert digest["monthLabel"] == "September"
    assert digest["sourceUrl"] == "https://schule.de/o.pdf"


def test_digest_says_when_the_plan_is_outdated_or_missing():
    old = og.build_digest({"entries": ENTRIES[:1], "school_year": "2025/26"}, AUTO, NOW)
    assert old["status"] == "outdated" and "10.09.2026" in old["detail"]
    assert og.build_digest({}, AUTO, NOW)["status"] == "pending"
    failed = og.build_digest({"error": "Schulwebseite nicht erreichbar."}, AUTO, NOW)
    assert failed["status"] == "error" and failed["detail"] == "Schulwebseite nicht erreichbar."


def test_refresh_due():
    fresh = {"source_key": og.source_key(AUTO), "checked_at": "2026-09-28T05:00:00+00:00", "parser": og.PARSER_VERSION}
    assert not og.refresh_due(fresh, AUTO, NOW)
    assert og.refresh_due({**fresh, "parser": og.PARSER_VERSION - 1}, AUTO, NOW)  # read again after parser changes
    assert og.refresh_due({**fresh, "checked_at": "2026-09-27T20:00:00+00:00"}, AUTO, NOW)
    assert og.refresh_due({**fresh, "error": "x", "checked_at": "2026-09-28T05:20:00+00:00"}, AUTO, NOW)
    assert og.refresh_due(fresh, {"mode": "fixed", "pdf_url": "https://x/y.pdf"}, NOW)


def test_refresh_reads_the_new_pdf_and_keeps_entries_on_errors():
    saved = {}
    parsed = {"entries": ENTRIES, "school_year": "2026/27", "stand": "31.08.2026",
              "first_date": "2026-09-10", "last_date": "2026-12-01"}
    found = {"url": "https://schule.de/o-neu.pdf", "name": "o-neu.pdf", "published": "2026-09-03", "via": "wordpress"}
    with patch.object(og, "load_state", side_effect=lambda: dict(saved)), \
            patch.object(og, "save_state", side_effect=lambda state: saved.update(state)), \
            patch.object(og, "discover_latest_pdf", return_value=found), \
            patch.object(og, "_get", return_value=(b"%PDF-1.7", {"last-modified": "Wed"})), \
            patch.object(og, "parse_pdf", return_value=parsed) as parse:
        state = og.refresh(AUTO, NOW)
        assert state["pdf_url"] == "https://schule.de/o-neu.pdf" and state["error"] is None
        assert len(state["entries"]) == 4
        # Same file within a day: not downloaded and parsed again
        og.refresh(AUTO, NOW)
        assert parse.call_count == 1
    with patch.object(og, "load_state", side_effect=lambda: dict(saved)), \
            patch.object(og, "save_state", side_effect=lambda state: saved.update(state)), \
            patch.object(og, "discover_latest_pdf", side_effect=og.OrgaplanError("Webseite nicht erreichbar.")):
        state = og.refresh(AUTO, NOW)
    assert state["error"] == "Webseite nicht erreichbar."
    assert len(state["entries"]) == 4  # the last good plan stays


def test_layout_decides_between_wrapped_line_and_new_item():
    # "fits": the next line's first word would have fitted → a deliberate break → new item
    assert og.join_lines(["Bibliothek 7c 10.00 h", "Chemieprojekttag 8. Klassen"], [None, True]) == \
        "Bibliothek 7c 10.00 h · Chemieprojekttag 8. Klassen"
    # continuation markers win even over a deliberate break
    assert og.join_lines(["Einschulungsfeier neue 7. Klassen;", "11 h; Aula"], [None, True]) == \
        "Einschulungsfeier neue 7. Klassen; 11 h; Aula"
    # did not fit: wrapped, unless the text clearly starts a new item
    assert og.join_lines(["Teilnahme einzelner SuS am Berliner", "Schulchorpreis im FEZ"], [None, False]) == \
        "Teilnahme einzelner SuS am Berliner Schulchorpreis im FEZ"
    assert og.join_lines(["Zensurenkonf. Sek I, online, 14 h", "Korrekturschluss Noten LUSD"], [None, False]) == \
        "Zensurenkonf. Sek I, online, 14 h · Korrekturschluss Noten LUSD"
    assert og.join_lines(["Einführung in die 5.PK; 6. Stde", "Unterricht nach Plan"], [None, False]) == \
        "Einführung in die 5.PK; 6. Stde Unterricht nach Plan"
    assert og.join_lines(["Klausur Q1: GK 1 + Q3", "GK 2"], [None, False]) == "Klausur Q1: GK 1 + Q3 GK 2"
