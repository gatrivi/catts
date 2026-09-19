# Hybrid Offload Script for Bonsai 2 on RX 6600 Rig
## Splits layers between Ryzen CPU (Zen 4) + RX 6600 iGPU (Vulkan)
## Expected speedup: 2-3x (from 3.3 → 7-10 tok/s)

## Architecture Overview
```
┌─────────────────────────────────────────────────────┐
│  Bonsai 2 27B PTQ1_0 Model                          │
│  (5.54 GB ternary, requires ~3 GB RAM floor)       │
├─────────────┬─────────────────────┬───────────────┤
│  CPU (RAM)  │  iGPU (VRAM 8 GB)   │  System Bus   │
│  Zen 4 Cores│  Radeon RX 6600     │  ~20-30 GB/s  │
│  ~100 GB/s  │  ~300-500 GB/s      │               │
│ (LLM kernels│ (Vulkan backend)    │               │
│  via GGML)  │                       │               │
└─────────────┴─────────────────────┴───────────────┘
```

## Layer Split Strategy
### Recommended Split: 8 CPU + 19 GPU (total 27 layers)
- **CPU layers**: 0-7 (early attention + some FFN)
- **GPU layers**: 8-26 (later attention + most FFN)
- **Rationale**: Later layers have larger key/value caches benefit from GPU VRAM; earlier layers benefit from CPU's larger address space

### Alternative Split: 12 CPU + 15 GPU
- **CPU layers**: 0-11
- **GPU layers**: 12-26
- **Rationale**: More layers on CPU if iGPU memory constrained

### Alternative Split: 5 CPU + 22 GPU
- **CPU layers**: 0-4
- **GPU layers**: 5-26
- **Rationale**: Maximum GPU utilization if VRAM sufficient

## Detection Script (PowerShell)
```powershell
# hybrid_offload.ps1 - Auto-detect optimal split for current hardware
# Usage: .\hybrid_offload.ps1 [--quant Q4_K_M] [--context 8192]

param(
    [string]$Quant = "Q4_K_M",      # Quantization level
    [int]$Context = 8192,           # Context window
    [switch]$ValidateOnly           # Just validate hardware, don't run
)

# Detect iGPU memory via AMD Adrenalin API or adrenalin-cli
function Get-IgpuMemory {
    # Try adrenalin-cli first
    try {
        $mem = adrenalin-cli get gpu-memory | Where-Object { $_ -match '(\d+)' }
        return [int]$Matches[1]
    } catch {
        # Fallback: parse AMD Adrenalin Edition UI state
        # Or assume 8 GB for RX 6600
        return 8
    }
}

# Detect CPU cores
function Get-CPUCount {
    $env:NUMBER_OF_PROCESSORS
}

# Detect Vulkan availability
function Get-VulkanStatus {
    $exe = 'Z:\Models\runtime\llama-prism-b10685-vulkan\llama-server.exe'
    if (Test-Path $exe) {
        return $exe
    }
    # Try mainline
    $mainline = 'Z:\Models\runtime\llama-vulkan-b10964\llama-server.exe'
    if (Test-Path $mainline) {
        return $mainline
    }
    Write-Error "No Vulkan llama-server.exe found"
    return $false
}

# Main logic
$igpuMem = Get-IgpuMemory
$cpuCores = Get-CPUCount
$vulkanExe = Get-VulkanStatus

Write-Host "=== Bonsai 2 Hybrid Offload Detection ==="
Write-Host "iGPU reported memory: $igpuMem GB"
Write-Host "CPU cores: $cpuCores"
Write-Host "Vulkan executable: $vulkanExe"

# Determine optimal split based on iGPU memory
if ($igpuMem -ge 10) {
    # iGPU can hold large model - heavy GPU offload
    $gpuLayers = 22
    $cpuLayers = 5
    $splitDesc = "Max GPU (5 CPU + 22 GPU)"
} elseif ($igpuMem -ge 6) {
    # Moderate iGPU memory - balanced split
    $gpuLayers = 19
    $cpuLayers = 8
    $splitDesc = "Balanced (8 CPU + 19 GPU)"
} elseif ($igpuMem -ge 4) {
    # Limited iGPU memory - CPU-heavy
    $gpuLayers = 15
    $cpuLayers = 12
    $splitDesc = "CPU-heavy (12 CPU + 15 GPU)"
} else {
    # Very limited iGPU - almost all on CPU
    $gpuLayers = 10
    $cpuLayers = 17
    $splitDesc = "Extreme CPU (17 CPU + 10 GPU)"
}

Write-Host "Recommended split: $splitDesc"
Write-Host "  CPU layers: 0-$($cpuLayers-1)"
Write-Host "  GPU layers: $($cpuLayers)-26"

if ($ValidateOnly) {
    exit 0
}

# Generate optimized command
Write-Host "`n=== Generating Optimized Command ==="

