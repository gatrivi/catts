# D2 round-2 runbook — ptq1_0 matvec access-pattern redesign (2026-09-24)

For the next agent. Self-contained: read this + `GPU_SPEEDUP_ASSESSMENT_2026-09-22.md`
(sections "D1 profile RESULT", "D2 prep", "D2 session") before touching anything.

## Goal

Raise the ptq1_0 matvec kernel from **41 GB/s cold** to tq2_0-parity **~102 GB/s**.
Payoff if reached: PTQ1_0 (the fidelity-verified quant) goes 6.4 → **~11.5-14 t/s**
decode on the RX 6600. Fallback outcome (honest negative) is also acceptable — see
"Definition of done".

## Verified state (do not re-derive)

- GPU-busy decode sums (timestamp-true): TQ2_0 **81.8 ms/tok** (12.2 t/s ceiling),
  PTQ1_0 **157.8 ms/tok** (6.3 t/s ceiling). Wall ≈ GPU-sum at ≥4 GB free RAM;
  low RAM costs 25-30%. MUL_MAT = 84-92% of that; attention 1-4%. The bottleneck
  is INSIDE the matvec.
- Three ptq1_0 matvec designs TIE (f32 LUT, f32 closed-form, true vecq int-dot with
  u32 loads): gate/up 17408×5120 ≈ **378-381 µs**, qkv 10240×5120 ≈ **226-231**,
  lm_head 248320×5120 ≈ **6690-6771 µs** in-suite. tq2_0 same walk: 132.8 / 80.2 /
  **2956 µs**. Eliminated: LDS-vs-ALU decode, byte-vs-u32 loads, f32-vs-q8_1
  activations, pipeline config stdq/sub16.
- Calibration points on lm_head (280 MB ptq1_0 — Infinity-Cache-immune, use THIS
  shape for all A/Bs): ptq1_0 ≈ 6700 µs (41 GB/s cold), tq2_0 2956 µs (103 GB/s),
  **q4_0 3300 µs (~217 GB/s ≈ peak)** — proof the card can stream at peak with the
  right walk (q4_0 = smallest blocks, pure nibble unpack + int-dot).
- `mul_mat_vecq_funcs.glsl` was repaired 2026-09-24 (had never compiled since
  09-22; all earlier "vecq" numbers were the f32 fallback). Current tree =
  pristine `prism-b10709-9a9394a` + ONE region-uniform PTQ1_0 section. 68/68
  correctness. Don't re-break it; there is a pristine copy of the reasoning in
  the assessment doc if a diff is ever needed.

## The suspect (round-1 conclusion)

Access-pattern structure, shared by every ptq1_0 design: 128-elem blocks = 28 B,
16 threads/block → a warp touches only **56 B contiguous** and the row stride is
1120 B (k=5120, 40 blocks/row). tq2_0: 66-B blocks → 132 B/warp; q4_0: 20-B blocks
but 8 threads/block and pure int-dot → ~peak. Round 2 = change the WALK, not the
decode.

## Hard rules

- **C: is at ~99%**: named ninja targets ONLY (`test-backend-ops`, `llama-bench`,
  `llama-server`). NEVER bare `ninja`. Keep ≥1.5 GB free on C:; check with
  `df -h /c` or Explorer.
- Do NOT edit `kaggle/golden_prompts.json` (frozen spec). No downloads. No new
  runtimes.
- GPU must be exclusive for decode checks: no llama-server process, ports 9103/9151
  free. The nightly Task Scheduler task **CATTS-NightJobs (02:30)** owns the GPU
  then — don't hold it past 02:00; its report lands in
  `local-coding/data/night/<date>/MORNING_REPORT.md`.
- Record free RAM in every capture (the scripts do it); distrust any number taken
  under 2.5 GB free.
- Suite numbers for tensors ≤32 MB are IC-inflated — never compare sub-32 MB
  shapes across builds; lm_head only for A/B verdicts.

## Token-free iteration loop (exact commands)

```bash
export PATH="/c/tools/llvm-mingw/bin:/e/zengatrivi-drive-e/catts/.venv/Scripts:$PATH"

# 1. edit shaders (see experiment queue), then:
ninja -C C:/src/llama.cpp/build test-backend-ops        # ~2 min; if funcs.glsl
                                                        # changed and ninja skips
                                                        # regen: touch
                                                        # .../vulkan-shaders/mul_mat_vecq.comp

# 2. correctness (must be all OK before any perf claim):
cd C:/src/llama.cpp/build/bin
./test-backend-ops.exe test -b Vulkan1 -o MUL_MAT -p "ptq1_0|tq2_0|q2_k|q6_k|q4_0"

# 3. perf A/B (lm_head = verdict; gate/up = secondary):
./test-backend-ops.exe perf -b Vulkan1 -o MUL_MAT -p "ptq1_0.*n=1,|tq2_0.*n=1,|q4_0.*n=1," 2>&1 | grep -E "m=248320|m=17408" 

# 4. regression: tq2_0 and q4_0 numbers must not move.
```

