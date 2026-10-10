#!/usr/bin/env bash
set -euo pipefail

APP_ID="com.peclark.TapeFileBrowser"
BIN_PATH="${HOME}/.local/bin/tape-file-browser"
TOOL_PATH="${HOME}/.local/bin/tape-tool"
DASD_TOOL_PATH="${HOME}/.local/bin/as400-dasd"
FORMAT_MODULE_PATH="${HOME}/.local/bin/tape_formats.py"
TEXT_MODULE_PATH="${HOME}/.local/bin/tape_text.py"
DASD_MODULE_PATH="${HOME}/.local/bin/as400_dasd.py"
GUIDED_MODULE_PATH="${HOME}/.local/bin/as400_5250.py"
CMD_MODULE_PATH="${HOME}/.local/bin/as400_cmd.py"
CONFIG_MODULE_PATH="${HOME}/.local/bin/as400_config.py"
OBJECT_TYPE_MODULE_PATH="${HOME}/.local/bin/as400_object_types.py"
CAPABILITIES_MODULE_PATH="${HOME}/.local/bin/as400_capabilities.py"
PROGRAMS_MODULE_PATH="${HOME}/.local/bin/as400_programs.py"
LIBRARIES_MODULE_PATH="${HOME}/.local/bin/as400_libraries.py"
REFERENCE_CODES_MODULE_PATH="${HOME}/.local/bin/as400_reference_codes.py"
MESSAGE_QUEUES_MODULE_PATH="${HOME}/.local/bin/as400_message_queues.py"
JOBS_MODULE_PATH="${HOME}/.local/bin/as400_jobs.py"
DIRECTORY_MODULE_PATH="${HOME}/.local/bin/as400_directory.py"
MENUS_MODULE_PATH="${HOME}/.local/bin/as400_menus.py"
CONNECTIONS_MODULE_PATH="${HOME}/.local/bin/as400_connections.py"
INDEXES_MODULE_PATH="${HOME}/.local/bin/as400_indexes.py"
MESSAGES_MODULE_PATH="${HOME}/.local/bin/as400_messages.py"
RECORDS_MODULE_PATH="${HOME}/.local/bin/as400_records.py"
ANCHORS_MODULE_PATH="${HOME}/.local/bin/as400_anchors.py"
EXTERNAL_TYPE_PATH="${HOME}/.local/bin/as400_external_types.tsv"
INTERNAL_TYPE_PATH="${HOME}/.local/bin/as400_internal_types.tsv"
DESKTOP_PATH="${HOME}/.local/share/applications/${APP_ID}.desktop"

rm -f \
    "${BIN_PATH}" \
    "${TOOL_PATH}" \
    "${DASD_TOOL_PATH}" \
    "${FORMAT_MODULE_PATH}" \
    "${TEXT_MODULE_PATH}" \
    "${DASD_MODULE_PATH}" \
    "${GUIDED_MODULE_PATH}" \
    "${CMD_MODULE_PATH}" \
    "${CONFIG_MODULE_PATH}" \
    "${OBJECT_TYPE_MODULE_PATH}" \
    "${CAPABILITIES_MODULE_PATH}" \
    "${PROGRAMS_MODULE_PATH}" "${MESSAGE_QUEUES_MODULE_PATH}" "${JOBS_MODULE_PATH}" "${DIRECTORY_MODULE_PATH}" "${MENUS_MODULE_PATH}" "${CONNECTIONS_MODULE_PATH}" "${INDEXES_MODULE_PATH}" "${MESSAGES_MODULE_PATH}" "${RECORDS_MODULE_PATH}" \
    "${LIBRARIES_MODULE_PATH}" \
    "${REFERENCE_CODES_MODULE_PATH}" \
    "${ANCHORS_MODULE_PATH}" \
    "${EXTERNAL_TYPE_PATH}" \
    "${INTERNAL_TYPE_PATH}" \
    "${DESKTOP_PATH}"

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

echo "Tape File Browser and AS/400 DASD tools removed."
