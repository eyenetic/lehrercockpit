"""Tests für grades/notes service layer (backend/users/user_service.py) — Phase 9.

Non-DB tests use unittest.mock.
DB tests require DATABASE_URL and are skipped automatically without it.
"""
import os
import pytest
from unittest.mock import MagicMock, call, patch


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_mock_conn():
    """Erstellt einen Mock für psycopg3 Connection."""
    conn = MagicMock()
    return conn


@pytest.fixture
def db_conn():
    """Echte DB-Connection mit Rollback nach jedem Test."""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        pytest.skip("DATABASE_URL nicht gesetzt")
    import psycopg
    conn = psycopg.connect(db_url)
    from backend.migrations import run_migrations
    run_migrations(conn)
    conn.commit()
    yield conn
    conn.rollback()
    conn.close()


# ── Non-DB mock tests: get_grades ─────────────────────────────────────────────

def test_get_grades_executes_query_with_user_id():
    """get_grades(conn, user_id) führt SQL mit user_id-Parameter aus."""
    from backend.users.user_service import get_grades

    conn = _make_mock_conn()
    conn.execute.return_value.fetchall.return_value = []

    result = get_grades(conn, user_id=42)

    assert result == []
    conn.execute.assert_called_once()
    call_args = conn.execute.call_args
    # user_id=42 must be in the query parameters
    assert (42,) in call_args.args or 42 in str(call_args)


def test_get_grades_returns_list_of_dicts():
    """get_grades() gibt eine Liste von dicts zurück."""
    from backend.users.user_service import get_grades
    from datetime import date, datetime, timezone

    conn = _make_mock_conn()
    mock_row = (
        1,           # id
        42,          # user_id
        "5a",        # class_name
        "Mathe",     # subject
        "2+",        # grade_value
        date(2026, 3, 25),  # grade_date
        "Test",      # note
        datetime(2026, 3, 25, tzinfo=timezone.utc),   # created_at
        datetime(2026, 3, 25, tzinfo=timezone.utc),   # updated_at
    )
    conn.execute.return_value.fetchall.return_value = [mock_row]

    result = get_grades(conn, user_id=42)

    assert len(result) == 1
    assert result[0]["id"] == 1
    assert result[0]["class_name"] == "5a"
    assert result[0]["grade_value"] == "2+"


# ── Non-DB mock tests: upsert_grade ──────────────────────────────────────────

def test_upsert_grade_insert_returns_grade_dict():
    """upsert_grade(conn, user_id, ...) gibt einen grade-dict zurück."""
    from backend.users.user_service import upsert_grade
    from datetime import date, datetime, timezone

    conn = _make_mock_conn()
    mock_row = (
        10, 42, "5a", "Mathe", "2+",
        date(2026, 3, 25), "",
        datetime(2026, 3, 25, tzinfo=timezone.utc),
        datetime(2026, 3, 25, tzinfo=timezone.utc),
    )
    conn.execute.return_value.fetchone.return_value = mock_row

    result = upsert_grade(
        conn, user_id=42, class_name="5a", subject="Mathe",
        grade_value="2+", grade_date=None, note="",
    )

    assert isinstance(result, dict)
    assert result["id"] == 10
    assert result["user_id"] == 42
    assert result["class_name"] == "5a"
    assert result["grade_value"] == "2+"


def test_upsert_grade_not_found_returns_empty_dict():
    """upsert_grade() gibt {} zurück wenn der Eintrag nicht gefunden wurde."""
    from backend.users.user_service import upsert_grade

    conn = _make_mock_conn()
    conn.execute.return_value.fetchone.return_value = None

    result = upsert_grade(
        conn, user_id=42, class_name="5a", subject="Mathe",
        grade_value="2+", grade_id=9999,
    )

    assert result == {}


# ── Non-DB mock tests: delete_grade ──────────────────────────────────────────

