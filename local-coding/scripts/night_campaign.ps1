# night_campaign.ps1 â€” 23-night knowledge campaign (scripts-only, zero cloud tokens).
# Supersedes night_jobs.ps1 as the CATTS-NightJobs target (02:30 daily).
# Day index = nights since 2026-09-25 (day 1) .. Oct 15+ (day 21+).
# Each night: telemetry -> scheduled slice(s) -> JSONL knowledge append -> coverage map update.
# All output under data/campaign/. Never kills processes; RAM-floor guarded; GPU exclusive assumed
# (user asleep; CATTS-GPUConfirm is a separate daytime task).
param(
  [int]$DayIndex = 0,          # 0 = auto-compute from date
  [string]$ForceSlice = '',    # run one slice only (smoke tests)
  [switch]$AllowDay,
  [switch]$PreflightOnly
)
$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
$venv = 'E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe'
$tbops = 'C:/src/llama.cpp/build/bin/test-backend-ops.exe'
$server = 'C:/src/llama.cpp/build/bin/llama-server.exe'
$env:PATH = 'C:\tools\llvm-mingw\bin;' + $env:PATH
$day = Get-Date -Format 'yyyyMMdd'
if ($DayIndex -eq 0) { $DayIndex = ((Get-Date) - (Get-Date '2026-09-25')).Days + 1 }
$outDir = Join-Path $root "data\campaign\$day"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
Start-Transcript -Path (Join-Path $outDir 'runner.log') -Force | Out-Null
function Info([string]$m) { Write-Host ("[campaign d{0} {1}] {2}" -f $DayIndex, (Get-Date -Format 'HH:mm:ss'), $m) }

$lock = Join-Path $outDir 'lock.flag'
if ((Test-Path $lock) -and (-not $ForceSlice)) { Info 'already ran today - exiting'; Stop-Transcript | Out-Null; exit 0 }
if (-not $ForceSlice) { Set-Content -Path $lock -Value (Get-Date -Format o) }

# ---- telemetry + guards ----
$freeMb = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB)
$gpuUtil = $null
try { $gpuUtil = (Get-Counter '\GPU Engine(*)\Utilization Percentage' -ErrorAction Stop).CounterSamples | Measure-Object CookedValue -Maximum | Select-Object -ExpandProperty Maximum } catch {}
$srv = Get-Process llama-server -ErrorAction SilentlyContinue
$telemetry = [ordered]@{ date = (Get-Date -Format o); day = $DayIndex; ram_free_mb = $freeMb;
  gpu_util_max_pct = [math]::Round($gpuUtil, 1); llama_server_running = [bool]$srv; c_free_gb = [math]::Round((Get-PSDrive C).Free/1GB, 2) }
Info ("telemetry: " + ($telemetry | ConvertTo-Json -Compress))
$knowledge = Join-Path $root 'data\campaign\knowledge.jsonl'
$coverage = Join-Path $root 'data\campaign\coverage.json'
$map = if (Test-Path $coverage) { Get-Content $coverage -Raw | ConvertFrom-Json } else { [ordered]@{} }

function Record([string]$cell, $value, [string]$unit, $extra) {
  $e = if ($null -ne $extra) { $extra } else { [ordered]@{} }
  $rec = [ordered]@{ date = (Get-Date -Format o); day = $DayIndex; cell = $cell; value = $value; unit = $unit; telemetry = $telemetry; extra = $e }
  Add-Content -Path $knowledge -Value ($rec | ConvertTo-Json -Depth 6 -Compress) -Encoding UTF8
  if ($map.PSObject.Properties[$cell]) { $map.$cell.runs += 1; $map.$cell.values += $value; $map.$cell.last = (Get-Date -Format o) }
  else { $map | Add-Member -NotePropertyName $cell -NotePropertyValue ([ordered]@{ runs = 1; values = @($value); last = (Get-Date -Format o) }) }
  $map | ConvertTo-Json -Depth 6 | Set-Content -Path $coverage -Encoding UTF8
}

