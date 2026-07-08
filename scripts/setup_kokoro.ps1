# Install Kokoro TTS deps into repo .venv
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"

& $py -m pip install kokoro soundfile --no-cache-dir

Write-Host ""
Write-Host "Kokoro deps ready."
Write-Host "Start server:  .\scripts\start_kokoro.ps1"
Write-Host "CATTS .env:    CATTS_TTS_ENGINE=kokoro  CATTS_KOKORO_URL=http://127.0.0.1:8880"
