#Requires -Version 5.1
<#
  Wire omp to local Bonsai. Usage:
    .\scripts\setup-bonsai-omp.ps1
    .\scripts\setup-bonsai-omp.ps1 -AsDefault
    .\scripts\setup-bonsai-omp.ps1 -TestOnly
#>
param(
    [switch]$AsDefault,
    [switch]$TestOnly
)

$ErrorActionPreference = 'Stop'
$port = if ($env:BONSAI_PORT) { [int]$env:BONSAI_PORT } else { 9099 }
$baseUrl = "http://127.0.0.1:$port/v1"
$modelId = 'Bonsai-4B-Q1_0.gguf'
$ompDir = Join-Path $env:USERPROFILE '.omp\agent'
$modelsYml = Join-Path $ompDir 'models.yml'
$configYml = Join-Path $ompDir 'config.yml'
$bonsaiBlock = @"
  bonsai:
    baseUrl: $baseUrl
    api: openai-completions
    apiKey: local
    auth: none
    models:
      - id: $modelId
        name: Bonsai 4B
        contextWindow: 8192
        maxTokens: 2048
"@

[Environment]::SetEnvironmentVariable('BONSAI_PORT', "$port", 'User')
[Environment]::SetEnvironmentVariable('BONSAI_BASE_URL', $baseUrl, 'User')
$env:BONSAI_PORT = "$port"
$env:BONSAI_BASE_URL = $baseUrl

$omp = Join-Path $env:USERPROFILE '.bun\bin\omp.exe'
if (-not (Test-Path $omp)) {
    Write-Host 'Installing omp...' -ForegroundColor Yellow
    bun install -g @oh-my-pi/pi-coding-agent | Out-Null
}
if (-not (Test-Path $omp)) { throw 'omp missing - run: bun install -g @oh-my-pi/pi-coding-agent' }

try {
    $r = Invoke-RestMethod -Uri "$baseUrl/models" -TimeoutSec 8
    $ids = @($r.data | ForEach-Object { $_.id })
    if ($ids -notcontains $modelId) { throw "model $modelId not listed" }
    Write-Host "OK: Bonsai on :$port"
} catch {
    Write-Host "FAIL: Bonsai not up on :$port - run: npm run bonsai" -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}

if ($TestOnly) { exit 0 }

New-Item -ItemType Directory -Force -Path $ompDir | Out-Null
if (-not (Test-Path $modelsYml)) {
    Set-Content -Path $modelsYml -Value "# omp providers`nproviders:`n$bonsaiBlock`n" -Encoding utf8
} else {
    $raw = Get-Content $modelsYml -Raw
    $raw = $raw -replace '(?ms)^\s*bonsai:.*?(?=^\s{0,2}\w|\z)', ''
    if ($raw -notmatch '(?m)^providers:\s*$') { $raw = "providers:`n$raw" }
    Set-Content -Path $modelsYml -Value ($raw.TrimEnd() + "`n$bonsaiBlock`n") -Encoding utf8
}

if ($AsDefault) {
    if (-not (Test-Path $configYml)) {
        $cfg = "setupVersion: 1`nmodelRoles:`n  default: bonsai/" + $modelId + "`n  smol: bonsai/" + $modelId + "`n"
        Set-Content -Path $configYml -Value $cfg -Encoding utf8
    } else {
        $out = Get-Content $configYml | ForEach-Object {
            if ($_ -match '^\s*default:\s*') { return ('  default: bonsai/' + $modelId) }
            if ($_ -match '^\s*smol:\s*') { return ('  smol: bonsai/' + $modelId) }
            $_
        }
        Set-Content -Path $configYml -Value $out -Encoding utf8
    }
}

& $omp models find bonsai | Out-Host
Write-Host ''
Write-Host 'Ready: npm run bonsai  (window 1)  then  cd project  &&  omp  (window 2)'