Shader files: `C:/src/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/`
`mul_mat_vec_ptq1_0.comp` (f32 path), `mul_mat_vecq_funcs.glsl` (vecq repack4,
lines ~565-647), pipeline creation `ggml-vulkan.cpp` (~line 5285-5330, `ptq_spec` /
`ptq_wg_denoms`).

## Experiment queue (cheapest first)

- **E1 — DONE 2026-09-24 evening (partially):** `GGML_PTQ1_0_WG` env switch STAGED in
  `ggml-vulkan.cpp` (ptq1_0 f32 + vecq pipelines; scales local_size_x only — grid math
  and NUM_ROWS untouched). Results, all correctness-gated on Vulkan1:
  - WG=32 (default): 392 / 6805 µs (gate/up / lm_head) — control, 68/68 OK
  - WG=64: 396 / 6819 µs — exact tie, 68/68 OK
  - WG=128: **365 / 5595 µs (lm_head −18%)** BUT 1 correctness failure:
    `m=16 n=1 k=1024` (ERR 0.86, RX 6600 only; Vega iGPU passes; both f32 and vecq
    paths fail → shared structure, NOT the ptq trit decode; reduction code reads
    runtime `gl_NumSubgroups` and looks right). k=1024 is the only suite shape with
    num_blocks_per_row == it_size (8==8) — prime suspect class.
  - **E1b (PARKED 2026-09-24 night — low value):** root-cause found-in-part: the failing
    case is the **batched** `m=16 n=1 k=1024 bs=[3,2]` (a pre-existing suite case, not a
    production shape); plain and all production shapes pass at WG=128 in perf mode. Two
    operational discoveries: (a) **test mode silently culls large shapes** (nothing over
    ~k=1024/m=16 class prints — production-shape correctness can only be gated via
    `golden_check`, not test-backend-ops); (b) WG=128's total upside is only ~5-7%
    end-to-end (lm_head = 4.2% of decode; gate/up = 39% at -7%) — not worth the red test.
    Revisit ONLY if E2/E3 need workgroups > 32.
  - **Production stays at WG=32** (the env switch exists for experiments only).
- **E2 — elements-per-thread 8 → 16** in `mul_mat_vec_ptq1_0.comp` (thread owns
  16 contiguous elems = 2 u32 pairs; halve NUM_ROWS to keep LDS temp small).
  Per-warp contiguous footprint doubles.
- **E3 — multi-block walk:** thread processes 2 CONSECUTIVE blocks before moving
  on (both f32 path and vecq repack4 call order), so a warp covers 112 B
  contiguous per issue instead of 56.
- **E4 — RGP capture** (only if E2-E3 fail): Radeon GPU Profiler on a
  `llama-bench`-driven decode for per-instruction truth. Needs an installer —
  disk risk on C:, ask the user first.

## Unattended confirm (installed 2026-09-24, FIRST RUN SAME DAY: PASS)

`scripts/wait_gpu_confirm.ps1` + Task Scheduler **CATTS-GPUConfirm** (daily 10:00,
polls until 22:00): waits for no llama-server + ports 9103/9151 free + RAM ≥ 4 GB
(2 consecutive polls), then runs the per-op decode profile AND the golden gate
unattended, writing `data/confirm/<date>/CONFIRM_REPORT.md` (one run/day lock,
never kills processes). Cancel: `schtasks /Delete /TN CATTS-GPUConfirm`.
The night runner (CATTS-NightJobs 02:30) is unchanged and complementary.

First run result (2026-09-24 18:41): perop PASS (157.9 ms/tok, no regression vs
157.8) + golden **7/8 identical** — meets the ≥7/8 bar; the one diverge is the
documented toolcall token-0 coin-flip (0.007 nats), same profile as pre-repair →
the repaired vecq path is fidelity-equivalent. Capture:
`data/golden/confirm-20260924-183714.json`.
Setup gotchas fixed during the first run (already in the script): llvm-mingw PATH
for the direct server start (0xC0000139), separate stdout/stderr redirect files,
`-SkipPerop` switch.

## Definition of done

- Win path: lm_head ≤ ~2800 µs (tq2_0 parity) with all correctness green →
  end-to-end confirm: `python scripts/d1_perop_profile.py 8192 q8_0 48
  Z:/catts/local-coding/data/models/bonsai2-27b-ptq10/Ternary-Bonsai-2-27B-PTQ1_0.gguf`
  → MUL_MAT GPU-sum must drop from 157.8 toward ~90 ms/tok → then golden gate:
  `scripts/golden_capture.py` against a live :9103 server built from C:/src
  (`--name bonsai2-ptq10` — golden_check compares by model name!), compare vs
  `data/kaggle_runs/gold-20260921/golden.json`; bar ≥7/8 prompts identical.
- Then update: `GPU_SPEEDUP_ASSESSMENT_2026-09-22.md` (D2 r2 section),
  `docs/SESSION_CONTEXT.md` (dated entry), `MODEL_ROSTER.md` if promoting.
- Negative path: document the tie honestly in the same docs, close the shader
  track for good, keep TQ2_0 as daily driver. Do NOT leave the tree broken —
  every `ninja` regen must stay green (K-quants pristine + one PTQ1_0 section).

## Context: budget & sibling work