# --- LANE 5.2: guard de frescura del build (2026-09-26) ---
# Sin esto se miden binarios viejos y salen falsos negativos (ya paso con MTP:
# el server era de 02:18 y el fix del head MTP jamas se habia compilado).
$buildStale = $false
if (Test-Path $server) {
  $srvT = (Get-Item $server).LastWriteTime
  foreach ($src in @('C:/src/llama.cpp/src/models/qwen35.cpp',
                     'C:/src/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vecq_funcs.glsl',
                     'C:/src/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vec_ptq1_0.comp')) {
    if ((Test-Path $src) -and ((Get-Item $src).LastWriteTime -gt $srvT)) { $buildStale = $true }
  }
}
if ($buildStale) {
  Record 'build:stale' ("llama-server.exe " + (Get-Item $server).LastWriteTime.ToString('s') + " es mas viejo que el source: los numeros de hoy pueden ser falsos negativos") 'string' @{}
  Info 'BUILD STALE - los numeros de esta corrida no son confianza'
}
function PerfCell([string]$label, [string]$pfilter, [string]$sizePat) {
  # run one perf filter, parse us/run for the wanted shape(s), record each as a cell
  $out = & $tbops perf -b Vulkan1 -o MUL_MAT -p $pfilter 2>&1
  $out | Out-File -FilePath (Join-Path $outDir ("perf-$label.txt")) -Encoding UTF8
  foreach ($line in ($out | Where-Object { $_ -match 'us/run' })) {
    $t = $line -replace '\x1b\[[0-9;]*m', ''
    if ($t -match 'm=(\d+),n=(\d+),k=(\d+)') {
      $m = $matches[1]; $n = $matches[2]; $k = $matches[3]
      if ($t -match ':\s+(\d+) runs -\s+([\d.]+) us/run') {
        $us = [double]$matches[2]
        if (-not $sizePat -or ($m -eq $sizePat)) {
          $cell = "mm:$tname-m$m-n$n-k$k"
          Record $cell $us 'us_per_run' @{ raw = $t.Trim() }
        }
      }
    }
  }
}
$tname = 'unknown'   # set by matrix slices for cell naming

function SuiteRegression {
  Info 'slice: full suite regression snapshot'
  $log = Join-Path $outDir 'suite.txt'
  & $tbops test -b Vulkan1 -o MUL_MAT -p "tq2_0|ptq1_0|q2_k|q4_0|tq2_0" 2>&1 | Out-File -FilePath $log -Encoding UTF8
  $txt = Get-Content $log -Raw
  $passed = if ($txt -match '(\d+)/(\d+) tests passed') { "$($matches[1])/$($matches[2])" } else { 'unknown' }
  Record 'suite:mul_mat_regression' $passed 'pass_fraction' @{ log = $log }
}

function Bandwidth {
  Info 'slice: CPY bandwidth sweep (1..256 MB)'
  $out = & $tbops perf -b Vulkan1 -o CPY -p "type_src=f32,type_dst=f32,ne_src=\[(262144|1048576|4194304|16777216|67108864)," 2>&1
  $out | Out-File -FilePath (Join-Path $outDir 'bandwidth-cpy.txt') -Encoding UTF8
  foreach ($line in ($out | Where-Object { $_ -match 'us/run' })) {
    $t = $line -replace '\x1b\[[0-9;]*m', ''
    if ($t -match 'ne_src=\[(\d+),1,1,1\]') {
      $elems = [int64]$matches[1]
      if ($t -match ':\s+(\d+) runs -\s+([\d.]+) us/run -\s+([\d.]+) kB/run -\s+([\d.]+) GB/s') {
        $us = [double]$matches[2]
        $mb = [math]::Round($elems * 4 / 1MB, 1)
        $gbps = [double]$matches[4]
        Record "bw:cpy-${mb}MB" $gbps 'GB/s_read_write' @{ us_per_run = $us }
      }
    }
  }
}

function TypeMatrix([string]$t) {
  Info "slice: type matrix $t (production shapes x n=1,2,4,8)"
  $script:tname = $t
  PerfCell $t "$t`.*n=1," ''
  PerfCell "$t-n248" "$t`.*m=(17408|248320),n=(2|4|8)," ''
}

