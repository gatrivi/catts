# Bonsai-2 27B PTQ1_0 on RX 6600: root cause + fix options (2026-09-18)

Read-only investigation while the user worked: no model run, no downloads, no runtime
change, no server stopped. Supersedes the first version of this file (same date), whose
leading hypothesis ("offload/VRAM bound") is now falsified by measurement.

## 1. Measured cause: the PTQ1_0 Vulkan matvec kernel itself is ~6x too slow
`test-backend-ops.exe perf -b Vulkan1 -o MUL_MAT` on the same decode-shaped case
(m=4096, n=1, k=14336, i.e. one FFN matvec of a 27B qwen35 model):

| type_a   | us/run | GFLOPS | note |
|----------|--------|--------|------|
| ptq1_0   | 602    | 195    | the format Bonsai-2 ships |
| tq2_0    | 109    | 1080   | ternary, 2-bit, has its own shader |
| q4_0     | 92     | 1275   | reference quant path |
| q2_0     | 63     | 1880   | fork-only fast 2-bit path |
ptq1_0 prefill (n=512): 4.11 TFLOPS (vs tq2_0 5.10) - so only the matvec path is broken.
Correctness: `test-backend-ops test -b Vulkan1 -o MUL_MAT -p ptq1_0` = 28/28 OK, Backend Vulkan1 OK.

Model arithmetic from those numbers (26.87e9 ternary weights = 53.7 GFLOP/token):
- decode: 53.7 / 195 GFLOPS = 275 ms/token = 3.6 tok/s   (measured: 3.33 tok/s)
- prefill: 53.7 / 4.11 TFLOPS = 13 ms/token = 77 tok/s  (measured: 32-65 tok/s)
Both match, so the kernel throughput explains the whole picture. VRAM/offload is NOT
required to explain it (it stays a separate, secondary constraint - see section 3).

## 2. Why the kernel is slow (source, PrismML-Eng/llama.cpp)
`vulkan-shaders/ptq1_0.glsl` - the trit accessor used by mul_mat_vec via dequant_funcs.glsl:
three-way branch to pick the byte (qs[0..15], qs[16..23], qh[0..1]), then
`for (i < n) v = (v*3) & 0xFF;` - a data-dependent serial loop of up to 4 steps - then
`float(int((v*3)>>8) - 1)`. Per weight element, every token: branch + serial integer chain.
With n=1 output column there is no other work to hide that latency (hence 195 GFLOPS);
at n=512 it is hidden (4.11 TFLOPS).
By contrast `mul_mat_vec_tq2_0.comp` never unpacks trits: it uses `unpack8()` byte tricks +
unrolled FMA chains and the identity `d*(sum b*q - sum b)`. That is the fast pattern.

## 3. Memory arithmetic (unchanged, secondary)
arch qwen35, 64 layers, head_count_kv 4, key_length = value_length = 256
=> 131,072 KV values/token = 512 KiB/token at f16.

| context | f16 KV | q8_0 KV |
|---------|--------|---------|
| 8192    | 4.00 GiB | 1.06 GiB |
| 16384   | 8.00 GiB | 2.13 GiB |
Weights 5.54 GiB. So 8K + q8 KV + compute ~= 6.9-7.2 GiB of 7.98 GiB total VRAM: fits only
with an idle GPU. Observed now: 5315 MiB used by PID 22116 (Qwen3.5-9B @32K :8123, 3499 MB)
and PID 7824 (MiniCPM5-2B @16K :9122, 1772 MB); system RAM 15.4 GB total / 5.5 GB free.

## 4. Fix options
A. Optimize the shader (correct fix, but toolchain-gated)
   Replace the base-3 recurrence + branch with a 256-entry byte->5-trits lookup (or a
   branchless formulation), i.e. give ptq1_0 the same shape as the tq2_0 kernel.
   Expected: ~1.0-1.3 TFLOPS at n=1 => 42-50 ms/token => ~20-24 tok/s, weights unchanged
   at 5.54 GiB. Blocker: no build toolchain on the rig - cl/cmake/ninja/glslc/Vulkan SDK all
   MISSING (git, llvm-mingw clang/gcc and VS2019 dirs are present). Needs CMake + Vulkan SDK
   + a fork checkout, i.e. user-approved downloads, then a measured A/B.

B. Requantize the model to TQ2_0 and use the existing fast kernel (no compiler)
   `llama-quantize --allow-requantize <ptq1_0.gguf> <out.gguf> TQ2_0` (fork's quantize reads
   PTQ1_0; TQ2_0 = ternary, per-256-block f16 scale, 2-bit pack).
   Expected: same decode estimate (~20 tok/s) via the measured tq2_0 kernel.
   Costs/risks: weights 5.54 -> ~6.3 GiB (+0.7), which makes the 8 GB fit much tighter;
   PTQ1_0 has a scale per 128 trits and TQ2_0 per 256, so two source blocks with different
   scales cannot both be represented - double-quantization error that needs a quality check;
   whether the fork's quantize accepts TQ2_0 output is UNVERIFIED.

## 5. Not verified / open
- No patch applied, no rebuild, no requantize run: all gains above are arithmetic
  predictions from measured kernel throughputs.
- Whether the fork's llama-quantize accepts TQ2_0 as an output type.
- Whether a 256->5-trit LUT actually recovers ~1 TFLOPS at n=1 (needs the rebuild to measure).
- Model quality after requantization.

Cross-check: the parallel MiniCPM5-131K session hit the same VRAM wall
("131K full ctx needs ~7 GB VRAM alone - close :8123 first").
