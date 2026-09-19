$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$desktop = [Environment]::GetFolderPath('Desktop')
$destination = Join-Path $desktop 'CATTS local.lnk'
if (Test-Path -LiteralPath $destination) { throw "Ya existe $destination; no se reemplazo." }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($destination)
$shortcut.TargetPath = Join-Path $root 'CATTS.cmd'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Un solo terminal: modelos locales y apps de CATTS'
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,137"
$shortcut.Save()
Write-Host "Creado: $destination"