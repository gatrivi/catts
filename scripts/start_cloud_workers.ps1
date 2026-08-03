# Start three Cursor My Machines workers (one cwd per project).
# Docs: docs/PHONE_VOICE_HUB.md · docs/CLOUD_AGENTS.md
param(
  [switch]$SkipCattsAlias  # do not also start legacy catboxprime
)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$agent = Get-Command agent -ErrorAction SilentlyContinue
if (-not $agent) {
  $fallback = Join-Path $env:LOCALAPPDATA "cursor-agent\agent.cmd"
  if (Test-Path $fallback) { $agentCmd = $fallback }
  else { throw "agent CLI missing. Install: irm 'https://cursor.com/install?win32=true' | iex" }
} else {
  $agentCmd = $agent.Source
}

$regPath = Join-Path $Root "data\voice_projects.json"
if (-not (Test-Path $regPath)) { throw "missing $regPath" }
$reg = Get-Content $regPath -Raw | ConvertFrom-Json

$logDir = Join-Path $Root "data\cloud_agents"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Start-NamedWorker([string]$Name, [string]$WorkerDir) {
  if (-not (Test-Path $WorkerDir)) {
    Write-Host "SKIP $Name — cwd missing: $WorkerDir"
    return
  }
  Write-Host "worker → name=$Name cwd=$WorkerDir"
  $safe = ($Name -replace '[^a-zA-Z0-9_-]', '_')
  Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-Command",
    "Set-Location '$WorkerDir'; & '$agentCmd' worker start --name '$Name' --worker-dir '$WorkerDir'"
  ) -WorkingDirectory $WorkerDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "worker_$safe.log") `
    -RedirectStandardError (Join-Path $logDir "worker_$safe.err.log")
}

foreach ($p in $reg.projects) {
  Start-NamedWorker -Name $p.worker -WorkerDir $p.cwd
}

if (-not $SkipCattsAlias) {
  # backward compat: catboxprime → catts cwd
  $catts = $reg.projects | Where-Object { $_.id -eq "catts" } | Select-Object -First 1
  if ($catts) {
    Start-NamedWorker -Name "catboxprime" -WorkerDir $catts.cwd
  }
}

Write-Host "Workers launching. Phone: https://cursor.com/agents → catbox-catts | catbox-rosario | catbox-catreader"
Write-Host "Voice hub: http://100.87.252.18:59200/static/talk.html"
