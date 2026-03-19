from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from backend.dashboard import build_dashboard_payload


PROJECT_ROOT = Path(__file__).resolve().parent
MOCK_DATA_PATH = PROJECT_ROOT / "data" / "mock-dashboard.json"
MONITOR_STATE_PATH = PROJECT_ROOT / "data" / "document-monitor-state.json"


class LehrerCockpitHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/dashboard":
            payload = build_dashboard_payload(MOCK_DATA_PATH, MONITOR_STATE_PATH)
            self._send_json(payload)
            return

        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run() -> None:
    port = int(os.getenv("PORT", "4173"))
    server = ThreadingHTTPServer(("127.0.0.1", port), LehrerCockpitHandler)
    print(f"Lehrer-Cockpit laeuft auf http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
