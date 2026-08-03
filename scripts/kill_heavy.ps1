# Kill CATTS heavy workers (XTTS/STT/Fish/Kokoro/Madlad). Keeps nothing hot.
# Usage: .\scripts\kill_heavy.ps1
$ErrorActionPreference = "SilentlyContinue"
$patterns = @(
    "xtts_worker.py",
    "stt_worker.py",
    "translate_madlad_worker.py",
    "kokoro_server.py",
    "tools\\api_server.py",
    "tools\\run_webui.py",
    "fish-speech-zluda"
)
$killed = 0
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | ForEach-Object {
    $cmd = $_.CommandLine
    if (-not $cmd) { return }
    foreach ($p in $patterns) {
        if ($cmd -like "*$p*") {
            Write-Host "kill $($_.ProcessId) $p"
            Stop-Process -Id $_.ProcessId -Force
            $killed++
            break
        }
    }
}
Write-Host "killed=$killed"
# Optional: stop CATTS API too
# Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*uvicorn*api.main*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