def test_delete_grade_uses_ownership_check():
    """delete_grade(conn, user_id, grade_id) nutzt WHERE id=%s AND user_id=%s."""
    from backend.users.user_service import delete_grade

    conn = _make_mock_conn()
    conn.execute.return_value.rowcount = 1

    result = delete_grade(conn, user_id=42, grade_id=7)

    assert result is True
    # Verify the SQL call includes both grade_id and user_id
    call_args = conn.execute.call_args
    sql = call_args.args[0].lower()
    params = call_args.args[1]
    assert "user_id" in sql or "where" in sql
    assert 7 in params
    assert 42 in params


def test_delete_grade_returns_false_when_not_found():
    """delete_grade() gibt False zurück wenn kein Eintrag gelöscht wurde."""
    from backend.users.user_service import delete_grade

    conn = _make_mock_conn()
    conn.execute.return_value.rowcount = 0

    result = delete_grade(conn, user_id=42, grade_id=9999)

    assert result is False


def test_delete_grade_returns_false_for_wrong_owner():
    """delete_grade() gibt False zurück wenn user_id nicht übereinstimmt."""
    from backend.users.user_service import delete_grade

    conn = _make_mock_conn()
    conn.execute.return_value.rowcount = 0  # no rows deleted = wrong owner

    result = delete_grade(conn, user_id=99, grade_id=7)

    assert result is False


# ── Non-DB mock tests: upsert_note ────────────────────────────────────────────

def test_upsert_note_returns_note_dict():
    """upsert_note(conn, user_id, class_name, note_text) gibt einen note-dict zurück."""
    from backend.users.user_service import upsert_note
    from datetime import datetime, timezone

    conn = _make_mock_conn()
    mock_row = (
        5, 42, "5a", "Klassenarbeit nächste Woche",
        datetime(2026, 3, 25, tzinfo=timezone.utc),
        datetime(2026, 3, 25, tzinfo=timezone.utc),
    )
    conn.execute.return_value.fetchone.return_value = mock_row

    result = upsert_note(conn, user_id=42, class_name="5a", note_text="Klassenarbeit nächste Woche")

    assert isinstance(result, dict)
    assert result["id"] == 5
    assert result["class_name"] == "5a"
    assert result["note_text"] == "Klassenarbeit nächste Woche"


def test_upsert_note_uses_user_id_and_class_name():
    """upsert_note() übergibt user_id und class_name an SQL."""
    from backend.users.user_service import upsert_note
    from datetime import datetime, timezone

    conn = _make_mock_conn()
    mock_row = (5, 42, "5a", "Test", datetime(2026, 3, 25, tzinfo=timezone.utc), datetime(2026, 3, 25, tzinfo=timezone.utc))
    conn.execute.return_value.fetchone.return_value = mock_row

    upsert_note(conn, user_id=42, class_name="5a", note_text="Test")

    call_args = conn.execute.call_args
    params = call_args.args[1]
    assert 42 in params
    assert "5a" in params


# ── Non-DB mock tests: delete_note ────────────────────────────────────────────

def test_delete_note_uses_user_id_and_class_name():
    """delete_note() nutzt WHERE user_id=%s AND class_name=%s."""
    from backend.users.user_service import delete_note

    conn = _make_mock_conn()
    conn.execute.return_value.rowcount = 1

    result = delete_note(conn, user_id=42, class_name="5a")

    assert result is True
    call_args = conn.execute.call_args
    params = call_args.args[1]
    assert 42 in params
    assert "5a" in params


def test_delete_note_returns_false_when_not_found():
    """delete_note() gibt False zurück wenn keine Notiz gefunden."""
    from backend.users.user_service import delete_note

    conn = _make_mock_conn()
    conn.execute.return_value.rowcount = 0

    result = delete_note(conn, user_id=42, class_name="unbekannt")

    assert result is False


# ── DB integration tests ──────────────────────────────────────────────────────

