"""itslearning messages sort by their real date (newest first in the Posteingang)."""
from backend.itslearning_adapter import _sortable_time


def test_german_and_iso_timestamps_become_sortable():
    assert _sortable_time("09.10.2026 11:32") == "2026-10-09T11:32"
    assert _sortable_time("Freitag, 9. Oktober 2026 08:05") == "2026-10-09T08:05"
    assert _sortable_time("2026-09-30T17:00:00") == "2026-09-30T17:00"
    # day-first strings sorted as text put 09.10. before 30.09. – the sortable form does not
    assert _sortable_time("30.09.2026 08:00") < _sortable_time("09.10.2026 08:00")


def test_unreadable_timestamps_give_no_key():
    assert _sortable_time("gestern") == ""
    assert _sortable_time("") == ""
    assert _sortable_time("45.13.2026") == ""
