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
    from backend.classwork_cache import load_cache, save_cache
    _DASHBOARD_IMPORT_ERROR: Exception | None = None
except Exception as _exc:
    build_dashboard_payload = None  # type: ignore[assignment]
    save_itslearning_settings = None  # type: ignore[assignment]
    load_cache = None  # type: ignore[assignment]
    save_cache = None  # type: ignore[assignment]
    _DASHBOARD_IMPORT_ERROR = _exc
    import traceback
    traceback.print_exc()


PROJECT_ROOT = Path(__file__).resolve().parent
MOCK_DATA_PATH = PROJECT_ROOT / "data" / "mock-dashboard.json"
MONITOR_STATE_PATH = PROJECT_ROOT / "data" / "document-monitor-state.json"
CLASSWORK_CACHE_PATH = PROJECT_ROOT / "data" / "classwork-cache.json"
ENV_FILE_PATH = PROJECT_ROOT / ".env.local"

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")


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


# ── HTTP handler ──────────────────────────────────────────────────────────────

class LehrerCockpitHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

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
            payload = build_dashboard_payload(MOCK_DATA_PATH, MONITOR_STATE_PATH, CLASSWORK_CACHE_PATH)
            self._send_json(payload)
            return

        if parsed.path == "/api/classwork":
            # Serve the persisted classwork cache (uploaded Excel data)
            if load_cache is None:
                self._send_json({"status": "error", "detail": "Cache module not available."}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            result = load_cache(CLASSWORK_CACHE_PATH)
            self._send_json(result)
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/classwork/upload":
            self._handle_classwork_upload()
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


# ── File parsing helpers ───────────────────────────────────────────────────────

def _extract_multipart_file(body: bytes, content_type: str) -> bytes | None:
    """Extract raw file bytes from a multipart/form-data body."""
    import re as _re
    boundary_match = _re.search(r"boundary=([^\s;]+)", content_type)
    if not boundary_match:
        return None
    boundary = ("--" + boundary_match.group(1)).encode()
    parts = body.split(boundary)
    for part in parts:
        if b"filename=" not in part:
            continue
        sep = b"\r\n\r\n"
        idx = part.find(sep)
        if idx == -1:
            sep = b"\n\n"
            idx = part.find(sep)
        if idx == -1:
            continue
        file_data = part[idx + len(sep):]
        if file_data.endswith(b"\r\n"):
            file_data = file_data[:-2]
        return file_data
    return None


def _parse_classwork_xlsx(file_bytes: bytes) -> dict:
    """Parse XLS/XLSX bytes with openpyxl (or CSV fallback) and return classwork cache dict."""
    from io import BytesIO as _BytesIO
    from datetime import datetime as _dt
    import hashlib as _hashlib
    import re as _re

    now = _dt.now()

    def _clean_header(value: str) -> str:
        return _re.sub(r"[\r\n]+", " ", str(value)).strip()

    try:
        from openpyxl import load_workbook as _load_wb
        wb = _load_wb(_BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception:
        # CSV fallback
        import csv as _csv
        text = file_bytes.decode("utf-8", errors="replace")
        reader = _csv.reader(text.splitlines())
        all_rows = [r for r in reader if any(c.strip() for c in r)]
        if not all_rows:
            raise ValueError("Datei ist leer oder kein lesbares Format.")
        header = [c.strip() for c in all_rows[0]]
        structured = [
            {header[i]: (row[i].strip() if i < len(row) else "") for i in range(len(header))}
            for row in all_rows[1:] if any(c.strip() for c in row)
        ]
        preview = [" | ".join(c.strip() for c in row[:6] if c.strip()) for row in all_rows[:9]]
        return {
            "status": "ok", "title": "Klassenarbeitsplan",
            "detail": f"CSV hochgeladen. {len(structured)} Eintraege gelesen.",
            "updatedAt": now.strftime("%H:%M"), "scrapedAt": now.isoformat(),
            "previewRows": preview, "structuredRows": structured[:200],
            "sourceUrl": "", "scrapeMode": "upload",
            "dataHash": _hashlib.sha256(file_bytes).hexdigest()[:16],
            "hasChanges": False, "noChanges": False,
        }

    all_structured: list[dict] = []
    preview_rows: list[str] = []
    total_sheets = len(wb.sheetnames)

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        raw_rows: list[list[str]] = []
        for row in sheet.iter_rows(values_only=True):
            values = [str(v).strip() if v is not None else "" for v in row]
            if any(v for v in values):
                raw_rows.append(values)
            if len(raw_rows) >= 60:
                break

        if not raw_rows:
            continue

        header = [_clean_header(col) if col else f"Spalte{i+1}" for i, col in enumerate(raw_rows[0])]

        for row in raw_rows[1:]:
            if not any(v for v in row):
                continue
            entry: dict = {"_sheet": sheet_name}
            for i, col in enumerate(header):
                entry[col] = row[i] if i < len(row) else ""
            all_structured.append(entry)

        if not preview_rows:
            preview_rows = [" | ".join(v for v in row[:6] if v) for row in raw_rows[:9] if any(row)]

    wb.close()

    if not all_structured:
        raise ValueError("Tabelle ist leer oder kein lesbares Format.")

    return {
        "status": "ok", "title": "Klassenarbeitsplan",
        "detail": f"Excel-Datei hochgeladen. {len(all_structured)} Eintraege aus {total_sheets} Tabellenblättern gelesen.",
        "updatedAt": now.strftime("%H:%M"), "scrapedAt": now.isoformat(),
        "previewRows": preview_rows, "structuredRows": all_structured[:200],
        "sourceUrl": "", "scrapeMode": "upload",
        "dataHash": _hashlib.sha256(file_bytes).hexdigest()[:16],
        "hasChanges": False, "noChanges": False,
    }


def run() -> None:
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0"
    server = ThreadingHTTPServer((host, port), LehrerCockpitHandler)
    print(f"Lehrer-Cockpit läuft auf http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run()
