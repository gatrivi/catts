#Requires -Version 5.1
<#
.SYNOPSIS
  Queue of small autonomous tasks via Hermes + local LM Studio.
.PARAMETER Workdir
  Project cwd for tools and AGENTS.md discovery.
.PARAMETER MaxMinutes
  Stop after N minutes (0 = no limit).
#>
param(
    [string]$Workdir = 'e:\zengatrivi-drive-e\catts',
    [int]$MaxMinutes = 480,
    [string]$LogDir = ''
)

$ErrorActionPreference = 'Continue'
if (-not $LogDir) { $LogDir = Join-Path $Workdir 'logs\overnight' }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$profilePath = Join-Path $env:USERPROFILE 'Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1'
if (Test-Path $profilePath) { . $profilePath }

$tasks = @(
    'Lee docs/PROJECT_AUDIT.md. Escribe docs/OVERNIGHT_AUDIT.md con los 5 issues mas accionables y comandos para verificar cada uno.',
    'Corre scripts/check_env.py. Resume el output en docs/OVERNIGHT_ENV.md.',
    'Revisa README.md y CHANGELOG.md. Anota gaps obvios en docs/OVERNIGHT_DOCS.md (max 30 lineas).',
    'Busca TODO/FIXME en api/ y services/. Lista en docs/OVERNIGHT_TODOS.md con archivo:linea.'
)

$started = Get-Date
$i = 0
foreach ($prompt in $tasks) {
    $i++
    if ($MaxMinutes -gt 0 -and ((Get-Date) - $started).TotalMinutes -ge $MaxMinutes) {
        Write-Host "Time limit ($MaxMinutes min) reached."
        break
    }
    $log = Join-Path $LogDir ("task-$i-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
    Write-Host "[$i/$($tasks.Count)] $log"
    Push-Location $Workdir
    try {
        hermes -z $prompt --yolo --provider lmstudio -m ornith-1.0-9b 2>&1 | Tee-Object -FilePath $log
    } finally {
        Pop-Location
    }
    Start-Sleep -Seconds 30
}
Write-Host "Done. Logs: $LogDir"
