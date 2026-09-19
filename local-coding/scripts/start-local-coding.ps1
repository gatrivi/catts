# Start one model; qwen.ps1 checks competing GPU workloads before launch.
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'qwen.ps1') -ServerOnly
exit $LASTEXITCODE
