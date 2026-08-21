# Locker Uninstaller for Windows 11

$installDir = "$env:LOCALAPPDATA\Locker"
$startShortcut = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Locker Encrypted Vault.lnk"

Write-Host "Uninstalling Locker Encrypted Vault..." -ForegroundColor Cyan

if (Test-Path $installDir) {
    Remove-Item -Path $installDir -Recurse -Force
}

if (Test-Path $startShortcut) {
    Remove-Item -Path $startShortcut -Force
}

try {
    Remove-Item -Path "HKCU:\Software\Classes\.locker" -Recurse -ErrorAction SilentlyContinue
    Remove-Item -Path "HKCU:\Software\Classes\.vault" -Recurse -ErrorAction SilentlyContinue
    Remove-Item -Path "HKCU:\Software\Classes\LockerVaultFile" -Recurse -ErrorAction SilentlyContinue
} catch {}

Write-Host "Locker has been cleanly uninstalled from Windows 11." -ForegroundColor Green
