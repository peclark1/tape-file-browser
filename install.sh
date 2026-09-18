#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="com.peclark.TapeFileBrowser"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
BIN_PATH="${BIN_DIR}/tape-file-browser"
DESKTOP_PATH="${APP_DIR}/${APP_ID}.desktop"
PIN=true

if [[ "${1:-}" == "--no-pin" ]]; then
    PIN=false
fi

mkdir -p "${BIN_DIR}" "${APP_DIR}"
install -m 0755 "${SCRIPT_DIR}/tape-file-browser.py" "${BIN_PATH}"

sed "s|@EXEC@|${BIN_PATH}|g" \
    "${SCRIPT_DIR}/${APP_ID}.desktop" > "${DESKTOP_PATH}"
chmod 0644 "${DESKTOP_PATH}"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi

if ${PIN} && command -v gsettings >/dev/null 2>&1; then
    python3 - "${APP_ID}.desktop" <<'PY' || true
import sys

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    desktop_id = sys.argv[1]
    settings = Gio.Settings.new("org.gnome.shell")
    favorites = list(settings.get_strv("favorite-apps"))
    if desktop_id not in favorites:
        favorites.append(desktop_id)
        settings.set_strv("favorite-apps", favorites)
        Gio.Settings.sync()
        print("Pinned Tape File Browser to the GNOME/Ubuntu dock.")
    else:
        print("Tape File Browser is already pinned to the GNOME/Ubuntu dock.")
except Exception as exc:
    print(f"Could not automatically pin the launcher: {exc}")
PY
fi

echo
echo "Installed Tape File Browser."
echo "Executable: ${BIN_PATH}"
echo "Launcher:   ${DESKTOP_PATH}"
echo
if ! ${PIN}; then
    echo "Dock pinning was skipped (--no-pin)."
fi
echo "You can also launch it from the application menu as 'Tape File Browser'."
