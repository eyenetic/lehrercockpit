"""Tests for backend/crypto.py — Fernet encryption for module configs."""
import os
import pytest

# These tests can run without DATABASE_URL
# They DO require the cryptography package

try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

skip_no_crypto = pytest.mark.skipif(
    not CRYPTO_AVAILABLE,
    reason="cryptography package not installed"
)


@pytest.fixture
def fernet_key():
    return Fernet.generate_key().decode()


# ── is_encryption_enabled() ───────────────────────────────────────────────────

def test_encryption_disabled_when_no_key(monkeypatch):
    """Returns False when ENCRYPTION_KEY env var is not set."""
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    # Re-import to pick up env change
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)
    assert crypto_mod.is_encryption_enabled() is False


@skip_no_crypto
def test_encryption_enabled_with_valid_key(monkeypatch, fernet_key):
    """Returns True when a valid ENCRYPTION_KEY is set."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)
    assert crypto_mod.is_encryption_enabled() is True


# ── encrypt_config() without key ─────────────────────────────────────────────

def test_encrypt_config_no_key_returns_original(monkeypatch):
    """Returns the original dict unchanged when no key is set."""
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"username": "teacher1", "password": "secret123"}
    result = crypto_mod.encrypt_config(config)
    assert result == config


def test_encrypt_config_no_key_returns_same_object_or_equal(monkeypatch):
    """Does NOT modify the original dict (backward compat path)."""
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"username": "teacher1", "password": "secret123"}
    original_password = config["password"]
    crypto_mod.encrypt_config(config)
    # Original must not be mutated
    assert config["password"] == original_password


# ── encrypt_config() with key ─────────────────────────────────────────────────

@skip_no_crypto
def test_encrypt_config_password_field_encrypted(monkeypatch, fernet_key):
    """Encrypts string fields containing 'password' → value starts with enc:"""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"password": "mysecretpass"}
    result = crypto_mod.encrypt_config(config)
    assert result["password"].startswith("enc:"), f"Expected enc: prefix, got: {result['password'][:20]}"


@skip_no_crypto
def test_encrypt_config_secret_field_encrypted(monkeypatch, fernet_key):
    """Encrypts string fields containing 'secret' → value starts with enc:"""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"api_secret": "my-api-secret"}
    result = crypto_mod.encrypt_config(config)
    assert result["api_secret"].startswith("enc:")


@skip_no_crypto
def test_encrypt_config_token_field_encrypted(monkeypatch, fernet_key):
    """Encrypts string fields containing 'token' → value starts with enc:"""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"auth_token": "tok_abc123"}
    result = crypto_mod.encrypt_config(config)
    assert result["auth_token"].startswith("enc:")


@skip_no_crypto
def test_encrypt_config_username_not_encrypted(monkeypatch, fernet_key):
    """Leaves username field unchanged (not sensitive)."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"username": "teacher1", "password": "secret"}
    result = crypto_mod.encrypt_config(config)
    assert result["username"] == "teacher1"


@skip_no_crypto
def test_encrypt_config_server_url_not_encrypted(monkeypatch, fernet_key):
    """Leaves server_url field unchanged."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"server_url": "https://example.com", "password": "pass"}
    result = crypto_mod.encrypt_config(config)
    assert result["server_url"] == "https://example.com"


@skip_no_crypto
def test_encrypt_config_ical_url_not_encrypted(monkeypatch, fernet_key):
    """Leaves ical_url field unchanged."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"ical_url": "https://cal.example.com/feed.ics", "password": "pass"}
    result = crypto_mod.encrypt_config(config)
    assert result["ical_url"] == "https://cal.example.com/feed.ics"


@skip_no_crypto
def test_encrypt_config_non_string_values_unchanged(monkeypatch, fernet_key):
    """Leaves non-string values (int, bool, None, list, dict) unchanged."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {
        "count": 42,
        "enabled": True,
        "nothing": None,
        "tags": ["a", "b"],
        "nested": {"key": "val"},
    }
    result = crypto_mod.encrypt_config(config)
    assert result["count"] == 42
    assert result["enabled"] is True
    assert result["nothing"] is None
    assert result["tags"] == ["a", "b"]
    assert result["nested"] == {"key": "val"}


@skip_no_crypto
def test_encrypt_config_does_not_mutate_original(monkeypatch, fernet_key):
    """Does NOT modify the original dict (returns a copy)."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"password": "originalpass"}
    original_password = config["password"]
    result = crypto_mod.encrypt_config(config)
    # Original must still be plaintext
    assert config["password"] == original_password
    # Result must be different
    assert result["password"] != original_password


