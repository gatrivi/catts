# Lift CATTS API (same as `npm start`)
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$hostName = if ($env:CATTS_API_HOST) { $env:CATTS_API_HOST } else { "0.0.0.0" }
$port = if ($env:CATTS_API_PORT) { $env:CATTS_API_PORT } else { "59200" }
Write-Host "CATTS API → http://127.0.0.1:$port/"
& "$Root\.venv\Scripts\python.exe" -m uvicorn api.main:app --host $hostName --port $port
