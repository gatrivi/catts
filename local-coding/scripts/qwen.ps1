# One short entry point for the verified local Qwen Coder 7B.
[CmdletBinding()]
param(
  [switch]$ServerOnly,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$OmpArgs
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$port = 9100
$healthUrl = "http://127.0.0.1:$port/health"

function Test-QwenReady {
  try { return (Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3).status -eq 'ok' }
  catch { return $false }
}

if (-not (Test-QwenReady)) {
  $conflictingPorts = @(8080, 9099, 9101 | Where-Object {
    Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue
  })
  if ($conflictingPorts.Count) {
    throw "Qwen 7B needs the GPU alone. Active local workload port(s): $($conflictingPorts -join ', ')."
  }
  $launcher = Join-Path $PSScriptRoot 'start-qwen-coder.ps1'
  Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`"" `
    -WorkingDirectory $root -WindowStyle Hidden | Out-Null
  $deadline = (Get-Date).AddMinutes(4)
  do { Start-Sleep -Seconds 2 } until ((Test-QwenReady) -or ((Get-Date) -ge $deadline))
}

if (-not (Test-QwenReady)) { throw 'Qwen Coder 7B did not become ready on :9100.' }
Write-Host 'Qwen Coder 7B ready. Starting OMP local session.' -ForegroundColor Green
if ($ServerOnly) { exit 0 }

$omp = Join-Path $env:USERPROFILE '.bun\bin\omp.exe'
if (-not (Test-Path -LiteralPath $omp)) { throw "OMP not found: $omp" }
& $omp '--model' 'local-coder/Qwen2.5-Coder-7B-Instruct-Q3_M.gguf' @OmpArgs
exit $LASTEXITCODE
