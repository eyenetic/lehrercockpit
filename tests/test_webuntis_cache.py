"""WebUntis feed cache: fast reloads, last good copy when WebUntis fails."""
from unittest.mock import patch

import pytest

from backend import webuntis_adapter as wa

CAL = "BEGIN:VCALENDAR\nEND:VCALENDAR\n"


@pytest.fixture(autouse=True)
def _empty_cache():
    wa._ical_cache.clear()
    yield
    wa._ical_cache.clear()


def test_second_load_is_served_from_cache():
    with patch.object(wa, "_download_ical", return_value=CAL) as download:
        assert wa._cached_ical("https://x.webuntis.com/a") == CAL
        assert wa._cached_ical("https://x.webuntis.com/a") == CAL
    assert download.call_count == 1


def test_new_link_is_fetched_at_once():
    with patch.object(wa, "_download_ical", return_value=CAL) as download:
        wa._cached_ical("https://x.webuntis.com/a")
        wa._cached_ical("https://x.webuntis.com/b")
    assert download.call_count == 2


def test_failure_falls_back_to_last_good_copy():
    with patch.object(wa, "_download_ical", return_value=CAL):
        wa._cached_ical("https://x.webuntis.com/a")
    url, (stamp, text) = next(iter(wa._ical_cache.items()))
    wa._ical_cache[url] = (stamp - wa._FRESH_SECONDS - 1, text)  # no longer fresh
    with patch.object(wa, "_download_ical", side_effect=OSError("down")):
        assert wa._cached_ical(url) == CAL


def test_non_calendar_is_not_cached():
    with patch.object(wa, "_download_ical", return_value="<html>login</html>"):
        with pytest.raises(ValueError):
            wa._cached_ical("https://x.webuntis.com/a")
    assert not wa._ical_cache


def test_refresh_fetches_anew_but_not_more_than_every_20_seconds():
    with patch.object(wa, "_download_ical", return_value=CAL) as download:
        wa._cached_ical("https://x.webuntis.com/a")
        wa._cached_ical("https://x.webuntis.com/a", force=True)   # just fetched: served from cache
        assert download.call_count == 1
        url = "https://x.webuntis.com/a"
        stamp, text = wa._ical_cache[url]
        wa._ical_cache[url] = (stamp - wa._FORCE_MIN_SECONDS - 1, text)
        wa._cached_ical(url)                                        # normal load: still fresh enough
        assert download.call_count == 1
        wa._cached_ical(url, force=True)                            # "Aktualisieren"
        assert download.call_count == 2
