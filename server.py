"""Local development HTTP server (stdlib ThreadingHTTPServer).

This is the **local dev** entrypoint only.  Production uses gunicorn + app.py.

File-parsing helpers (multipart extraction, XLSX parsing) are imported from
backend/file_utils.py so they are not duplicated across this file and app.py.
"""
from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import time
from urllib.parse import parse_qs, urlparse

try:
    from backend.dashboard import build_dashboard_payload
    from backend.config import load_settings
    from backend.mail_adapter import get_mail_preview
    from backend.classwork_cache import load_cache, save_cache
    from backend.grades_store import create_grade_entry, load_gradebook, save_gradebook
    from backend.notes_store import create_note, load_notes, save_notes
    from backend.local_settings import save_classwork_file, save_itslearning_settings, save_nextcloud_settings
    from backend.file_utils import extract_multipart_file as _extract_multipart_file, parse_classwork_xlsx as _parse_classwork_xlsx
    _DASHBOARD_IMPORT_ERROR: Exception | None = None
except Exception as _exc:
    build_dashboard_payload = None  # type: ignore[assignment]
    load_settings = None  # type: ignore[assignment]
    get_mail_preview = None  # type: ignore[assignment]
    save_classwork_file = None  # type: ignore[assignment]
    save_itslearning_settings = None  # type: ignore[assignment]
    save_nextcloud_settings = None  # type: ignore[assignment]
    load_cache = None  # type: ignore[assignment]
    save_cache = None  # type: ignore[assignment]
    create_grade_entry = None  # type: ignore[assignment]
    load_gradebook = None  # type: ignore[assignment]
    save_gradebook = None  # type: ignore[assignment]
    create_note = None  # type: ignore[assignment]
    load_notes = None  # type: ignore[assignment]
    save_notes = None  # type: ignore[assignment]
    _extract_multipart_file = None  # type: ignore[assignment]
    _parse_classwork_xlsx = None  # type: ignore[assignment]
    _DASHBOARD_IMPORT_ERROR = _exc
    import traceback
    traceback.print_exc()


PROJECT_ROOT = Path(__file__).resolve().parent
MOCK_DATA_PATH = PROJECT_ROOT / "data" / "mock-dashboard.json"
MONITOR_STATE_PATH = PROJECT_ROOT / "data" / "document-monitor-state.json"
CLASSWORK_CACHE_PATH = PROJECT_ROOT / "data" / "classwork-cache.json"
WEBUNTIS_CACHE_PATH = PROJECT_ROOT / "data" / "webuntis-cache.json"
GRADES_LOCAL_PATH = PROJECT_ROOT / "data" / "grades-local.json"
NOTES_LOCAL_PATH = PROJECT_ROOT / "data" / "class-notes-local.json"
ENV_FILE_PATH = PROJECT_ROOT / ".env.local"
CLASSWORK_LOCAL_PATH = PROJECT_ROOT / "data" / "classwork-plan-local.xlsx"
DASHBOARD_CACHE_TTL_SECONDS = int(os.environ.get("DASHBOARD_CACHE_TTL_SECONDS", "45"))

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
_DASHBOARD_CACHE: dict[str, object] = {"payload": None, "created_monotonic": 0.0}


def _load_env_file() -> None:
    """Load .env.local into os.environ (only sets keys that aren't already set)."""
    env_path = PROJECT_ROOT / ".env.local"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def _invalidate_dashboard_cache() -> None:
    _DASHBOARD_CACHE["payload"] = None
    _DASHBOARD_CACHE["created_monotonic"] = 0.0


def _get_cached_dashboard_payload(*, force_refresh: bool) -> dict[str, object]:
    cached_payload = _DASHBOARD_CACHE.get("payload")
    created_monotonic = float(_DASHBOARD_CACHE.get("created_monotonic") or 0.0)
    if (
        not force_refresh
        and cached_payload is not None
        and (time.monotonic() - created_monotonic) <= DASHBOARD_CACHE_TTL_SECONDS
    ):
        return cached_payload  # type: ignore[return-value]

    payload = build_dashboard_payload(
        MOCK_DATA_PATH,
        MONITOR_STATE_PATH,
        CLASSWORK_CACHE_PATH,
        WEBUNTIS_CACHE_PATH,
    )
    _DASHBOARD_CACHE["payload"] = payload
    _DASHBOARD_CACHE["created_monotonic"] = time.monotonic()
    return payload


# ── HTTP handler ──────────────────────────────────────────────────────────────

class LehrerCockpitHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".json": "application/json",
        ".png": "image/png",
        ".webp": "image/webp",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/dashboard":
            if _DASHBOARD_IMPORT_ERROR is not None:
                self._send_json(
                    {"error": "dashboard module failed to import", "detail": str(_DASHBOARD_IMPORT_ERROR)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
            force_refresh = query.get("refresh", ["0"])[0].lower() in {"1", "true", "yes"}
            payload = _get_cached_dashboard_payload(force_refresh=force_refresh)
            self._send_json(payload)
            return

        if parsed.path == "/api/mail":
            if get_mail_preview is None:
                self._send_json(
                    {"status": "error", "detail": "Mail adapter not available."},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
            result = get_mail_preview()
            self._send_json(result)
            return

        if parsed.path == "/api/classwork":
            # Serve the persisted classwork cache (uploaded Excel data)
            if load_cache is None:
                self._send_json({"status": "error", "detail": "Cache module not available."}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            result = load_cache(CLASSWORK_CACHE_PATH)
            self._send_json(result)
            return

        if parsed.path == "/api/grades":
            if load_gradebook is None:
                self._send_json({"status": "error", "detail": "Grades store not available."}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json(load_gradebook(GRADES_LOCAL_PATH))
            return

        if parsed.path == "/api/notes":
            if load_notes is None:
                self._send_json({"status": "error", "detail": "Notes store not available."}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json(load_notes(NOTES_LOCAL_PATH))
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/classwork/upload":
            self._handle_classwork_upload()
            return

        if parsed.path == "/api/classwork/browser-fetch":
            import socket

            hostname = socket.gethostname()
            is_local = (
                os.environ.get("IS_LOCAL_RUNTIME", "").lower() in ("1", "true", "yes")
                or "render" not in hostname.lower()
            )
            if not is_local:
                self._send_json(
                    {
                        "status": "error",
                        "detail": "Browser-Abruf ist nur lokal verfuegbar, nicht auf dem Server.",
                    },
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0") or 0)
                body = json.loads(self.rfile.read(content_length)) if content_length else {}
            except Exception:
                body = {}

            onedrive_url = body.get("url", "") or os.environ.get("CLASSWORK_ONEDRIVE_URL", "")
            if not onedrive_url:
                self._send_json(
                    {
                        "status": "error",
                        "detail": (
                            "Kein OneDrive-Link konfiguriert. "
                            "Bitte CLASSWORK_ONEDRIVE_URL in .env.local setzen."
                        ),
                    },
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                from backend.classwork_browser import fetch_classwork_from_browser, write_to_cache
            except ImportError as exc:
                self._send_json(
                    {"status": "error", "detail": f"classwork_browser.py fehlt: {exc}"},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            result = fetch_classwork_from_browser(onedrive_url)
            if result.get("status") == "ok":
                result["cacheWritten"] = write_to_cache(result)
                _invalidate_dashboard_cache()
            self._send_json(result)
            return

        if parsed.path == "/api/local-settings/itslearning":
            if not self._is_local_request():
                self._send_json({"error": "local-only"}, status=HTTPStatus.FORBIDDEN)
                return

            if _DASHBOARD_IMPORT_ERROR is not None or save_itslearning_settings is None:
                self._send_json(
                    {"error": "settings module failed to import", "detail": str(_DASHBOARD_IMPORT_ERROR)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            payload = self._read_json_body()
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", "")).strip()
            base_url = str(payload.get("baseUrl", "https://berlin.itslearning.com")).strip() or "https://berlin.itslearning.com"
            max_updates = payload.get("maxUpdates", 6)

            if not username or not password:
                self._send_json(
                    {"error": "validation", "detail": "Benutzername und Passwort werden benoetigt."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                save_itslearning_settings(
                    ENV_FILE_PATH,
                    base_url=base_url,
                    username=username,
                    password=password,
                    max_updates=int(max_updates),
                )
            except Exception as exc:
                self._send_json(
                    {"error": "save-failed", "detail": f"{type(exc).__name__}: {exc}"},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            self._send_json({
                "status": "ok",
                "detail": "itslearning-Zugang lokal gespeichert.",
                "username": username,
                "baseUrl": base_url,
            })
            _invalidate_dashboard_cache()
            return

        if parsed.path == "/api/local-settings/nextcloud":
            if not self._is_local_request():
                self._send_json({"error": "local-only"}, status=HTTPStatus.FORBIDDEN)
                return

            if _DASHBOARD_IMPORT_ERROR is not None or save_nextcloud_settings is None:
                self._send_json(
                    {"error": "settings module failed to import", "detail": str(_DASHBOARD_IMPORT_ERROR)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            payload = self._read_json_body()
            current_settings = load_settings() if load_settings is not None else None
            current_nextcloud = getattr(current_settings, "nextcloud", None)

            username = str(payload.get("username", "")).strip() or getattr(current_nextcloud, "username", "")
            password = str(payload.get("password", "")).strip() or getattr(current_nextcloud, "password", "")
            base_url = (
                str(payload.get("baseUrl", getattr(current_nextcloud, "base_url", "https://nextcloud-g2.b-sz-heos.logoip.de"))).strip()
                or getattr(current_nextcloud, "base_url", "https://nextcloud-g2.b-sz-heos.logoip.de")
            )
            workspace_url = (
                str(payload.get("workspaceUrl", getattr(current_nextcloud, "workspace_url", "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/apps/files/"))).strip()
                or getattr(current_nextcloud, "workspace_url", "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/apps/files/")
            )
            q1q2_url = (
                str(payload.get("q1q2Url", getattr(current_nextcloud, "q1q2_url", "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008901"))).strip()
                or getattr(current_nextcloud, "q1q2_url", "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008901")
            )
            q3q4_url = (
                str(payload.get("q3q4Url", getattr(current_nextcloud, "q3q4_url", "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008900"))).strip()
                or getattr(current_nextcloud, "q3q4_url", "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008900")
            )
            link_1_label = str(payload.get("link1Label", getattr(current_nextcloud, "link_1_label", ""))).strip()
            link_1_url = str(payload.get("link1Url", getattr(current_nextcloud, "link_1_url", ""))).strip()
            link_2_label = str(payload.get("link2Label", getattr(current_nextcloud, "link_2_label", ""))).strip()
            link_2_url = str(payload.get("link2Url", getattr(current_nextcloud, "link_2_url", ""))).strip()
            link_3_label = str(payload.get("link3Label", getattr(current_nextcloud, "link_3_label", ""))).strip()
            link_3_url = str(payload.get("link3Url", getattr(current_nextcloud, "link_3_url", ""))).strip()

            try:
                save_nextcloud_settings(
                    ENV_FILE_PATH,
                    base_url=base_url,
                    username=username,
                    password=password,
                    workspace_url=workspace_url,
                    q1q2_url=q1q2_url,
                    q3q4_url=q3q4_url,
                    link_1_label=link_1_label,
                    link_1_url=link_1_url,
                    link_2_label=link_2_label,
                    link_2_url=link_2_url,
                    link_3_label=link_3_label,
                    link_3_url=link_3_url,
                )
            except Exception as exc:
                self._send_json(
                    {"error": "save-failed", "detail": f"{type(exc).__name__}: {exc}"},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            self._send_json(
                {
                    "status": "ok",
                    "detail": "Nextcloud-Arbeitsbereich lokal gespeichert.",
                    "username": username,
                    "baseUrl": base_url,
                    "workspaceUrl": workspace_url,
                    "q1q2Url": q1q2_url,
                    "q3q4Url": q3q4_url,
                    "link1Label": link_1_label,
                    "link1Url": link_1_url,
                    "link2Label": link_2_label,
                    "link2Url": link_2_url,
                    "link3Label": link_3_label,
                    "link3Url": link_3_url,
                }
            )
            _invalidate_dashboard_cache()
            return

        if parsed.path == "/api/local-settings/classwork-upload":
            if not self._is_local_request():
                self._send_json({"error": "local-only"}, status=HTTPStatus.FORBIDDEN)
                return

            if _DASHBOARD_IMPORT_ERROR is not None or save_classwork_file is None:
                self._send_json(
                    {"error": "settings module failed to import", "detail": str(_DASHBOARD_IMPORT_ERROR)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            payload = self._read_json_body()
            filename = str(payload.get("filename", "")).strip()
            content_base64 = str(payload.get("contentBase64", "")).strip()

            if not filename or not content_base64:
                self._send_json(
                    {"error": "validation", "detail": "Bitte eine XLSX-Datei auswaehlen."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                save_classwork_file(CLASSWORK_LOCAL_PATH, filename=filename, content_base64=content_base64)
            except Exception as exc:
                self._send_json(
                    {"error": "save-failed", "detail": f"{type(exc).__name__}: {exc}"},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            self._send_json(
                {
                    "status": "ok",
                    "detail": "Klassenarbeitsplan lokal importiert. Das Cockpit liest die Datei jetzt neu ein.",
                    "path": str(CLASSWORK_LOCAL_PATH),
                }
            )
            _invalidate_dashboard_cache()
            return

        if parsed.path == "/api/local-settings/grades":
            if not self._is_local_request():
                self._send_json({"error": "local-only"}, status=HTTPStatus.FORBIDDEN)
                return

            if load_gradebook is None or save_gradebook is None or create_grade_entry is None:
                self._send_json(
                    {"error": "grades module failed to import", "detail": str(_DASHBOARD_IMPORT_ERROR)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            payload = self._read_json_body()
            mode = str(payload.get("mode", "append")).strip() or "append"
            current = load_gradebook(GRADES_LOCAL_PATH)
            current_entries = current.get("entries", [])

            if mode == "replace":
                entries = payload.get("entries", [])
                result = save_gradebook(GRADES_LOCAL_PATH, entries if isinstance(entries, list) else [])
                self._send_json({"status": "ok", "detail": "Noten lokal gespeichert.", **result})
                _invalidate_dashboard_cache()
                return

            if mode == "delete":
                entry_id = str(payload.get("id", "")).strip()
                if not entry_id:
                    self._send_json({"error": "validation", "detail": "Eintrags-ID fehlt."}, status=HTTPStatus.BAD_REQUEST)
                    return
                remaining = [entry for entry in current_entries if entry.get("id") != entry_id]
                result = save_gradebook(GRADES_LOCAL_PATH, remaining)
                self._send_json({"status": "ok", "detail": "Eintrag entfernt.", **result})
                _invalidate_dashboard_cache()
                return

            entry = create_grade_entry(payload)
            if not entry["classLabel"] or not entry["studentName"] or not entry["title"]:
                self._send_json(
                    {"error": "validation", "detail": "Klasse, Schueler:in und Titel werden benoetigt."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            result = save_gradebook(GRADES_LOCAL_PATH, [entry] + current_entries)
            self._send_json({"status": "ok", "detail": "Note lokal gespeichert.", **result})
            _invalidate_dashboard_cache()
            return

        if parsed.path == "/api/local-settings/notes":
            if not self._is_local_request():
                self._send_json({"error": "local-only"}, status=HTTPStatus.FORBIDDEN)
                return

            if load_notes is None or save_notes is None or create_note is None:
                self._send_json(
                    {"error": "notes module failed to import", "detail": str(_DASHBOARD_IMPORT_ERROR)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            payload = self._read_json_body()
            mode = str(payload.get("mode", "upsert")).strip() or "upsert"
            current = load_notes(NOTES_LOCAL_PATH)
            current_notes = current.get("notes", [])

            if mode == "delete":
                class_label = str(payload.get("classLabel", "")).strip().upper()
                if not class_label:
                    self._send_json({"error": "validation", "detail": "Klasse fehlt."}, status=HTTPStatus.BAD_REQUEST)
                    return
                remaining = [item for item in current_notes if item.get("classLabel") != class_label]
                result = save_notes(NOTES_LOCAL_PATH, remaining)
                self._send_json({"status": "ok", "detail": "Notiz entfernt.", **result})
                _invalidate_dashboard_cache()
                return

            note = create_note(payload)
            if not note["classLabel"]:
                self._send_json({"error": "validation", "detail": "Klasse wird benoetigt."}, status=HTTPStatus.BAD_REQUEST)
                return
            remaining = [item for item in current_notes if item.get("classLabel") != note["classLabel"]]
            if note["text"]:
                remaining = [note] + remaining
            result = save_notes(NOTES_LOCAL_PATH, remaining)
            self._send_json({"status": "ok", "detail": "Notiz lokal gespeichert.", **result})
            _invalidate_dashboard_cache()
            return

        self._send_json({"error": "not-found"}, status=HTTPStatus.NOT_FOUND)

    def _handle_classwork_upload(self) -> None:
        """Handle multipart file upload of XLS/XLSX/CSV, parse, save to cache."""
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", "0") or 0)

        if not content_length:
            self._send_json({"error": "no-body", "detail": "Kein Dateiinhalt empfangen."}, status=HTTPStatus.BAD_REQUEST)
            return

        if content_length > 20 * 1024 * 1024:  # 20 MB max
            self._send_json({"error": "too-large", "detail": "Datei zu groß (max 20 MB)."}, status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return

        raw_body = self.rfile.read(content_length)

        file_bytes = _extract_multipart_file(raw_body, content_type)
        if file_bytes is None:
            file_bytes = raw_body

        try:
            result = _parse_classwork_xlsx(file_bytes)
        except Exception as exc:
            self._send_json(
                {"error": "parse-failed", "detail": f"Datei konnte nicht gelesen werden: {type(exc).__name__}: {exc}"},
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
            return

        if save_cache:
            save_cache(CLASSWORK_CACHE_PATH, result)
        _invalidate_dashboard_cache()

        self._send_json(result)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self._send_cors_headers()
        super().end_headers()

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        if not raw_body:
            return {}
        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _is_local_request(self) -> bool:
        host, *_rest = self.client_address
        return host in {"127.0.0.1", "::1", "localhost"}

    def log_message(self, fmt: str, *args) -> None:
        super().log_message(fmt, *args)


# ── File parsing helpers live in backend/file_utils.py ────────────────────────
# _extract_multipart_file and _parse_classwork_xlsx are imported at the top of
# this file from backend.file_utils — they are no longer duplicated here.


def run() -> None:
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0"
    server = ThreadingHTTPServer((host, port), LehrerCockpitHandler)
    print(f"Lehrer-Cockpit läuft auf http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run()
