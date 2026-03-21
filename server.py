from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlparse

try:
    from backend.dashboard import build_dashboard_payload
    from backend.local_settings import save_itslearning_settings
    from backend.classwork_scraper import scrape_classwork_plan
    from backend.classwork_cache import load_cache, save_cache, cache_age_minutes
    _DASHBOARD_IMPORT_ERROR: Exception | None = None
except Exception as _exc:
    build_dashboard_payload = None  # type: ignore[assignment]
    save_itslearning_settings = None  # type: ignore[assignment]
    scrape_classwork_plan = None  # type: ignore[assignment]
    load_cache = None  # type: ignore[assignment]
    save_cache = None  # type: ignore[assignment]
    cache_age_minutes = None  # type: ignore[assignment]
    _DASHBOARD_IMPORT_ERROR = _exc
    import traceback
    traceback.print_exc()


PROJECT_ROOT = Path(__file__).resolve().parent
MOCK_DATA_PATH = PROJECT_ROOT / "data" / "mock-dashboard.json"
MONITOR_STATE_PATH = PROJECT_ROOT / "data" / "document-monitor-state.json"
CLASSWORK_CACHE_PATH = PROJECT_ROOT / "data" / "classwork-cache.json"
ENV_FILE_PATH = PROJECT_ROOT / ".env.local"

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

# Load .env.local early so CLASSWORK_PLAN_URL and other vars are available
def _load_env_file() -> None:
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

CLASSWORK_PLAN_URL = os.environ.get("CLASSWORK_PLAN_URL", "")

# Cron interval in seconds (default: every 6 hours)
SCRAPE_INTERVAL_SECONDS = int(os.environ.get("CLASSWORK_SCRAPE_INTERVAL_SECONDS", str(6 * 3600)))
# Minimum age before auto-refresh triggers (minutes)
SCRAPE_MIN_AGE_MINUTES = float(os.environ.get("CLASSWORK_SCRAPE_MIN_AGE_MINUTES", "30"))

# In-flight lock to prevent concurrent scrapes
_scrape_lock = threading.Lock()
_scrape_in_progress = False


def _run_scrape(url: str) -> dict:
    """Run the scraper, save result to cache and return it."""
    global _scrape_in_progress

    if not scrape_classwork_plan or not save_cache:
        return {"status": "error", "detail": "Scraper module not available."}

    with _scrape_lock:
        if _scrape_in_progress:
            return load_cache(CLASSWORK_CACHE_PATH) if load_cache else {"status": "busy", "detail": "Scrape bereits aktiv."}
        _scrape_in_progress = True

    try:
        print(f"[classwork] Starting scrape for: {url}", flush=True)
        result = scrape_classwork_plan(url)
        save_cache(CLASSWORK_CACHE_PATH, result)
        print(f"[classwork] Scrape done. status={result.get('status')}, rows={len(result.get('structuredRows', []))}", flush=True)
        return result
    finally:
        _scrape_in_progress = False


def _cron_worker() -> None:
    """Background thread that periodically scrapes the classwork plan."""
    if not CLASSWORK_PLAN_URL:
        print("[classwork-cron] No CLASSWORK_PLAN_URL set, cron disabled.", flush=True)
        return

    print(f"[classwork-cron] Started. Interval: {SCRAPE_INTERVAL_SECONDS}s, min age: {SCRAPE_MIN_AGE_MINUTES}min", flush=True)

    # Initial delay so server can start cleanly
    time.sleep(30)

    while True:
        try:
            age = cache_age_minutes(CLASSWORK_CACHE_PATH) if cache_age_minutes else None
            if age is None or age >= SCRAPE_MIN_AGE_MINUTES:
                _run_scrape(CLASSWORK_PLAN_URL)
            else:
                print(f"[classwork-cron] Cache fresh ({age:.1f}min old), skipping.", flush=True)
        except Exception as exc:
            print(f"[classwork-cron] Error: {exc}", flush=True)
        time.sleep(SCRAPE_INTERVAL_SECONDS)


class LehrerCockpitHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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

        if parsed.path == "/api/classwork":
            # Return cached classwork data (fast, no scraping)
            if load_cache is None:
                self._send_json({"status": "error", "detail": "Cache module not available."}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            result = load_cache(CLASSWORK_CACHE_PATH)
            age = cache_age_minutes(CLASSWORK_CACHE_PATH) if cache_age_minutes else None
            result["cacheAgeMinutes"] = round(age, 1) if age is not None else None
            result["scrapeInProgress"] = _scrape_in_progress
            self._send_json(result)
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/classwork/scrape":
            # Manually trigger a scrape (available from any origin since data is public)
            url = CLASSWORK_PLAN_URL
            if not url:
                self._send_json({"error": "no-url", "detail": "CLASSWORK_PLAN_URL ist nicht konfiguriert."}, status=HTTPStatus.BAD_REQUEST)
                return

            if scrape_classwork_plan is None:
                self._send_json({"error": "no-scraper", "detail": "Scraper-Modul nicht verfuegbar."}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return

            if _scrape_in_progress:
                # Return current cache with busy flag
                result = load_cache(CLASSWORK_CACHE_PATH) if load_cache else {}
                result["scrapeInProgress"] = True
                result["detail"] = "Scrape laeuft bereits. Bitte in 30 Sekunden erneut versuchen."
                self._send_json(result)
                return

            # Run scrape in background, return immediately with 202 Accepted
            # so the frontend can poll /api/classwork for the result
            thread = threading.Thread(target=_run_scrape, args=(url,), daemon=True)
            thread.start()

            self._send_json(
                {"status": "started", "detail": "Scrape wurde gestartet. Ergebnis in /api/classwork abrufbar."},
                status=HTTPStatus.ACCEPTED,
            )
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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

    # Start cron background thread
    if CLASSWORK_PLAN_URL:
        cron_thread = threading.Thread(target=_cron_worker, daemon=True)
        cron_thread.start()
        print(f"[classwork-cron] Background scraper scheduled every {SCRAPE_INTERVAL_SECONDS}s", flush=True)

    server = ThreadingHTTPServer((host, port), LehrerCockpitHandler)
    print(f"Lehrer-Cockpit laeuft auf http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run()
