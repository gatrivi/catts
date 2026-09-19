# Bonsai-2 27B TQ2_0 launcher (RX 6600 / 16 GB RAM rig) - UPDATED 2026-09-18.
# TQ2_0 uses the fork's fast ternary Vulkan kernel (~1080 GFLOPS) vs PTQ1_0's broken
# ptq1_0 kernel (~195 GFLOPS). Measured GPU-exclusive: decode 12-13 tok/s (was 3.3),
# quality probes PASS (toCents + trace-find_dup both correct).
# REQUIREMENTS: GPU exclusive - stop other VRAM users (Spark/Qwen/MiniCPM) first,
# else layers spill to CPU and speed collapses to <1 tok/s. Load ~85 s warm / ~140 s cold.
# 100K ctx does NOT pay off (KV pushes weights off GPU -> 3.2 tok/s); keep -c 8192.
$ErrorActionPreference = "Stop"
$exe = 'Z:\Models\runtime\llama-prism-b10685-vulkan\llama-server.exe'
$model = 'Z:\catts\local-coding\data\models\bonsai2-27b-tq2_0\Ternary-Bonsai-2-27B-TQ2_0.gguf'
$port = if ($env:BONSAI2_PORT) { [int]$env:BONSAI2_PORT } else { 9103 }
if (-not (Test-Path $exe)) { throw "Missing $exe" }
if (-not (Test-Path $model)) { throw "Missing $model" }
$mem = Get-CimInstance Win32_OperatingSystem
$freeGB = [math]::Round($mem.FreePhysicalMemory * 1KB / 1GB, 1)
if ($freeGB -lt 3) { throw "Only $freeGB GB free RAM (need ~3 GB floor)" }
Write-Host "Bonsai-2 27B TQ2_0 -> http://127.0.0.1:$port" -ForegroundColor Green
Write-Host "Load ~85-140 s. Decode ~12-13 tok/s (GPU exclusive)." -ForegroundColor Yellow
Write-Host "Ctrl+C to stop." -ForegroundColor Yellow
& $exe -m $model --host 127.0.0.1 --port $port --alias bonsai2 --device Vulkan1 -ngl 99 -c 8192 -np 1 `
    -ctk q8_0 -ctv q8_0 -fa on --jinja --no-warmup -b 256 -ub 128 `
    --temp 0.6 --top-p 0.95 --top-k 20