@skip_no_crypto
def test_encrypt_config_produces_different_ciphertext_each_time(monkeypatch, fernet_key):
    """Two encryptions of the same value produce different ciphertext (Fernet uses random IV)."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"password": "samepassword"}
    result1 = crypto_mod.encrypt_config(config)
    result2 = crypto_mod.encrypt_config(config)
    # Same encrypted prefix but different ciphertext due to random IV
    assert result1["password"] != result2["password"]


# ── decrypt_config() with key ─────────────────────────────────────────────────

@skip_no_crypto
def test_decrypt_config_decrypts_enc_prefixed_values(monkeypatch, fernet_key):
    """Decrypts enc:-prefixed values back to original plaintext."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    original = {"password": "mypassword123"}
    encrypted = crypto_mod.encrypt_config(original)
    assert encrypted["password"].startswith("enc:")

    decrypted = crypto_mod.decrypt_config(encrypted)
    assert decrypted["password"] == "mypassword123"


@skip_no_crypto
def test_decrypt_config_leaves_non_enc_values_unchanged(monkeypatch, fernet_key):
    """Leaves non-enc: values unchanged (backward compat with plaintext DB records)."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"password": "plaintext_not_encrypted", "username": "user1"}
    result = crypto_mod.decrypt_config(config)
    assert result["password"] == "plaintext_not_encrypted"
    assert result["username"] == "user1"


@skip_no_crypto
def test_decrypt_config_handles_empty_dict(monkeypatch, fernet_key):
    """Handles empty dict {} without error."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    result = crypto_mod.decrypt_config({})
    assert result == {}


@skip_no_crypto
def test_decrypt_config_handles_none_values(monkeypatch, fernet_key):
    """Handles None values without error."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"password": None, "username": "user1"}
    result = crypto_mod.decrypt_config(config)
    assert result["password"] is None
    assert result["username"] == "user1"


# ── Round-trip tests ──────────────────────────────────────────────────────────

@skip_no_crypto
def test_round_trip_encrypt_decrypt(monkeypatch, fernet_key):
    """decrypt_config(encrypt_config(config)) equals original config."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    original = {
        "username": "teacher1",
        "password": "supersecret",
        "server_url": "https://example.com",
        "api_token": "tok_abc123",
        "ical_url": "https://cal.example.com/ical",
    }
    encrypted = crypto_mod.encrypt_config(original)
    decrypted = crypto_mod.decrypt_config(encrypted)
    assert decrypted == original


@skip_no_crypto
def test_round_trip_mixed_config(monkeypatch, fernet_key):
    """Round-trip works for configs with mixed field types."""
    monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    original = {
        "username": "user",
        "password": "pass123",
        "port": 443,
        "enabled": True,
        "tags": ["a", "b"],
    }
    result = crypto_mod.decrypt_config(crypto_mod.encrypt_config(original))
    assert result == original


# ── Without key (backward compat) ─────────────────────────────────────────────

def test_decrypt_config_no_key_returns_unchanged(monkeypatch):
    """decrypt_config({"password": "plaintext"}) returns unchanged when no key set."""
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    import importlib
    import backend.crypto as crypto_mod
    importlib.reload(crypto_mod)

    config = {"password": "plaintext"}
    result = crypto_mod.decrypt_config(config)
    assert result == {"password": "plaintext"}


# ── Invalid key ───────────────────────────────────────────────────────────────

@skip_no_crypto
def test_invalid_fernet_key_raises_value_error(monkeypatch):
    """Setting an invalid ENCRYPTION_KEY raises ValueError when get_fernet() is called."""
    monkeypatch.setenv("ENCRYPTION_KEY", "not-a-valid-fernet-key-at-all")
    import importlib
    import backend.crypto as crypto_mod
    # The module validates key at import time if ENCRYPTION_KEY is set.
    # Reloading with a bad key should raise ValueError.
    with pytest.raises((ValueError, Exception)):
        importlib.reload(crypto_mod)
