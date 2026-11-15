#!/usr/bin/env bash
# Remove application files; preserve case data and settings.
set -euo pipefail
INSTALL_DIR="${EVORA_INSTALL_DIR:-${XDG_DATA_HOME:-${HOME}/.local/share}/evora}"
BIN_DIR="${EVORA_BIN_DIR:-${HOME}/.local/bin}"
DESKTOP_DIR="${EVORA_APPLICATIONS_DIR:-${XDG_DATA_HOME:-${HOME}/.local/share}/applications}"
ICON_DIR="${EVORA_ICON_DIR:-${XDG_DATA_HOME:-${HOME}/.local/share}/icons/hicolor/256x256/apps}"
[[ -d "${INSTALL_DIR}" ]] || exit 0
exec 9>"${INSTALL_DIR}/.evora-session.lock"
if ! flock -n 9; then echo "Close EVORA before uninstalling." >&2; exit 1; fi
if [[ -x "${INSTALL_DIR}/evora-updater" ]]; then
  "${INSTALL_DIR}/evora-updater" --recover "${INSTALL_DIR}"
fi
if [[ ! -x "${INSTALL_DIR}/evora-updater" ]]; then
  echo "Reinstall EVORA before removing its program files." >&2
  exit 1
fi
"${INSTALL_DIR}/evora-updater" --uninstall "${INSTALL_DIR}"
if [[ -L "${BIN_DIR}/evora" && "$(readlink "${BIN_DIR}/evora")" == "${INSTALL_DIR}/evora" ]]; then
  rm -f -- "${BIN_DIR}/evora"
fi
rm -f -- "${DESKTOP_DIR}/evora.desktop" "${ICON_DIR}/evora.png"
echo "EVORA removed. Case data and settings were kept."
