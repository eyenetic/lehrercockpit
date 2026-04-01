#!/bin/zsh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display alert "Python 3 fehlt" message "Bitte zuerst Python 3 installieren, damit der Cockpit Agent gestartet werden kann." as critical'
  exit 1
fi

python3 agent_server.py --mode mac
