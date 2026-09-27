# Clone + install Fish Speech ZLUDA for AMD (RX 6600 etc.)
# Prerequisites (do these FIRST — see docs/FISH_ZLUDA_RX6600.md):
#   1) Python 3.10/3.11 from python.org (not Store)
#   2) VC++ redistributable
#   3) HIP SDK 5.7.1 + HIP_PATH / Path
#   4) Brknsoul rocBLAS libs for RX 6600 (gfx1032)
#   5) Reboot
# Then run this script from an elevated cmd/powershell.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $RepoRoot

$FishRoot = $env:CATTS_FISH_ROOT
if (-not $FishRoot) {
    $FishRoot = Join-Path (Split-Path $RepoRoot -Parent) "fish-speech-zluda"
}

Write-Host "Fish Speech root: $FishRoot"

if (-not (Test-Path $FishRoot)) {
    Write-Host "Cloning patientx/fish-speech-zluda ..."
    git clone https://github.com/patientx/fish-speech-zluda.git $FishRoot
}

Set-Location $FishRoot
if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "Running install-amd.bat (long: torch + models + ZLUDA patch) ..."
    cmd /c install-amd.bat
} else {
    Write-Host "venv already present — skip install-amd.bat (delete venv to reinstall)"
}

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  1) Set CATTS_FISH_ROOT=$FishRoot in CATTS .env"
Write-Host "  2) Set CATTS_TTS_ENGINE=fish"
Write-Host "  3) Set CATTS_FISH_URL=http://127.0.0.1:8080"
Write-Host "  4) Start API: .\scripts\start_fish_api.ps1"
Write-Host "  5) Restart CATTS; GET /health should show tts_engine=fish tts_ready=true"
