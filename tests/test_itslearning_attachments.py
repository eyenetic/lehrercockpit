"""itslearning-Anhänge über den Server: nur itslearning-Adressen, sichere Dateiarten."""
import io

import pytest

from backend import itslearning_adapter as ad
from backend.config import ItslearningSettings

SETTINGS = ItslearningSettings(base_url="https://berlin.itslearning.com", username="u", password="p", max_updates=1)


class _Resp(io.BytesIO):
    def __init__(self, body, ctype):
        super().__init__(body)
        self.headers = type("H", (), {"get_content_type": lambda self_: ctype})()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Opener:
    def __init__(self, replies):
        self.replies = list(replies)

    def open(self, request, timeout=None):
        return _Resp(*self.replies.pop(0))


@pytest.fixture(autouse=True)
def _fresh_sessions():
    ad._sessions.clear()
    yield
    ad._sessions.clear()


def test_only_itslearning_hosts():
    base = "https://berlin.itslearning.com"
    assert ad.attachment_host_allowed("https://berlin.itslearning.com/file/1", base)
    assert ad.attachment_host_allowed("https://cdn.itslearning.com/x.png", base)
    assert not ad.attachment_host_allowed("https://evil.example/x.png", base)
    assert not ad.attachment_host_allowed("http://berlin.itslearning.com/file/1", base)


def test_picture_is_shown_inline(monkeypatch):
    monkeypatch.setattr(ad, "_login", lambda s: _Opener([(b"PNG", "image/png")]))
    content, ctype, inline = ad.fetch_attachment(SETTINGS, "https://berlin.itslearning.com/file/1")
    assert (content, ctype, inline) == (b"PNG", "image/png", True)


def test_svg_and_html_are_never_shown_inline(monkeypatch):
    monkeypatch.setattr(ad, "_login", lambda s: _Opener([(b"<svg/>", "image/svg+xml")]))
    _, ctype, inline = ad.fetch_attachment(SETTINGS, "https://berlin.itslearning.com/file/2")
    assert (ctype, inline) == ("application/octet-stream", False)


def test_login_page_twice_means_no_access(monkeypatch):
    monkeypatch.setattr(ad, "_login", lambda s: _Opener([(b"<html>", "text/html")]))
    with pytest.raises(ValueError):
        ad.fetch_attachment(SETTINGS, "https://berlin.itslearning.com/file/3")


def test_foreign_url_is_refused():
    with pytest.raises(ValueError):
        ad.fetch_attachment(SETTINGS, "https://evil.example/x.png")
