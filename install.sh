#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="com.peclark.TapeFileBrowser"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
BIN_PATH="${BIN_DIR}/tape-file-browser"
TOOL_PATH="${BIN_DIR}/tape-tool"
FORMAT_MODULE_PATH="${BIN_DIR}/tape_formats.py"
TEXT_MODULE_PATH="${BIN_DIR}/tape_text.py"
DESKTOP_PATH="${APP_DIR}/${APP_ID}.desktop"
PIN=true
HEADLESS=false

for arg in "$@"; do
    case "$arg" in
        --no-pin)
            PIN=false
            ;;
        --headless)
            HEADLESS=true
            PIN=false
            ;;
        -h|--help)
            cat <<'EOF'
Usage: bash install.sh [--headless] [--no-pin]

  --headless  Install only tape-tool and the shared tape core. No GTK/X
              components, desktop launcher, or GNOME integration are installed.
  --no-pin    Install the GTK application but do not pin it to the GNOME dock.
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

mkdir -p "${BIN_DIR}"
install -m 0755 "${SCRIPT_DIR}/tape_tool.py" "${TOOL_PATH}"
install -m 0644 "${SCRIPT_DIR}/tape_formats.py" "${FORMAT_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/tape_text.py" "${TEXT_MODULE_PATH}"

if ! ${HEADLESS}; then
    mkdir -p "${APP_DIR}"
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
fi

echo
echo "Installed tape-tool."
echo "Executable:   ${TOOL_PATH}"
echo "Format core:  ${FORMAT_MODULE_PATH}"
echo "Text helpers: ${TEXT_MODULE_PATH}"

if ${HEADLESS}; then
    echo
    echo "Headless installation complete; GTK/X components were skipped."
    echo "Try: tape-tool --help"
else
    echo "GTK browser:  ${BIN_PATH}"
    echo "Launcher:     ${DESKTOP_PATH}"
    echo
    if ! ${PIN}; then
        echo "Dock pinning was skipped."
    fi
    echo "You can launch the GUI from the application menu as 'Tape File Browser'."
fi
