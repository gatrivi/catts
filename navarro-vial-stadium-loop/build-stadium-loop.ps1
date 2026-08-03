# Build stadium loop with crossfade animation (requires ffmpeg + Python 3)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LoopDir = Join-Path $RepoRoot "navarro-vial-stadium-loop"
if (-not (Test-Path (Join-Path $LoopDir "frame-01-terreno.png"))) {
  $Zip = Join-Path $RepoRoot "navarro-vial-stadium-loop.zip"
  if (-not (Test-Path $Zip)) { throw "Missing zip: $Zip" }
  Expand-Archive -Path $Zip -DestinationPath $LoopDir -Force
}
Set-Location $LoopDir
python assemble_stadium_loop.py
if ($LASTEXITCODE -ne 0) { throw "assemble_stadium_loop.py failed" }
