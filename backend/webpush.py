"""Minimal Web Push sender: message encryption (RFC 8291, aes128gcm) and VAPID (RFC 8292).

Implemented on top of `cryptography` (already a dependency) instead of
pywebpush, which would pull in aiohttp and requests.

Keys come from the environment:
  VAPID_PUBLIC_KEY   uncompressed P-256 point, base64url (65 bytes)
  VAPID_PRIVATE_KEY  private scalar, base64url (32 bytes)
  VAPID_SUBJECT      contact, e.g. mailto:admin@schule.de
Generate them with scripts/generate_vapid_keys.py.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import time
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .http_utils import tls_context

RECORD_SIZE = 4096
TIMEOUT = 15


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    value = value.strip()
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _hkdf_block(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    """HKDF-SHA256 for outputs of at most one block (all RFC 8291 uses)."""
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:length]


def _public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def private_key_from_b64(value: str) -> ec.EllipticCurvePrivateKey:
    return ec.derive_private_key(int.from_bytes(b64url_decode(value), "big"), ec.SECP256R1())


def encrypt(plaintext: bytes, ua_public_b64: str, auth_secret_b64: str, *,
            salt: bytes | None = None, as_private: ec.EllipticCurvePrivateKey | None = None) -> bytes:
    """Encrypt a push message body for one subscription (RFC 8291 / RFC 8188).

    salt and as_private are only passed in tests (RFC 8291 example); normally random.
    """
    ua_public_bytes = b64url_decode(ua_public_b64)
    auth_secret = b64url_decode(auth_secret_b64)
    ua_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public_bytes)
    as_private = as_private or ec.generate_private_key(ec.SECP256R1())
    as_public_bytes = _public_bytes(as_private.public_key())
    salt = salt or os.urandom(16)

    ecdh_secret = as_private.exchange(ec.ECDH(), ua_public)
    key_info = b"WebPush: info\x00" + ua_public_bytes + as_public_bytes
    ikm = _hkdf_block(auth_secret, ecdh_secret, key_info, 32)
    cek = _hkdf_block(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf_block(salt, ikm, b"Content-Encoding: nonce\x00", 12)

    if len(plaintext) + 1 + 16 > RECORD_SIZE:
        raise ValueError("Push-Nachricht ist zu lang.")
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)  # 0x02 = last record
    header = salt + struct.pack("!IB", RECORD_SIZE, len(as_public_bytes)) + as_public_bytes
    return header + ciphertext


def vapid_authorization(endpoint: str, private_key_b64: str, subject: str, *, now: float | None = None) -> str:
    """Authorization header value for the push service of this endpoint (RFC 8292)."""
    parsed = urlparse(endpoint)
    claims = {
        "aud": f"{parsed.scheme}://{parsed.netloc}",
        "exp": int((now or time.time()) + 12 * 3600),
        "sub": subject,
    }
    header = {"typ": "JWT", "alg": "ES256"}
    signing_input = (
        b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    )
    key = private_key_from_b64(private_key_b64)
    r, s = decode_dss_signature(key.sign(signing_input.encode("ascii"), ec.ECDSA(hashes.SHA256())))
    signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    token = signing_input + "." + b64url_encode(signature)
    return f"vapid t={token}, k={b64url_encode(_public_bytes(key.public_key()))}"


@dataclass
class VapidConfig:
    public_key: str
    private_key: str
    subject: str


def vapid_config() -> VapidConfig | None:
    public_key = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    private_key = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    subject = os.environ.get("VAPID_SUBJECT", "").strip() or "mailto:admin@lehrercockpit.com"
    if not (public_key and private_key):
        return None
    return VapidConfig(public_key, private_key, subject)


class SubscriptionGone(Exception):
    """The push service no longer knows this subscription (HTTP 404/410)."""


def send(subscription: dict, payload: dict, config: VapidConfig, *, ttl: int = 12 * 3600) -> int:
    """Send one push message. Returns the HTTP status; raises SubscriptionGone on 404/410."""
    endpoint = str(subscription["endpoint"])
    if urlparse(endpoint).scheme != "https":
        raise SubscriptionGone("Ungültiger Push-Endpunkt.")
    body = encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   subscription["p256dh"], subscription["auth"])
    request = Request(endpoint, data=body, method="POST", headers={
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(ttl),
        "Urgency": "normal",
        "Authorization": vapid_authorization(endpoint, config.private_key, config.subject),
    })
    try:
        with urlopen(request, timeout=TIMEOUT, context=tls_context()) as response:
            return response.status
    except HTTPError as exc:
        if exc.code in (404, 410):
            raise SubscriptionGone(f"HTTP {exc.code}") from exc
        return exc.code
