"""Anhänge gegen eine echte Datenbank: Kontingent, Besitz, Löschen mit dem Konto."""
import os

import pytest

pytestmark = pytest.mark.db

from backend import own_files


@pytest.fixture
def conn():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        pytest.skip("DATABASE_URL nicht gesetzt")
    import psycopg
    from backend.migrations import run_migrations
    from backend.users.user_store import create_user

    with psycopg.connect(url) as c:
        run_migrations(c)
        own_files.migrate(c)
        c.users = (create_user(c, "Ola", "Anhang").id, create_user(c, "Per", "Fremd").id)
        c.commit()
        yield c
        c.rollback()
        c.execute("DELETE FROM users WHERE id = ANY(%s)", (list(c.users),))
        c.commit()


def test_store_load_delete_and_cascade(conn):
    me, other = conn.users
    stored = own_files.add(conn, me, b"\x00" * 1000)
    assert own_files.used(conn, me) == 1000
    assert own_files.load(conn, me, stored["id"]) == b"\x00" * 1000
    assert own_files.load(conn, other, stored["id"]) is None
    assert own_files.delete(conn, other, stored["id"]) is False
    assert own_files.delete(conn, me, stored["id"]) is True and own_files.used(conn, me) == 0
    again = own_files.add(conn, me, b"\x01" * 50)
    conn.execute("DELETE FROM users WHERE id = %s", (me,))
    assert conn.execute("SELECT COUNT(*) FROM own_files WHERE id = %s", (again["id"],)).fetchone()[0] == 0