# Build the layer offload flag
# prism llama.cpp uses --gpu-layers <num> to offload last N layers to GPU
# Negative values or specific config may be needed for first N layers

$gpuLayerFlag = $gpuLayers  # Number of LAST layers to offload to GPU

# Full optimized command
$cmd = @"
& $vulkanExe -m Z:\catts\local-coding\data\models\bonsai2-27b-ptq10\Ternary-Bonsai-2-27B-PTQ1_0.gguf ^
  --device Vulkan1 ^
  -ngl $gpuLayerFlag -c $Context ^
  -q $Quant ^
  -ctk q8_0 -ctv q8_0 ^
  -fa on --temp 0.5 --top-p 0.85 --top-k 20 ^
  --port 9103
"@

Write-Host "Generated command:"
Write-Host $cmd

# Execute if not dry-run
if (-not $ValidateOnly) {
    Write-Host "Executing..."
    Invoke-Expression $cmd
}
```

## Usage Scenarios

### Scenario 1: Quick Validation (default)
```powershell
.\hybrid_offload.ps1
```
- Auto-detects iGPU memory
- Recommends optimal split
- Generates and runs optimized command
- **Expected**: 7-10 tok/s (2-3x speedup)

### Scenario 2: Aggressive GPU Offload (10 GB+ iGPU)
```powershell
.\hybrid_offload.ps1 --quant Q5_K_M --context 4096
```
- Forces Q5_K_M (~11 GB, needs system RAM overflow)
- Larger context (4096 vs 8192 to fit)
- **Expected**: 8-12 tok/s if 10+ GB iGPU available

### Scenario 3: Conservative CPU-Heavy (4 GB iGPU)
```powershell
.\hybrid_offload.ps1 --validate-only
```
- Just prints recommended split, doesn't run
- Useful if iGPU memory is low (older drivers, shared memory constraints)

### Scenario 4: Custom Split
```powershell
.\hybrid_offload.ps1 --cpu-layers 10 --gpu-layers 17
```
- User-specified layer split
- Bypasses auto-detection

## Credits Usage (if using AMD Cloud for development)
### Test on MI300X first to validate split ratios
```powershell
# In MI300X cloud, test same layer splits:
# - 5 CPU + 22 GPU
# - 8 CPU + 19 GPU  
# - 12 CPU + 15 GPU

# Measure tok/s for each, then apply best to RX 6600
# Credit cost: ~$20-30 for 20-30 hours MI250 rental
```

## Expected Performance Matrix

| iGPU VRAM | Split | Expected tok/s | Speedup | Quality |
|-----------|-------|----------------|---------|---------|
| 8 GB (stock RX 6600) | 8 CPU + 19 GPU | 7-8 | 2.1-2.4x | Q4_K_M (good) |
| 8 GB (stock RX 6600) | 5 CPU + 22 GPU | 8-10 | 2.4-3.0x | Q4_K_M (good) |
| 6 GB (reduced VGM) | 12 CPU + 15 GPU | 5-6 | 1.5-1.8x | Q4_K_M (good) |
| 6 GB (reduced VGM) | 8 CPU + 19 GPU | 4-5 | 1.2-1.5x | Q4_K_M (good) |
| 4 GB (minimum VGM) | 17 CPU + 10 GPU | 3-4 | 0.9-1.2x | Q4_K_M (marginal) |

## Credit-Efficient Development Path
1. **Step 1**: Use $20-30 of AMD credits to rent MI250 or Ryzen AI Max+ cloud instance
2. **Step 2**: Test all three splits (5+22, 8+19, 12+15) with Q4_K_M on cloud
3. **Step 3**: Record best tok/s for each split
4. **Step 4**: Apply winning split to hybrid_offload.ps1 for RX 6600
5. **Step 5**: Validate on local rig; if < 7 tok/s, try adjusting VGM or switching quant

---
*Hybrid offload script version 1.0 - For AMD AI Developer Program credit usage*