"""Erzeugt ein VAPID-Schlüsselpaar für Web-Push.

Ausführen:  python3 scripts/generate_vapid_keys.py
Die drei Zeilen als Umgebungsvariablen beim Backend (Render) eintragen.
Den privaten Schlüssel niemals ins Repository committen.
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


key = ec.generate_private_key(ec.SECP256R1())
public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
private = key.private_numbers().private_value.to_bytes(32, "big")
print(f"VAPID_PUBLIC_KEY={_b64(public)}")
print(f"VAPID_PRIVATE_KEY={_b64(private)}")
print("VAPID_SUBJECT=mailto:admin@deine-schule.de")
