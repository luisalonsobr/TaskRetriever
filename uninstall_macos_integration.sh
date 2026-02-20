#!/bin/bash
set -euo pipefail

LABEL="com.hardlou.whatsapp-task-manager.watch"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"
APP_DIR="$HOME/Applications/WhatsApp Task Manager.app"

launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"
rm -rf "$APP_DIR"

echo "Removed LaunchAgent and GUI app launcher."
