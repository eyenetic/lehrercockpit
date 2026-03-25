"""
Symmetric encryption for sensitive module configuration values.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` library.
Key material is loaded from the ENCRYPTION_KEY environment variable.
The key must be a URL-safe base64-encoded 32-byte value (Fernet format).

Generate a key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Prefix that marks an encrypted value stored in the DB
_ENC_PREFIX = "enc:"

# Sensitive field patterns — a key is sensitive if it contains any of these substrings (lowercase)
_SENSITIVE_PATTERNS = ("password", "secret", "token", "credential")

# One-time warning flag so we don't spam the log on every call
_warn_once_done = False

# Try importing cryptography; mark as unavailable if not installed
try:
    from cryptography.fernet import Fernet, InvalidToken
    _FERNET_AVAILABLE = True
except ImportError:
    Fernet = None  # type: ignore[assignment,misc]
    InvalidToken = Exception  # type: ignore[assignment,misc]
    _FERNET_AVAILABLE = False
    logger.warning(
        "[crypto] `cryptography` package not installed — encryption unavailable. "
        "Run: pip install cryptography>=42.0.0"
    )


def _validate_key(raw_key: str) -> None:
    """Raise ValueError if raw_key is not a valid Fernet key."""
    if not _FERNET_AVAILABLE:
        raise ValueError(
            "ENCRYPTION_KEY is set but the `cryptography` package is not installed. "
            "Run: pip install cryptography>=42.0.0"
        )
    try:
        Fernet(raw_key.encode())
    except Exception as exc:
        raise ValueError(
            f"ENCRYPTION_KEY is not a valid Fernet key: {exc}. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from exc


# ── Validate key at import time if ENCRYPTION_KEY is set ─────────────────────
_raw_key_at_import = os.environ.get("ENCRYPTION_KEY", "").strip()
if _raw_key_at_import:
    _validate_key(_raw_key_at_import)


# ── Public API ────────────────────────────────────────────────────────────────

def is_encryption_enabled() -> bool:
    """Return True if ENCRYPTION_KEY is set and the cryptography package is available."""
    return _FERNET_AVAILABLE and bool(os.environ.get("ENCRYPTION_KEY", "").strip())


def get_fernet() -> Optional["Fernet"]:
    """Load key from ENCRYPTION_KEY env var and return a Fernet instance, or None if not set."""
    if not _FERNET_AVAILABLE:
        return None
    raw_key = os.environ.get("ENCRYPTION_KEY", "").strip()
    if not raw_key:
        return None
    return Fernet(raw_key.encode())


def _is_sensitive(key: str) -> bool:
    """Return True if the field key matches a sensitive pattern."""
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in _SENSITIVE_PATTERNS)


def encrypt_config(config: dict) -> dict:
    """Encrypt sensitive string values in a config dict.

    Sensitive fields (those whose key contains 'password', 'secret', 'token',
    or 'credential') have their string values encrypted and prefixed with 'enc:'.
    Non-string values and non-sensitive fields are returned unchanged.

    If ENCRYPTION_KEY is not set, logs a one-time warning and returns config unchanged.
    """
    global _warn_once_done

    fernet = get_fernet()
    if fernet is None:
        if not _warn_once_done:
            logger.warning(
                "[crypto] ENCRYPTION_KEY not set — module config credentials will be stored "
                "in plaintext. Set ENCRYPTION_KEY to enable encryption at rest."
            )
            _warn_once_done = True
        return config

    result: Dict[str, Any] = {}
    for key, value in config.items():
        if _is_sensitive(key) and isinstance(value, str) and value:
            # Don't double-encrypt values already encrypted
            if value.startswith(_ENC_PREFIX):
                result[key] = value
            else:
                encrypted_bytes = fernet.encrypt(value.encode("utf-8"))
                result[key] = _ENC_PREFIX + encrypted_bytes.decode("ascii")
        else:
            result[key] = value
    return result


def decrypt_config(config: dict) -> dict:
    """Decrypt 'enc:'-prefixed values in a config dict back to plaintext.

    Values without the 'enc:' prefix are returned as-is (backward compatible
    with existing plaintext records). If ENCRYPTION_KEY is not set, config is
    returned unchanged.
    """
    fernet = get_fernet()
    if fernet is None:
        return config

    result: Dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, str) and value.startswith(_ENC_PREFIX):
            encrypted_part = value[len(_ENC_PREFIX):]
            try:
                decrypted = fernet.decrypt(encrypted_part.encode("ascii")).decode("utf-8")
                result[key] = decrypted
            except (InvalidToken, Exception) as exc:
                logger.error(
                    "[crypto] Failed to decrypt field '%s': %s — returning raw value",
                    key,
                    type(exc).__name__,
                )
                result[key] = value  # Return raw value rather than crash
        else:
            result[key] = value
    return result
