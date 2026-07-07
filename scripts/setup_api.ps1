# Install CATTS API/book dependencies into the repo virtual environment.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"

& $py -m pip install -r requirements.txt --no-cache-dir

Write-Host "API deps ready. Start: .\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 59200"
