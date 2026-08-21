# ==============================================================================
# Locker Encrypted Vault - Windows 11 PowerShell Installer
# 100% Offline, Zero-Knowledge Storage Vault & Virtual Drive Mount
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "     Locker Encrypted Vault - Windows 11 Installer  " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. Test Python Availability
$pythonExe = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonExe) {
    $pythonExe = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $pythonExe) {
    Write-Host "Error: Python 3 was not found in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3 from https://www.python.org or Windows Store (check 'Add Python to PATH')."
    Exit 1
}

$pyCmd = $pythonExe.Source
Write-Host "[✓] Found Python at: $pyCmd" -ForegroundColor Green

# Determine paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Resolve-Path "$scriptDir\.."

$installDir = "$env:LOCALAPPDATA\Locker"
$binDir = "$installDir\bin"
$appDir = "$installDir\app"
$venvDir = "$installDir\venv"

Write-Host "[*] Installing Locker files to: $appDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
New-Item -ItemType Directory -Force -Path $binDir | Out-Null

Copy-Item "$repoDir\app.py" -Destination "$appDir\" -Force
Copy-Item "$repoDir\cli.py" -Destination "$appDir\" -Force
Copy-Item "$repoDir\vault_core.py" -Destination "$appDir\" -Force
if (Test-Path "$repoDir\assets") {
    Copy-Item "$repoDir\assets" -Destination "$appDir\" -Recurse -Force
}

# 2. Setup Virtual Environment
Write-Host "[*] Setting up Python virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path "$venvDir\Scripts\python.exe")) {
    & $pyCmd -m venv "$venvDir"
}

$venvPython = "$venvDir\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install cryptography pyperclip --quiet

Write-Host "[✓] Cryptographic dependencies installed successfully." -ForegroundColor Green

# 3. Create Windows Batch Launchers in bin/
$cliBat = "$binDir\locker.bat"
$guiBat = "$binDir\locker-gui.bat"

"@echo off`r`n""$venvPython"" ""$appDir\cli.py"" %*" | Out-File -Encoding ascii $cliBat
"@echo off`r`nstart /b "" ""$venvPython"" ""$appDir\app.py"" %*" | Out-File -Encoding ascii $guiBat

Write-Host "[✓] Batch launchers created:" -ForegroundColor Green
Write-Host "    - $cliBat"
Write-Host "    - $guiBat"

# 4. Update Windows User PATH Environment Variable
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    Write-Host "[*] Adding $binDir to User PATH environment variable..." -ForegroundColor Cyan
    $newPath = "$userPath;$binDir"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
}

# 5. Create Start Menu Shortcut
try {
    $startMenuDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
    $shortcutPath = "$startMenuDir\Locker Encrypted Vault.lnk"
    
    $wshell = New-Object -ComObject WScript.Shell
    $shortcut = $wshell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "$venvDir\Scripts\pythonw.exe"
    $shortcut.Arguments = """$appDir\app.py"""
    $shortcut.WorkingDirectory = "$appDir"
    $shortcut.Description = "Locker Encrypted Vault Application"
    $shortcut.Save()
    
    Write-Host "[✓] Created Windows Start Menu Shortcut: Locker Encrypted Vault" -ForegroundColor Green
} catch {
    Write-Host "Notice: Start Menu shortcut creation skipped ($($_.Exception.Message))" -ForegroundColor Yellow
}

# 6. Register Windows Registry File Association (.locker and .vault)
try {
    Write-Host "[*] Registering .locker and .vault file associations in Windows Registry..." -ForegroundColor Cyan
    
    $cmdVal = """$venvPython"" ""$appDir\app.py"" --vault ""%1"""
    
    New-Item -Path "HKCU:\Software\Classes\.locker" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\Classes\.locker" -Name "(default)" -Value "LockerVaultFile"
    
    New-Item -Path "HKCU:\Software\Classes\.vault" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\Classes\.vault" -Name "(default)" -Value "LockerVaultFile"
    
    New-Item -Path "HKCU:\Software\Classes\LockerVaultFile" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\Classes\LockerVaultFile" -Name "(default)" -Value "Locker Encrypted Vault Container"
    
    New-Item -Path "HKCU:\Software\Classes\LockerVaultFile\shell\open\command" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\Classes\LockerVaultFile\shell\open\command" -Name "(default)" -Value $cmdVal

    Write-Host "[✓] Registered Windows 11 .locker and .vault double-click associations." -ForegroundColor Green
} catch {
    Write-Host "Notice: Registry file association skipped ($($_.Exception.Message))" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "====================================================" -ForegroundColor Green
Write-Host "  Locker Windows 11 Installation Complete!          " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host "You can now run Locker via:"
Write-Host "  - Windows Start Menu: Search 'Locker Encrypted Vault'"
Write-Host "  - Command Prompt / PowerShell: locker status or locker-gui"
Write-Host "  - Double-click any .locker or .vault file directly!"
