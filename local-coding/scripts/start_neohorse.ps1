# NeoHorse 4B launcher (fast router, ~36 tok/s) - port 9107.
$ErrorActionPreference = "Stop"
$exe = 'Z:\Models\runtime\llama-vulkan-b10964\llama-server.exe'
$model = 'Z:\catts\local-coding\data\models\neohorse14b-q8\NeoHorse-1-4B-Q8_0.gguf'
$port = 9107
if (-not (Test-Path $exe)) { throw "Missing $exe" }
if (-not (Test-Path $model)) { throw "Missing $model" }
Write-Host "NeoHorse 4B -> http://127.0.0.1:$port" -ForegroundColor Green
Write-Host "Close other model servers first (GPU exclusive). Ctrl+C stops." -ForegroundColor Yellow
& $exe -m $model --host 127.0.0.1 --port $port --alias neohorse --device Vulkan1 -ngl 99 -c 16384 -np 1 -ctk q8_0 -ctv q8_0 -fa on --jinja --no-warmup --temp 0.5 --top-p 0.85 --top-k 20
