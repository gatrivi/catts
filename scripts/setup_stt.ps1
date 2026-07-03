$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { py -3 -m venv .venv }
$py = ".\.venv\Scripts\python.exe"

Write-Host "Installing faster-whisper (no pip cache to save RAM)..."
& $py -m pip install faster-whisper --no-cache-dir
Write-Host "Installing argostranslate..."
& $py -m pip install argostranslate --no-cache-dir
Write-Host "Installing Argos EN-ES language packs..."
& $py scripts\install_argos_packages.py
Write-Host "STT + translate ready. Restart CATTS API."
