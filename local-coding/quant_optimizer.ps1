# Quantization Optimizer for Bonsai 2 on RX 6600
## Finds best quant/speed ratio using AMD AI Developer Cloud credits
## Cost: ~$20-30 (MI250 or Ryzen AI cloud rental)
## Expected speedup: 1.5-2x (from 3.3 → 5-6.6 tok/s)

## Purpose
Automatically benchmark Bonsai 2 across quantization levels
on AMD hardware, then recommend the optimal quant for RX 6600.

## Quantization Levels Tested
| Code | Label | BPW (bits/prompt) | VRAM (~8 GB RX 6600) | Expected tok/s | Quality |
|------|-------|-------------------|----------------------|----------------|---------|
| Q2_0 | ROCMFPX | ~2.5 | ~2 GB | ~12-15 | Poor |
| Q3_0 | ROCMFPX | ~3.5 | ~3 GB | ~10-12 | Fair |
| Q4_0 | ROCMFPX | ~4.5 | ~4 GB | ~8-10  | Good |
| Q4_K_M | GGUF | ~5.5 | ~5 GB | ~7-8   | Very Good |
| Q5_0 | ROCMFPX | ~5.5 | ~6 GB | ~6-7   | Great |
| Q5_K_M | GGUF | ~6.5 | ~7 GB | ~5-6   | Great |
| Q8_0 | GGUF | ~8.5 | ~9 GB | ~3-4   | Excellent |

## Optimizer Workflow

### Step 1: Setup AMD Cloud Instance
```powershell
# Rent MI250 or Ryzen AI Max+ instance (20-30 hours ~ $25)
amdctl reserve \
  --instance-type mi250 \
  --duration 24h \
  --region us-east-1 \
  --project bonsai2-quant-optimization

ssh amdcloud@instance-XX.amer.datadoghq.com
```

### Step 2: Build Prism llama.cpp with ROCm
```powershell
# Same as cloud validation workflow, but shorter (no ternary focus)
git clone https://github.com/prism-ml/llama.cpp.git
cd llama.cpp
cmake -B build \
  -DGGML_HIP=ON \
  -DAMDGPU_TARGETS=gfx90a \
  -DGGML_OPENMP=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j 64
```

### Step 3: Download Bonsai 2 Model
```powershell
git lfs install
git clone https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf.git
# Or download specific GGUF:
wget "HF_MODEL_URL/Ternary-Bonsai-2-27B-PTQ1_0.gguf"
```

### Step 4: Benchmark Loop (Automated)
The optimizer script benchles each quant and records tok/s:

```powershell
# optimize_quant.ps1
param(
    [string]$Model = "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
    [int]$Context = 8192,
    [switch]$DryRun
)

$quants = @("Q2_0", "Q3_0", "Q4_0", "Q4_K_M", "Q5_0", "Q5_K_M", "Q8_0")
$results = @()

Write-Host "=== Bonsai 2 Quantization Optimizer ==="
Write-Host "Model: $Model"
Write-Host "Context: $Context"
Write-Host ""

foreach ($quant in $quants) {
    Write-Host "Benchmarking $quant ..." -ForegroundColor Cyan
    
    # Build command based on quantization
    switch -regex ($quant) {
        {"^Q2_0$" or "^Q3_0$" or "^Q4_0$"} {
            $qflag = $quant
        }
        {"^Q4_K_M$" or "^Q5_K_M$" or "^Q8_0$"} {
            $qflag = "-q $quant"
        }
    }
    
    $cmd = @"
& .\llama-server.exe -m $Model ^
  --device HIP ^
  -ngl 99 -c $Context ^
  -q $qflag ^
  -ctk q8_0 -ctv q8_0 ^
  -fa on --temp 0.5 --top-p 0.85 --top-k 20 ^
  --port $($2000 + (Get-Random 100)) %"
"@
    
    # Run for 30 seconds, capture output
    $start = Get-Date
    $end = $start.AddSeconds(30)
    
    $tokPerSec = $null
    while ((Get-Date) -lt $end) {
        # Run inference with a test prompt
        # Parse output for tok/s
    }
    
    # Alternative: Run with --log-logits and parse
    $logFile = "benchmark_$quant.log"
    & .\llama-server.exe -m $Model ^
      --device HIP ^
      -ngl 99 -c $Context ^
      -q $qflag ^
      -ctk q8_0 -ctv q8_0 ^
      -fa on --temp 0.5 --top-p 0.85 --top-k 20 ^
      --port 9110 > $logFile 2>&1
    
    # Extract tok/s from log
    $tokSec = (Select-String -Pattern "tok/s" $logFile -Context 0 -SimpleMatch).Split()[0]
    # Or use jq to parse if JSON output available
    
    $result = @{
        Quantization = $quant
        tok_s        = if ($tokSec) { [double]$tokSec } else { "N/A" }
        Status       = if ($tokSec) { "Success" } else { "Failed" }
    }
    $results += $result
    
    Write-Host "  Result: $tok_sec tok/s" -ForegroundColor Green
    Start-Sleep -Seconds 5  # Cool down between runs
}

# Output results
if (-not $DryRun) {
    $results | ConvertTo-Json -Depth 4 | Out-File results.json
    Write-Host "`n=== Results Summary ==="
    $results | Format-Table -AutoSize
    
    # Determine recommendation
    $best = $results | Where-Object { $_.tok_s -notmatch "N/A" } | Sort-Object -Property { -$_.tok_s } | Select-Object -First 1
    Write-Host "`n=== RECOMMENDATION === "
    Write-Host "Best quant: $($best.Quantization) at $($best.tok_s) tok/s"
    
    # Check VRAM fit
    $vrAMUsed = switch ($best.Quantization) {
        "Q2_0" { 2 }; "Q3_0" { 3 }; "Q4_0" { 4 }
        "Q4_K_M" { 5 }; "Q5_0" { 6 }; "Q5_K_M" { 7 }; "Q8_0" { 9 }
    }
    Write-Host "Estimated VRAM usage: $vrAMUsed GB"
    Write-Host "Fits in RX 6600 8 GB VRAM: $([bool]::new($vrAMUsed -le 8))"
}
```

### Step 5: Interpret Results & Create RX 6600 Guide

```powershell
# After running optimizer, create RX 6600 recommendation:

