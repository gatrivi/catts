# run_ab_mmvq.ps1 - A/B production del vecq PTQ1_0: LUT (flag off) vs int-dot vecq (flag on)
#
# Por que A/B y no un numero suelto: el comentario de ggml-vulkan.cpp:9720 ya media
# "matvec lm_head 5319 -> 5440 us" con el vecq, o sea el kernel viejo era ~2% MAS LENTO.
# Ese numero estaba contaminado por los 3 defectos (lane map + packing sin mascara).
# Con el parche aplicado y la suite en verde, hay que volver a medir.
#
# Espera a que test-backend-ops libere la GPU, corre los 2 brazos y escribe
# data/ab_mmvq_20260926.json. La flag es opt-in por getenv()!=null, asi que
# hay queLIMPIARLA en el brazo OFF (no sirve ponerla en "0").
param()
$ErrorActionPreference = 'Stop'

$py    = 'E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe'
$sc    = 'Z:\catts\local-coding\scripts\d1_perop_profile.py'
$model = 'Z:/catts/local-coding/data/models/bonsai2-27b-ptq10/Ternary-Bonsai-2-27B-PTQ1_0.gguf'
$prof  = 'Z:\catts\local-coding\data\profile'
$out   = Join-Path $prof 'ab_mmvq_20260926.json'
$log   = 'Z:\catts\local-coding\data\ab_mmvq.log'

function Wait-GpuFree([int]$maxS = 900) {
  for ($i = 0; $i -lt $maxS; $i++) {
    $busy = Get-Process test-backend-ops, llama-server -ErrorAction SilentlyContinue
    if (-not $busy) { return $true }
    Start-Sleep 10
  }
  return $false
}

function Run-Arm([string]$name, [bool]$mmvq) {
  if ($mmvq) { $env:GGML_PTQ1_0_MMVQ = '1' } else { Remove-Item Env:\GGML_PTQ1_0_MMVQ -ErrorAction SilentlyContinue }
  $before = @(Get-ChildItem (Join-Path $prof 'd1_perop_*.json') -EA SilentlyContinue | ForEach-Object { $_.Name })
  $p = Start-Process -FilePath $py -ArgumentList @($sc, '8192', 'q4_0', '48', $model) -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput "$log.$name.out" -RedirectStandardError "$log.$name.err"
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 5
    $new = Get-ChildItem (Join-Path $prof 'd1_perop_*.json') -EA SilentlyContinue | Where-Object { $before -notcontains $_.Name } | Select-Object -First 1
    if ($new) { break }
    if ($p.HasExited) { break }
  }
  if (-not $new) { Write-Host "BRAZO $name SIN JSON (exit=$($p.ExitCode))"; return $null }
  Start-Sleep 2
  $j = Get-Content $new.FullName -Raw | ConvertFrom-Json
  $mv = ($j.ops | Where-Object { $_.op -match 'MUL_MAT_VEC ptq1_0' } | Measure-Object total_us -Sum).Sum
  [pscustomobject]@{
    arm                 = $name
    ggml_ptq1_0_mmvq    = [bool]$mmvq
    file                = $new.Name
    load_s              = [math]::Round($j.load_s, 1)
    step_ms             = [math]::Round($j.total_us_last_step / 1000.0, 2)
    tps                 = [math]::Round(1000.0 / ($j.total_us_last_step / 1000.0), 2)
    mul_mat_vec_ptq1_0_ms = [math]::Round($mv / 1000.0, 2)
  }
}

Write-Host 'esperando a que test-backend-ops libere la GPU...'
if (-not (Wait-GpuFree)) { Write-Host 'TIMEOUT esperando GPU'; exit 3 }
Start-Sleep 5

$off = Run-Arm 'mmvq0' $false
Start-Sleep 5
$on  = Run-Arm 'mmvq1' $true

$res = [pscustomobject]@{
  captured = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')
  model    = 'Ternary-Bonsai-2-27B-PTQ1_0.gguf'
  note     = 'A/B del vecq con el parche D1+D2 aplicado; suite MUL_MAT en verde. OFF = LUT (mul_mat_vec_ptq1_0), ON = int-dot vecq'
  off      = $off
  on       = $on
}
if ($off -and $on) {
  $res | Add-Member -NotePropertyName delta_tps_pct -NotePropertyValue ([math]::Round(100.0 * ($on.tps / $off.tps - 1.0), 2))
  $res | Add-Member -NotePropertyName delta_matvec_pct -NotePropertyValue ([math]::Round(100.0 * ($on.mul_mat_vec_ptq1_0_ms / $off.mul_mat_vec_ptq1_0_ms - 1.0), 2))
}
$res | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $out
Write-Host "WROTE $out"
