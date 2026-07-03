$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { py -3 -m venv .venv }
$py = ".\.venv\Scripts\python.exe"

& $py -m pip install --upgrade pip
& $py -m pip install faster-whisper argostranslate python-docx

Write-Host "Installing Argos EN-ES language packs..."
& $py -c @"
import argostranslate.package
argostranslate.package.update_package_index()
for fc, tc in [('en','es'),('es','en')]:
    pkgs = argostranslate.package.get_available_packages()
    pkg = next(p for p in pkgs if p.from_code==fc and p.to_code==tc)
    argostranslate.package.install_from_path(pkg.download())
    print('installed', fc, '->', tc)
"@

Write-Host "STT ready. Restart CATTS API."
