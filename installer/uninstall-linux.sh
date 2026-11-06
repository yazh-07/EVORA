#!/usr/bin/env bash
# EVORA Linux Workstation Uninstaller

set -euo pipefail

INSTALL_DIR="${HOME}/.local/share/evora"
BIN_LINK="${HOME}/.local/bin/evora"
DESKTOP_ENTRY="${HOME}/.local/share/applications/evora.desktop"
ICON_FILE="${HOME}/.local/share/icons/hicolor/256x256/apps/evora.png"

echo "Uninstalling EVORA Workstation..."

rm -rf "${INSTALL_DIR}"
rm -f "${BIN_LINK}"
rm -f "${DESKTOP_ENTRY}"
rm -f "${ICON_FILE}"

if command -v update-desktop-database > /dev/null 2>&1; then
  update-desktop-database "${HOME}/.local/share/applications" || true
fi

echo "EVORA has been successfully uninstalled from your user environment."
