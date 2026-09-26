# tier0_ptq10.ps1 - Tier-0 clean-GPU window: first per-op profile of the 27B PTQ1_0
# on THIS box (RX 6800). Nothing has ever measured this model per-op; the 90-100%
# roofline claim in KERNEL_HEADROOM came from an RX 6600 + TQ2_0 run, so we do NOT
# know whether the vecq kernel is the bottleneck or an opportunity.
#
# Gate first: refuse to measure while anything else uses the GPU (>4% util), because
# the whole lesson of 2026-09-26 morning is that Edge HW-accel (21%+) silently
# invalidates absolute numbers.
#
# Output: data/profile/d1_perop_<stamp>.json (written by d1_perop_profile.py)
#         data/profile/raw/tier0_{out,err}.log
# Usage:  powershell -File tier0_ptq10.ps1 [-Reps 2] [-Force]

param(
  [int]$Reps = 2,
  [switch]$Force,
  [switch]$QuietConfirmed
)
$ErrorActionPreference = 'Stop'

$py      = 'E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe'
$sc      = 'Z:\catts\local-coding\scripts\d1_perop_profile.py'
$model   = 'Z:/catts/local-coding/data/models/bonsai2-27b-ptq10/Ternary-Bonsai-2-27B-PTQ1_0.gguf'
$profDir = 'Z:\catts\local-coding\data\profile'
$rawDir  = Join-Path $profDir 'raw'
$so      = Join-Path $rawDir 'tier0_out.log'
$se      = Join-Path $rawDir 'tier0_err.log'
$summary = Join-Path $profDir 'tier0_ptq10_summary.json'

foreach ($f in @($py, $sc, $model)) {
  if (-not (Test-Path $f)) { Write-Host "FALTA: $f"; exit 2 }
}
New-Item -ItemType Directory -Force -Path $rawDir | Out-Null

function Get-GpuUtil {
  try {
    $s = (Get-Counter '\GPU Engine(*\Utilization Percentage' -ErrorAction Stop).CounterSamples
    ($s | Measure-Object -Property CookedValue -Sum).Sum
  } catch { return -1.0 }
}

# --- gate: quiet GPU -------------------------------------------------------
if ($QuietConfirmed) {
  Write-Host 'gate: ventana confirmada por la sesion madre (GPU <1% medida interactivamente)'
  $ok = $true
} elseif (-not $Force) {
  $ok = $false
  for ($i = 0; $i -lt 12; $i++) {
    $u = Get-GpuUtil
    Write-Host ("gpu_util={0:N1}%  intento {1}/12" -f $u, ($i + 1))
    if ($u -ge 0 -and $u -lt 4.0) { $ok = $true; break }
    Start-Sleep 5
  }
  if (-not $ok) { Write-Host 'GATE FAIL: la GPU no esta quieta; no se mide (ver DIA_NO_MEDIBLE)'; exit 3 }
} else {
  Write-Host 'GATE BYPASEADO con -Force: los numeros quedan como contaminados'
}

$cFree = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
# Este run es read-only en disco (un JSON + un log, ~100 KB). El umbral es propio y
# bajo a proposito: el piso de 6 GB del usuario es una regla de su trabajo, no de esta
# medicion. Si C: esta <2 GB el server no puede ni arrancar.
if ($cFree -lt 2) { Write-Host "GATE FAIL: C: libre $cFree GB (<2, server no arranca)"; exit 3 }
Write-Host "gate ok: gpu quieta, C: libre $cFree GB (AVISO: bajo el piso de 6 GB del usuario)"

# --- runs ------------------------------------------------------------------
$got = @()
for ($r = 1; $r -le $Reps; $r++) {
  $before = @(Get-ChildItem (Join-Path $profDir 'd1_perop_*.json') -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
  Write-Host "--- rep $r/$Reps ---"
  $p = Start-Process -FilePath $py -ArgumentList @($sc, '8192', 'q4_0', '48', $model) `
        -RedirectStandardOutput $so -RedirectStandardError $se -PassThru -WindowStyle Hidden
  $new = $null
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 5
    $new = Get-ChildItem (Join-Path $profDir 'd1_perop_*.json') -ErrorAction SilentlyContinue |
             Where-Object { $before -notcontains $_.Name } | Select-Object -First 1
    if ($new) { break }
    if ($p.HasExited) { Start-Sleep 2; break }
  }
  if (-not $new) {
    Write-Host "rep $r SIN JSON (exit=$($p.ExitCode))"
    if (Test-Path $se) { Get-Content $se -Tail 15 | ForEach-Object { Write-Host "  stderr: $_" } }
    continue
  }
  Start-Sleep 2
  $j = Get-Content $new.FullName -Raw | ConvertFrom-Json
  $step_ms = [math]::Round($j.total_us_last_step / 1000.0, 2)
  Write-Host ("  {0}  load={1:N1}s  decode_step={2} ms  -> {3:N1} t/s teorico" -f `
      $new.Name, $j.load_s, $step_ms, $(if ($step_ms -gt 0) { 1000.0 / $step_ms } else { 0 }))
  $got += [pscustomobject]@{
    run           = $r
    file          = $new.Name
    load_s        = $j.load_s
    step_ms       = $step_ms
    tps_from_step = [math]::Round(1000.0 / [math]::Max($step_ms, 0.001), 2)
    top_op        = $j.ops[0].op
    top_op_us     = $j.ops[0].total_us
    ops_count     = $j.ops.Count
  }
  Start-Sleep 3
}

if ($got.Count -eq 0) { Write-Host 'TIER0: ninguna corrida producjo JSON'; exit 4 }

$out = [pscustomobject]@{
  captured   = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')
  model      = 'Ternary-Bonsai-2-27B-PTQ1_0.gguf (PTQ1_0, 5.5GB)'
  gpu        = 'RX 6800 (esta caja) - PRIMER per-op de este modelo'
  contaminated   = (-not $QuietConfirmed)
  note       = 'decode_step_ms = suma de un paso de decode; tps_from_step es el techo SIN overhead de server/sampling'
  runs       = $got
}
$out | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $summary
Write-Host "WROTE $summary"
$got | Format-Table -AutoSize run, step_ms, tps_from_step, top_op_us, top_op | Out-String | Write-Host


