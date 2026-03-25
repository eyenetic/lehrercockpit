"""Local dev launch script — starts the stdlib ThreadingHTTPServer from server.py.

This is NOT a test file.  It was previously named server_test.py which caused
confusion (pytest would try to collect it as a test suite).

Usage:
    python3 dev_runner.py

For production, Render uses gunicorn via the Procfile:
    gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
"""
import server

if __name__ == "__main__":
    server.run()
