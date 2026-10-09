"""
Zugangscode-Verwaltung für Lehrkräfte.
Codes werden nur gehasht gespeichert (argon2id).
"""
import hashlib
import secrets
import string
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

# Argon2id-Parameter (OWASP 2024)
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

CODE_LENGTH = 32
CODE_ALPHABET = string.ascii_letters + string.digits  # keine Sonderzeichen für einfache Eingabe

PREFIX_LENGTH = 8  # legacy: plaintext prefixes of this length are no longer stored
LOOKUP_TAG_HEX = 4  # 16 bits: narrows the login lookup, reveals next to nothing about the code

# Self-chosen codes (invitation, change, reset)
MIN_CHOSEN_LENGTH = 8


def chosen_code_problem(code: str) -> "str | None":
    """Why a self-chosen access code is not acceptable, or None."""
    if len(code) < MIN_CHOSEN_LENGTH:
        return f"Der Code braucht mindestens {MIN_CHOSEN_LENGTH} Zeichen."
    if not code.isalnum():
        return "Der Code darf nur Buchstaben und Ziffern enthalten."
    return None


def get_code_prefix(plaintext_code: str) -> str:
    """Lookup tag stored next to the argon2 hash so login only verifies a few rows.

    Formerly the first 8 characters of the code in plaintext – which, with codes of
    8 characters, was nearly the whole code (and the vault key derives from it).
    Now "h" + 16 bits of SHA-256: many codes share a tag, nothing can be read back.

    Returns:
        e.g. "h3f2a", or "" if the code is falsy.
    """
    if not plaintext_code:
        return ""
    return "h" + hashlib.sha256(plaintext_code.encode("utf-8")).hexdigest()[:LOOKUP_TAG_HEX]


def generate_code() -> str:
    """Generiert einen kryptographisch zufälligen Zugangscode.

    Returns:
        Ein zufälliger Code der Länge CODE_LENGTH aus CODE_ALPHABET.
    """
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def hash_code(code: str) -> str:
    """Hasht einen Zugangscode mit argon2id.

    Args:
        code: Plaintext-Zugangscode.

    Returns:
        argon2id-Hash-String.
    """
    return _ph.hash(code)


def verify_code(code: str, code_hash: str) -> bool:
    """Verifiziert einen Zugangscode gegen einen gespeicherten Hash.

    Args:
        code: Plaintext-Zugangscode zur Überprüfung.
        code_hash: Gespeicherter argon2id-Hash.

    Returns:
        True wenn Code korrekt, False bei Fehler oder falschem Code.
    """
    try:
        return _ph.verify(code_hash, code)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(code_hash: str) -> bool:
    """Prüft ob der Hash mit veralteten Parametern erstellt wurde.

    Args:
        code_hash: Gespeicherter argon2id-Hash.

    Returns:
        True wenn der Hash neu berechnet werden sollte.
    """
    return _ph.check_needs_rehash(code_hash)
