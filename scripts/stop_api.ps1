# Stop CATTS API on :59200 (uvicorn). Optional -Heavy kills STT/XTTS/Kokoro too.
param([switch]$Heavy)
$ErrorActionPreference = "SilentlyContinue"
$port = if ($env:CATTS_API_PORT) { [int]$env:CATTS_API_PORT } else { 59200 }
$killed = 0
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and (
    $_.CommandLine -match 'uvicorn.*api\.main' -or
    $_.CommandLine -match 'npm-start\.cjs' -or
    $_.CommandLine -match 'scripts\\start_api\.ps1'
  )
} | ForEach-Object {
  Write-Host "kill $($_.ProcessId)"
  Stop-Process -Id $_.ProcessId -Force
  $killed++
}
Get-NetTCPConnection -LocalPort $port -State Listen -EA SilentlyContinue | ForEach-Object {
  Stop-Process -Id $_.OwningProcess -Force -EA SilentlyContinue
}
Write-Host "api_stopped killed=$killed port=$port"
if ($Heavy) {
  & "$PSScriptRoot\kill_heavy.ps1"
}