function ConfigAxes {
  Info 'slice: reduction-mode axis (SHMEM/HYBRID/SUBGROUP) on tq2_0 + ptq1_0'
  foreach ($rm in 0, 1, 2) {
    $env:GGML_VK_DMMV_REDUC = "$rm"
    foreach ($t in 'tq2_0', 'ptq1_0') {
      $script:tname = "$t-reduc$rm"
      PerfCell $t "$t`.*n=1," ''
    }
  }
  Remove-Item Env:GGML_VK_DMMV_REDUC -ErrorAction SilentlyContinue
  Info 'slice: workgroup width axis (ptq1_0, env GGML_PTQ1_0_WG)'
  foreach ($wg in '', '64', '128') {
    if ($wg -eq '') { Remove-Item Env:GGML_PTQ1_0_WG -ErrorAction SilentlyContinue; $lbl = 'default' } else { $env:GGML_PTQ1_0_WG = $wg; $lbl = $wg }
    $script:tname = "ptq1_0-wg$lbl"
    PerfCell $t "ptq1_0.*n=1," ''
  }
  Remove-Item Env:GGML_PTQ1_0_WG -ErrorAction SilentlyContinue
}

function Baseline {
  Info 'slice: 3-run baseline (profile_day1)'
  $blocker = $null
  $srv0 = Get-Process llama-server -ErrorAction SilentlyContinue
  if ($srv0) { $blocker = "llama-server PID $($srv0.Id) running" }
  else {
    $t = New-Object Net.Sockets.TcpClient
    try { $t.Connect('127.0.0.1', 9103); if ($?) { $blocker = 'port 9103 busy' } } catch { } finally { $t.Close() }
  }
  if ($blocker) { Record 'baseline:blocked' $blocker 'string' @{}; Info "baseline BLOCKED: $blocker"; return }
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'profile_day1.ps1') -Repeats 3 -Note "campaign night d$DayIndex" 2>&1 | Tee-Object -FilePath (Join-Path $outDir 'baseline.log')
  $j = Get-ChildItem (Join-Path $root 'data\profile') -Filter 'd1_*.json' | Sort-Object LastWriteTime | Select-Object -Last 1
  if ($j) { $jj = ([System.IO.File]::ReadAllText($j.FullName) -replace '^ï»¿','') | ConvertFrom-Json; Record 'baseline:mean_tps' $jj.summary.mean_tps_p1 't/s' @{ json = $j.FullName } }
}

function Sweep {
  Info 'slice: gpu_sweep (first full matrix)'
  & $venv (Join-Path $PSScriptRoot 'gpu_sweep.py') 2>&1 | Set-Content -Path (Join-Path $outDir 'sweep.log') -Encoding UTF8
  Record 'sweep:completed' ($LASTEXITCODE -eq 0) 'bool' @{ log = (Join-Path $outDir 'sweep.log') }
}

