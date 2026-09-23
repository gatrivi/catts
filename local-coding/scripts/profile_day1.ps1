# profile_day1.ps1 — Day-1 baseline capture for the Bonsai-2 RX 6600 profiling plan.
# Runs the proven TQ2_0 bench N times under strict preflight (GPU exclusivity rule),
# parses timings, writes data/profile/d1_<ts>.json + raw logs.
# Usage: profile_day1.ps1 [-Repeats 3] [-Preflight] [-Note "..."]
param(
  [int]$Repeats = 3,
  [switch]$Preflight,
  [string]$Note = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$outDir = Join-Path $root 'data\profile'
$rawDir = Join-Path $outDir 'raw'
New-Item -ItemType Directory -Force -Path $rawDir | Out-Null

$venv  = 'E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe'
$bench = Join-Path $PSScriptRoot 'bonsai2_tq2_bench.py'

function Fail([string]$msg) { Write-Host "PREFLIGHT FAIL: $msg"; exit 2 }

# --- preflight: disk, venv, GPU exclusivity, RAM ---
$cFreeGb = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
if ($cFreeGb -lt 1) { Fail "C: solo $cFreeGb GB libres (min 1 GB para builds)" }
if (-not (Test-Path $venv))  { Fail "venv no encontrado: $venv" }
if (-not (Test-Path $bench)) { Fail "bench no encontrado: $bench" }
$srv = Get-Process llama-server -ErrorAction SilentlyContinue
if ($srv) { Fail "llama-server corriendo (PID $($srv.Id)) - detenelo primero (CATTS.cmd stop all)" }
$t = New-Object Net.Sockets.TcpClient
try { $t.Connect('127.0.0.1', 9103); $portBusy = $true } catch { $portBusy = $false } finally { $t.Close() }
if ($portBusy) { Fail 'puerto 9103 ocupado' }
$freeMb = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory)
if ($freeMb -lt 2500) { Fail "solo $([int]($freeMb/1024)) MB RAM libres (min 2500)" }

$gpu   = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'RX 6600' } | Select-Object -First 1
$cpu   = (Get-CimInstance Win32_Processor).Name
$ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
Write-Host "PREFLIGHT OK: C: $cFreeGb GB | RAM free $([int]($freeMb/1024)) MB | GPU: $($gpu.Name) drv $($gpu.DriverVersion)"

if ($Preflight) { exit 0 }

# --- capture: N independent bench runs (each starts+stops its own server) ---
$runs = @()
$lastStamp = ''
for ($i = 1; $i -le $Repeats; $i++) {
  Write-Host "== run $i/$Repeats =="
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $lastStamp = $stamp
  $raw = Join-Path $rawDir "$stamp-run$i.txt"
  $out = & $venv $bench 2>&1 | Tee-Object -FilePath $raw
  $text = ($out | Out-String)
  if ($LASTEXITCODE -ne 0) {
    Write-Host "run $i FAILED (exit $LASTEXITCODE) - ver $raw"
    $runs += [ordered]@{ run = $i; error = "exit $LASTEXITCODE"; raw = $raw }
    continue
  }
  $load = $null
  if ($text -match 'LOAD_SECONDS\s+([\d.]+)') { $load = [double]$matches[1] }
  $probes = @()
  foreach ($m in [regex]::Matches($text, 'prompt\s+(\d+)\s+tk\s*\|\s*decode\s+(\d+)\s+tk in\s+([\d.]+)s\s*=>\s*([\d.]+)')) {
    $probes += [ordered]@{
      prompt_tokens = [int]$m.Groups[1].Value
      decode_tokens = [int]$m.Groups[2].Value
      seconds       = [double]$m.Groups[3].Value
      tps           = [double]$m.Groups[4].Value
    }
  }
  $runs += [ordered]@{ run = $i; load_s = $load; probes = $probes; raw = $raw }
}

# --- summary + JSON ---
$tpsList = @()
foreach ($r in $runs) { if ($r.probes -and $r.probes.Count -gt 0) { $tpsList += $r.probes[0].tps } }
$meanTps = if ($tpsList.Count) { [math]::Round(($tpsList | Measure-Object -Average).Average, 2) } else { $null }
$okRuns = @($runs | Where-Object { -not $_.error }).Count

$result = [ordered]@{
  captured = (Get-Date -Format o)
  note     = $Note
  spec     = 'd1 baseline: bonsai2_tq2_bench.py defaults (TQ2_0, 8K ctx, q4_0 KV, Vulkan, shipped b10685 runtime)'
  system   = [ordered]@{
    gpu            = $gpu.Name
    driver         = $gpu.DriverVersion
    driver_date    = $gpu.DriverDate
    cpu            = $cpu
    ram_total_gb   = $ramGb
    ram_free_mb    = $freeMb
    c_free_gb      = $cFreeGb
    windows        = [Environment]::OSVersion.VersionString
  }
  runs    = $runs
  summary = [ordered]@{
    repeats      = $Repeats
    ok_runs      = $okRuns
    mean_tps_p1  = $meanTps
    expected     = '12-13 t/s short-ctx (roster); baseline for per-op profiling'
  }
}
$jsonPath = Join-Path $outDir "d1_$lastStamp.json"
$result | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $jsonPath
Write-Host "`nWROTE $jsonPath"
Write-Host "mean decode t/s (probe 1): $meanTps  [$okRuns/$Repeats runs ok]"
if ($okRuns -eq 0) { exit 1 }
exit 0
