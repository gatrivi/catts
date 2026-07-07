#Requires -Version 5.1
<#
.SYNOPSIS
  Guarda el token LM Studio en ~/.secrets/lm-api-token (NO pegues el token en este archivo).

.USAGE
  .\scripts\setup-lmstudio.ps1 -FromClipboard   # copia token en LM Studio, corre esto
  .\scripts\setup-lmstudio.ps1 -Token "..."      # o pasarlo por parametro
  .\scripts\setup-lmstudio.ps1 -TestOnly        # probar / reparar token guardado
#>
param(
    [string]$Token = '',
    [switch]$FromClipboard,
    [switch]$TestOnly
)

$ErrorActionPreference = 'Stop'
$secretsDir = Join-Path $env:USERPROFILE '.secrets'
$tokenFile = Join-Path $secretsDir 'lm-api-token'
$baseUrl = 'http://127.0.0.1:42/v1'

function Normalize-LmToken([string]$Raw) {
    if (-not $Raw) { return '' }
    return ($Raw -replace '[\x00-\x1F\x7F]', '').Trim()
}

function Get-LmToken {
    if ($Token) { return Normalize-LmToken $Token }
    if (Test-Path $tokenFile) { return Normalize-LmToken (Get-Content $tokenFile -Raw) }
    if ($env:LM_API_KEY) { return Normalize-LmToken $env:LM_API_KEY }
    return $null
}

function Save-LmToken([string]$Value) {
    $clean = Normalize-LmToken $Value
    if (-not $clean) { throw 'Empty token' }
    New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null
    Set-Content -Path $tokenFile -Value $clean -NoNewline -Encoding utf8
    [Environment]::SetEnvironmentVariable('LM_API_KEY', $clean, 'User')
    [Environment]::SetEnvironmentVariable('LM_STUDIO_API_KEY', $clean, 'User')
    [Environment]::SetEnvironmentVariable('LM_BASE_URL', $baseUrl, 'User')
    [Environment]::SetEnvironmentVariable('LM_STUDIO_BASE_URL', $baseUrl, 'User')
    $env:LM_API_KEY = $clean
    $env:LM_STUDIO_API_KEY = $clean
    $env:LM_BASE_URL = $baseUrl
    $env:LM_STUDIO_BASE_URL = $baseUrl
    $hermesEnv = Join-Path $env:LOCALAPPDATA 'hermes\.env'
    if (Test-Path $hermesEnv) {
        $lines = Get-Content $hermesEnv | Where-Object { $_ -notmatch '^(LM_API_KEY|LM_BASE_URL)=' }
        $lines += "LM_API_KEY=$clean"
        $lines += "LM_STUDIO_API_KEY=$clean"
        $lines += "LM_BASE_URL=$baseUrl"
        $lines += "LM_STUDIO_BASE_URL=$baseUrl"
        Set-Content -Path $hermesEnv -Value $lines -Encoding utf8
    }
    return $clean
}

function Test-LmStudio {
    param([string]$Bearer)
    if (-not $Bearer) {
        Write-Host "FAIL: no token. Save to $tokenFile or pass -Token" -ForegroundColor Red
        return $false
    }
    try {
        $r = Invoke-RestMethod -Uri "$baseUrl/models" -Headers @{ Authorization = "Bearer $Bearer" } -TimeoutSec 10
        $ids = @($r.data | ForEach-Object { $_.id })
        Write-Host "OK: LM Studio reachable. Models: $($ids -join ', ')"
        return $true
    } catch {
        Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

if ($TestOnly) {
    if (Test-Path $tokenFile) {
        $clean = Save-LmToken (Get-Content $tokenFile -Raw)
        Write-Host "Repaired token file + env"
    }
    exit $(if (Test-LmStudio (Get-LmToken)) { 0 } else { 1 })
}

if (-not $Token) {
    if ($FromClipboard) {
        $Token = Get-Clipboard -Raw -ErrorAction SilentlyContinue
        if (-not $Token) { throw 'Portapapeles vacio. Copia el token en LM Studio primero.' }
        Write-Host 'Token leido del portapapeles.'
    } else {
        Write-Host 'Copia el token en LM Studio, luego:'
        Write-Host '  Enter solo = usar portapapeles (recomendado; Ctrl+V no funciona aqui)'
        Write-Host '  o click derecho para pegar en la linea'
        $input = Read-Host 'Token'
        if (-not $input -or $input -eq '^V') {
            $input = Get-Clipboard -Raw -ErrorAction SilentlyContinue
            if ($input) { Write-Host 'Token leido del portapapeles.' }
        }
        $Token = $input
    }
}
$clean = Save-LmToken $Token
Write-Host "Saved: $tokenFile"

if (-not (Test-LmStudio $clean)) { exit 1 }

Write-Host ''
Write-Host 'Test omp:'
Write-Host '  omp -p --model ornith-1.0-9b --auto-approve "di hola en una palabra"'
Write-Host 'Test hermes:'
Write-Host '  hermes -z "di hola" --yolo --provider lmstudio -m ornith-1.0-9b'
