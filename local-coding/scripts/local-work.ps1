param(
    [Parameter(Mandatory=$true)][string]$Project,
    [switch]$Print,
    [string]$Prompt,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$agent = Join-Path $env:USERPROFILE '.bun\bin\omp.exe'
if (-not (Test-Path -LiteralPath $agent)) { throw 'OMP missing.' }
if (-not (Test-Path -LiteralPath $Project -PathType Container)) { throw 'Project folder missing.' }
if ($CheckOnly) {
    foreach ($path in @('E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe', (Join-Path $root 'scripts\local_advisor.py'), (Join-Path $root 'config\local-omp\models.yml'), (Join-Path $root 'config\local-omp\config.yml'))) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Missing: $path" }
    }
    Write-Host 'OK: editor dependencies found; no model started or profile modified.'
    exit 0
}
try {
    $health = Invoke-RestMethod 'http://127.0.0.1:9102/health' -TimeoutSec 3
    if ($health.status -ne 'ok') { throw 'Not ready' }
} catch { throw 'Start npm.cmd run qwen35 in CATTS and wait for READY first.' }
$previous = $env:PI_CODING_AGENT_DIR
try {
    $env:PI_CODING_AGENT_DIR = 'E:\zengatrivi-drive-e\catts\data\local-omp'
    New-Item -ItemType Directory -Force -Path $env:PI_CODING_AGENT_DIR | Out-Null
    # models.yml se refresca siempre (contexto/maxTokens viven en el repo); config.yml solo si falta.
    Copy-Item -LiteralPath (Join-Path $root 'config\local-omp\models.yml') -Destination (Join-Path $env:PI_CODING_AGENT_DIR 'models.yml') -Force
    $configDestination = Join-Path $env:PI_CODING_AGENT_DIR 'config.yml'
    if (-not (Test-Path -LiteralPath $configDestination)) {
        Copy-Item -LiteralPath (Join-Path $root 'config\local-omp\config.yml') -Destination $configDestination
    }
    $arguments = @('--cwd', (Resolve-Path -LiteralPath $Project).Path,
        '--model', 'taller/qwen35-local', '--smol', 'taller/qwen35-local',
        '--slow', 'taller/qwen35-local', '--plan', 'taller/qwen35-local',
        '--config', (Join-Path $root 'config\local-omp\limits.json'),
        '--thinking', 'off', '--no-title', '--no-extensions', '--no-skills',
        '--no-lsp', '--no-pty', '--tools', 'read,edit,write,grep,glob',
        '--approval-mode', 'write', '--max-time', '10m',
        '--system-prompt', 'You are a local coding assistant working inside the user''s project with tools. Read project instructions before editing. When the user asks for a change, make it now: read the file with the read tool, then apply it with the edit tool in this same turn. Never answer with instructions or code for the user to paste; the edit is your answer. Work on one small task; make exactly the requested change and preserve unrelated changes. No shell tool is available: give the user the exact test command to run. Never claim a test passed unless its output was provided. If a tool call fails twice the same way, stop and explain what failed. Keep answers concise. Save important task context to TASK.md when requested.')
    if ($Print) { $arguments += '-p' }
    $notePath = & 'E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe' (Join-Path $root 'scripts\local_advisor.py') --project $Project --note-path
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $notePath)) {
        $note = Get-Content -LiteralPath $notePath -Raw -Encoding UTF8
        if ($note.Length -le 6000) {
            $arguments += @('--append-system-prompt', "Previous local consultant notes, not verified facts. Check against current source before using:`n$note")
            Write-Host 'Nota del consultor local incluida para este proyecto.'
        } else {
            Write-Host "Nota demasiado larga para incluir automaticamente. Podes leerla en: $notePath"
        }
    }
    if ($Prompt) { $arguments += $Prompt }
    & $agent @arguments
    $result = $LASTEXITCODE
} finally { $env:PI_CODING_AGENT_DIR = $previous }
exit $result
