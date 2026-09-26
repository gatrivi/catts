# KERNEL HEADROOM — WHERE THE 53 ms ACTUALLY GOES (2026-09-25)

Answers "matmul/matvec/kernel isn't as good as it could be" with measurements
instead of intuition. **Short version: the tq2_0 matvec kernel is done — 68% of the
decode step runs at 90-100% of the card's measured memory copy rate. The
recoverable time is in ~724 small dispatches (≈5 ms) and in speculative decode
(the 2×), not in the matvec.**

## 1. Per-op roofline audit (production, not in-suite)

Source: `data/profile/d1_perop_20260925-161826.json` (GGML_VK_PERF_LOGGER, 8192 ctx,
q8_0 KV, one steady-state decode step, 53.37 ms GPU-sum). Reference points measured
on this RX 6600: **185 GB/s** cold copy (64-256 MB), 445-644 GB/s only when
Infinity-Cache-resident (≤16 MB, i.e. never in production at 6.1 GB/token).

| op | calls | µs/call | MB/call | GB/s | vs 185 |
|---|---|---|---|---|---|
| MUL_MAT_VEC tq2_0 m=17408 k=5120 | 128 | 124.8 | 21.3 | 179 | 97% |
| MUL_MAT_ADD tq2_0 m=5120 k=17408 | 64 | 116.1 | 21.3 | 192 | 104% |
| MUL_MAT_VEC tq2_0 m=10240 k=5120 | 48 | 75.4 | 12.5 | 174 | 94% |
| MUL_MAT_VEC tq2_0 m=6144 k=5120 | 48 | 49.3 | 7.5 | 159 | 86% |
| MUL_MAT_VEC tq2_0 m=5120 k=6144 | 48 | 48.7 | 7.5 | 161 | 87% |
| MUL_MAT_VEC tq2_0 m=248320 k=5120 (lm_head) | 1 | 1570.7 | 303.1 | 202 | 109% |
| MUL_MAT_VEC tq2_0 m=12288 k=5120 | 16 | 88.1 | 15.0 | 179 | 97% |
| MUL_MAT_VEC tq2_0 m=1024 k=5120 (MoE) | 32 | 16.6 | 1.25 | 79 | 43% |
| MUL_MAT_VEC tq2_0 m=48 k=5120 (MoE) | 96 | 5.3 | 0.06 | 12 | 6% |

**36.6 ms (68%) of the step is these tq2_0 matvecs, moving 6.1 GB at ~180 GB/s =
90-100% of roofline.** There is no meaningful kernel win left in them. The
lm_head — the shape the whole track was A/B-ing — is only 2.9% of the step and is
already the *fastest* op per byte (109% of the copy rate).

## 2. The vecq port is confirmed healthy everywhere (new measurement)

Isolated A/B, `GGML_VK_DISABLE_MMVQ=1`, same binary, production shapes (in-suite
µs/run, so absolute numbers are IC-warm; the *ratio* is the signal):

| shape | vecq ON | vecq OFF | speedup |
|---|---|---|---|
| m=17408 k=5120 | 119.5 (186 GB/s) | 138.4 | 1.16× |
| m=5120 k=17408 | 80.5 (277) | 141.6 | **1.76×** |
| m=10240 k=5120 | 59.8 (219) | 86.1 | 1.44× |
| m=6144 k=5120 | 36.1 (218) | 59.5 | 1.65× |
| m=5120 k=6144 | 31.5 (250) | 51.3 | 1.63× |
| m=12288 k=5120 | 63.3 (249) | 95.4 | 1.51× |
| m=248320 k=5120 | 1645 (193) | 2960 | **1.80×** |

vecq is active on **all seven** production shapes (no silent fallback) and wins on
every one. Combined with the RGP ISA data (`RGP_ATOM_CAPTURE_2026-09-25.md`:
tq2_0 = 11788 bytes of ISA vs q4_0 = 6872) the picture is coherent: tq2_0 spends
1.71× the instructions to move the same bytes, and wins anyway because it is
memory-bound, not issue-bound.

