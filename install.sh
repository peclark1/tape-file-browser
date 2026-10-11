#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="com.peclark.TapeFileBrowser"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
BIN_PATH="${BIN_DIR}/tape-file-browser"
TOOL_PATH="${BIN_DIR}/tape-tool"
DASD_TOOL_PATH="${BIN_DIR}/as400-dasd"
FORMAT_MODULE_PATH="${BIN_DIR}/tape_formats.py"
TEXT_MODULE_PATH="${BIN_DIR}/tape_text.py"
DASD_MODULE_PATH="${BIN_DIR}/as400_dasd.py"
GUIDED_MODULE_PATH="${BIN_DIR}/as400_5250.py"
CMD_MODULE_PATH="${BIN_DIR}/as400_cmd.py"
CONFIG_MODULE_PATH="${BIN_DIR}/as400_config.py"
OBJECT_TYPE_MODULE_PATH="${BIN_DIR}/as400_object_types.py"
CAPABILITIES_MODULE_PATH="${BIN_DIR}/as400_capabilities.py"
PROGRAMS_MODULE_PATH="${BIN_DIR}/as400_programs.py"
LIBRARIES_MODULE_PATH="${BIN_DIR}/as400_libraries.py"
REFERENCE_CODES_MODULE_PATH="${BIN_DIR}/as400_reference_codes.py"
AFP_MODULE_PATH="${BIN_DIR}/as400_afp.py"
OUTQ_MODULE_PATH="${BIN_DIR}/as400_outq.py"
INTPRF_MODULE_PATH="${BIN_DIR}/as400_internal_profiles.py"
SBSD_MODULE_PATH="${BIN_DIR}/as400_subsystems.py"
LDA_MODULE_PATH="${BIN_DIR}/as400_local_data.py"
SPLCB_MODULE_PATH="${BIN_DIR}/as400_spool_controls.py"
JMQ_MODULE_PATH="${BIN_DIR}/as400_jmq.py"
PNLGRP_MODULE_PATH="${BIN_DIR}/as400_panel_groups.py"
EDTD_MODULE_PATH="${BIN_DIR}/as400_edit_descriptions.py"
PRTQ_MODULE_PATH="${BIN_DIR}/as400_printer_queues.py"
ALRTBL_MODULE_PATH="${BIN_DIR}/as400_alert_tables.py"
PRDDFN_MODULE_PATH="${BIN_DIR}/as400_product_definitions.py"
ARCHIDX_MODULE_PATH="${BIN_DIR}/as400_archival_indexes.py"
MESSAGE_QUEUES_MODULE_PATH="${BIN_DIR}/as400_message_queues.py"
JOBS_MODULE_PATH="${BIN_DIR}/as400_jobs.py"
DIRECTORY_MODULE_PATH="${BIN_DIR}/as400_directory.py"
MENUS_MODULE_PATH="${BIN_DIR}/as400_menus.py"
CONNECTIONS_MODULE_PATH="${BIN_DIR}/as400_connections.py"
INDEXES_MODULE_PATH="${BIN_DIR}/as400_indexes.py"
MESSAGES_MODULE_PATH="${BIN_DIR}/as400_messages.py"
RECORDS_MODULE_PATH="${BIN_DIR}/as400_records.py"
ANCHORS_MODULE_PATH="${BIN_DIR}/as400_anchors.py"
EXTERNAL_TYPE_PATH="${BIN_DIR}/as400_external_types.tsv"
INTERNAL_TYPE_PATH="${BIN_DIR}/as400_internal_types.tsv"
DATA_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/tape-file-browser"
LIBRARY_CATALOG_PATH="${DATA_DIR}/as400_libraries.json"
DESKTOP_PATH="${APP_DIR}/${APP_ID}.desktop"
PIN=true
TEXT_MODE_ONLY=false

for arg in "$@"; do
    case "$arg" in
        --no-pin)
            PIN=false
            ;;
        --text-mode|--headless)
            TEXT_MODE_ONLY=true
            PIN=false
            ;;
        -h|--help)
            cat <<'EOF'
