"""Tests für backend/onedrive_share.py (öffentliche OneDrive-Freigaben lesen)."""
import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from backend import onedrive_share as od

SHARE = "https://1drv.ms/x/c/abc123/EXAMPLE?e=xyz"


class _Response:
    def __init__(self, body=b"", status=200):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.status = status

    def read(self, *_args):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _http_error(code):
    return HTTPError("https://example", code, "err", {}, io.BytesIO(b""))


@pytest.fixture(autouse=True)
def _fresh_token_cache():
    od._token_cache.clear()
    yield
    od._token_cache.clear()


def test_share_id_matches_microsoft_encoding():
    # Example from the Microsoft Graph docs ("Encoding sharing URLs").
    url = "https://onedrive.live.com/redir?resid=1231244193912!12&authKey=1201919!12921!1"
    assert od.share_id(url) == (
        "u!aHR0cHM6Ly9vbmVkcml2ZS5saXZlLmNvbS9yZWRpcj9yZXNpZD0xMjMxMjQ0MTkzOTEyITEyJmF1dGhLZXk9MTIwMTkxOSExMjkyMSEx"
    )


@pytest.mark.parametrize("url,expected", [
    ("https://1drv.ms/x/s!AbC", True),
    ("https://onedrive.live.com/edit?id=1", True),
    ("http://1drv.ms/x/s!AbC", False),
    ("https://evil.example/1drv.ms", False),
    ("", False),
])
def test_is_onedrive_link(url, expected):
    assert od.is_onedrive_link(url) is expected


def _responses(*responses):
    """urlopen side effect returning the given responses/exceptions in order."""
    calls = []

    def fake(request, **_kwargs):
        calls.append(request)
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item
    return fake, calls


def test_download_uses_badger_token_and_download_url():
    item = {"name": "Klassenarbeiten.xlsx", "size": 5, "eTag": "\"{A},7\"",
            "lastModifiedDateTime": "2026-09-20T10:00:00Z", "@content.downloadUrl": "https://dl.example/file"}
    fake, calls = _responses(_Response({"token": "tok"}), _Response(item), _Response(b"bytes"))
    with patch.object(od, "urlopen", side_effect=fake):
        data, meta = od.download(SHARE)
    assert data == b"bytes"
    assert meta == {"name": "Klassenarbeiten.xlsx", "size": 5, "etag": "\"{A},7\"",
                    "modified": "2026-09-20T10:00:00Z"}
    token_request, item_request, file_request = calls
    assert token_request.full_url == od.TOKEN_URL
    assert json.loads(token_request.data) == {"appId": od.BADGER_APP_ID}
    assert f"/shares/{od.share_id(SHARE)}/driveitem" in item_request.full_url
    assert item_request.get_header("Authorization") == "Badger tok"
    assert item_request.get_header("Prefer") == "autoredeem"
    assert file_request.full_url == "https://dl.example/file"
    assert file_request.get_header("Authorization") is None


def test_token_is_cached():
    item = {"size": 1, "@content.downloadUrl": "https://dl.example/f"}
    fake, calls = _responses(_Response({"token": "tok"}), _Response(item), _Response(item))
    with patch.object(od, "urlopen", side_effect=fake):
        od.resolve(SHARE)
        od.resolve(SHARE)
    assert len(calls) == 3  # one token request for two resolves


@pytest.mark.parametrize("code", [401, 403, 429])
def test_refusals_raise_blocked(code):
    fake, _ = _responses(_Response({"token": "tok"}), _http_error(code))
    with patch.object(od, "urlopen", side_effect=fake):
        with pytest.raises(od.OneDriveBlocked):
            od.resolve(SHARE)


def test_missing_link_is_reported():
    fake, _ = _responses(_Response({"token": "tok"}), _http_error(404))
    with patch.object(od, "urlopen", side_effect=fake):
        with pytest.raises(od.OneDriveError, match="nicht gefunden"):
            od.resolve(SHARE)


def test_folder_links_and_huge_files_are_rejected():
    fake, _ = _responses(_Response({"token": "tok"}), _Response({"name": "Ordner", "size": 0}))
    with patch.object(od, "urlopen", side_effect=fake):
        with pytest.raises(od.OneDriveError, match="Download-Adresse"):
            od.resolve(SHARE)
    od._token_cache.clear()
    big = {"size": od.MAX_BYTES + 1, "@content.downloadUrl": "https://dl.example/f"}
    fake, _ = _responses(_Response({"token": "tok"}), _Response(big))
    with patch.object(od, "urlopen", side_effect=fake):
        with pytest.raises(od.OneDriveError, match="zu groß"):
            od.download(SHARE)


def test_non_onedrive_urls_are_not_requested():
    with patch.object(od, "urlopen") as opened:
        with pytest.raises(od.OneDriveError):
            od.resolve("https://example.com/plan.xlsx")
    opened.assert_not_called()
