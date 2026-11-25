"""Nutzung zählen gegen eine echte Datenbank: Upsert, „active“ einmal pro Tag, Zusammenfassung."""
import os
from datetime import date
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.db

from backend import usage

DAY = date(2031, 3, 4)  # far from real data, removed afterwards


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
        usage.migrate(c)
        user = create_user(c, "Uta", "Zählung")
        c.commit()
        c.user_id = user.id
        yield c
        c.rollback()
        c.execute("DELETE FROM usage_counts WHERE day >= %s", (DAY,))
        c.execute("DELETE FROM users WHERE id = %s", (user.id,))
        c.commit()


def test_counts_add_up_and_active_once_per_day(conn):
    with patch.object(usage, "today", return_value=DAY):
        usage.record_open(conn, conn.user_id, "phone")
        usage.record_open(conn, conn.user_id, "desktop")
        usage.record_video(conn, "einrichtung", ended=False)
        usage.bump(conn, "invite")
        data = usage.summary(conn, 7)
    week = data["week"]
    assert (week["open"], week["open:phone"], week["open:desktop"], week["active"]) == (2, 1, 1, 1)
    assert week["video:einrichtung:start"] == 1 and week["invite"] == 1
    assert data["days"][-1]["day"] == DAY.isoformat()
    assert data["teachers"]["active_7"] >= 1
