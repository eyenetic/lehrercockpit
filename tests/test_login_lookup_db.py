"""Login lookup without plaintext code prefixes – needs a real DB connection."""
import os

import pytest


@pytest.fixture
def db_conn():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        pytest.skip("DATABASE_URL nicht gesetzt")
    import psycopg
    from backend.migrations import run_migrations

    conn = psycopg.connect(db_url)
    run_migrations(conn)
    conn.commit()
    yield conn
    conn.rollback()
    conn.close()


@pytest.mark.db
def test_login_after_plaintext_prefix_was_removed(db_conn):
    from backend.auth.access_code import get_code_prefix, hash_code
    from backend.migrations import _migrate_drop_plaintext_code_prefixes
    from backend.users.user_service import authenticate_by_code
    from backend.users.user_store import create_user, set_access_code

    user = create_user(db_conn, "Lookup", "Test")
    code = "Herbst2026xy"
    set_access_code(db_conn, user.id, hash_code(code), code_prefix=code[:8].upper())  # old format
    _migrate_drop_plaintext_code_prefixes(db_conn)
    stored = db_conn.execute("SELECT code_prefix FROM user_access_codes WHERE user_id = %s", (user.id,)).fetchone()[0]
    assert stored is None  # plaintext gone

    assert authenticate_by_code(db_conn, code).id == user.id
    stored = db_conn.execute("SELECT code_prefix FROM user_access_codes WHERE user_id = %s", (user.id,)).fetchone()[0]
    assert stored == get_code_prefix(code) and code[:4] not in stored

    assert authenticate_by_code(db_conn, code).id == user.id      # via the tag
    assert authenticate_by_code(db_conn, "Herbst2026xz") is None
