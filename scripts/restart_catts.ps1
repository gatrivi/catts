$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
& npm.cmd stop
Start-Sleep -Seconds 2
& npm.cmd start
Start-Sleep -Seconds 5
& npm.cmd run tts:status
