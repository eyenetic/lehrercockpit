"""New feedback notifies admins by e-mail (when SMTP is set up)."""
from contextlib import contextmanager

from backend import feedback, mailer


class _SyncThread:
    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


def test_admins_get_a_mail(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "is_configured", lambda: True)
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, html: sent.append((to, subject, html)))
    monkeypatch.setattr("threading.Thread", _SyncThread)

    @contextmanager
    def fake_conn():
        yield object()

    monkeypatch.setattr("backend.db.db_connection", fake_conn)
    monkeypatch.setattr(feedback, "admin_emails", lambda conn: ["admin@example.org"])

    assert feedback.mail_admins_in_background("problem", "Denise", "Stundenplan <leer>", "https://app/admin.html") is True
    assert sent and sent[0][0] == "admin@example.org"
    assert "Problem von Denise" in sent[0][1]
    assert "&lt;leer&gt;" in sent[0][2]  # message is escaped


def test_without_smtp_nothing_is_sent(monkeypatch):
    monkeypatch.setattr(mailer, "is_configured", lambda: False)
    assert feedback.mail_admins_in_background("idee", "Tina", "x", "https://app") is False
