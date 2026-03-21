#!/usr/bin/env python3
"""Production entry point for Render.

Delegates entirely to server.py which provides:
  GET  /api/health
  GET  /api/dashboard     (plan_digest + classwork cache overlay)
  GET  /api/classwork     (Playwright-scraped cache)
  POST /api/classwork/scrape          (trigger background scrape)
  GET  /api/classwork/scrape/progress (SSE live progress)
  POST /api/local-settings/itslearning

PORT is read from the $PORT environment variable (Render sets this automatically).
"""
import server

if __name__ == "__main__":
    server.run()
