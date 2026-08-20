# Keep CatTS reachable for Cursor Cloud Agents while away (no Termius).
# Starts: (1) API :59200  (2) My Machines worker  (3) anti-sleep
$ErrorActionPreference = "Continue"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$logDir = Join-Path $Root "data\cloud_agents"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Test-PortOpen([int]$Port) {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $iar = $c.BeginConnect("127.0.0.1", $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(800, $false)
    if (-not $ok) { $c.Close(); return $false }
    $c.EndConnect($iar); $c.Close(); return $true
  } catch { return $false }
}

powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change hibernate-timeout-ac 0 | Out-Null
powercfg /change monitor-timeout-ac 30 | Out-Null
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 2>$null
powercfg /SETACTIVE SCHEME_CURRENT 2>$null
Write-Host "power: AC sleep/hibernate off; lid=DoNothing"

if (-not (Test-PortOpen 59200)) {
  Write-Host "starting CatTS API :59200"
  $py = Join-Path $Root ".venv\Scripts\python.exe"
  Start-Process -FilePath $py -ArgumentList @(
    "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "59200"
  ) -WorkingDirectory $Root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "api.log") `
    -RedirectStandardError (Join-Path $logDir "api.err.log")
  $deadline = (Get-Date).AddSeconds(45)
  while ((Get-Date) -lt $deadline) {
    if (Test-PortOpen 59200) { break }
    Start-Sleep -Milliseconds 500
  }
} else {
  Write-Host "API already on :59200"
}

$workerRunning = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -match "agent\.cmd|cursor-agent.*index" -and $_.CommandLine -match "worker" }
# also match node running worker via agent CLI
if (-not $workerRunning) {
  $workerRunning = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match "start_cloud_worker" }
}
# Prefer checking worker.log freshness + agent debug; for boot: always try start if no recent log lock
$needWorker = $true
try {
  $dbg = & agent worker debug --json 2>$null | ConvertFrom-Json
  if ($dbg.visibilityProbe.privacy.totalCount -ge 1) { $needWorker = $false; Write-Host "worker already visible" }
} catch {}

# Multi-project workers (catbox-catts / rosario / catreader + legacy catboxprime)
$multi = $true
if ($env:CATTS_MULTI_WORKERS -eq "0") { $multi = $false }

if ($needWorker) {
  if ($multi) {
    Write-Host "starting multi-project Cursor workers"
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
      "-NoProfile", "-ExecutionPolicy", "Bypass",
      "-File", (Join-Path $Root "scripts\start_cloud_workers.ps1")
    ) -WorkingDirectory $Root -WindowStyle Hidden `
      -RedirectStandardOutput (Join-Path $logDir "workers_multi.log") `
      -RedirectStandardError (Join-Path $logDir "workers_multi.err.log")
  } else {
    Write-Host "starting Cursor My Machines worker (catboxprime)"
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
      "-NoProfile", "-ExecutionPolicy", "Bypass",
      "-File", (Join-Path $Root "scripts\start_cloud_worker.ps1")
    ) -WorkingDirectory $Root -WindowStyle Hidden `
      -RedirectStandardOutput (Join-Path $logDir "worker.log") `
      -RedirectStandardError (Join-Path $logDir "worker.err.log")
  }
} else {
  Write-Host "worker(s) already visible — skip start"
}

Start-Sleep -Seconds 2
try {
  $h = (Invoke-WebRequest -Uri "http://127.0.0.1:59200/health" -UseBasicParsing -TimeoutSec 8).Content
  Write-Host "API health: $h"
} catch {
  Write-Host "API health FAIL: $($_.Exception.Message)"
}
# Slack down-alert (optional): needs CATTS_SLACK_WEBHOOK_URL in .env
$slackWatch = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -match "watch_api_slack\.ps1" }
$hasSlack = $env:CATTS_SLACK_WEBHOOK_URL
if (-not $hasSlack -and (Test-Path "$Root\.env")) {
  $hasSlack = (Get-Content "$Root\.env" | Where-Object { $_ -match '^\s*CATTS_SLACK_WEBHOOK_URL\s*=\s*\S' } | Select-Object -First 1)
}
if ($hasSlack -and -not $slackWatch) {
  Write-Host "starting Slack API watchdog"
  Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $Root "scripts\watch_api_slack.ps1")
  ) -WorkingDirectory $Root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "slack_watch.log") `
    -RedirectStandardError (Join-Path $logDir "slack_watch.err.log")
} elseif (-not $hasSlack) {
  Write-Host "Slack watchdog skipped (set CATTS_SLACK_WEBHOOK_URL)"
}

Write-Host "Tailscale listen: http://100.87.252.18:59200/"
Write-Host "Voice hub HTTPS (mic): https://100.87.252.18:59200/static/talk.html  — run scripts\start_api_https.ps1"
Write-Host "Tailscale Serve (valid cert): enable https://login.tailscale.com/f/serve?node=na5746KeCj11CNTRL then: tailscale serve --bg 59200"
Write-Host "Web: https://cursor.com/agents  → catbox-catts | catbox-rosario | catbox-catreader (alias catboxprime)"
Write-Host "Logs: $logDir"

# Best-effort HTTPS proxy for phone mic (no-op if Serve not enabled on tailnet)
try {
  $serve = & tailscale serve status 2>$null
  if (-not $serve -or $serve -match "No serve config") {
    & tailscale serve --bg 59200 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Host "tailscale serve :59200 OK" }
    else { Write-Host "tailscale serve not enabled yet — use start_api_https.ps1 or enable Serve URL above" }
  } else {
    Write-Host "tailscale serve already configured"
  }
} catch {
  Write-Host "tailscale serve skipped: $($_.Exception.Message)"
}
