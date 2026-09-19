# ponytail: RX 6600-safe Bonsai start (stock demo OOMs with -c 0 / 4 slots)
$ErrorActionPreference = "Stop"
$d = "E:\zengatrivi-drive-e\catts\external\Bonsai-demo"
$recovered = "Z:\models\external\Bonsai-demo"
$localExe = Join-Path $d "bin\vulkan\llama-server.exe"
$localModel = Join-Path $d "models\gguf\4B\Bonsai-4B-Q1_0.gguf"
if (-not ((Test-Path $localExe) -and (Test-Path $localModel))) {
  $d = $recovered
}
$exe = Join-Path $d "bin\vulkan\llama-server.exe"
$model = Join-Path $d "models\gguf\4B\Bonsai-4B-Q1_0.gguf"
if (-not (Test-Path $exe)) { throw "Missing $exe" }
if (-not (Test-Path $model)) { throw "Missing $model" }
$port = if ($env:BONSAI_PORT) { [int]$env:BONSAI_PORT } else { 9099 }
Write-Host "Bonsai → http://127.0.0.1:$port  (leave this window open; Ctrl+C to stop)" -ForegroundColor Green
& $exe -m $model --host 127.0.0.1 --port $port -ngl 99 -fa on -c 8192 -np 1 --device Vulkan1 --temp 0.5 --top-p 0.85 --top-k 20 --reasoning off
