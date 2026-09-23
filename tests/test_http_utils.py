"""Tests für backend/http_utils.py (TLS-Kontext, Prüfung von Nutzer-URLs)."""
import socket
import ssl

import pytest

from backend import http_utils
from backend.http_utils import UnsafeUrlError, require_public_https_url, tls_context


def _resolve_to(monkeypatch, address):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]
    monkeypatch.setattr(http_utils.socket, "getaddrinfo", fake_getaddrinfo)


def test_tls_context_verifies_certificates():
    context = tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_public_https_url_is_accepted(monkeypatch):
    _resolve_to(monkeypatch, "93.184.216.34")
    assert require_public_https_url("https://cloud.schule.de/") == "https://cloud.schule.de"


@pytest.mark.parametrize("url", ["http://cloud.schule.de", "ftp://cloud.schule.de", "cloud.schule.de", ""])
def test_non_https_urls_are_rejected(url):
    with pytest.raises(UnsafeUrlError):
        require_public_https_url(url)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1"])
def test_internal_addresses_are_rejected(monkeypatch, address):
    _resolve_to(monkeypatch, address)
    with pytest.raises(UnsafeUrlError):
        require_public_https_url("https://intern.example")


def test_credentials_in_url_are_rejected(monkeypatch):
    _resolve_to(monkeypatch, "93.184.216.34")
    with pytest.raises(UnsafeUrlError):
        require_public_https_url("https://user:pass@cloud.schule.de")
