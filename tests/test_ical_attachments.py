"""Anhänge (ATTACH) aus Kalender-Abos, z. B. Infoblätter an itslearning-Terminen."""
from backend.ical_utils import parse_calendar

FEED = "\r\n".join([
    "BEGIN:VCALENDAR",
    "BEGIN:VEVENT",
    "UID:1",
    "DTSTART:20261110T080000",
    "DTEND:20261110T090000",
    "SUMMARY:Abgabe Referat",
    "ATTACH;FMTTYPE=image/png;FILENAME=Infoblatt.png:https://berlin.itslearning.com/file/abc?x=1",
    "ATTACH:https://berlin.itslearning.com/files/Aufgabe%201.pdf",
    "ATTACH;ENCODING=BASE64;VALUE=BINARY:AAAA",
    "ATTACH:javascript:alert(1)",
    "END:VEVENT",
    "END:VCALENDAR",
])


def test_attachments_are_links_with_names():
    entry = parse_calendar(FEED)[0]
    assert entry.attachments == [
        {"url": "https://berlin.itslearning.com/file/abc?x=1", "name": "Infoblatt.png", "type": "image/png"},
        {"url": "https://berlin.itslearning.com/files/Aufgabe%201.pdf", "name": "Aufgabe 1.pdf", "type": ""},
    ]


def test_entries_without_attachments_have_an_empty_list():
    feed = FEED.replace("ATTACH", "X-IGNORED")
    assert parse_calendar(feed)[0].attachments == []


def test_formatted_description_is_kept():
    feed = FEED.replace("SUMMARY:Abgabe Referat",
                        "SUMMARY:Abgabe Referat\r\nX-ALT-DESC;FMTTYPE=text/html:<table><tr><td>7a</td></tr></table>")
    assert parse_calendar(feed)[0].description_html == "<table><tr><td>7a</td></tr></table>"
    assert parse_calendar(FEED)[0].description_html == ""
