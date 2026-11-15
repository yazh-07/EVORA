#!/usr/bin/env bash
# Install a Linux release without replacing case data or settings.
set -euo pipefail
INSTALL_DIR="${EVORA_INSTALL_DIR:-${XDG_DATA_HOME:-${HOME}/.local/share}/evora}"
BIN_DIR="${EVORA_BIN_DIR:-${HOME}/.local/bin}"
DESKTOP_DIR="${EVORA_APPLICATIONS_DIR:-${XDG_DATA_HOME:-${HOME}/.local/share}/applications}"
ICON_DIR="${EVORA_ICON_DIR:-${XDG_DATA_HOME:-${HOME}/.local/share}/icons/hicolor/256x256/apps}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/evora-install.json" && -x "${SCRIPT_DIR}/backend/evora" ]]; then
  DIST_DIR="${SCRIPT_DIR}"
else
  DIST_DIR="${SCRIPT_DIR}/../dist/linux/evora"
fi
if [[ ! -f "${DIST_DIR}/evora-install.json" || ! -x "${DIST_DIR}/evora-updater" ]]; then
  echo "Extract the Linux release and run install.sh from that folder." >&2
  exit 1
fi
mkdir -p "${INSTALL_DIR}" "${BIN_DIR}" "${DESKTOP_DIR}" "${ICON_DIR}"
INSTALL_DIR="$(cd "${INSTALL_DIR}" && pwd -P)"
DIST_DIR="$(cd "${DIST_DIR}" && pwd -P)"
if [[ "${INSTALL_DIR}" == "${DIST_DIR}" ]]; then
  echo "Extract the release outside the installation folder." >&2
  exit 1
fi
exec 9>"${INSTALL_DIR}/.evora-session.lock"
if ! flock -n 9; then echo "Close EVORA before installing." >&2; exit 1; fi
if [[ -x "${INSTALL_DIR}/evora-updater" ]]; then
  "${INSTALL_DIR}/evora-updater" --recover "${INSTALL_DIR}"
fi
if [[ -L "${INSTALL_DIR}/backend" ]] || [[ -d "${INSTALL_DIR}/backend" && -n "$(find "${INSTALL_DIR}/backend" -type l -print -quit)" ]]; then
  echo "The backend folder contains links. Choose a separate installation folder." >&2
  exit 1
fi
# Copy only program paths. Legacy evora_data and other local folders stay put.
cp -a --remove-destination "${DIST_DIR}/backend" "${INSTALL_DIR}/"
for name in evora evora-updater icon.png install.sh uninstall.sh; do
  cp -a --remove-destination "${DIST_DIR}/${name}" "${INSTALL_DIR}/${name}"
done
cp --remove-destination "${DIST_DIR}/evora-install.json" "${INSTALL_DIR}/evora-install.json"
ln -sfn "${INSTALL_DIR}/evora" "${BIN_DIR}/evora"
cp "${INSTALL_DIR}/icon.png" "${ICON_DIR}/evora.png"
desktop_exec="${INSTALL_DIR//\\/\\\\}"
desktop_exec="${desktop_exec//\"/\\\"}"
desktop_exec="${desktop_exec//\$/\\\$}"
desktop_exec="${desktop_exec//\`/\\\`}"
desktop_exec="${desktop_exec//%/%%}"
cat > "${DESKTOP_DIR}/evora.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=EVORA
Exec="${desktop_exec}/evora"
Icon=evora
Terminal=false
Categories=Security;Science;
StartupNotify=true
EOF
chmod 755 "${DESKTOP_DIR}/evora.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${DESKTOP_DIR}" || true
fi
echo "EVORA installed. Open it from your applications menu or run evora."
