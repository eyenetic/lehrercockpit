"""Tests für backend/auth/access_code.py – rein in-memory, keine DB nötig."""
import string

from backend.auth.access_code import (
    CODE_ALPHABET,
    CODE_LENGTH,
    PREFIX_LENGTH,
    generate_code,
    get_code_prefix,
    hash_code,
    needs_rehash,
    verify_code,
)


def test_generate_code_length():
    """Code hat Länge CODE_LENGTH (32)."""
    code = generate_code()
    assert len(code) == CODE_LENGTH
    assert len(code) == 32


def test_generate_code_uniqueness():
    """100 generierte Codes sind alle verschieden."""
    codes = {generate_code() for _ in range(100)}
    assert len(codes) == 100


def test_generate_code_charset():
    """Code enthält nur Buchstaben und Ziffern (CODE_ALPHABET)."""
    allowed = set(string.ascii_letters + string.digits)
    for _ in range(10):
        code = generate_code()
        for ch in code:
            assert ch in allowed, f"Unerlaubtes Zeichen '{ch}' in Code '{code}'"


def test_hash_code_returns_string():
    """Hash ist ein String."""
    code = generate_code()
    result = hash_code(code)
    assert isinstance(result, str)


def test_hash_code_not_plaintext():
    """Hash ist nicht gleich dem Original-Code."""
    code = generate_code()
    result = hash_code(code)
    assert result != code


def test_hash_code_different_each_time():
    """Gleicher Code → verschiedene Hashes (Salt)."""
    code = generate_code()
    hash1 = hash_code(code)
    hash2 = hash_code(code)
    assert hash1 != hash2


def test_verify_code_correct():
    """Korrekte Verifikation gibt True zurück."""
    code = generate_code()
    code_hash = hash_code(code)
    assert verify_code(code, code_hash) is True


def test_verify_code_wrong():
    """Falsche Verifikation gibt False zurück."""
    code = generate_code()
    wrong_code = generate_code()
    code_hash = hash_code(code)
    assert verify_code(wrong_code, code_hash) is False


def test_verify_code_empty_string():
    """Leerer Code gibt False zurück."""
    code = generate_code()
    code_hash = hash_code(code)
    assert verify_code("", code_hash) is False


def test_needs_rehash_fresh_hash():
    """Frischer Hash braucht kein Rehash."""
    code = generate_code()
    code_hash = hash_code(code)
    assert needs_rehash(code_hash) is False


def test_full_flow():
    """generate → hash → verify in einem Test."""
    code = generate_code()
    assert len(code) == CODE_LENGTH

    code_hash = hash_code(code)
    assert isinstance(code_hash, str)
    assert code_hash != code

    assert verify_code(code, code_hash) is True

    other_code = generate_code()
    assert verify_code(other_code, code_hash) is False


# ── Additional gap-filling tests ──────────────────────────────────────────────

def test_generate_code_returns_nonempty_string():
    """generate_code() gibt einen nicht-leeren String zurück."""
    code = generate_code()
    assert isinstance(code, str)
    assert len(code) > 0


def test_generate_code_two_calls_differ():
    """Zwei Aufrufe von generate_code() liefern unterschiedliche Werte."""
    code1 = generate_code()
    code2 = generate_code()
    assert code1 != code2


def test_hash_code_is_argon2_format():
    """Hash beginnt mit '$argon2' (erkennbares argon2id-Format, kein Plaintext)."""
    code = generate_code()
    result = hash_code(code)
    assert result.startswith("$argon2"), (
        f"Erwartet '$argon2...' prefix, bekommen: {result[:20]!r}"
    )


def test_hash_code_not_stored_as_plaintext():
    """Hash != Original — Code wird NICHT im Klartext gespeichert."""
    code = generate_code()
    h = hash_code(code)
    assert h != code
    assert code not in h


def test_verify_code_with_none_like_empty_is_false():
    """verify_code mit leerem String und gültigem Hash → False (kein Absturz)."""
    code = generate_code()
    h = hash_code(code)
    result = verify_code("", h)
    assert result is False


def test_hash_salt_makes_two_hashes_unique():
    """Gleicher Plaintext → verschiedene Hashes wegen Salt (argon2 built-in)."""
    code = generate_code()
    h1 = hash_code(code)
    h2 = hash_code(code)
    assert h1 != h2, "Salt muss sicherstellen dass zwei Hashes desselben Codes verschieden sind"


# ── get_code_prefix() tests ───────────────────────────────────────────────────

def test_get_code_prefix_returns_first_8_chars_uppercased():
    """get_code_prefix('ABCDEFGH1234') → 'ABCDEFGH' (erste 8 Zeichen)."""
    result = get_code_prefix("ABCDEFGH1234")
    assert result == "ABCDEFGH"
    assert len(result) == PREFIX_LENGTH


def test_get_code_prefix_uppercase_short_code():
    """get_code_prefix('abc') → 'ABC' (uppercased, kürzer als 8 Zeichen)."""
    result = get_code_prefix("abc")
    assert result == "ABC"
    assert len(result) == 3


def test_get_code_prefix_empty_string_returns_empty():
    """get_code_prefix('') → '' (leerer String)."""
    result = get_code_prefix("")
    assert result == ""


def test_get_code_prefix_none_returns_empty():
    """get_code_prefix(None) → '' (kein Absturz)."""
    result = get_code_prefix(None)
    assert result == ""


def test_get_code_prefix_exactly_8_chars():
    """get_code_prefix mit genau 8 Zeichen → alle 8 Zeichen."""
    result = get_code_prefix("ABCDEFGH")
    assert result == "ABCDEFGH"
    assert len(result) == 8


def test_get_code_prefix_longer_than_8_truncated():
    """get_code_prefix mit mehr als 8 Zeichen → nur erste 8 Zeichen."""
    result = get_code_prefix("ABCDEFGHIJKLMNOP")
    assert result == "ABCDEFGH"
    assert len(result) == PREFIX_LENGTH


def test_get_code_prefix_lowercase_becomes_uppercase():
    """get_code_prefix konvertiert Kleinbuchstaben zu Großbuchstaben."""
    result = get_code_prefix("abcdefghXYZ")
    assert result == "ABCDEFGH"


def test_get_code_prefix_generated_code_returns_8_char_prefix():
    """get_code_prefix auf generate_code() → PREFIX_LENGTH Zeichen zurück."""
    code = generate_code()
    prefix = get_code_prefix(code)
    assert len(prefix) == PREFIX_LENGTH
    assert prefix == code[:PREFIX_LENGTH].upper()
