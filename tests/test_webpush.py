"""Tests für backend/webpush.py (RFC 8291 Verschlüsselung, RFC 8292 VAPID)."""
import json
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from backend import webpush as wp

# RFC 8291, Section 5 / Appendix A
RFC_PLAINTEXT = "When I grow up, I want to be a watermelon"
RFC_AS_PRIVATE = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
RFC_UA_PUBLIC = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
RFC_SALT = "DGv6ra1nlYgDCS1FRnbzlw"
RFC_AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
RFC_BODY = (
    "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wE"
    "qKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
)


def test_encryption_matches_rfc8291_example():
    body = wp.encrypt(
        RFC_PLAINTEXT.encode(),
        RFC_UA_PUBLIC,
        RFC_AUTH,
        salt=wp.b64url_decode(RFC_SALT),
        as_private=wp.private_key_from_b64(RFC_AS_PRIVATE),
    )
    assert wp.b64url_encode(body) == RFC_BODY


def test_vapid_token_is_verifiable():
    private = ec.generate_private_key(ec.SECP256R1())
    scalar = private.private_numbers().private_value.to_bytes(32, "big")
    header = wp.vapid_authorization("https://fcm.googleapis.com/fcm/send/abc", wp.b64url_encode(scalar),
                                    "mailto:test@schule.de", now=1_000_000)
    assert header.startswith("vapid t=")
    token = header.split("t=", 1)[1].split(",", 1)[0]
    k = header.split("k=", 1)[1]
    signing_input, signature_b64 = token.rsplit(".", 1)
    claims = json.loads(wp.b64url_decode(signing_input.split(".")[1]))
    assert claims == {"aud": "https://fcm.googleapis.com", "exp": 1_000_000 + 12 * 3600, "sub": "mailto:test@schule.de"}
    public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), wp.b64url_decode(k))
    raw = wp.b64url_decode(signature_b64)
    signature = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    public.verify(signature, signing_input.encode(), ec.ECDSA(hashes.SHA256()))  # raises if invalid


def test_config_requires_both_keys(monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    assert wp.vapid_config() is None
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    assert wp.vapid_config().subject.startswith("mailto:")


def test_gone_subscriptions_are_reported():
    import io
    from urllib.error import HTTPError

    private = ec.generate_private_key(ec.SECP256R1())
    ua = ec.generate_private_key(ec.SECP256R1()).public_key()
    subscription = {
        "endpoint": "https://push.example/sub/1",
        "p256dh": wp.b64url_encode(wp._public_bytes(ua)),
        "auth": wp.b64url_encode(b"0123456789abcdef"),
    }
    config = wp.VapidConfig("pub", wp.b64url_encode(private.private_numbers().private_value.to_bytes(32, "big")),
                            "mailto:x@y.de")
    gone = HTTPError("https://push.example", 410, "Gone", {}, io.BytesIO(b""))
    with patch.object(wp, "urlopen", side_effect=gone):
        with pytest.raises(wp.SubscriptionGone):
            wp.send(subscription, {"title": "t"}, config)
