# Bonsai-2 27B on RX 6600: measured best setup + 30 t/s / 100K feasibility (2026-09-18)

Rig: Ryzen 5 PRO 4650G, RX 6600 8 GB, 16 GB RAM. Runtime: Prism fork b10685 Vulkan
(only runtime that loads ternary GGUFs). Tests run with GPU exclusive (Spark-4B stopped).

## 1. Measured results

| Config | Decode t/s | Notes |
|--------|-----------|-------|
| PTQ1_0, ngl99, 8K, q8 KV (old) | 3.3 | ptq1_0 Vulkan matvec kernel ~195 GFLOPS (broken) |
| **TQ2_0, ngl99, 8K, q8 KV, GPU exclusive** | **12.0** | tq2_0 kernel ~1080 GFLOPS; full weights on GPU |
| TQ2_0, ngl99, 100K, q4 KV | 3.2 | KV ~6.7 GB forces weight layers to CPU (DDR4) |
| TQ2_0, 4K, GPU shared w/ Spark-4B | 0.38 | VRAM contention -> most layers on CPU |

Verdict: TQ2_0 conversion (already on disk, 6.95 GB) is the single biggest free win: 3.6x.

## 2. Physics of the 30 t/s @ 100K target

- Decode is bandwidth-bound. Weights 6.5 GB / RX 6600 224 GB/s = 29 ms/token = **~34 t/s
  theoretical ceiling** with a perfect kernel and zero attention cost. Measured kernel
  efficiency ~60% -> ~20 t/s realistic max at short ctx.
- 100K ctx KV = 512 KiB/token f16; q4_0 KV still ~6.7 GB -> does NOT fit in 8 GB alongside
  6.5 GB weights. Spill to DDR4 (~40 GB/s) adds seconds/token of attention read at long ctx.
- **30 t/s @ 100K is not physically possible on this rig.** Realistic ceilings:
  - 8-16K ctx: ~12-20 t/s (needs ptq/tq2 kernel LUT optimization to approach 20)
  - 100K ctx: ~2-5 t/s (KV in RAM), maybe ~8-10 with KV-cache eviction/sliding window tricks

## 3. Recommended setup (best measured, no cloud)

```
llama-server -m .../Ternary-Bonsai-2-27B-TQ2_0.gguf --device Vulkan1 -ngl 99 \
  -c 8192 -ctk q8_0 -ctv q8_0 -fa on --temp 0.6 --jinja
```
Requirements: GPU exclusive (stop other VRAM users first), ~7 GB free RAM for load.

## 4. Where AMD AI Developer Program credits WOULD matter

Credits do not speed up the local rig; they buy MI250/MI300X time to develop/validate
software that then runs locally. Ranked by expected local gain per dollar:

1. **Fix the ptq1_0 Vulkan shader** (256-entry byte->5-trits LUT, same shape as tq2_0 kernel).
   Predicted 3.3 -> 20-24 t/s with original 5.5 GB weights (better VRAM headroom than TQ2_0).
   Toolchain: cmake + Vulkan SDK + fork checkout. Can be developed locally too (no build tools
   on rig currently) — cloud only speeds iteration.
2. **TQ2_0 quality validation**: double-quantization (PTQ1_0 scale/128 -> TQ2_0 scale/256) may
   degrade quality; needs a real coding-task A/B before promoting 12 t/s setup.
3. **KV-in-RAM attention path for 100K**: streaming/paged KV with GPU-resident hot window.
   Biggest engineering effort; only path toward usable 100K.

Skip: cloud quant benchmarks of Q4_K_M/Q5_0/Q5_K_M (quant_optimizer.ps1) — those quants do
not exist for this ternary model; script is not runnable as designed.
