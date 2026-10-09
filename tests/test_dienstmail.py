"""Dienstmail via IMAP: read-only, headers only, readable errors."""
import imaplib

import pytest

from backend import dienstmail


class FakeIMAP:
    calls = []

    def __init__(self, host, port, ssl_context=None, timeout=None):
        FakeIMAP.calls = [("connect", host, port)]

    def login(self, user, password):
        FakeIMAP.calls.append(("login", user))
        if password != "app-pw":
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    def select(self, mailbox, readonly=False):
        FakeIMAP.calls.append(("select", mailbox, readonly))
        return "OK", [b"3"]

    def uid(self, command, *args):
        FakeIMAP.calls.append(("uid", command, args))
        if command == "search":
            return "OK", [b"7 8 9"]
        header = (b"From: =?utf-8?q?M=C3=BCller=2C_Anna?= <anna@schule.de>\r\n"
                  b"Subject: Elternabend\r\nDate: Fri, 09 Oct 2026 10:15:00 +0200\r\n\r\n")
        return "OK", [
            (b"1 (UID 9 FLAGS () BODY[HEADER.FIELDS (FROM SUBJECT DATE)] {120}", header), b")",
            (b"2 (UID 8 FLAGS (\\Seen) BODY[HEADER.FIELDS (FROM SUBJECT DATE)] {120}", header), b")",
        ]

    def logout(self):
        FakeIMAP.calls.append(("logout",))


@pytest.fixture(autouse=True)
def fake_imap(monkeypatch):
    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeIMAP)
    dienstmail._cache.clear()


def test_reads_newest_headers_without_marking_them_read():
    messages = dienstmail.fetch_headers("ich@schule.berlin.de", "app-pw")
    assert [m["id"] for m in messages] == ["9", "8"]          # newest first
    assert messages[0]["from"] == "Müller, Anna" and messages[0]["subject"] == "Elternabend"
    assert messages[0]["unread"] is True and messages[1]["unread"] is False
    assert ("select", "INBOX", True) in FakeIMAP.calls        # EXAMINE: read-only
    fetch = next(c for c in FakeIMAP.calls if c[0] == "uid" and c[1] == "fetch")
    assert "BODY.PEEK" in fetch[2][1]                          # does not set \\Seen
    assert FakeIMAP.calls[-1] == ("logout",)


def test_wrong_app_password_gives_a_readable_message():
    with pytest.raises(dienstmail.DienstmailError, match="App-Passwort"):
        dienstmail.fetch_headers("ich@schule.berlin.de", "falsch")


def test_payload_caches_and_reports_errors():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    assert dienstmail.build_payload({}, now)["configured"] is False
    bad = dienstmail.build_payload({"address": "ich@schule.berlin.de", "app_password": "falsch"}, now)
    assert bad["data"]["error"] and bad["data"]["messages"] == []
    good = dienstmail.build_payload({"address": "ich@schule.berlin.de", "app_password": "app-pw"}, now)
    assert len(good["data"]["messages"]) == 2 and good["data"]["webmail_url"].startswith("https://")


class FakeIMAPOrder(FakeIMAP):
    """UID order ≠ date order (a mail moved into the inbox later)."""

    def uid(self, command, *args):
        FakeIMAP.calls.append(("uid", command, args))
        if command == "search":
            return "OK", [b"1 2"]
        def row(uid, date):
            return (f"x (UID {uid} FLAGS ())".encode(), f"From: a@b.de\r\nSubject: s{uid}\r\nDate: {date}\r\n\r\n".encode())
        return "OK", [row(2, "Mon, 05 Oct 2026 08:00:00 +0200"), b")", row(1, "Fri, 09 Oct 2026 08:00:00 +0200"), b")"]


def test_messages_are_sorted_by_date(monkeypatch):
    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeIMAPOrder)
    messages = dienstmail.fetch_headers("ich@schule.berlin.de", "app-pw")
    assert [m["id"] for m in messages] == ["1", "2"]  # 09.10. before 05.10.


class FakeIMAPBody(FakeIMAP):
    def uid(self, command, *args):
        FakeIMAP.calls.append(("uid", command, args))
        raw = (b"From: a@b.de\r\nSubject: Elternabend\r\nMIME-Version: 1.0\r\n"
               b"Content-Type: multipart/mixed; boundary=X\r\n\r\n"
               b"--X\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>Liebe Kolleg:innen,</p><p>Raum 104 &amp; 105</p>\r\n"
               b"--X\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename=plan.pdf\r\n\r\nJVBERi0=\r\n--X--\r\n")
        return "OK", [(b"1 (UID 9 BODY[] {300}", raw), b")"]


def test_message_text_is_read_without_marking_it_read(monkeypatch):
    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeIMAPBody)
    message = dienstmail.fetch_message("ich@schule.berlin.de", "app-pw", "9")
    assert "Liebe Kolleg:innen" in message["text"] and "Raum 104 & 105" in message["text"]
    assert message["attachments"] == ["plan.pdf"] and message["truncated"] is False
    fetch = next(c for c in FakeIMAP.calls if c[0] == "uid" and c[1] == "fetch")
    assert fetch[2][1].startswith("(BODY.PEEK[]")
    assert ("select", "INBOX", True) in FakeIMAP.calls


def test_message_id_must_be_a_number():
    with pytest.raises(dienstmail.DienstmailError):
        dienstmail.fetch_message("ich@schule.berlin.de", "app-pw", "1:*")
