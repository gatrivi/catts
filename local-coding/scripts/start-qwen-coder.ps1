# Local coding tier. Q4/8K was load-tested; agent tool reliability is not established.
[CmdletBinding()]
param(
  [ValidateSet('Q3_M', 'Q4_K_M')][string]$Quant = 'Q3_M',
  [ValidateRange(1024, 16384)][int]$Context = 8192
)
$ErrorActionPreference = "Stop"
$exe = "Z:\models\runtime\llama-vulkan\llama-server.exe"
$model = "Z:\models\coding\Qwen2.5-Coder-7B-Instruct-$Quant.gguf"
if (-not (Test-Path -LiteralPath $exe)) { throw "Missing $exe" }
if (-not (Test-Path -LiteralPath $model)) { throw "Missing $model" }
$port = if ($env:QWEN_CODER_PORT) { [int]$env:QWEN_CODER_PORT } else { 9100 }
Write-Host "Qwen Coder 7B $Quant -> http://127.0.0.1:$port (RX 6600, $Context context)" -ForegroundColor Green
& $exe -m $model --host 127.0.0.1 --port $port -ngl 99 -fa on -c $Context -np 1 --device Vulkan1 --no-warmup --jinja -ctk q8_0 -ctv q8_0 --temp 0.2 --top-p 0.9
