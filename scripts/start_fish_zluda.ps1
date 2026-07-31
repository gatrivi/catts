# Start Fish Speech (ZLUDA) for CATTS - RX 6600 / HIP 5.7
# Requires: Python 3.11 fish venv, torch cu118 + ZLUDA patch, Brknsoul gfx1032 in HIP rocblas library
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Fish = if ($env:CATTS_FISH_ROOT) { $env:CATTS_FISH_ROOT } else {
  $sibling = Join-Path (Split-Path $Root -Parent) "fish-speech-zluda"
  $ext = Join-Path $Root "external\fish-speech-zluda"
  if (Test-Path "$sibling\zluda\zluda.exe") { $sibling }
  elseif (Test-Path "$ext\zluda\zluda.exe") { $ext }
  else { $sibling }
}
$Shadow = Join-Path $Root "external\hip57-shadow"
$LogDir = Join-Path $Root "data\fish_logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-Path "$Fish\zluda\zluda.exe")) {
  throw "Missing $Fish\zluda\zluda.exe - set CATTS_FISH_ROOT or run setup_fish_zluda.ps1"
}

# Prefer writable HIP shadow; else system HIP 5.7 (gfx1032 libs must be in rocblas\library)
$sysGfx = "C:\Program Files\AMD\ROCm\5.7\bin\rocblas\library\TensileLibrary_lazy_gfx1032.dat"
if (Test-Path "$Shadow\bin\rocblas\library\TensileLibrary_lazy_gfx1032.dat") {
  $env:HIP_PATH = "$Shadow\"
  $env:PATH = "$Shadow\bin;C:\Program Files\AMD\ROCm\5.7\bin;" + $env:PATH
} elseif (Test-Path $sysGfx) {
  $env:HIP_PATH = "C:\Program Files\AMD\ROCm\5.7\"
  $env:PATH = "C:\Program Files\AMD\ROCm\5.7\bin;" + $env:PATH
} else {
  throw "Missing gfx1032 rocBLAS libs - copy external\rocm-libs-gfx1032\extracted\library\* into HIP rocblas\library"
}

$env:HIP_VISIBLE_DEVICES = "1"
$env:PYTHONUTF8 = "1"
$env:ZLUDA_COMGR_LOG_LEVEL = "1"
$env:FISH_SKIP_WARMUP = "1"  # bind :8080 fast; first real synth still compiles on ZLUDA

Write-Host "Fish root: $Fish"
Write-Host "HIP_PATH: $($env:HIP_PATH)"
Write-Host "Starting Fish on 127.0.0.1:8080 (first ZLUDA compile can take 30-90+ min)..."
$p = Start-Process -FilePath "$Fish\zluda\zluda.exe" `
  -ArgumentList @("--", "$Fish\venv\Scripts\python.exe", "-u", "tools\api_server.py", "--mode", "tts", "--half", "--listen", "127.0.0.1:8080", "--workers", "1") `
  -WorkingDirectory $Fish -PassThru `
  -RedirectStandardOutput "$LogDir\api_out.log" `
  -RedirectStandardError "$LogDir\api_err.log" `
  -WindowStyle Hidden
Write-Host "PID $($p.Id) - logs: $LogDir"
Write-Host 'When healthy: PUT /tts/engine {"engine":"fish"} or UI dropdown. Synth: scripts\_fish_read_es.py'
