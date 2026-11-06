#!/usr/bin/env bash
# EVORA Linux Workstation Installer
# Installs standalone EVORA desktop application and registers desktop launcher.

set -euo pipefail

INSTALL_DIR="${HOME}/.local/share/evora"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "============================================================"
echo "  EVORA — Forensic Evidence Fusion Workstation Installer"
echo "============================================================"

# Check for compiled bundle
DIST_DIR="${REPO_DIR}/dist/evora"
if [ ! -d "${DIST_DIR}" ]; then
  echo "Error: Compiled distribution not found at ${DIST_DIR}."
  echo "Please build the package first using PyInstaller."
  exit 1
fi

echo "Installing EVORA to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
rm -rf "${INSTALL_DIR:?}"/*
cp -r "${DIST_DIR}"/* "${INSTALL_DIR}/"
chmod +x "${INSTALL_DIR}/evora"

echo "Creating launcher symlink in ${BIN_DIR}..."
mkdir -p "${BIN_DIR}"
ln -sf "${INSTALL_DIR}/evora" "${BIN_DIR}/evora"

echo "Installing application icons..."
mkdir -p "${ICON_DIR}"
if [ -f "${REPO_DIR}/desktop/icon.png" ]; then
  cp "${REPO_DIR}/desktop/icon.png" "${ICON_DIR}/evora.png"
fi

echo "Creating desktop application entry..."
mkdir -p "${DESKTOP_DIR}"
cat << EOF > "${DESKTOP_DIR}/evora.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=EVORA
GenericName=Forensic Evidence Fusion Workstation
Comment=Offline multi-modal forensic analysis, knowledge graph projection, and AI evidence synthesis.
Exec=${INSTALL_DIR}/evora
Icon=evora
Terminal=false
Categories=Security;Development;Science;Utility;
StartupNotify=true
EOF

chmod +x "${DESKTOP_DIR}/evora.desktop"

# Refresh desktop launcher database if available
if command -v update-desktop-database > /dev/null 2>&1; then
  update-desktop-database "${DESKTOP_DIR}" || true
fi

echo "============================================================"
echo "  Installation Complete!"
echo "  - Command line : evora"
echo "  - Desktop app  : Search 'EVORA' in your applications menu"
echo "  - Installation : ${INSTALL_DIR}"
echo "============================================================"
