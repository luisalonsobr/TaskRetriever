#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$(command -v python3)"
LABEL="com.hardlou.whatsapp-task-manager.watch"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_OUT="/tmp/whatsapp-tasks.log"
LOG_ERR="/tmp/whatsapp-tasks.err.log"
APP_DIR="$HOME/Applications/WhatsApp Task Manager.app"
ICON_SRC="${PROJECT_DIR}/icons/install.png"
ICON_FILE="app-icon.icns"

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3 not found in PATH"
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/Applications"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${PROJECT_DIR}/main.py</string>
    <string>watch</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${PROJECT_DIR}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_OUT}</string>
  <key>StandardErrorPath</key>
  <string>${LOG_ERR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl enable "gui/$(id -u)/${LABEL}"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"

mkdir -p "${APP_DIR}/Contents/MacOS"
mkdir -p "${APP_DIR}/Contents/Resources"

if command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1 && [[ -f "${ICON_SRC}" ]]; then
  ICONSET_BASE="$(mktemp -d "/tmp/whatsapp-task-icon.XXXXXX")"
  ICONSET_DIR="${ICONSET_BASE}/app.iconset"
  mkdir -p "${ICONSET_DIR}"

  sips -z 16 16 "${ICON_SRC}" --out "${ICONSET_DIR}/icon_16x16.png" >/dev/null
  sips -z 32 32 "${ICON_SRC}" --out "${ICONSET_DIR}/icon_16x16@2x.png" >/dev/null
  sips -z 32 32 "${ICON_SRC}" --out "${ICONSET_DIR}/icon_32x32.png" >/dev/null
  sips -z 64 64 "${ICON_SRC}" --out "${ICONSET_DIR}/icon_32x32@2x.png" >/dev/null
  sips -z 128 128 "${ICON_SRC}" --out "${ICONSET_DIR}/icon_128x128.png" >/dev/null
  sips -z 256 256 "${ICON_SRC}" --out "${ICONSET_DIR}/icon_128x128@2x.png" >/dev/null
  sips -z 256 256 "${ICON_SRC}" --out "${ICONSET_DIR}/icon_256x256.png" >/dev/null
  sips -z 512 512 "${ICON_SRC}" --out "${ICONSET_DIR}/icon_256x256@2x.png" >/dev/null
  sips -z 512 512 "${ICON_SRC}" --out "${ICONSET_DIR}/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "${ICON_SRC}" --out "${ICONSET_DIR}/icon_512x512@2x.png" >/dev/null

  iconutil -c icns "${ICONSET_DIR}" -o "${APP_DIR}/Contents/Resources/${ICON_FILE}"
  rm -rf "${ICONSET_BASE}"
else
  echo "⚠️ Skipping GUI icon generation: missing tools (sips/iconutil) or ${ICON_SRC} not found."
fi

cat > "${APP_DIR}/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDisplayName</key>
  <string>WhatsApp Task Manager</string>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>CFBundleIdentifier</key>
  <string>com.hardlou.whatsapp-task-manager.gui</string>
  <key>CFBundleName</key>
  <string>WhatsApp Task Manager</string>
  <key>CFBundleIconFile</key>
  <string>${ICON_FILE}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSUIElement</key>
  <false/>
</dict>
</plist>
EOF

cat > "${APP_DIR}/Contents/MacOS/launcher" <<EOF
#!/bin/bash
exec "${PYTHON_BIN}" "${PROJECT_DIR}/main.py" gui "\$@"
EOF
chmod +x "${APP_DIR}/Contents/MacOS/launcher"

echo "Installed LaunchAgent: ${PLIST_PATH}"
echo "GUI app created: ${APP_DIR}"
echo "Background watch is active now and will auto-start at login."
echo "Open GUI from Finder/Spotlight: WhatsApp Task Manager"
