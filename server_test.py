#!/usr/bin/env python3
"""Minimal Railway-compatible server for testing."""
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PORT = int(os.environ.get("PORT", 8080))
CORS = os.environ.get("CORS_ORIGIN", "*")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.command}] {self.path} -> {args[0] if args else ''}", flush=True)
    
    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", CORS)
        self.end_headers()
        self.wfile.write(body)
    
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", CORS)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_GET(self):
        if self.path == "/api/health":
            self.send_json({"status": "ok", "port": PORT})
        elif self.path == "/api/dashboard":
            try:
                mock_path = Path(__file__).parent / "data" / "mock-dashboard.json"
                data = json.loads(mock_path.read_text())
                self.send_json(data)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
        else:
            self.send_json({"error": "not found"}, 404)

if __name__ == "__main__":
    import sys
    print(f"Python version: {sys.version}", flush=True)
    print(f"PORT env var: {os.environ.get('PORT', 'NOT SET')}", flush=True)
    print(f"Starting server on 0.0.0.0:{PORT}", flush=True)
    try:
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"Server ready and listening on port {PORT}", flush=True)
        server.serve_forever()
    except Exception as e:
        print(f"FATAL: Server failed to start: {e}", flush=True)
        sys.exit(1)