User budget-conscious: keep web/model calls minimal; all heavy measurement is
local scripts. Night runner (scripts-only, no LLM) handles baseline/sweep —
read its morning report before starting GPU work. Fidelity path vs speed path
are separate: TQ2_0 requant (Colab runbook `docs/COLAB_TQ2_REQUANT_JOB.md`) is
orthogonal and awaits user execution.

---

# PHASE B SPEC — TQ2_0 int-dot vecq port (execute in a fresh session)

Goal: give the daily driver TQ2_0 the integer-dot vecq path that q4_0 has (q4_0 proves
217 GB/s = 97% of peak on this card; TQ2_0 currently runs the float-FMA matvec at
~102 GB/s-class). Expected 12–13 → est. 15–20 t/s. Everything below is pre-derived;
implementation should be ~90 min.

## Wiring (3 touch points, mirrors how PTQ1_0's vecq was added)
1. `vulkan-shaders-gen.cpp` line ~776: the q8_1 variant list — add `|| tname == "tq2_0"`
   to `is_legacy_quant(tname) || mxfp4 || is_k_quant(tname) || iq1_s || iq1_m || ptq1_0`.
2. `mul_mat_vecq.comp`: add `DATA_A_TQ2_0` to the `K_PER_ITER 16` condition (line ~14,
   alongside Q2_0/PTQ1_0/QUANT_K).
3. `ggml-vulkan.cpp`: create the q8_1 pipeline for TQ2_0 (mirror the PTQ1_0 q8_1
   creation ~line 5361: same denoms `{2*rm_stdq_int,1,1}`, spec `{wg_size_subgroup_int,
   2*rm_stdq_int, i+1}`). The dispatch getter's switch already lists GGML_TYPE_TQ2_0,
   and `b_type == GGML_TYPE_Q8_1` routes automatically once the pipeline exists.

## The branch (clone Q2_0 — the only other 2-bit q−1 int-dot path, suite-proven)
In `mul_mat_vecq_funcs.glsl`, add `#if defined(DATA_A_TQ2_0)` next to DATA_A_Q2_0's:
- `get_dm(ib)`: tq2_0 block = 256 elems = 8 q8_1 blocks → `data_a[ib / 8u].d`
  (single f16 scale per block; no mins — NOT Q2_0's per-block layout).
- `repack4(ib, iqs)`: tq2_0 byte = 4 consecutive 2-bit weights (same packing as Q2_0's
  bytes!) → reuse `unpack_q2_0()` verbatim. Indexing: elements e = (ib%8)*32 + iqs*16
  + k (k=0..15); byte0 = e/4 (multiple of 4 → u32-aligned);
  `qs_idx = (ib%8)*8 + iqs*4`; `bits = pack32(u16vec2(qs16[qs_idx], qs16[qs_idx+1]))`;
  `i32vec4(unpack_q2_0(bits), unpack_q2_0(bits>>8), unpack_q2_0(bits>>16),
  unpack_q2_0(bits>>24))`.
- `mmvq_dot_product`: identical shape to Q2_0's (4× dotPacked4x8EXT against
  cache_b_qs[0..3]) + `mul_q8_1(q_sum, get_dm(ib), cache_b_ds, 2)` (16 of 32 elems).
- **Open detail (the one judgment call):** the exact `mul_q8_1` correction/divisor —
  Q2_0's branch is suite-proven; tq2_0's w = (q−1)·d matches Q2_0's weight semantics
  (q−1)·d, so clone the divisor (2) and let the suite decide. If 68/68 fails on tq2_0
  only, read the cache_b fill in mul_mat_vecq.comp and adjust the ds.y term/divisor.

## Verification loop (same as E2)
1. `ninja test-backend-ops` (touch mul_mat_vecq.comp first) → suite
   `test -p "tq2_0|ptq1_0|q2_k|q4_0"` → 68/68 required.
2. `perf -p "tq2_0.*n=1,"` → compare vs baseline: gate/up 132.8 µs, down 141.7,
   lm_head 2956 (in-suite); **lm_head is the cold-true verdict** (target ≤ ~2200 µs =
   tq2_0 ≥ ~140 GB/s cold).
3. Regression: ptq1_0/q4_0 numbers must not move.
4. Relink `llama-server` TOO (gotcha: shader changes need both targets).
5. End-to-end: perop capture of TQ2_0 (baseline 81.8 ms/tok GPU-sum) → golden gate
   (`--name bonsai2-ptq10`?? NO — TQ2_0 capture needs `--name` matching its golden...
   NOTE: there is no TQ2_0 golden — the golden reference IS PTQ1_0 (they share weights:
   TQ2_0 = requant of PTQ1_0). Cross-model fidelity is NOT assertable; instead run the
   PTQ1_0 golden gate (must stay 7/8 — proves no regression) + a 2-prompt sanity on
   TQ2_0 (count300 text stability vs pre-port).
6. Variance: 2 captures; record both.

## Success bar
MUL_MAT(TQ2_0) sum 68.4 → ≤ ~50 ms/tok (→ daily driver ~15-20 t/s). Tie (±5%) =
documented negative; the track then closes (upstream PR still has the int8 story).
