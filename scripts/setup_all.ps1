# Full local AI stack install (run one at a time; close other apps on 16GB RAM)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"

Write-Host "=== XTTS (voice clone) ==="
& "$PSScriptRoot\setup_xtts.ps1"
Write-Host "=== STT + translate ==="
& "$PSScriptRoot\setup_stt.ps1"
Write-Host "=== Main API deps ==="
& $py -m pip install -r requirements.txt --no-cache-dir
Write-Host "Done. Start: .\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 59200"
