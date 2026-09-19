# Qwen3.8 27B Q3-DOWN-XS on RX 6600.  It deliberately owns the GPU by itself.
[CmdletBinding()]
param(
  [int]$Port = 9101,
  [ValidateRange(1024, 32768)][int]$Context = 16384,
  [switch]$AllowCompetingGpu
)

$ErrorActionPreference = 'Stop'
$exe = 'Z:\models\runtime\llama-vulkan\llama-server.exe'
$model = 'Z:\models\coding\Qwen3.8-27B-Q3-DOWN-XS\Qwen3.8-27B-Q3-DOWN-XS.gguf'

if (-not (Test-Path -LiteralPath $exe)) { throw "Missing Vulkan llama.cpp runtime: $exe" }
if (-not (Test-Path -LiteralPath $model)) { throw "Missing model: $model. Run: npm run qwen27:download" }
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port is already listening." }
if (-not $AllowCompetingGpu) {
  # Fish on :8080 and the other local LLMs all contend for the RX 6600's 8 GB.
  $conflicts = @(8080, 9099, 9100 | Where-Object { Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue })
  if ($conflicts.Count) {
    throw "GPU workload(s) already listening on port(s) $($conflicts -join ', '). Preserve them; stop only when safe, or explicitly pass -AllowCompetingGpu."
  }
}

# Prevent the Vulkan backend from allocating hot tensors in PCIe-backed host-visible VRAM.
$env:GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM = '1'
Write-Host "Qwen3.8 27B Q3-DOWN-XS -> http://127.0.0.1:$Port/v1 ($Context tokens, Vulkan, GPU-only)" -ForegroundColor Green
& $exe -m $model --host 127.0.0.1 --port $Port --alias Qwen3.8-27B-Q3-DOWN-XS `
  --device Vulkan1 -ngl 999 -c $Context -np 1 -ctk q8_0 -ctv q8_0 -fa on `
  --jinja --reasoning off --reasoning-format none --no-warmup --metrics
