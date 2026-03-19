from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlparse

try:
    from backend.dashboard import build_dashboard_payload
    _DASHBOARD_IMPORT_ERROR: Exception | None = None
except Exception as _exc:
    build_dashboard_payload = None  # type: ignore[assignment]
    _DASHBOARD_IMPORT_ERROR = _exc
    import traceback
    traceback.print_exc()


PROJECT_ROOT = Path(__file__).resolve().parent
MOCK_DATA_PATH = PROJECT_ROOT / "data" / "mock-dashboard.json"
MONITOR_STATE_PATH = PROJECT_ROOT / "data" / "document-monitor-state.json"


CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "https://lehrercockpit.eyenetic.com")


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


def run() -> None:
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0"
    server = ThreadingHTTPServer((host, port), LehrerCockpitHandler)
    print(f"Lehrer-Cockpit laeuft auf http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
