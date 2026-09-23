"""Shared HTTP helpers: verified TLS and outbound URL validation.

TLS verification is never disabled. python.org builds on macOS ship without
system CA certificates, which used to trigger insecure fallbacks in several
adapters; the certifi bundle fixes that case properly.
"""
from __future__ import annotations

import ipaddress
import socket
import ssl
from functools import lru_cache
from urllib.parse import urlparse


@lru_cache(maxsize=1)
def tls_context() -> ssl.SSLContext:
    """Return a certificate-verifying SSL context (certifi bundle when available)."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


class UnsafeUrlError(ValueError):
    """Raised when a user-supplied URL must not be requested by the server."""


def require_public_https_url(url: str) -> str:
    """Validate a user-supplied URL before the server requests it.

    Only https URLs whose host resolves exclusively to public addresses are
    allowed, so a stored config cannot make the server call internal services.

    Returns the URL without a trailing slash. Raises UnsafeUrlError otherwise.
    """
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.hostname:
        raise UnsafeUrlError("Bitte eine https-Adresse angeben.")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("Die Adresse darf keine Zugangsdaten enthalten.")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrlError("Der Server wurde nicht gefunden.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise UnsafeUrlError("Die Adresse zeigt auf ein internes Netz.")
    return candidate.rstrip("/")
