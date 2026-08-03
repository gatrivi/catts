# Install Kokoro ONNX TTS (fastkokoro) into repo .venv
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
. "$PSScriptRoot\_cache_env.ps1"

if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"

# Pocket requires NumPy 2+, while Numba/FastKokoro require NumPy <2.5.
& $py -m pip install "numpy>=2,<2.5" "fastkokoro[cpu]" --no-cache-dir

Write-Host ""
Write-Host "Kokoro ONNX (fastkokoro) ready."
Write-Host "Start server:  .\scripts\start_kokoro.ps1"
Write-Host "CATTS .env:    CATTS_TTS_ENGINE=kokoro  CATTS_KOKORO_URL=http://127.0.0.1:8880"
Write-Host "Bonus DirectML: stop servers, pip install onnxruntime-directml, set FASTKOKORO_ONNX_AUTO_PROVIDERS=true"
