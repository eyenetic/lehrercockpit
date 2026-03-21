#!/bin/bash
# watch-classwork.sh
#
# Called by launchd FSEvents watcher whenever Downloads, Desktop, or OneDrive changes.
# Finds the newest Klassenarbeitsplan Excel and uploads it to the local server
# (and optionally to Render as backup).
#
# Also called at boot (RunAtLoad) and can be run manually.

set -uo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_URL="http://127.0.0.1:${PORT:-8080}"
UPLOAD_ENDPOINT="${LOCAL_URL}/api/classwork/upload"
LOCK_FILE="/tmp/classwork-upload.lock"
STATE_FILE="/tmp/classwork-last-uploaded.txt"
LOG_TAG="[classwork-watcher $(date '+%H:%M:%S')]"

# ── Prevent concurrent runs ────────────────────────────────────────────────────
if [ -f "$LOCK_FILE" ]; then
  echo "$LOG_TAG Lock exists, skipping." ; exit 0
fi
touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# ── Find newest matching Excel ─────────────────────────────────────────────────
SEARCH_DIRS=()
[ -d "$HOME/Downloads" ]     && SEARCH_DIRS+=("$HOME/Downloads")
[ -d "$HOME/Desktop" ]       && SEARCH_DIRS+=("$HOME/Desktop")

# OneDrive — try multiple possible paths
for od in \
    "$HOME/Library/CloudStorage/OneDrive-MOIAGmbH" \
    "$HOME/Library/CloudStorage/OneDrive-Personal" \
    "$HOME/OneDrive"; do
  [ -d "$od" ] && SEARCH_DIRS+=("$od") && break
done

# Messages attachments (iMessage received files)
[ -d "$HOME/Library/Messages/Attachments" ] && SEARCH_DIRS+=("$HOME/Library/Messages/Attachments")

XLSX_FILE=$(find "${SEARCH_DIRS[@]}" \
  -maxdepth 8 \
  \( -name "*Klassenarbeitsplan*.xlsx" \
     -o -name "*lassenarbeitsplan*.xlsx" \
     -o -name "*classwork*.xlsx" \) \
  -type f \
  2>/dev/null \
  | grep -v "\.Trash" \
  | xargs ls -t 2>/dev/null \
  | head -1 || true)

if [ -z "$XLSX_FILE" ]; then
  echo "$LOG_TAG Kein Klassenarbeitsplan Excel gefunden."
  exit 0
fi

# ── Skip if already uploaded this exact file ──────────────────────────────────
FILE_HASH=$(md5 -q "$XLSX_FILE" 2>/dev/null || md5sum "$XLSX_FILE" 2>/dev/null | cut -d' ' -f1)
LAST_HASH=$(cat "$STATE_FILE" 2>/dev/null || echo "")

if [ "$FILE_HASH" = "$LAST_HASH" ]; then
  echo "$LOG_TAG Datei unveraendert (${XLSX_FILE##*/}), kein Upload."
  exit 0
fi

echo "$LOG_TAG Neue Datei erkannt: $XLSX_FILE"

# ── Wait for server to be ready ────────────────────────────────────────────────
for i in $(seq 1 10); do
  if curl -sf "${LOCAL_URL}/api/health" >/dev/null 2>&1; then
    break
  fi
  echo "$LOG_TAG Warte auf Server... ($i)"
  sleep 2
done

# ── Upload to local server ─────────────────────────────────────────────────────
RESPONSE=$(curl -sf -w "\n%{http_code}" \
  --max-time 60 \
  -X POST "$UPLOAD_ENDPOINT" \
  -F "file=@${XLSX_FILE}" 2>&1 || echo -e "\n000")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

if [ "$HTTP_CODE" = "200" ]; then
  DETAIL=$(echo "$BODY" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('detail',''))" 2>/dev/null || echo "$BODY")
  echo "$LOG_TAG ✓ Upload OK: $DETAIL"
  echo "$FILE_HASH" > "$STATE_FILE"
else
  echo "$LOG_TAG ✗ Upload fehlgeschlagen: HTTP $HTTP_CODE"
  echo "$BODY"
fi
