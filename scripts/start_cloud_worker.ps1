# My Machines worker — Cloud Agents (web) execute TTS/audiobook tools on this PC.
# Docs: docs/CLOUD_AGENTS.md · https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines
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

$name = if ($env:CURSOR_WORKER_NAME) { $env:CURSOR_WORKER_NAME } else { "catboxprime" }
Write-Host "Cursor My Machines worker → name=$name cwd=$Root"
& $agentCmd worker start --name $name --worker-dir $Root