function ServerProbe([string]$label, [string[]]$extraArgs, [string]$model, [int]$ctx, [string]$kv) {
  # start server, run a realistic-prompt decode probe twice, record server decode t/s
  $a = @('-m', $model, '--host', '127.0.0.1', '--port', '9103', '--alias', 'camp',
         '--device', 'Vulkan1', '-ngl', '99', '-c', "$ctx", '-np', '1', '-ctk', $kv, '-ctv', $kv,
         '-fa', 'on', '--jinja', '--no-warmup', '--temp', '0.0') + $extraArgs
  $log = Join-Path $outDir "server-$label.log"; $logErr = Join-Path $outDir "server-$label.err.log"
  $srv = Start-Process -FilePath $server -ArgumentList $a -RedirectStandardOutput $log -RedirectStandardError $logErr -PassThru -WindowStyle Hidden
  $ready = $false; $t0 = Get-Date
  while (((Get-Date) - $t0).TotalSeconds -lt 900) {
    if ($srv.HasExited) { break }
    try { if ((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9103/health' -TimeoutSec 2).StatusCode -eq 200) { $ready = $true; break } } catch { }
    Start-Sleep -Seconds 2
  }
  if (-not $ready) { if (-not $srv.HasExited) { $srv.Kill() }; Info "server $label FAILED to start"; return $null }
  $prompt = "Rewrite this paragraph in clearer English and keep the meaning: The React component re-renders whenever its state changes, and the useEffect hook runs after every render by default unless a dependency array is provided. Cleaning up subscriptions in the cleanup function prevents memory leaks when the component unmounts, so returning a cleanup closure from useEffect is the recommended pattern for any subscription, timer, or event listener registered inside the effect body."
  $res = @()
  foreach ($r in 1, 2) {
    $t = Get-Date
    $resp = & $venv -c "import httpx,json; r=httpx.post('http://127.0.0.1:9103/v1/chat/completions', json={'model':'x','temperature':0,'max_tokens':200,'chat_template_kwargs':{'enable_thinking':False},'messages':[{'role':'user','content':'''$prompt'''}]}, timeout=600).json(); print(json.dumps({'n':r['usage']['completion_tokens'],'tps':r.get('timings',{}).get('predicted_per_second')}))" 2>&1
    $o = ($res + $resp) | Out-String
    try { $j = ($resp | ConvertFrom-Json); $res += $j } catch { }
  }
  $srv.CloseMainWindow() | Out-Null; Start-Sleep -Seconds 3; if (-not $srv.HasExited) { $srv.Kill() }
  return $res
}

function SpecDecode {
  Info 'slice: ngram speculative decode A/B (TQ2_0, realistic prompt)'
  $model = 'Z:/catts/local-coding/data/models/bonsai2-27b-tq2_0/Ternary-Bonsai-2-27B-TQ2_0.gguf'
  $b = ServerProbe 'spec-base' @() $model 8192 'q4_0'
  if ($null -ne $b) { Record 'specdec:tq2_0-base' ($b | ConvertTo-Json -Compress) 'tps_list' @{} }
  $n = ServerProbe 'spec-ngram' @('--spec-type', 'ngram-simple') $model 8192 'q4_0'
  if ($null -ne $n) { Record 'specdec:tq2_0-ngram' ($n | ConvertTo-Json -Compress) 'tps_list' @{} }
  Info 'slice: DSpark drafter A/B (downloads drafter if missing)'
  $ddir = 'Z:/catts/local-coding/data/models/dspark-drafter'
  if (-not (Test-Path $ddir)) {
    New-Item -ItemType Directory -Force -Path $ddir | Out-Null
    $listing = & curl.exe -sL 'https://huggingface.co/api/models/MobiusDevelopment/Bonsai-27B-Q1_0-gguf' 2>&1 | Out-String
    $listing | Out-File -FilePath (Join-Path $outDir 'mobius-listing.json') -Encoding UTF8
    if ($listing -match '"rfilename":"([^"]*(?:[Dd]raft|[Dd]spark|ds)[^"]*\.gguf)"') {
      $fn = $matches[1]
      Info "downloading drafter: $fn"
      & curl.exe -sL "https://huggingface.co/MobiusDevelopment/Bonsai-27B-Q1_0-gguf/resolve/main/$fn" -o (Join-Path $ddir $fn)
      Record 'drafter:downloaded' $fn 'filename' @{ dir = $ddir }
    } else {
      Record 'drafter:downloaded' 'NOT_FOUND' 'string' @{ listing = (Join-Path $outDir 'mobius-listing.json') }
      Info 'drafter file not found in repo listing - marked in coverage'
      return
    }
  }
  $drafter = (Get-ChildItem $ddir -Filter '*.gguf' | Select-Object -First 1).FullName
  if ($drafter) {
    $model2 = 'Z:/catts/local-coding/data/models/bonsai2-27b-ptq10/Ternary-Bonsai-2-27B-PTQ1_0.gguf'
    $d = ServerProbe 'spec-dspark' @('--spec-type', 'draft-dspark', '--model-draft', $drafter) $model2 8192 'q8_0'
    if ($null -ne $d) { Record 'specdec:ptq10-dspark' ($d | ConvertTo-Json -Compress) 'tps_list' @{} }
  }
}

function MTPLean {
  Info 'slice: mtp-lean + draft-mtp (the #217 Hadamard fix is in-tree, never tested)'
  $mtp = 'Z:/catts/local-coding/data/models/bonsai2-27b-ptq10-mtp/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf'
  $drafter = 'Z:/catts/local-coding/data/models/dspark-drafter/Bonsai-27B-dspark-Q4_1.gguf'
  if (-not (Test-Path $mtp)) { Record 'mtp:model' 'missing' 'string' @{ path = $mtp }; return }
  if (-not (Test-Path $drafter)) { Record 'mtp:drafter' 'missing' 'string' @{ path = $drafter }; return }
  if ($buildStale) { Record 'mtp:skipped' 'build_stale' 'string' @{}; Info 'skipped mtp: build stale'; return }
  $freeMb = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB)
  if ($freeMb -lt 8000) { Record 'mtp:skipped' "ram_free=${freeMb}MB" 'string' @{ need_mb = 8000 }; Info "skipped mtp: only ${freeMb}MB free (need 8000)"; return }
  $base = ServerProbe 'mtp-base' @() $mtp 8192 'q4_0'
  if ($null -ne $base) { Record 'mtp:lean-base' ($base | ConvertTo-Json -Compress) 'tps_list' @{} }
  $spec = ServerProbe 'mtp-draft' @('--spec-type', 'draft-mtp', '--model-draft', $drafter, '--spec-draft-n-max', '4') $mtp 8192 'q4_0'
  if ($null -ne $spec) {
    Record 'mtp:lean-draft-mtp' ($spec | ConvertTo-Json -Compress) 'tps_list' @{}
    $b = @($base | ForEach-Object { $_.tps } | Where-Object { $_ })
    $s = @($spec | ForEach-Object { $_.tps } | Where-Object { $_ })
    if ($b.Count -and $s.Count) { Record 'mtp:acceptance_speedup' ([math]::Round(($s | Measure-Object -Average).Average / ($b | Measure-Object -Average).Average, 3)) 'ratio_draft_over_base' @{ base_tps = $b; spec_tps = $s } }
  } else {
    Record 'mtp:lean-draft-mtp' 'server_failed' 'string' @{ is_error = $true; build_stale = $buildStale; note = 'draft-mtp did not start: es error de build/modelo, NO una medicion de perf; nunca leerlo como resultado' }
  }
}

function LongContext {
  Info 'slice: long-context 32K decode profile (TQ2_0, q4 KV)'
  $model = 'Z:/catts/local-coding/data/models/bonsai2-27b-tq2_0/Ternary-Bonsai-2-27B-TQ2_0.gguf'
  $r = ServerProbe 'longctx-32k' @() $model 32768 'q4_0'
  if ($null -ne $r) { Record 'longctx:tq2_0-32k' ($r | ConvertTo-Json -Compress) 'tps_list' @{} }
}

function Workload {
  Info 'slice: workload characterization (catintassist serving logs)'
  $found = @()
  foreach ($d in 'C:\zengatrivi\REACTJS\catintassist', 'Z:\catts\local-coding\data') {
    if (Test-Path $d) {
      $logs = Get-ChildItem $d -Recurse -Include '*.log','*.jsonl' -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 1KB } | Select-Object -First 20
      foreach ($l in $logs) {
        $lines = Get-Content $l.FullName -ErrorAction SilentlyContinue | Select-Object -First 200
        $toks = ($lines | Select-String -Pattern '(\d+)\s*tokens?' -AllMatches | ForEach-Object { $_.Matches } | ForEach-Object { [int]$_.Groups[1].Value })
        if ($toks.Count -gt 0) { $found += [ordered]@{ log = $l.FullName; token_samples = ($toks | Measure-Object -Average -Maximum).Average; max = ($toks | Measure-Object -Maximum).Maximum } }
      }
    }
  }
  Record 'workload:token_lengths' ($found | ConvertTo-Json -Depth 4 -Compress) 'summary' @{ n_logs = $found.Count }
}

function GapFill {
  Info 'slice: gap-fill (cells with 0 or 1 runs)'
  $low = @()
  foreach ($p in $map.PSObject.Properties) { if ($p.Value.runs -lt 2 -and $p.Name -notmatch 'suite|sweep|drafter|workload') { $low += $p.Name } }
  Info ("low-coverage cells: " + ($low -join ', '))
  Record 'campaign:low_coverage_cells' ($low -join ',') 'list' @{ n = $low.Count }
  # re-run type matrices as the generic filler (they cover the most cells)
  if ($low.Count -gt 0) { TypeMatrix 'tq2_0'; TypeMatrix 'ptq1_0' }
}

function RGP {
  Info 'slice: RGP single-dispatch captures (tq2_0 vs q4_0, tiny + lmhead, trace+counters)'
  $harness = Join-Path $PSScriptRoot 'rgp_capture.ps1'
  if (-not (Test-Path $harness)) { Record 'rgp:harness' $false 'bool' @{}; return }
  $rgpDir = Join-Path $root 'data\profile\rgp'
  $jobs = @(
    @{ tag = 'tiny-tq2_0';   wl = 'tiny';   ty = 'tq2_0'; sweep = '3,4'; heavy = $true },
    @{ tag = 'tiny-q4_0';    wl = 'tiny';   ty = 'q4_0';  sweep = '3,4'; heavy = $true },
    @{ tag = 'lmhead-tq2_0'; wl = 'lmhead'; ty = 'tq2_0'; sweep = '3,4'; heavy = $false },
    @{ tag = 'lmhead-q4_0';  wl = 'lmhead'; ty = 'q4_0';  sweep = '3,4'; heavy = $false }
  )
  foreach ($j in $jobs) {
    Info "RGP capture $($j.tag) ($($j.ty), $($j.wl), heavy=$($j.heavy))"
    $hargs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $harness, '-Tag', $j.tag, '-Workload', $j.wl, '-Type', $j.ty, '-Sweep', $j.sweep)
    if ($j.heavy) { $hargs += '-Trace'; $hargs += '-Counters' }
    & powershell.exe @hargs 2>&1 | ForEach-Object { Write-Host "    $_" }
    $last = Join-Path $rgpDir "last_$($j.tag).json"
    if (Test-Path $last) {
      $r = Get-Content $last -Raw | ConvertFrom-Json
      Record "rgp:$($j.tag)" $r.capture_kb 'KB_rgp_trace' @{ status = $r.status; dispatch = $r.dispatch; shape = $r.shape; type = $r.type; capture = $r.capture; trace = $r.trace; counters = $r.counters }
      if ($r.status -eq 'ok') {
        $isa = & $venv (Join-Path $PSScriptRoot 'rgp_isa_notes.py') --extract $r.capture 2>&1
        $isa | Out-File -FilePath (Join-Path $outDir "isa-$($j.tag).txt") -Encoding UTF8
        $code = ($isa | Select-String -Pattern 'isa_code_bytes=(\d+)' | ForEach-Object { [int]$_.Matches[0].Groups[1].Value } | Sort-Object -Descending | Select-Object -First 1)
        if ($code) { Record "isa:code_bytes-$($j.ty)" $code 'bytes_ISA' @{ shape = $r.shape; capture = $r.capture } }
      }
    } else {
      Record "rgp:$($j.tag)" 'no-result' 'string' @{ status = 'skipped_or_failed' }
    }
  }
  $a = Join-Path $rgpDir 'last_tiny-tq2_0.json'; $b = Join-Path $rgpDir 'last_tiny-q4_0.json'
  if ((Test-Path $a) -and (Test-Path $b)) {
    $ra = Get-Content $a -Raw | ConvertFrom-Json; $rb = Get-Content $b -Raw | ConvertFrom-Json
    if (($ra.status -eq 'ok') -and ($rb.status -eq 'ok')) {
      Record 'rgp:tiny_trace_delta_kb' ([int]($rb.capture_kb - $ra.capture_kb)) 'KB_q4_0_minus_tq2_0' @{ tq2_0_kb = $ra.capture_kb; q4_0_kb = $rb.capture_kb }
    }
  }
}

