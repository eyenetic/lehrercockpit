#!/bin/bash
# sync-classwork.sh
#
# Runs on the Mac Mini (always online).
# Finds the local Klassenarbeitsplan Excel file and uploads it to Render.
#
# Usage:
#   ./sync-classwork.sh
#   ./sync-classwork.sh /path/to/file.xlsx   # explicit file path
#
# Cron setup (daily at 06:00):
#   crontab -e
#   0 6 * * * /path/to/lehrercockpit/sync-classwork.sh >> /tmp/classwork-sync.log 2>&1
#
# On Mac Mini via SSH:
#   ssh mac-mini "cd ~/lehrercockpit && ./sync-classwork.sh"

RENDER_URL="https://lehrercockpit.onrender.com"
UPLOAD_ENDPOINT="${RENDER_URL}/api/classwork/upload"

# ── Locate the Excel file ──────────────────────────────────────────────────────

if [ -n "${1:-}" ] && [ -f "$1" ]; then
  # Explicit path given as argument
  XLSX_FILE="$1"
else
  # Auto-search: Downloads, Desktop, Messages attachments, OneDrive
  XLSX_FILE=$(find \
    ~/Downloads \
    ~/Desktop \
    ~/Library/Messages/Attachments \
    ~/Library/CloudStorage \
    -maxdepth 6 \
    \( -name "*Klassenarbeitsplan*.xlsx" -o -name "*lassenarbeitsplan*.xlsx" -o -name "*classwork*.xlsx" \) \
    -type f 2>/dev/null \
    | grep -v "\.Trash" \
    | sort -r \
    | head -1)
fi

if [ -z "$XLSX_FILE" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Kein Klassenarbeitsplan .xlsx gefunden."
  echo "  Bitte Pfad als Argument angeben: $0 /pfad/zu/datei.xlsx"
  exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Datei gefunden: $XLSX_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Upload zu $UPLOAD_ENDPOINT ..."

# ── Upload ─────────────────────────────────────────────────────────────────────

RESPONSE=$(curl -s -w "\n%{http_code}" \
  --max-time 90 \
  -X POST "$UPLOAD_ENDPOINT" \
  -F "file=@${XLSX_FILE}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

if [ "$HTTP_CODE" = "200" ]; then
  DETAIL=$(echo "$BODY" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('detail',''))" 2>/dev/null || echo "$BODY")
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Erfolgreich: $DETAIL"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ Fehler: HTTP $HTTP_CODE"
  echo "$BODY"
  exit 1
fi
