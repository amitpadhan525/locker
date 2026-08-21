#!/usr/bin/env bash
# Locker Uninstaller for Linux

set -e

INSTALL_DIR="${HOME}/.local/share/locker"
BIN_DIR="${HOME}/.local/bin"
APPS_DIR="${HOME}/.local/share/applications"
MIME_DIR="${HOME}/.local/share/mime/packages"

echo "Uninstalling Locker Encrypted Vault..."

rm -rf "${INSTALL_DIR}"
rm -f "${BIN_DIR}/locker"
rm -f "${BIN_DIR}/locker-gui"
rm -f "${APPS_DIR}/locker-vault.desktop"
rm -f "${MIME_DIR}/application-x-locker.xml"

if command -v update-mime-database &> /dev/null; then
    update-mime-database "${HOME}/.local/share/mime" &> /dev/null || true
fi

echo "Locker has been cleanly uninstalled from your Linux workstation."
