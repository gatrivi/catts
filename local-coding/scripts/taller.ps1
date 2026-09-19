param([switch]$CheckOnly, [switch]$SmokeTest, [switch]$Expert)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = 'E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe'
$serverScript = Join-Path $root 'scripts\qwen35_local.py'
$reactRoot = 'C:\zengatrivi\REACTJS'
$projects = [ordered]@{}
$folders = @('C:\zengatrivi\REACTJS\rosario-cards-v1', 'C:\zengatrivi\REACTJS\trufi-tmm', $root)
if (Test-Path -LiteralPath $reactRoot) {
    $folders += @(Get-ChildItem -LiteralPath $reactRoot -Directory |
        Where-Object { -not $_.Name.StartsWith('.') } |
        Sort-Object Name | Select-Object -ExpandProperty FullName)
}
foreach ($folder in ($folders | Select-Object -Unique)) {
    if (Test-Path -LiteralPath $folder -PathType Container) {
        $projects.Add([string]($projects.Count + 1), $folder)
    }
}
function Test-Ready([int]$Port = 9102) {
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2
        return $health.status -eq 'ok'
    } catch { return $false }
}
if ($CheckOnly) {
    foreach ($path in @($python, $serverScript, (Join-Path $root 'scripts\local-work.ps1')) + @($projects.Values)) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Falta: $path" }
    }
    Write-Host 'OK: proyectos y herramientas encontrados.'
    foreach ($entry in $projects.GetEnumerator()) { Write-Host "$($entry.Key)  $($entry.Value)" }
    exit 0
}
while ($true) {
$owned = $null
$expertMode = $false
try {
    Write-Host "`n  TALLER LOCAL - sin suscripcion de IA`n" -ForegroundColor Cyan
    foreach ($entry in $projects.GetEnumerator()) {
        Write-Host ('  {0,2}  {1}' -f $entry.Key, (Split-Path $entry.Value -Leaf))
    }
    Write-Host "`n  O  Otra carpeta (selector de Windows, tambien Z:)"
    Write-Host '  A  Apagar modelo local'
    Write-Host '  H  Ayuda breve'
    Write-Host '  0  Salir'
    $choice = if ($SmokeTest) { '1' } else { (Read-Host "`nElegi numero o letra").Trim().ToUpperInvariant() }
    if ($choice -eq '0') { return }
    if ($choice -eq 'A') { & $python $serverScript --stop; & $python $serverScript --expert --stop; continue }
    if ($choice -eq 'H') { Get-Content (Join-Path $root 'TRABAJAR_SIN_PLAN.txt'); continue }
    if ($choice -eq 'O') {
        Add-Type -AssemblyName System.Windows.Forms
        $picker = New-Object System.Windows.Forms.FolderBrowserDialog
        try {
            $picker.Description = 'Elegi la carpeta del proyecto'
            $picker.SelectedPath = $reactRoot
            $picker.ShowNewFolderButton = $false
            if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { continue }
            $project = $picker.SelectedPath
        } finally { $picker.Dispose() }
    } else {
        if (-not $projects.Contains($choice)) { throw 'Elegi un numero de la lista, O, A, H o 0.' }
        $project = $projects[$choice]
    }
    if (-not (Test-Path -LiteralPath $project -PathType Container)) { throw "No encuentro $project" }
    if ($SmokeTest) { $expertMode = [bool]$Expert } else {
        Write-Host "`n1  Editor 9B (rapido, edita archivos)"
        Write-Host '2  Consultor 27B (lento, diagnostico y plan guardado para el editor)'
        Write-Host '3  Tarea (experimental): plan 27B -> Bonsai 4B -> pruebas -> revision 27B'
        $mode = (Read-Host 'Modo [Enter = 1]').Trim()
        if ($mode -notin @('', '1', '2', '3')) { throw 'Elegi modo 1, 2 o 3.' }
        if ($mode -eq '3') {
            Push-Location -LiteralPath $root
            try { & $python -m scripts.local_task --project $project }
            finally { Pop-Location }
            continue
        }
        $expertMode = $mode -eq '2'
    }
    $port = if ($expertMode) { 9101 } else { 9102 }
    $alias = if ($expertMode) { 'qwen27-local' } else { 'qwen35-local' }
    if (-not (Test-Ready -Port $port)) {
        Write-Host "`nCargando modelo (puede tardar 2 minutos). Espera aca..." -ForegroundColor Yellow
        $log = Join-Path $root 'data\taller-start'
        $serverArgs = @($serverScript, '--owner-pid', "$PID")
        if ($expertMode) { $serverArgs += '--expert' }
        $owned = Start-Process -FilePath $python -ArgumentList $serverArgs `
            -WorkingDirectory $root -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput "$log.out.log" -RedirectStandardError "$log.err.log"
        $deadline = (Get-Date).AddSeconds(300)
        while (-not (Test-Ready -Port $port)) {
            if ($owned.HasExited) { throw (Get-Content "$log.err.log" -Raw) }
            if ((Get-Date) -gt $deadline) { throw 'La carga tardo demasiado. Revisa data\taller-start.err.log.' }
            Start-Sleep -Seconds 2
        }
    }
    $models = Invoke-RestMethod "http://127.0.0.1:$port/v1/models" -TimeoutSec 3
    if (@($models.data.id) -notcontains $alias) { throw 'El puerto tiene otro modelo. No lo voy a usar.' }
    if ($SmokeTest) {
        if ($expertMode) {
            & $python (Join-Path $root 'scripts\local_advisor.py') --project (Join-Path $root 'data\local-react-proof') --question 'Un boton React dentro de un form envia el formulario al pulsarlo aunque solo deberia abrir un modal. Explica la causa y el cambio minimo en tres frases.' --max-tokens 160
            if ($LASTEXITCODE -ne 0) { throw 'Fallo la consulta de prueba.' }
        }
        Write-Host 'OK: arranque automatico y modelo local verificados.'; return
    }
    Write-Host "`nListo. Pedi un cambio pequeno e indica el archivo." -ForegroundColor Green
    Write-Host "Proyecto: $project"
    Write-Host 'Usa /exit para volver al menu y elegir otro proyecto.'
    if ($expertMode) {
        & $python (Join-Path $root 'scripts\local_advisor.py') --project $project
    } else {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\local-work.ps1') -Project $project
    }
} catch {
    Write-Host "`nNo se pudo continuar: $_" -ForegroundColor Red
    if ($SmokeTest) { throw }
} finally {
    if ($null -ne $owned -and -not $owned.HasExited) {
        if ($expertMode) { & $python $serverScript --expert --stop } else { & $python $serverScript --stop }
        $null = $owned.WaitForExit(15000)
    }
}
}
