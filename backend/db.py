"""
Zentrale Datenbankverbindungs-Verwaltung.
Stellt eine Thread-safe Connection-Factory bereit.
"""
import os
import threading
import time
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


# Opening a Postgres connection (TCP + TLS + auth) costs more than most queries,
# and one dashboard load needs about ten of them. Finished connections are kept
# for a short while and handed to the next caller. Connections idle for longer
# than _IDLE_SECONDS are closed instead of reused (the server may have dropped them).
_IDLE_SECONDS = 60
_MAX_IDLE = 8
_idle_lock = threading.Lock()
_idle: list[tuple[float, psycopg.Connection]] = []


def _take_idle() -> psycopg.Connection | None:
    now = time.monotonic()
    while True:
        with _idle_lock:
            if not _idle:
                return None
            since, conn = _idle.pop()
        if now - since < _IDLE_SECONDS and not conn.closed and not conn.broken:
            return conn
        try:
            conn.close()
        except Exception:
            pass


def _give_back(conn: psycopg.Connection) -> None:
    reusable = (
        not conn.closed
        and not conn.broken
        and conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE
    )
    if reusable:
        with _idle_lock:
            if len(_idle) < _MAX_IDLE:
                _idle.append((time.monotonic(), conn))
                return
    conn.close()


@contextmanager
def db_connection() -> Generator[psycopg.Connection, None, None]:
    """Context Manager für DB-Verbindungen mit auto-commit/rollback."""
    conn = _take_idle() or get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            conn.close()
        raise
    finally:
        _give_back(conn)
