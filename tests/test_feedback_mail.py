"""New feedback lands in the admins' own Dienstmail inbox (IMAP APPEND, nothing is sent)."""
from contextlib import contextmanager

from backend import dienstmail, feedback


class _SyncThread:
    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


@contextmanager
def _fake_conn():
    yield object()


def _sync(monkeypatch, boxes):
    monkeypatch.setattr("threading.Thread", _SyncThread)
    monkeypatch.setattr("backend.db.db_connection", _fake_conn)
    monkeypatch.setattr(feedback, "admin_mailboxes", lambda conn: boxes)


def test_feedback_is_put_into_admin_inbox(monkeypatch):
    stored = []
    _sync(monkeypatch, [("admin@example.org", "pw")])
    monkeypatch.setattr(dienstmail, "put_into_inbox", lambda *args: stored.append(args))

    feedback.mail_admins_in_background("problem", "Denise", "Stundenplan leer", "https://app/admin.html")

    assert len(stored) == 1
    address, password, subject, text = stored[0]
    assert address == "admin@example.org" and password == "pw"
    assert subject == "Lehrercockpit: Problem von Denise"
    assert "Stundenplan leer" in text and "https://app/admin.html" in text


def test_without_connected_dienstmail_nothing_happens(monkeypatch):
    stored = []
    _sync(monkeypatch, [])
    monkeypatch.setattr(dienstmail, "put_into_inbox", lambda *args: stored.append(args))
    feedback.mail_admins_in_background("idee", "Tina", "x", "https://app")
    assert stored == []


def test_one_failing_inbox_does_not_stop_the_others(monkeypatch):
    stored = []
    _sync(monkeypatch, [("a@example.org", "bad"), ("b@example.org", "pw")])

    def put(address, password, subject, text):
        if password == "bad":
            raise dienstmail.DienstmailError("nope")
        stored.append(address)

    monkeypatch.setattr(dienstmail, "put_into_inbox", put)
    feedback.mail_admins_in_background("frage", "Tina", "x", "https://app")
    assert stored == ["b@example.org"]


def test_put_into_inbox_appends_unread_message(monkeypatch):
    calls = {}

    class FakeIMAP:
        def __init__(self, *a, **k):
            pass

        def login(self, user, pw):
            calls["login"] = user

        def append(self, mailbox, flags, when, raw):
            calls.update(mailbox=mailbox, flags=flags, raw=raw)
            return "OK", [b""]

        def logout(self):
            calls["logout"] = True

    monkeypatch.setattr(dienstmail.imaplib, "IMAP4_SSL", FakeIMAP)
    dienstmail.put_into_inbox("me@example.org", "pw", "Lehrercockpit: Idee von Tina", "Hallo")
    assert calls["mailbox"] == "INBOX" and calls["flags"] == ""  # no \\Seen → shows as unread
    assert b"Subject: Lehrercockpit: Idee von Tina" in calls["raw"]
    assert b"To: me@example.org" in calls["raw"]
    assert calls["logout"]
