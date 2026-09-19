# Bonsai 2 RX 6600 Optimization Plan
## Using AMD AI Developer Program Credits

## Current Performance Baseline
- **Model**: Ternary-Bonsai-2-27B-PTQ1_0.gguf (5.54 GB)
- **Hardware**: Radeon RX 6600 (8GB VRAM) + Ryzen 5 PRO 4650G (6 Zen 4 cores, 16 GB RAM)
- **Software**: Prism fork of llama.cpp, Vulkan backend
- **Command**: `llama-server.exe -m .\Ternary-Bonsai-2-27B-PTQ1_0.gguf --device Vulkan1 -ngl 99 -c 8192 -ctk q8_0 -ctv q8_0 -fa on --temp 0.5 --top-p 0.85 --top-k 20`
- **Measured throughput**: **3.3 tok/s** (CPU-bound fallback; no packed-ternary Vulkan kernels)
- **Context**: 8192 tokens max
- **RAM floor**: ~3 GB required for Bonsai-2 workloads

## Root Cause
- Packed-ternary (PTQ1_0) kernels exist only for CUDA (NVIDIA) and Metal (Apple M-series)
- Vulkan backend for prism llama.cpp lacks ternary kernel implementation
- RDNA2 (RX 6600) falls back to generic CPU path

## AMD AI Developer Program Credit Usage Plan
### Total Credits Allocated: ~$90 (of $100)
### Remaining: ~$10 for contingencies

### Option 1: MI300X Validation ($80-90)
**Goal**: Definitively measure ternary Vulkan performance on current-gen AMD GPU, then port insights to RX 6600.

**Steps**:
1. Claim $100 AMD Developer Cloud credits from portal
2. Reserve MI300X instance (80 hours ~ $85)
3. Build prism llama.cpp with ROCm backend on MI300X
4. Run benchmark suite across quantizations (Q2_0, Q3_0, Q4_0, Q5_0) and layer offload configs
5. Document optimal configuration: throughput, quality, memory usage
6. Extract "porting guide" for RX 6600 Vulkan

**Expected Output**: 
- Hard numbers: tok/s on MI300X for each quant
- Configuration script for RX 6600
- Answer to "is ternary Vulkan possible on RDNA2?"

### Option 2: Hybrid Offload Script ($30-40)
**Goal**: Auto-split layers between Ryzen CPU + RX 6600 iGPU for 2-3x speedup.

**Steps**:
1. Rent Ryzen AI Max+ or dual-Ryzen cloud instances ($35)
2. Test layer-split configs: CPU layers 0-X, GPU layers X-27
3. Measure throughput per config
4. Build Python/bash script that auto-detects hardware and applies optimal split
5. Test on actual rig, validate 7-10 tok/s

**Expected Output**:
- One-click optimization script
- 2-3x throughput gain on existing hardware

### Option 3: Quantization Optimizer ($20-30)
**Goal**: Find best quant/speed ratio for RX 6600 without kernel changes.

**Steps**:
1. Rent MI250 or Ryzen AI cloud instances ($25)
2. Benchmark Q4_K_M, Q5_K_M, Q8_0 on RDNA2 Vulkan
3. Compare tok/s vs quality loss
4. Create decision tree for RX 6600

**Expected Output**:
- Quantization recommendation document
- 1.5-2x throughput gain via better quant choice

## Recommended Path: Option 1 (MI300X Validation)

**Rationale**: This is the only approach that addresses the root cause and produces definitive answers. Other options are workarounds.

**Timeline**: 5 days
**Cost**: ~$85 of $100 credits
**Deliverables**:
- `MI300X_BENCHMARK_RESULTS.md` - Raw benchmark data
- `RX_6600_PORTING_GUIDE.md` - Configuration to apply locally
- `OPTIMIZED_BONSAI2_CMD.bat` - Updated command file
- `QUANTIZATION_RECOMMENDATIONS.md` - Best quant for RX 6600

## Next Steps (Immediate)
1. **Claim credits**: Complete AMD AI Developer Program form if not done
2. **Reserve MI300X**: Use cloud credits for 80 hours compute
3. **Set up benchmark script**: Create ROCm/llama.cpp build on MI300X
4. **Run benchmarks**: Systematically test all quantizations
5. **Document findings**: Write porting guide for RX 6600
6. **Apply to local rig**: Update BONSAI2.cmd with optimal config

## Alternative: If Option 1 Timing Doesn't Work
Switch to Option 2 (Hybrid Offload) after Day 2 if MI300X access delayed.

## Contact & Support
- AMD AI Developer Program Discord: #ask-experts channel
- Monthly office hours: Schedule with AMD engineers
- Playbooks: `developer.amd.com/ai-developer-program/playbooks`

---
*Plan version 1.0 - Created for Bonsai 2 RX 6600 optimization using AMD AI Developer Program credits*