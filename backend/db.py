"""
Zentrale Datenbankverbindungs-Verwaltung.
Stellt eine Thread-safe Connection-Factory bereit.
"""
import os
import psycopg
from contextlib import contextmanager
from typing import Generator

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def get_connection() -> psycopg.Connection:
    """Erstellt eine neue DB-Verbindung. Caller ist für close() verantwortlich."""
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL nicht gesetzt. Multi-User-Funktionen erfordern PostgreSQL."
        )
    return psycopg.connect(DATABASE_URL)


@contextmanager
def db_connection() -> Generator[psycopg.Connection, None, None]:
    """Context Manager für DB-Verbindungen mit auto-commit/rollback."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
