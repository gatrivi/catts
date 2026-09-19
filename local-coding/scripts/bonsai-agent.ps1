# ponytail: Cursor-like local agent via omp + Bonsai (chat/edit-light; full tools need LM Studio)
$ErrorActionPreference = 'Stop'
$omp = Join-Path $env:USERPROFILE '.bun\bin\omp.exe'
$model = 'bonsai/Bonsai-4B-Q1_0.gguf'
$port = if ($env:BONSAI_PORT) { $env:BONSAI_PORT } else { 9099 }

if (-not (Test-Path $omp)) {
    & (Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts\setup-bonsai-omp.ps1') -AsDefault | Out-Null
}
try {
    Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 3 | Out-Null
} catch {
    Write-Host "Start Bonsai first: npm run bonsai" -ForegroundColor Red
    exit 1
}

# 4B ctx cap: omp tool schemas ~18k tokens — use --no-tools on Bonsai; LM Studio for full agent.
$ompArgs = @('--model', $model, '--no-tools')
if ($args.Count -gt 0) { & $omp @ompArgs @args } else { & $omp @ompArgs }
