# Knowledge pack — RX 6600 ternary decode campaign

Compiled: 2026-09-25 16:32. Source: 24 recorded measurements
across 6 groups, 24 cells
(23-night scripted campaign, zero cloud tokens).

Read this with `GPU_TRACK_FINDINGS_2026-09-24.md` (track history and refuted
hypotheses) and `D2_ROUND2_RUNBOOK_2026-09-24.md` (build/test loop). The task:
design a Vulkan decode kernel for PTQ1_0/TQ2_0 ternary weights on RDNA2 that
beats the measured baselines below. The correctness oracle is the golden gate
(bar >=7/8 prompts, toolcall coin-flip excluded — see findings doc) plus the
68-test suite.

## Hard constraints

- Card: RX 6600 8 GB, 224 GB/s peak, 32 MB Infinity Cache (working sets under
  ~32 MB get cache-inflated numbers — use lm_head 248320x5120 for cold-true).
- TQ2_0: 6.48 GB/token -> 34.5 t/s at 100% bandwidth. PTQ1_0: 5.95 GB -> 37.6.
- Weights are ternary {-1,0,1}*scale; 2-bit/trit fields need ~1 ALU op per
  element to extract (six variant families measured at this wall — do not
  re-test the refuted list in the findings doc).
- C: has ~3 GB free: named ninja targets only, no new installs without asking.

## baseline (1 measurements)

| cell | value(s) | unit |
|---|---|---|
| baseline:mean_tps | 10.25 | t/s |

## bw (5 measurements)

| cell | value(s) | unit |
|---|---|---|
| bw:cpy-16MB | 644 | GB/s_read_write |
| bw:cpy-1MB | 445.3 | GB/s_read_write |
| bw:cpy-256MB | 184.8 | GB/s_read_write |
| bw:cpy-4MB | 585.1 | GB/s_read_write |
| bw:cpy-64MB | 183.5 | GB/s_read_write |

## drafter (1 measurements)

| cell | value(s) | unit |
|---|---|---|
| drafter:downloaded | ["NOT_FOUND"] | string |

## mm (14 measurements)

| cell | value(s) | unit |
|---|---|---|
| mm:q4_0-m10240-n1-k5120 | 72.96 | us_per_run |
| mm:q4_0-m12288-n1-k5120 | 128 | us_per_run |
| mm:q4_0-m17408-n1-k5120 | 236.6 | us_per_run |
| mm:q4_0-m17408-n2-k5120 | 237.9 | us_per_run |
| mm:q4_0-m17408-n4-k5120 | 366.7 | us_per_run |
| mm:q4_0-m17408-n8-k5120 | 803.9 | us_per_run |
| mm:q4_0-m248320-n1-k5120 | 3312 | us_per_run |
| mm:q4_0-m248320-n2-k5120 | 3325 | us_per_run |
| mm:q4_0-m248320-n4-k5120 | 5187 | us_per_run |
| mm:q4_0-m248320-n8-k5120 | 1.13e+04 | us_per_run |
| mm:q4_0-m4096-n1-k14336 | 90.87 | us_per_run |
| mm:q4_0-m5120-n1-k17408 | 235.8 | us_per_run |
| mm:q4_0-m5120-n1-k6144 | 44.65 | us_per_run |
| mm:q4_0-m6144-n1-k5120 | 52.85 | us_per_run |

## specdec (2 measurements)

| cell | value(s) | unit |
|---|---|---|
| specdec:tq2_0-base | ["[{\"n\":76,\"tps\":17.563613064705287},{\"n\":76,\"tps\":19.141466925459298}]"] | tps_list |
| specdec:tq2_0-ngram | ["[{\"n\":76,\"tps\":19.30662943318825},{\"n\":76,\"tps\":20.00072535963971}]"] | tps_list |

## sweep (1 measurements)

| cell | value(s) | unit |
|---|---|---|
| sweep:completed | 0 | bool |

## Sources and loop

- Shaders: `C:/src/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/`
  (`mul_mat_vec_ptq1_0.comp`, `mul_mat_vec_tq2_0.comp`, `mul_mat_vecq.comp`,
  `mul_mat_vecq_funcs.glsl` — all fork-local changes documented).
- Build: `ninja -C C:/src/llama.cpp/build test-backend-ops llama-server`
  (named targets ONLY; touch mul_mat_vecq.comp to force shader regen;
  relink llama-server too when shaders change).
- Perf: `test-backend-ops perf -b Vulkan1 -o MUL_MAT -p "<type>.*n=1,"` —
  lm_head m=248320 is the cold-true A/B shape.
- Correctness: `test-backend-ops test -b Vulkan1 -o MUL_MAT -p ...` (test mode
  culls large shapes — production correctness goes through the golden gate).
- End-to-end: `scripts/d1_perop_profile.py` (GPU-sum ms/tok per op family).
- Golden: `scripts/golden_capture.py --url http://127.0.0.1:9103 --name
  bonsai2-ptq10` then `golden_check.py` (>=7/8; toolcall coin-flip excluded,
  see findings doc gate rule).

## Open questions this pack cannot answer

- Per-instruction issue analysis (needs RGP capture — not installed).
- Whether a from-scratch ISA-level ternary kernel beats the GLSL path
  (never attempted; the measured wall is per-element ALU cost).