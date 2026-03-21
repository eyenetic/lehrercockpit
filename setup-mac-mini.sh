#!/bin/bash
# setup-mac-mini.sh
#
# One-shot setup script — run ONCE on the Mac Mini.
# Sets up the Lehrer-Cockpit backend to run permanently with auto-start,
# folder watching for Excel auto-upload, and Tailscale Funnel for HTTPS.
#
# Usage (run on Mac Mini):
#   cd ~ && bash <(curl -fsSL https://raw.githubusercontent.com/eyenetic/lehrercockpit/main/setup-mac-mini.sh)
#
# Or via SSH after key setup:
#   ssh mac-mini "bash <(curl -fsSL https://raw.githubusercontent.com/eyenetic/lehrercockpit/main/setup-mac-mini.sh)"

set -euo pipefail

REPO="https://github.com/eyenetic/lehrercockpit.git"
INSTALL_DIR="$HOME/lehrercockpit"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/lehrercockpit"
PORT=8080

echo "========================================"
echo "  Lehrer-Cockpit Mac Mini Setup"
echo "========================================"

# ── 1. Clone or update repo ────────────────────────────────────────────────────

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "[1/7] Repo gefunden — aktualisiere..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "[1/7] Klone Repository..."
  git clone "$REPO" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ── 2. Python dependencies ─────────────────────────────────────────────────────

echo "[2/7] Installiere Python-Abhaengigkeiten..."
python3 -m pip install --quiet --user openpyxl pypdf

# ── 3. Create directories ──────────────────────────────────────────────────────

echo "[3/7] Erstelle Verzeichnisse..."
mkdir -p "$LOG_DIR" "$LAUNCHD_DIR" "$INSTALL_DIR/data"

# ── 4. Install launchd server plist ───────────────────────────────────────────

echo "[4/7] Installiere Server-LaunchAgent..."
cat > "$LAUNCHD_DIR/de.lehrercockpit.server.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>de.lehrercockpit.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${INSTALL_DIR}/server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PORT</key>
        <string>${PORT}</string>
        <key>CORS_ORIGIN</key>
        <string>*</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>PYTHONPATH</key>
        <string>${INSTALL_DIR}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/server.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/server-error.log</string>
</dict>
</plist>
PLIST

launchctl unload "$LAUNCHD_DIR/de.lehrercockpit.server.plist" 2>/dev/null || true
launchctl load "$LAUNCHD_DIR/de.lehrercockpit.server.plist"
echo "    Server-LaunchAgent geladen."

# ── 5. Install folder watcher plist ───────────────────────────────────────────

echo "[5/7] Installiere Ordner-Watcher..."

# Find OneDrive root
ONEDRIVE_ROOT=""
for candidate in \
    "$HOME/Library/CloudStorage/OneDrive-MOIAGmbH" \
    "$HOME/Library/CloudStorage/OneDrive-Personal" \
    "$HOME/OneDrive"; do
  if [ -d "$candidate" ]; then
    ONEDRIVE_ROOT="$candidate"
    break
  fi
done

# Watch paths: OneDrive + Downloads + Desktop
WATCH_PATHS=""
for watch_dir in "$HOME/Downloads" "$HOME/Desktop" "$ONEDRIVE_ROOT"; do
  [ -d "$watch_dir" ] || continue
  WATCH_PATHS="${WATCH_PATHS}
        <string>${watch_dir}</string>"
done

cat > "$LAUNCHD_DIR/de.lehrercockpit.watcher.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>de.lehrercockpit.watcher</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${INSTALL_DIR}/watch-classwork.sh</string>
    </array>
    <key>WatchPaths</key>
    <array>${WATCH_PATHS}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/watcher.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/watcher-error.log</string>
</dict>
</plist>
PLIST

launchctl unload "$LAUNCHD_DIR/de.lehrercockpit.watcher.plist" 2>/dev/null || true
launchctl load "$LAUNCHD_DIR/de.lehrercockpit.watcher.plist"
echo "    Watcher-LaunchAgent geladen."

# ── 6. Tailscale Funnel ────────────────────────────────────────────────────────

echo "[6/7] Konfiguriere Tailscale Funnel..."
if command -v tailscale &>/dev/null; then
  tailscale funnel --bg "${PORT}" 2>/dev/null || true
  FUNNEL_URL=$(tailscale funnel status 2>/dev/null | grep "https://" | head -1 | awk '{print $1}' || true)
  if [ -n "$FUNNEL_URL" ]; then
    echo "    Tailscale Funnel aktiv: $FUNNEL_URL"
    echo "    → Trage diese URL in Netlify index.html als BACKEND_API_URL ein."
  else
    echo "    Tailscale Funnel gestartet. URL: tailscale funnel status"
  fi
else
  echo "    Tailscale nicht gefunden. Manuell aktivieren: tailscale funnel ${PORT}"
fi

# ── 7. Initial upload ──────────────────────────────────────────────────────────

echo "[7/7] Initialer Upload des Klassenarbeitsplans..."
sleep 2  # wait for server to start
bash "$INSTALL_DIR/watch-classwork.sh" && echo "    Initialer Upload erfolgreich." || echo "    Kein Excel gefunden — wird automatisch hochgeladen, sobald eine Datei erkannt wird."

echo ""
echo "========================================"
echo "  Setup abgeschlossen!"
echo ""
echo "  Logs:    tail -f $LOG_DIR/server.log"
echo "  Watcher: tail -f $LOG_DIR/watcher.log"
echo "  Status:  launchctl list | grep lehrercockpit"
echo "========================================"