@pytest.mark.db
def test_db_grade_crud_roundtrip(db_conn):
    """Vollständiger CRUD-Roundtrip: create → get → delete → get (leer)."""
    from backend.users.user_service import (
        create_teacher, get_grades, upsert_grade, delete_grade,
    )

    user, _ = create_teacher(db_conn, "Grade", "CRUDTest")
    db_conn.commit()

    # Initial: leer
    grades = get_grades(db_conn, user.id)
    assert grades == []

    # Create
    grade = upsert_grade(
        db_conn, user_id=user.id,
        class_name="5a", subject="Mathe", grade_value="2+",
    )
    db_conn.commit()
    assert grade["id"] is not None
    assert grade["class_name"] == "5a"

    # Get
    grades = get_grades(db_conn, user.id)
    assert len(grades) == 1
    assert grades[0]["grade_value"] == "2+"

    # Delete
    deleted = delete_grade(db_conn, user_id=user.id, grade_id=grade["id"])
    db_conn.commit()
    assert deleted is True

    # Empty again
    grades = get_grades(db_conn, user.id)
    assert grades == []


@pytest.mark.db
def test_db_note_crud_roundtrip(db_conn):
    """Vollständiger CRUD-Roundtrip: upsert note → get → delete → get (leer)."""
    from backend.users.user_service import (
        create_teacher, get_notes, upsert_note, delete_note,
    )

    user, _ = create_teacher(db_conn, "Note", "CRUDTest")
    db_conn.commit()

    # Initial: leer
    notes = get_notes(db_conn, user.id)
    assert notes == []

    # Create
    note = upsert_note(db_conn, user_id=user.id, class_name="5a", note_text="Test Notiz")
    db_conn.commit()
    assert note["id"] is not None
    assert note["class_name"] == "5a"
    assert note["note_text"] == "Test Notiz"

    # Get
    notes = get_notes(db_conn, user.id)
    assert len(notes) == 1
    assert notes[0]["note_text"] == "Test Notiz"

    # Delete
    deleted = delete_note(db_conn, user_id=user.id, class_name="5a")
    db_conn.commit()
    assert deleted is True

    # Empty again
    notes = get_notes(db_conn, user.id)
    assert notes == []


@pytest.mark.db
def test_db_teacher_a_cannot_delete_teacher_b_grade(db_conn):
    """Teacher A kann nicht Teacher B's Note löschen (Ownership-Check)."""
    from backend.users.user_service import (
        create_teacher, upsert_grade, delete_grade,
    )

    user_a, _ = create_teacher(db_conn, "TeacherA", "OwnershipTest")
    user_b, _ = create_teacher(db_conn, "TeacherB", "OwnershipTest")
    db_conn.commit()

    # Teacher B creates a grade
    grade = upsert_grade(
        db_conn, user_id=user_b.id,
        class_name="6b", subject="Deutsch", grade_value="3",
    )
    db_conn.commit()
    assert grade["id"] is not None

    # Teacher A tries to delete Teacher B's grade
    deleted = delete_grade(db_conn, user_id=user_a.id, grade_id=grade["id"])
    assert deleted is False


@pytest.mark.db
def test_db_upsert_note_is_idempotent(db_conn):
    """upsert_note zweimal mit gleicher class_name → kein Duplikat, nur Update."""
    from backend.users.user_service import (
        create_teacher, get_notes, upsert_note,
    )

    user, _ = create_teacher(db_conn, "Upsert", "IdempotentTest")
    db_conn.commit()

    # First upsert
    note1 = upsert_note(db_conn, user_id=user.id, class_name="7c", note_text="Erste Notiz")
    db_conn.commit()

    # Second upsert — same class_name
    note2 = upsert_note(db_conn, user_id=user.id, class_name="7c", note_text="Zweite Notiz")
    db_conn.commit()

    # Should be same id (UPDATE, not INSERT)
    assert note1["id"] == note2["id"]

    # Text should be updated
    notes = get_notes(db_conn, user.id)
    assert len(notes) == 1
    assert notes[0]["note_text"] == "Zweite Notiz"
