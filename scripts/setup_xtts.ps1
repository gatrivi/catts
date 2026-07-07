# One-time: CPU voice clone (Coqui XTTS) in isolated .venv
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { python -m venv .venv }

$py = ".\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
& $py -m pip install numpy coqui-tts "transformers==4.48.2"

Write-Host "Testing import..."
& $py -c "from TTS.api import TTS; print('XTTS OK')"
Write-Host "Done. Restart CATTS API; header should show tts_engine=xtts"