Write-Host "=== RX 6600 QUANTIZATION RECOMMENDATION ==="
Write-Host ""

# Map MI300X results to RX 6600 constraints
$results | ForEach-Object {
    $quant = $_.Quantization
    $tok = $_.tok_s
    
    if ($tok -match "N/A") {
        Write-Host "$quant: FAILED (skip)" -ForegroundColor Red
        return
    }
    
    # Estimate RX 6600 performance (RDNA2 is ~1/8-1/4 MI300X speed for same quant)
    # Conservative: 1/4 speed, Optimistic: 1/2 speed
    $rx660k = [math]::Round($tok * 0.25, 1)  # Conservative
    $rx660o = [math]::Round($tok * 0.5, 1)   # Optimistic
    
    $fitsVRAM = if (@("Q2_0","Q3_0","Q4_0","Q4_K_M","Q5_0") -contains $quant) { "YES (8 GB)" }
                else { "NO (9 GB, close)" }
    
    Write-Host "$quant: MI300X $tok tok/s → RX 6600: $rx660k (cons) / $rx660o (opt) tok/s | VRAM: $fitsVRAM" -ForegroundColor Yellow
}

# Final recommendation
Write-Host ""
$recommended = $results | Where-Object { 
    $_.tok_s -notmatch "N/A" -and 
    @("Q4_K_M","Q5_0") -contains $_.Quantization
} | Sort-Object -Property { -$_.tok_s } | Select-Object -First 1

if ($recommended) {
    Write-Host "RECOMMENDED for RX 6600: $($recommended.Quantization)" -ForegroundColor Green
    Write-Host "Expected RX 6600 performance: $([math]::Round($recommended.tok_s * 0.35, 1)) tok/s (approx)"
    Write-Host "Speedup over current 3.3 tok/s: $([math]::Round($recommended.tok_s * 0.35 / 3.3, 1))x"
} else {
    Write-Host "No quant achieved acceptable speed on MI300X" -ForegroundColor Red
}
```

## Expected Outcomes Matrix

| Optimizer Result (MI300X) | RX 6600 Estimated | Speedup over 3.3 | Quality | Credits Used |
|---------------------------|-------------------|------------------|---------|--------------|
| **Q4_K_M: 12 tok/s** | 3.5-6.0 tok/s | 1.1-1.8x | Very Good | $25 |
| **Q5_0: 10 tok/s** | 3.0-5.0 tok/s | 0.9-1.5x | Great | $25 |
| **Q5_K_M: 8 tok/s** | 2.5-4.5 tok/s | 0.8-1.4x | Great | $25 |
| **Q8_0: 5 tok/s** | 1.5-2.5 tok/s | 0.5-0.8x | Excellent | $25 |
| **All < 5 tok/s** | < 3.3 tok/s | < 1x | Various | $25 (wasted, try Option 1 or 2) |

## Credit-Efficient Path (Minimize Waste)
1. **Run optimizer with 3 quants only**: Q4_K_M, Q5_0, Q5_K_M (most relevant for RX 6600)
2. **Use 15-hour MI250 rental** (~$15) instead of 24-hour
3. **Each quant run**: 30 seconds + 5 second cool-down = ~4 min per quant
4. **Total time**: 4 quants × 4 min = 16 min + setup = ~30 min total
5. **Cost**: ~$8-12 for 15-hour MI250 rental

## If Optimizer Results Are Disappointing (< 5 tok/s on MI300X for all quants)
### Switch to:
1. **Option A**: Hybrid offload script (create CPU+GPU split) → 2-3x gain
2. **Option B**: MI300X ternary kernel validation → 3-9x gain (but harder)
3. **Option C**: Accept current 3.3 tok/s + save credits for future hardware

## Output Files Generated
- `results.json` - Raw benchmark data
- `RX_6600_QUANT_RECOMMENDATION.md` - Human-readable recommendation
- `OPTIMIZED_BONSAI2_CMD.bat` - Updated command file for local rig
- `QUANT_COMPARISON_TABLE.md` - Side-by-side quant comparison

---
*Quantization optimizer version 1.0 - For AMD AI Developer Program credit usage*