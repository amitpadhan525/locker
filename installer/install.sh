#!/usr/bin/env bash
# ==============================================================================
# Locker Encrypted Vault - Linux Installer Script
# 100% Offline, Zero-Knowledge Storage Vault & Virtual Drive Mount
# ==============================================================================

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}     Locker Encrypted Vault - Linux Installer       ${NC}"
echo -e "${CYAN}====================================================${NC}"

# 1. Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed on this system.${NC}"
    echo "Please install Python 3 (e.g., sudo apt install python3 python3-pip python3-venv python3-tk)"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}[✓] Found ${PYTHON_VERSION}${NC}"

# Determine repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

INSTALL_DIR="${HOME}/.local/share/locker"
BIN_DIR="${HOME}/.local/bin"
APPS_DIR="${HOME}/.local/share/applications"
MIME_DIR="${HOME}/.local/share/mime/packages"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

mkdir -p "${INSTALL_DIR}" "${BIN_DIR}" "${APPS_DIR}" "${MIME_DIR}" "${ICON_DIR}"

echo -e "${CYAN}[*] Installing Locker files to ${INSTALL_DIR}...${NC}"

# Copy application files
cp "${REPO_DIR}/app.py" "${INSTALL_DIR}/"
cp "${REPO_DIR}/cli.py" "${INSTALL_DIR}/"
cp "${REPO_DIR}/vault_core.py" "${INSTALL_DIR}/"
cp -r "${REPO_DIR}/assets" "${INSTALL_DIR}/"

# Copy Icon
if [ -f "${REPO_DIR}/assets/locker-banner.svg" ]; then
    cp "${REPO_DIR}/assets/locker-banner.svg" "${ICON_DIR}/locker.svg"
fi

# 2. Setup Virtual Environment
VENV_DIR="${INSTALL_DIR}/venv"
echo -e "${CYAN}[*] Setting up Python virtual environment at ${VENV_DIR}...${NC}"
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip --quiet
"${VENV_DIR}/bin/pip" install cryptography pyperclip --quiet

echo -e "${GREEN}[✓] Cryptographic dependencies installed successfully.${NC}"

# 3. Create Terminal Wrapper Scripts
# locker-gui (Desktop GUI)
cat << 'EOF' > "${BIN_DIR}/locker-gui"
#!/usr/bin/env bash
LOCKER_DIR="${HOME}/.local/share/locker"
exec "${LOCKER_DIR}/venv/bin/python3" "${LOCKER_DIR}/app.py" "$@"
EOF
chmod +x "${BIN_DIR}/locker-gui"

# locker (CLI)
cat << 'EOF' > "${BIN_DIR}/locker"
#!/usr/bin/env bash
LOCKER_DIR="${HOME}/.local/share/locker"
exec "${LOCKER_DIR}/venv/bin/python3" "${LOCKER_DIR}/cli.py" "$@"
EOF
chmod +x "${BIN_DIR}/locker"

echo -e "${GREEN}[✓] Executable wrappers created at:${NC}"
echo "    - ${BIN_DIR}/locker (CLI)"
echo "    - ${BIN_DIR}/locker-gui (Desktop Application)"

# 4. Register Desktop Launcher (.desktop file)
DESKTOP_FILE="${APPS_DIR}/locker-vault.desktop"
cat << EOF > "${DESKTOP_FILE}"
[Desktop Entry]
Name=Locker Encrypted Vault
Comment=100% Offline Zero-Knowledge Storage Container & Drive Mount
Exec=${BIN_DIR}/locker-gui %f
Icon=locker
Terminal=false
Type=Application
MimeType=application/x-locker;application/x-vault;
Categories=Utility;Security;
Keywords=encryption;vault;security;privacy;passwords;
EOF
chmod +x "${DESKTOP_FILE}"

# 5. Register MIME Type for .locker and .vault files
MIME_XML="${MIME_DIR}/application-x-locker.xml"
cat << 'EOF' > "${MIME_XML}"
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-locker">
    <comment>Locker Encrypted Vault</comment>
    <glob pattern="*.locker"/>
    <glob pattern="*.vault"/>
  </mime-type>
</mime-info>
EOF

# Update mime database & desktop database
if command -v update-mime-database &> /dev/null; then
    update-mime-database "${HOME}/.local/share/mime" &> /dev/null || true
fi

if command -v xdg-mime &> /dev/null; then
    xdg-mime default locker-vault.desktop application/x-locker &> /dev/null || true
    xdg-mime default locker-vault.desktop application/x-vault &> /dev/null || true
fi

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "${APPS_DIR}" &> /dev/null || true
fi

echo -e "${GREEN}[✓] Registered OS Desktop entry & .locker / .vault file associations.${NC}"

# Check PATH
if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
    echo -e "${YELLOW}[!] Notice: ${BIN_DIR} is not in your current PATH.${NC}"
    echo "Add this line to your ~/.bashrc or ~/.zshrc file:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}  Locker Installation Complete!                      ${NC}"
echo -e "${GREEN}====================================================${NC}"
echo "You can now run:"
echo "  - locker-gui        (Launch Desktop GUI)"
echo "  - locker status    (Check CLI status)"
echo "  - Double-click any .locker or .vault file to open!"
