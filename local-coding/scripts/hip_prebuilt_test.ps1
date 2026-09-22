# L0/L1 del ladder HIP (docs/HIP_PREBUILT_LADDER.md).
# L0: confirma que el RX 6600 esta enumerado. L1: baja el prebuilt
# bin-win-hip-radeon del fork Prism (si falta) y corre llama-bench PTQ1_0
# con y sin HSA_OVERRIDE_GFX_VERSION=10.3.0. Nunca mata servidores vivos
# (regla un-modelo): aborta si detecta llama-server.
# Salida: data/hip_prebuilt/<stamp>/{result.json,bench-*.log}
# Exit: 0 HIP OK | 1 bench fallo | 2 modelo falta | 3 GPU no visible
#       4 llama-server vivo | 5 runtime/download fallo
param(
  [string]$RuntimeDir = "Z:/Models/runtime/llama-prism-hip-win",
  [string]$Model = "Z:/catts/local-coding/data/models/bonsai2-27b-ptq10/Ternary-Bonsai-2-27B-PTQ1_0.gguf",
  [string]$Base = "https://github.com/PrismML-Eng/llama.cpp/releases/download/prism-b10709-9a9394a",
  [string]$Asset = "llama-prism-b10709-9a9394a-bin-win-hip-radeon-x64.zip",
  [int]$PP = 128,
  [int]$TG = 32,
  [switch]$SkipDownload
)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent  # local-coding
$outDir = Join-Path $root ("data/hip_prebuilt/" + (Get-Date -Format yyyyMMdd-HHmmss))
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# L0: GPU visible
$gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'RX 6600' }
if (-not $gpu) {
  Write-Host "L0 FAIL: RX 6600 no enumerado (Win32_VideoController). Revisar cable/reasiento/Device Manager."
  exit 3
}
Write-Host ("L0 OK: {0} ({1}) driver {2}" -f $gpu.Name, $gpu.Status, $gpu.DriverVersion)

# regla un-modelo: no tocar servidores vivos
$srv = Get-Process llama-server -ErrorAction SilentlyContinue
if ($srv) {
  Write-Host ("ABORT: llama-server vivo (PID {0}). Detenlo y reintenta." -f (($srv.Id) -join ','))
  exit 4
}

# L1: runtime prebuilt
if (-not (Test-Path (Join-Path $RuntimeDir 'llama-bench.exe'))) {
  if ($SkipDownload) { Write-Host "ABORT: falta $RuntimeDir\llama-bench.exe y -SkipDownload"; exit 5 }
  $zip = Join-Path $env:TEMP $Asset
  Write-Host "descargando $Base/$Asset"
  & curl.exe -L --fail -o $zip "$Base/$Asset"
  if ($LASTEXITCODE -ne 0) { Write-Host "descarga fallo"; exit 5 }
  Expand-Archive -Path $zip -DestinationPath $RuntimeDir -Force
  Remove-Item $zip -ErrorAction SilentlyContinue
}
$bench = Get-ChildItem $RuntimeDir -Recurse -Filter llama-bench.exe | Select-Object -First 1
if (-not $bench) { Write-Host "ABORT: llama-bench.exe no encontrado bajo $RuntimeDir"; exit 5 }
Write-Host "bench: $($bench.FullName)"

if (-not (Test-Path $Model)) { Write-Host "ABORT: modelo no encontrado: $Model"; exit 2 }

$runs = @()
foreach ($ov in @('10.3.0', '')) {
  if ($ov) { $env:HSA_OVERRIDE_GFX_VERSION = $ov }
  else { Remove-Item Env:\HSA_OVERRIDE_GFX_VERSION -ErrorAction SilentlyContinue }
  $tag = 'override'; if (-not $ov) { $tag = 'plain' }
  $log = Join-Path $outDir "bench-$tag.log"
  Write-Host "== llama-bench ($tag) -p $PP -n $TG"
  $argv = ('"{0}" -m "{1}" -p {2} -n {3} -ngl 99 -c 2048' -f $bench.FullName, $Model, $PP, $TG)
  & cmd /c "$argv > `"$log`" 2>&1"
  $code = $LASTEXITCODE
  Get-Content $log -Tail 25 | Write-Host
  $runs += [ordered]@{ mode = $tag; override = $ov; exit_code = $code }
  if ($code -eq 0) { break }  # con override OK no hace falta el plain
}
Remove-Item Env:\HSA_OVERRIDE_GFX_VERSION -ErrorAction SilentlyContinue

$ok = [bool]($runs | Where-Object { $_.exit_code -eq 0 })
$status = 'hip_ok'; if (-not $ok) { $status = 'hip_fail' }
[pscustomobject]@{
  status = $status
  gpu = $gpu.Name; driver = $gpu.DriverVersion
  runtime = $RuntimeDir; model = $Model; runs = $runs
  stamp = (Get-Date -Format o)
} | ConvertTo-Json -Depth 4 | Out-File (Join-Path $outDir 'result.json') -Encoding utf8

if ($ok) {
  Write-Host "VEREDICTO: HIP OK - el prebuilt win-hip corre en gfx1032. Capturar golden: golden_capture.py contra un server de este runtime."
  exit 0
}
Write-Host "VEREDICTO: HIP FAIL - siguiente escalon L2 (ubuntu-rocm en WSL2/Linux): docs/HIP_PREBUILT_LADDER.md"
exit 1
