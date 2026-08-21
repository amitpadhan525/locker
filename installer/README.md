# Locker Installer Suite (Linux & Windows 11)

This directory contains 1-click automated installer scripts for installing **Locker** natively on **Linux** (Ubuntu, Debian, Fedora, Arch) and **Windows 11**.

---

## 🐧 Linux 1-Click Installation

Open your terminal and run:

```bash
chmod +x installer/install.sh
./installer/install.sh
```

### What `install.sh` Does:
1. Validates Python 3 installation.
2. Creates an isolated Python virtualenv at `~/.local/share/locker/venv`.
3. Installs `cryptography` and `pyperclip` dependencies.
4. Registers executable command-line wrappers `locker` and `locker-gui` in `~/.local/bin/`.
5. Creates a native desktop application launcher (`locker-vault.desktop`).
6. Registers `.locker` and `.vault` MIME file associations for double-clicking.

---

## 🪟 Windows 11 1-Click Installation

### Option A: Double-Click Batch File
Double-click `install.bat` inside the `installer/` folder.

### Option B: PowerShell
Open PowerShell and run:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\installer\install.ps1
```

### What `install.ps1` Does:
1. Installs Locker app files to `%LOCALAPPDATA%\Locker\app`.
2. Sets up Python virtualenv at `%LOCALAPPDATA%\Locker\venv`.
3. Installs `cryptography` and `pyperclip` dependencies.
4. Creates executable batch launchers (`locker.bat` and `locker-gui.bat`) in `%LOCALAPPDATA%\Locker\bin` and adds them to User `PATH`.
5. Creates a Start Menu shortcut (`Locker Encrypted Vault`).
6. Registers `.locker` and `.vault` container file associations in Windows Registry (`HKCU:\Software\Classes`).

---

## 🧹 Uninstalling Locker

### Linux
```bash
chmod +x installer/uninstall.sh
./installer/uninstall.sh
```

### Windows 11 (PowerShell)
```powershell
.\installer\uninstall.ps1
```
