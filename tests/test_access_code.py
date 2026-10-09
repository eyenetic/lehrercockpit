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


# ── get_code_prefix() tests: lookup tag, never plaintext ──────────────────────

def test_lookup_tag_contains_no_part_of_the_code():
    """Früher lagen die ersten 8 Zeichen im Klartext in der DB – jetzt nur ein Hash-Tag."""
    import hashlib
    for code in ("ABCDEFGH1234", "Sommer2026", "abcdefgh"):
        tag = get_code_prefix(code)
        assert tag == "h" + hashlib.sha256(code.encode()).hexdigest()[:4]
        assert code[:PREFIX_LENGTH].upper() not in tag.upper()


def test_lookup_tag_is_stable():
    assert get_code_prefix("Sommer2026") == get_code_prefix("Sommer2026")


def test_lookup_tag_fits_the_column():
    """user_access_codes.code_prefix ist VARCHAR(8)."""
    assert len(get_code_prefix(generate_code())) <= 8


def test_get_code_prefix_empty_string_returns_empty():
    assert get_code_prefix("") == ""


def test_get_code_prefix_none_returns_empty():
    assert get_code_prefix(None) == ""
