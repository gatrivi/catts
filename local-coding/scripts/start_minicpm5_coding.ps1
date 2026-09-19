# MiniCPM5-2B Q8 long-context coding server, hand-use launcher (RX 6600 8GB / 16GB RAM rig).
# Native context 131072 (GGUF-verified). Fully offloaded: ~2.5 GB weights + q8 KV at 131K
# fits 8 GB VRAM ALONE - close other model servers (e.g. the :8123 Qwen3.5-9B, ~5.4 GiB)
# before starting, or lower -c to 65536. Earlier measured on this rig: 48-60 tok/s decode.
# Port 9104 (9102 TALLER, 9103 BONSAI2 in use patterns). OpenAI API at http://127.0.0.1:9104/v1
$ErrorActionPreference = "Stop"
$exe = 'Z:\Models\runtime\llama-vulkan\llama-server.exe'
$model = 'Z:\catts\local-coding\data\models\minicpm5-2b-q8\MiniCPM5-2B-Q8_0.gguf'
$port = if ($env:MINICPM5_PORT) { [int]$env:MINICPM5_PORT } else { 9104 }
if (-not (Test-Path $exe)) { throw "Missing $exe" }
if (-not (Test-Path $model)) { throw "Missing $model" }
$mem = Get-CimInstance Win32_OperatingSystem
$freeGB = [math]::Round($mem.FreePhysicalMemory * 1KB / 1GB, 1)
if ($freeGB -lt 3) { throw "Only $freeGB GB free RAM (need ~3 GB floor)" }
try {
  $used = (Get-Counter '\GPU Memory(*)\ Dedicated Usage' -ErrorAction Stop).CounterSamples |
    Where-Object { $_.InstanceName -notmatch '^idp' -and $_.CookedValue -gt 1MB } |
    Measure-Object CookedValue -Sum
  if ($used.Sum) {
    $freeVRAM = [math]::Round(8 - $used.Sum / 1GB, 2)
    if ($freeVRAM -lt 6.5) {
      Write-Host "WARNING: only ~$freeVRAM GB VRAM free; 131K ctx needs ~7 GB. Close other model servers (e.g. :8123 Qwen3.5-9B) or lower -c to 65536." -ForegroundColor Red
    }
  }
} catch { } # VRAM counter unavailable: skip advisory
Write-Host "MiniCPM5-2B Q8 (131K ctx coding) -> http://127.0.0.1:$port" -ForegroundColor Green
Write-Host "If VRAM OOM: close other model servers, or edit -c down to 65536." -ForegroundColor Yellow
Write-Host "Ctrl+C to stop." -ForegroundColor Yellow
& $exe -m $model --host 127.0.0.1 --port $port --alias minicpm5-coding -ngl 99 -c 131072 -np 1 `
    -ctk q8_0 -ctv q8_0 -fa on --jinja --no-warmup -b 512 -ub 256 `
    --chat-template-kwargs '{"enable_thinking":false}' `
    --temp 0.2 --top-p 0.9 --top-k 40
