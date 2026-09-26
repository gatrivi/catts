# gpu_quiet_check.ps1 — dice si la GPU esta COMPARTIDA (medicion poco confiable).
# Por que: el usuario trabaja con videollamadas en MS Edge con aceleracion por
# hardware. Edge tiene un proceso GPU propio que usa el MISMO GPU que llama.cpp,
# y en esta máquina el contador '\GPU Engine(*)' NO existe (falla la API), o sea
# no se puede mirar la utilizacion barata. Queda el proxy: si hay un gpu-process
# de navegador vivo, cualquier numero de t/s de hoy es PROVISIONAL.
# Uso:  .\gpu_quiet_check.ps1            -> escribe QUIET|SHARED y sale 0|1
#       & $PSScriptRoot\gpu_quiet_check.ps1; if ($LASTEXITCODE) { 'no medir' }
# Sale 1 (SHARED) si hay navegador con gpu-process o alguien en el puerto 9103.
$ErrorActionPreference = 'Continue'

$browserGpu = @(Get-CimInstance Win32_Process `
    -Filter "Name='msedge.exe' OR Name='chrome.exe' OR Name='brave.exe' OR Name='vivaldi.exe'" `
    -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'gpu-process' })

$portBusy = $false
try {
    $s = New-Object System.Net.Sockets.TcpClient
    $portBusy = $s.ConnectAsync('127.0.0.1', 9103).Wait(250) -and $s.Connected
    $s.Close()
} catch { }

$reasons = @()
if ($browserGpu.Count -gt 0) { $reasons += "$($browserGpu.Count) proceso(s) GPU de navegador" }
if ($portBusy)               { $reasons += 'puerto 9103 ocupado' }

if ($reasons.Count -eq 0) {
    Write-Host 'QUIET'
    exit 0
}
Write-Host ("SHARED :: " + ($reasons -join ' | '))
Write-Host 'Los numeros tomados ahora son PROVISIONALES: Edge comparte el GPU y'
Write-Host 'deprime el brazo de 1 stream MAS que el de varios, o sea el ratio np'
Write-Host 'suele salir DISTORSIONADO (no solo mas bajo). Re-medir con Edge cerrado'
Write-Host 'o de noche. Para un ratio que vale, hacen falta 3 repeticiones.'
exit 1
