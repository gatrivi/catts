# Start local Kokoro OpenAI-compatible server on :8880
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Run .\scripts\setup_kokoro.ps1 first"
    exit 1
}

Write-Host "Starting Kokoro on http://127.0.0.1:8880 (first synth may download model)"
& $py scripts\kokoro_server.py
