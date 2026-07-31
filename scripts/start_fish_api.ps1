# Start Fish Speech API server via ZLUDA (--half tuned for RX 6600).
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent

$FishRoot = $env:CATTS_FISH_ROOT
if (-not $FishRoot) {
    $FishRoot = Join-Path (Split-Path $RepoRoot -Parent) "fish-speech-zluda"
}
if (-not (Test-Path $FishRoot)) {
    Write-Host "Missing $FishRoot — run .\scripts\setup_fish_zluda.ps1 first"
    exit 1
}

$py = Join-Path $FishRoot "venv\Scripts\python.exe"
$zluda = Join-Path $FishRoot "zluda\zluda.exe"
if (-not (Test-Path $py)) {
    Write-Host "Missing $py — run install-amd.bat inside fish-speech-zluda"
    exit 1
}
if (-not (Test-Path $zluda)) {
    Write-Host "Missing $zluda — re-run install-amd.bat (ZLUDA patch step)"
    exit 1
}

$Listen = if ($env:CATTS_FISH_LISTEN) { $env:CATTS_FISH_LISTEN } else { "127.0.0.1:8080" }
Write-Host "Starting Fish Speech API on http://$Listen (ZLUDA --half)"
Write-Host "First synth compiles kernels — can look hung once, then cached."

Set-Location $FishRoot
& $zluda -- $py tools\api_server.py --half --listen $Listen
