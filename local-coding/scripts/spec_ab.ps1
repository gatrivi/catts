param(
  [string]$Model = 'Z:\catts\local-coding\data\models\bonsai2-27b-ptq10-mtp\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf',
  [string]$Out = 'Z:\catts\local-coding\data\spec_ab_20260926.json',
  [int]$Runs = 3,
  [int]$NPredict = 256
)
$ErrorActionPreference = 'Continue'
$env:PATH = 'C:\tools\llvm-mingw\bin;' + $env:PATH
$exe = 'C:\src\llama.cpp\build\bin\llama-server.exe'
$prompt = 'Write a detailed paragraph about the history of the abacus.'
$rows = @()

function Wait-Ready($proc, $log, $timeoutSec) {
  $t0 = Get-Date
  while (((Get-Date) - $t0).TotalSeconds -lt $timeoutSec) {
    if (Test-Path $log) {
      $c = Get-Content $log -Raw -ErrorAction SilentlyContinue
      if ($c -match 'listening on') { return $true }
      if ($c -match 'Hadamard|error loading model|failed to load') { return $false }
    }
    if ($proc.HasExited) { return $false }
    Start-Sleep -Seconds 2
  }
  return $false
}

foreach ($arm in @('base','draft')) {
  $port = if ($arm -eq 'base') { 9201 } else { 9202 }
  $log  = "$env:TEMP\ab_$arm.err.log"
  Remove-Item $log -ErrorAction SilentlyContinue
  $argl = @('-m', $Model, '-ngl', '99', '-c', '8192', '--port', "$port")
  if ($arm -eq 'draft') { $argl += @('--spec-type','draft-mtp','--spec-draft-n-max','2') }
  $srv = Start-Process -FilePath $exe -ArgumentList $argl -RedirectStandardOutput "$env:TEMP\ab_$arm.out.log" -RedirectStandardError $log -WindowStyle Hidden -PassThru
  $ok = Wait-Ready $srv $log 300
  if (-not $ok) {
    $rows += [pscustomobject]@{ arm = $arm; run = 0; error = 'server no arrancó'; log = (Get-Content $log -Tail 5 -ErrorAction SilentlyContinue) }
    if (-not $srv.HasExited) { Stop-Process -Id $srv.Id -Force }
    continue
  }
  for ($i = 1; $i -le $Runs; $i++) {
    try {
      $body = @{ prompt = $prompt; n_predict = $NPredict; temperature = 0; seed = 42 } | ConvertTo-Json
      $r = Invoke-RestMethod -Uri "http://127.0.0.1:$port/completion" -Method Post -Body $body -TimeoutSec 600
      $rows += [pscustomobject]@{
        arm = $arm; run = $i
        predicted_n      = $r.timings.predicted_n
        tps_predicted     = [math]::Round($r.timings.predicted_per_second, 3)
        tps_prompt        = [math]::Round($r.timings.prompt_per_second, 3)
        predicted_ms     = $r.timings.predicted_ms
        drafted_n        = $r.timings.drafted_n
        n_draft_accepted = $r.timings.n_draft_accepted
        draft_accept_pct = if ($r.timings.drafted_n) { [math]::Round(100 * $r.timings.n_draft_accepted / $r.timings.drafted_n, 1) } else { $null }
        error = $null
      }
    } catch {
      $rows += [pscustomobject]@{ arm = $arm; run = $i; error = $_.Exception.Message }
    }
    $rows | ConvertTo-Json -Depth 5 | Set-Content -Path $Out -Encoding UTF8
  }
  if (-not $srv.HasExited) { Stop-Process -Id $srv.Id -Force }
  Start-Sleep -Seconds 5
}
$rows | ConvertTo-Json -Depth 5 | Set-Content -Path $Out -Encoding UTF8
'AB-DONE'
