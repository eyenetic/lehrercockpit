"""Tests für den Excel-Leser des Klassenarbeitsplans (backend/plan_digest.py)."""
from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook

from backend.plan_digest import _cell_date, _normalize_class_label, _read_classwork_workbook, _sheet_month_year

NOW = datetime(2026, 9, 28, 8, 0)


def _workbook(sheets: dict[str, list[list]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _read(data: bytes) -> dict:
    return _read_classwork_workbook(data, NOW, detail="Test.", source_url="")


def test_last_years_layout_month_sheets_with_classes_down():
    data = _workbook({"November 2026": [
        ["Klasse", "Mo 02.11.", "Di 03.11.", "Mi 04.11."],
        ["7a", "", "1. KA E Kö", ""],
        ["10b", "1. LEK Geo", "", "WPF 1. KA"],
        ["Q1", "", "", "Klausur Ma"],
    ]})
    result = _read(data)
    assert result["status"] == "ok"
    assert [(e["classLabel"], e["isoDate"], e["kind"]) for e in result["entries"]] == [
        ("10B", "2026-11-02", "LEK"),
        ("7A", "2026-11-03", "Klassenarbeit"),
        ("10B", "2026-11-04", "Klassenarbeit"),
        ("Q1", "2026-11-04", "Klausur"),
    ]
    assert result["lastDate"] == "2026-11-04"


def test_dates_down_classes_across_with_real_dates():
    data = _workbook({"KA-Plan 2026-27": [
        ["Datum", "7A", "7B", "8A"],
        [datetime(2026, 10, 5), "KA Deutsch", "", ""],
        [datetime(2026, 10, 6), "", "LEK Bio", "Vokabeltest E"],
        [datetime(2026, 10, 7), "", "", ""],
    ]})
    entries = _read(data)["entries"]
    assert [(e["classLabel"], e["isoDate"], e["kind"]) for e in entries] == [
        ("7A", "2026-10-05", "Klassenarbeit"),
        ("7B", "2026-10-06", "LEK"),
        ("8A", "2026-10-06", "Test"),
    ]


def test_sheet_without_year_uses_the_school_year():
    data = _workbook({"Januar": [
        ["", "12.01.", "13.01."],
        ["Kl. 9c", "KA Ma", ""],
        ["9 d", "", "2. KA Deu"],
    ]})
    entries = _read(data)["entries"]
    assert [(e["classLabel"], e["isoDate"]) for e in entries] == [("9C", "2027-01-12"), ("9D", "2027-01-13")]


def test_nothing_recognised_names_the_sheets():
    result = _read(_workbook({"Übersicht": [["Name", "Wert"], ["Ferien", "Herbst"]]}))
    assert result["status"] == "warning" and result["entries"] == []
    assert "„Übersicht“" in result["detail"]


def test_cell_dates():
    assert _cell_date(datetime(2026, 9, 1, 0, 0)) == date(2026, 9, 1)
    assert _cell_date("Mo 01.09.", (9, 2026)) == date(2026, 9, 1)
    assert _cell_date("1.9.", None, 2026) == date(2026, 9, 1)
    assert _cell_date("15.01.", None, 2026) == date(2027, 1, 15)
    assert _cell_date("05.01.", (12, 2026)) == date(2027, 1, 5)
    assert _cell_date("01.09.2026") == date(2026, 9, 1)
    assert _cell_date("2026-09-01") == date(2026, 9, 1)
    assert _cell_date("KA Deutsch") is None
    assert _cell_date("31.02.", (2, 2027)) is None


def test_sheet_names():
    assert _sheet_month_year("November 2025") == (11, 2025)
    assert _sheet_month_year("Nov. 25") == (11, 2025)
    assert _sheet_month_year("Oktober") == (10, None)
    assert _sheet_month_year("09.2026") == (9, 2026)
    assert _sheet_month_year("2026-09") == (9, 2026)
    assert _sheet_month_year("Übersicht") is None


def test_class_labels():
    assert _normalize_class_label("7a") == "7A"
    assert _normalize_class_label("07A") == "7A"
    assert _normalize_class_label("Kl. 10b") == "10B"
    assert _normalize_class_label("7 a (Mü)") == "7A"
    assert _normalize_class_label("Q1/Q2") == "Q1/2"
    assert _normalize_class_label("Q3") == "Q3"
    assert _normalize_class_label("Klasse") == ""
    assert _normalize_class_label("4a") == ""
    assert _normalize_class_label("Mathe") == ""