## 3. The dispatch tax — where the recoverable ~17 ms hides

**Measured per-dispatch floor: 2.29 µs** (`test-backend-ops perf -o ADD`,
ne=[4096,1,1,1] = 16 KB). 724 dispatches/token × 2.29 µs = 1.7 ms is irreducible.
Everything above that is opportunity:

| op | calls | µs/call | floor multiple | addressable |
|---|---|---|---|---|
| GET_ROWS | 97 | 19.0 | 8.3× | ~1.6 ms — MoE routing gathers (3/layer); 97/token is structural, 19 µs each is not |
| RMS_NORM_MUL (5120) | 129 | 13.3 | 5.8× | ~1.4 ms — 1 workgroup of 512 threads for 20 KB; latency-bound, not BW |
| RMS_NORM_MUL (expert norms) | 80 | 4.4 | 1.9× | ~0.2 ms |
| MUL | 322 | 4.2 | 1.8× | ~0.6 ms |
| MoE matvecs (m=48, m=1024) | 128 | 5.3 / 16.6 | — | ~0.5 ms — `mul_mat_id` degenerates to per-expert matvecs at n=1 |
| f32 MUL_MAT (1024², n=5/6/17) | 258 | 18 | — | 4.6 ms but at 233 GB/s (IC-assisted) — little room |
| FLASH_ATTN_EXT | 16 | 115.6 | — | 1.85 ms |

Ranked, realistic: **GET_ROWS 1.6 + RMS_NORM 1.6 + MoE batching 0.5 + MUL 0.6 ≈
4.3 ms (8%)** → 53.4 → ~49 ms → 20.4 → ~22 t/s. That is the *entire* remaining
kernel-side ceiling. Everything else is spec decode.

## 4. What to do about it, in order

1. **Speculative decode (the 2×).** Not a kernel problem. `MTPLean` slice added to
   the night campaign (day 2 = tonight): mtp-lean target + dspark drafter with
   `--spec-type draft-mtp`, RAM-guarded at 11 GB free, records
   `mtp:acceptance_speedup`. The #217 Hadamard fix is in-tree and untested; this
   is the first execution. ngram was marginal, dspark refuted on tq2_0
   (cross-gen spec-batch error) — mtp is the remaining untested path.
2. **GET_ROWS kernel** (1.6 ms). 19 µs to gather a routing index. Check
   `ggml-vulkan.cpp` get_rows: it likely uses a generic 1-thread-per-row gather
   with no vectorization. A specialised small-gather path (or hoisting the
   routing arithmetic so the gather disappears at n=1) is the fix.
3. **rms_norm at n=1** (1.4 ms). 512-thread workgroup, one workgroup, 20 KB —
   pure latency. `rms_norm_partials.comp` already exists for the multi-workgroup
   case; at decode with a single 5120 row, a smaller BLOCK_SIZE (128/256) or a
   2-stage path would cut the LDS reduction depth. Measure in production only —
   `test-backend-ops` has no RMS_NORM cases.
4. **MoE expert batching** (0.5 ms). Vulkan `mul_mat_id` loops per expert at
   n=1 → 96 dispatches of 0.06 MB. Fusing the 2 experts per layer into one
   dispatch is a real change in `ggml-vulkan.cpp`.

## 5. Measurement rules (do not skip)

- **In-suite numbers lie**: same shapes read 186-277 GB/s in `test-backend-ops`
  but 156-179 GB/s in production (IC-warm masking). Production perop is the only
  speed oracle; in-suite is for ratios only.
- Any change needs: touch `mul_mat_vecq.comp` to force regen → relink
  **llama-server too**, not just test-backend-ops → suite 68/68 → PTQ1_0 golden
  gate stays 7/8 → perop capture, 2 runs for variance.
- The tree was free from 16:48 on 2026-09-25 (the opencode PTQ1_0 agent stalled
  >4 h with no `ITERATION_LOG.md` and no file writes since; tree clean at
  `e728b26` + the `qwen35.cpp` #217 fix). One writer at a time still applies.
