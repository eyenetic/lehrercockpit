"""
Zugangscode-Verwaltung für Lehrkräfte.
Codes werden nur gehasht gespeichert (argon2id).
"""
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

PREFIX_LENGTH = 8


def get_code_prefix(plaintext_code: str) -> str:
    """Returns first PREFIX_LENGTH characters of the access code for DB pre-filtering.

    Args:
        plaintext_code: Plaintext access code.

    Returns:
        First 8 characters uppercased, or empty string if code is falsy.
    """
    if not plaintext_code:
        return ""
    return plaintext_code[:PREFIX_LENGTH].upper()


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
