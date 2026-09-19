$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$desktop = [Environment]::GetFolderPath('Desktop')
$destination = Join-Path $desktop 'Taller local.lnk'
if (Test-Path -LiteralPath $destination) { throw "Ya existe $destination; no se reemplazo." }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($destination)
$shortcut.TargetPath = Join-Path $root 'TALLER.cmd'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Programar sin suscripcion: Rosario o TMM'
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,21"
$shortcut.Save()
Write-Host "Creado: $destination"
