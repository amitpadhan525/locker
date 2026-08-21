@echo off
:: Locker Encrypted Vault Windows Installer Batch Launcher
title Locker Encrypted Vault Installer

echo Launching Locker PowerShell Installer...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"

pause
