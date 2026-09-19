# AMD AI Developer Cloud: ptq1_0 Vulkan shader fix + TQ2_0 validation (v2.0, 2026-09-18)
# SUPERSEDES v1.0 (kept as AMD_CLOUD_VALIDATION_WORKFLOW_v1_OBSOLETE.ps1): v1 benched
# Q2_0-Q8_0 quants that DO NOT EXIST for this ternary model, and rented MI300X for 80h.
# Local findings changed the mission:
#   - TQ2_0 conversion already gives 12-13 tok/s locally (3.6x) - quality PASSED 2 probes
#   - ptq1_0 matvec kernel is the broken one (195 GFLOPS); tq2_0 is fine (1080 GFLOPS)
#   - 30 t/s @ 100K ctx proven impossible on RX 6600 (bandwidth + KV size physics)
# So cloud credits buy ONE thing: develop/validate the LUT shader fix faster than local
# (rig has NO build tools: cmake/glslc/ninja/cl all missing), plus large-scale quality A/B.

## Mission (ranked)
1. Rewrite `vulkan-shaders/ptq1_0.glsl` trit accessor: replace 3-way branch + serial
   base-3 recurrence (`for i<n: v=(v*3)&0xFF`) with a 256-entry byte->5-trits LUT,
   same shape as the fast `mul_mat_vec_tq2_0.comp` (unpack8 + unrolled FMA).
   Predicted local result: PTQ1_0 decode 3.3 -> 20-24 tok/s at 5.5 GB weights
   (better 8 GB VRAM headroom than TQ2_0's 6.5 GB -> leaves room for longer ctx).
2. Validate: `test-backend-ops perf -b Vulkan0 -o MUL_MAT -p ptq1_0` before/after
   (target: 602 us -> ~100 us on the m=4096,n=1,k=14336 case) and
   `test-backend-ops test -b Vulkan0 -o MUL_MAT -p ptq1_0` 28/28 OK.
3. Quality A/B at scale: PTQ1_0+new shader vs TQ2_0 on a coding task battery
   (MI300X runs both fast, so this is cheap).

## Credit-efficient plan (~$15-25, not $85)
- Instance: MI250 or MI300X, 8-12 hours, NOT 80h. Shader work is Vulkan, so even a
  cheap instance with any AMD GPU + Vulkan driver works; MI300X only needed for the
  big quality battery.
- Timeline: ~2h toolchain+clone+build, ~2-4h shader dev+bench iterate, ~1h quality
  battery, ~1h package + teardown.

## Steps (on the cloud instance, Ubuntu)
```bash
sudo apt update && sudo apt install -y build-essential cmake ninja-build git \
  glslc vulkan-sdk libvulkan-dev
# Fork repo VERIFIED 2026-09-18: https://github.com/PrismML-Eng/llama.cpp (org is
# PrismML-Eng; the prism-ml/llama.cpp URL in older notes 404s).
git clone https://github.com/PrismML-Eng/llama.cpp.git && cd llama.cpp
git checkout b10685  # match local validated build

cmake -B build -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release -G Ninja
cmake --build build -j

# Baseline BEFORE editing:
./build/bin/test-backend-ops perf -b Vulkan0 -o MUL_MAT   # record ptq1_0 us/run

# Edit vulkan-shaders/ptq1_0.glsl (LUT rewrite), rebuild, re-run perf + correctness.
# Then full model A/B with Ternary-Bonsai-2-27B-PTQ1_0.gguf (5.5 GB, HF: prism-ml/Ternary-Bonsai-2-27B-gguf)
./build/bin/llama-server -m Ternary-Bonsai-2-27B-PTQ1_0.gguf -ngl 99 -c 8192 \
  -ctk q8_0 -ctv q8_0 -fa on --port 9103
```

## Deliverables to bring home
1. Patched `ptq1_0.glsl` (+ diff) - can be compiled locally later once SDK installed,
   or submit PR upstream to the fork so the next release ships it prebuilt.
2. Perf table: ptq1_0 us/run before/after on the decode-shaped matvec.
3. Quality battery results JSON (PTQ1_0+LUT vs TQ2_0).
4. If PR accepted: wait for next prism release zip instead of local toolchain install.

## Decision gate
- If LUT gets ptq1_0 to ~1 TFLOPS at n=1: promote PTQ1_0+LUT as the daily driver
  (20-24 t/s, 5.5 GB weights, room for 16K ctx q8 KV).
- If LUT fails (Vulkan compiler/scheduling surprises): keep TQ2_0 12 t/s setup as the
  daily driver (already validated) and stop spending.
