"""Excel-Dateien mit kleinen Stilfehlern (z. B. font family > 14) werden trotzdem gelesen."""
import zipfile
from io import BytesIO

import pytest
from openpyxl import Workbook

from backend.file_utils import parse_classwork_xlsx
from backend.plan_digest import load_workbook_lenient


def _xlsx_with_bad_font_family() -> bytes:
    wb = Workbook()
    wb.active["A1"] = "Klasse"
    raw = BytesIO()
    wb.save(raw)
    source = zipfile.ZipFile(BytesIO(raw.getvalue()))
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "xl/styles.xml":
                content = content.replace(b'<family val="2"', b'<family val="34"', 1)
            target.writestr(info, content)
    return out.getvalue()


def test_bad_font_family_is_repaired():
    data = _xlsx_with_bad_font_family()
    assert b'val="34"' in zipfile.ZipFile(BytesIO(data)).read("xl/styles.xml")
    wb = load_workbook_lenient(data, read_only=True, data_only=True)
    assert wb.active["A1"].value == "Klasse"


def test_unreadable_excel_is_never_guessed_as_csv():
    with pytest.raises(ValueError, match="Excel-Datei"):
        parse_classwork_xlsx(b"PK\x03\x04 kaputt")
