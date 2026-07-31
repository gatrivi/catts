# Start Kokoro ONNX (fastkokoro) OpenAI-compatible server on :8880
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
. "$PSScriptRoot\_cache_env.ps1"

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Run .\scripts\setup_kokoro.ps1 first"
    exit 1
}

$exe = ".\.venv\Scripts\fastkokoro.exe"
if (-not (Test-Path $exe)) {
    Write-Host "Run .\scripts\setup_kokoro.ps1 first"
    exit 1
}

$env:FASTKOKORO_HOST = "127.0.0.1"
$env:FASTKOKORO_PORT = "8880"
$env:FASTKOKORO_WARMUP = "true"
$env:FASTKOKORO_ONNX_AUTO_PROVIDERS = "false"
$env:FASTKOKORO_ONNX_PROVIDERS = "CPUExecutionProvider"
# 0.4.0 default b24 file 404'd on HF — use b96 checkpoint that still exists
$env:FASTKOKORO_MODEL_FILE = "onnx/kokoro-82m-streaming-b96-fp16.onnx"
$env:FASTKOKORO_MODEL_REPO = "msgflux/Kokoro-82M-streaming-onnx"

Write-Host "Starting Kokoro ONNX on http://127.0.0.1:8880 (model=$($env:FASTKOKORO_MODEL_FILE))"
& $exe