function Compile {
  Info 'slice: compile knowledge pack'
  & $venv (Join-Path $PSScriptRoot 'campaign_pack.py') 2>&1 | Tee-Object -FilePath (Join-Path $outDir 'pack.log')
  Record 'pack:compiled' (Test-Path (Join-Path $root 'docs\KNOWLEDGE_PACK.md')) 'bool' @{}
}

function Premortem {
  Info 'slice: premortem audit (question categories vs artifacts)'
  $cats = [ordered]@{
    bandwidth_curve = ($map.PSObject.Properties | Where-Object { $_.Name -match 'bw:' }).Count
    q4_0_matrix = ($map.PSObject.Properties | Where-Object { $_.Name -match 'mm:q4_0' }).Count
    tq2_0_matrix = ($map.PSObject.Properties | Where-Object { $_.Name -match 'mm:tq2_0' }).Count
    ptq1_0_matrix = ($map.PSObject.Properties | Where-Object { $_.Name -match 'mm:ptq1_0' }).Count
    config_axes = ($map.PSObject.Properties | Where-Object { $_.Name -match 'reduc|wg' }).Count
    spec_decode = ($map.PSObject.Properties | Where-Object { $_.Name -match 'specdec' }).Count
    long_context = ($map.PSObject.Properties | Where-Object { $_.Name -match 'longctx' }).Count
    workload = ($map.PSObject.Properties | Where-Object { $_.Name -match 'workload' }).Count
    baseline_variance = ($map.PSObject.Properties | Where-Object { $_.Name -match 'baseline' }).Count
    regression = ($map.PSObject.Properties | Where-Object { $_.Name -match 'suite' }).Count
    rgp_captures = ($map.PSObject.Properties | Where-Object { $_.Name -match '^rgp:' }).Count
    isa_code_bytes = ($map.PSObject.Properties | Where-Object { $_.Name -match '^isa:' }).Count
  }
  Record 'campaign:coverage_summary' ($cats | ConvertTo-Json -Compress) 'counts' @{}
  $cats | ConvertTo-Json | Set-Content -Path (Join-Path $outDir 'coverage-summary.json') -Encoding UTF8
}

