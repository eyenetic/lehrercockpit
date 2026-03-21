from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlparse

try:
    from backend.dashboard import build_dashboard_payload
    from backend.local_settings import save_itslearning_settings
    _DASHBOARD_IMPORT_ERROR: Exception | None = None
except Exception as _exc:
    build_dashboard_payload = None  # type: ignore[assignment]
    save_itslearning_settings = None  # type: ignore[assignment]
    _DASHBOARD_IMPORT_ERROR = _exc
    import traceback
    traceback.print_exc()


PROJECT_ROOT = Path(__file__).resolve().parent
MOCK_DATA_PATH = PROJECT_ROOT / "data" / "mock-dashboard.json"
MONITOR_STATE_PATH = PROJECT_ROOT / "data" / "document-monitor-state.json"
ENV_FILE_PATH = PROJECT_ROOT / ".env.local"


CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")


class LehrerCockpitHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/dashboard":
            if _DASHBOARD_IMPORT_ERROR is not None:
                self._send_json({"error": "dashboard module failed to import", "detail": str(_DASHBOARD_IMPORT_ERROR)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            payload = build_dashboard_payload(MOCK_DATA_PATH, MONITOR_STATE_PATH)
            self._send_json(payload)
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

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

            self._send_json(
                {
                    "status": "ok",
                    "detail": "itslearning-Zugang lokal gespeichert. Das Cockpit laedt die Updates jetzt neu.",
                    "username": username,
                    "baseUrl": base_url,
                }
            )
            return

        self._send_json({"error": "not-found"}, status=HTTPStatus.NOT_FOUND)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

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


def run() -> None:
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0"
    server = ThreadingHTTPServer((host, port), LehrerCockpitHandler)
    print(f"Lehrer-Cockpit laeuft auf http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