Usage: bash install.sh [--text-mode] [--no-pin]

  --text-mode  Install the command-line interface (CLI), curses text user
               interface (TUI), shared tape core, and AS/400 DASD explorer.
               No GTK/X components, desktop launcher, or GNOME integration
               are installed.
  --headless   Compatibility alias for --text-mode.
  --no-pin     Install the GTK4 graphical interface (GUI) but do not pin it to
               the GNOME dock.
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

mkdir -p "${BIN_DIR}" "${DATA_DIR}"
install -m 0755 "${SCRIPT_DIR}/tape_tool.py" "${TOOL_PATH}"
install -m 0755 "${SCRIPT_DIR}/as400_dasd_tool.py" "${DASD_TOOL_PATH}"
install -m 0644 "${SCRIPT_DIR}/tape_formats.py" "${FORMAT_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/tape_text.py" "${TEXT_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_dasd.py" "${DASD_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_5250.py" "${GUIDED_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_cmd.py" "${CMD_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_config.py" "${CONFIG_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_object_types.py" "${OBJECT_TYPE_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_capabilities.py" "${CAPABILITIES_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_programs.py" "${PROGRAMS_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_libraries.py" "${LIBRARIES_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_reference_codes.py" "${REFERENCE_CODES_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_afp.py" "${AFP_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_outq.py" "${OUTQ_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_internal_profiles.py" "${INTPRF_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_subsystems.py" "${SBSD_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_local_data.py" "${LDA_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_spool_controls.py" "${SPLCB_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_jmq.py" "${JMQ_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_panel_groups.py" "${PNLGRP_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_edit_descriptions.py" "${EDTD_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_printer_queues.py" "${PRTQ_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_alert_tables.py" "${ALRTBL_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_product_definitions.py" "${PRDDFN_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_archival_indexes.py" "${ARCHIDX_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_message_queues.py" "${MESSAGE_QUEUES_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_jobs.py" "${JOBS_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_directory.py" "${DIRECTORY_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_menus.py" "${MENUS_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_connections.py" "${CONNECTIONS_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_indexes.py" "${INDEXES_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_messages.py" "${MESSAGES_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_records.py" "${RECORDS_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_anchors.py" "${ANCHORS_MODULE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_external_types.tsv" "${EXTERNAL_TYPE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_internal_types.tsv" "${INTERNAL_TYPE_PATH}"
install -m 0644 "${SCRIPT_DIR}/as400_libraries.json" "${LIBRARY_CATALOG_PATH}"

if ! ${TEXT_MODE_ONLY}; then
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
echo "Installed tape-tool and as400-dasd."
echo "Tape CLI/TUI:  ${TOOL_PATH}"
echo "DASD explorer: ${DASD_TOOL_PATH}"
echo "Tape core:     ${FORMAT_MODULE_PATH}"
echo "Text helpers:  ${TEXT_MODULE_PATH}"
echo "DASD core:     ${DASD_MODULE_PATH}"
echo "Guided 5250:   ${GUIDED_MODULE_PATH}"
echo "CMD evidence:  ${CMD_MODULE_PATH}"
echo "Object types:   ${OBJECT_TYPE_MODULE_PATH}"
echo "IBM catalogs:   ${EXTERNAL_TYPE_PATH}, ${INTERNAL_TYPE_PATH}"
echo "DASD catalog:  ${LIBRARY_CATALOG_PATH}"

if ${TEXT_MODE_ONLY}; then
    echo
    echo "Text-mode installation complete; GTK/X components were skipped."
    echo "Tape CLI: tape-tool --help"
    echo "Tape TUI: tape-tool browse"
    echo "DASD CLI: as400-dasd --help"
    echo "DASD TUI: as400-dasd browse"
    echo "Guided TUI: as400-dasd browse5250"
else
    echo "GTK4 GUI:      ${BIN_PATH}"
    echo "Launcher:      ${DESKTOP_PATH}"
    echo
    if ! ${PIN}; then
        echo "Dock pinning was skipped."
    fi
    echo "You can launch the GUI from the application menu as 'Tape File Browser'."
fi
