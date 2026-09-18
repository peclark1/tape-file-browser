#!/usr/bin/env bash
set -euo pipefail

APP_ID="com.peclark.TapeFileBrowser"
BIN_PATH="${HOME}/.local/bin/tape-file-browser"
DESKTOP_PATH="${HOME}/.local/share/applications/${APP_ID}.desktop"

rm -f "${BIN_PATH}" "${DESKTOP_PATH}"

if command -v gsettings >/dev/null 2>&1; then
    python3 - "${APP_ID}.desktop" <<'PY' || true
import sys

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    desktop_id = sys.argv[1]
    settings = Gio.Settings.new("org.gnome.shell")
    favorites = [x for x in settings.get_strv("favorite-apps") if x != desktop_id]
    settings.set_strv("favorite-apps", favorites)
    Gio.Settings.sync()
except Exception:
    pass
PY
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${HOME}/.local/share/applications" >/dev/null 2>&1 || true
fi

echo "Tape File Browser removed."
