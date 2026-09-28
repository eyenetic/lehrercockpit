#!/usr/bin/env bash
# Netlify build: publish only the frontend (not the Python backend, tests or docs).
# Keep in sync with FRONTEND_FILES / FRONTEND_DIRS in app.py.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf public
mkdir -p public/data
cp index.html login.html onboarding.html admin.html manifest.json sw.js \
   styles.css styles.auth.css styles.admin.css public/
cp data/mock-dashboard.js public/data/
cp -R src icons public/
echo "Frontend in public/: $(find public -type f | wc -l | tr -d ' ') Dateien"