# ---- wait for GPU (scheduled runs only; never kills, up to 90 min) ----
if (-not $ForceSlice) {
  $deadline = (Get-Date).AddMinutes(90)
  $b = $null
  while ((Get-Date) -lt $deadline) {
    $b = $null
    $s0 = Get-Process llama-server -ErrorAction SilentlyContinue
    if ($s0) { $b = "llama-server PID $($s0.Id)" }
    else {
      foreach ($p in 9103, 9151) {
        $t = New-Object Net.Sockets.TcpClient
        try { $t.Connect('127.0.0.1', $p); if ($?) { $b = "port $p busy" } } catch { } finally { $t.Close() }
      }
    }
    if (-not $b) { break }
    Info "waiting for GPU: $b"
    Start-Sleep -Seconds 300
  }
  if ($b) { Record 'night:blocked' $b 'string' @{}; Info "still blocked after 90 min - recorded, exiting"; Stop-Transcript | Out-Null; exit 0 }
  Info 'GPU clear - starting slices'
}

# ---- schedule ----
$slices = @()
if ($ForceSlice) { $slices = @($ForceSlice) }
else {
  switch ($DayIndex) {
    1  { $slices = @('Baseline', 'Sweep', 'Bandwidth') }
    2  { $slices = @('Bandwidth', 'TypeMatrix-q4_0', 'RGP', 'MTPLean') }
    3  { $slices = @('RGP', 'TypeMatrix-tq2_0') }
    4  { $slices = @('TypeMatrix-ptq1_0') }
    5  { $slices = @('TypeMatrix-q4_0', 'TypeMatrix-tq2_0') }
    6  { $slices = @('ConfigAxes') }
    7  { $slices = @('Baseline') }
    8  { $slices = @('SpecDecode') }
    9  { $slices = @('SpecDecode') }
    10 { $slices = @('LongContext') }
    11 { $slices = @('Workload') }
    12 { $slices = @('TypeMatrix-tq2_0', 'TypeMatrix-ptq1_0') }
    13 { $slices = @('ConfigAxes', 'Bandwidth') }
    14 { $slices = @('GapFill') }
    15 { $slices = @('Baseline', 'TypeMatrix-q4_0') }
    16 { $slices = @('RGP') }
    17 { $slices = @('GapFill') }
    18 { $slices = @('SpecDecode') }
    19 { $slices = @('LongContext') }
    20 { $slices = @('GapFill') }
    21 { $slices = @('Compile') }
    22 { $slices = @('Premortem') }
    23 { $slices = @('Compile', 'Premortem') }
    default { $slices = @('GapFill') }
  }
}
$s = (Get-Date).TimeOfDay
foreach ($sl in $slices) {
  if (-not $AllowDay -and ((Get-Date).TimeOfDay -ge [TimeSpan]::FromHours(7)) -and ((Get-Date).TimeOfDay -lt [TimeSpan]::FromHours(20))) { Info 'daytime (07:00-20:00) - stopping to free the machine'; break }
  Info "=== SLICE $sl ==="
  switch -Wildcard ($sl) {
    'Baseline' { Baseline }
    'Sweep' { Sweep }
    'Bandwidth' { Bandwidth }
    'TypeMatrix-*' { TypeMatrix ($sl -replace 'TypeMatrix-', '') }
    'ConfigAxes' { ConfigAxes }
    'SpecDecode' { SpecDecode }
    'MTPLean' { MTPLean }
    'LongContext' { LongContext }
    'Workload' { Workload }
    'GapFill' { GapFill }
    'RGP' { RGP }
    'Compile' { Compile }
    'Premortem' { Premortem }
  }
}
Info 'campaign night complete'
Stop-Transcript | Out-Null
exit 0

