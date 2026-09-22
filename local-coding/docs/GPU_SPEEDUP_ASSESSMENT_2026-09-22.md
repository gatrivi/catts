# GPU speed-up track — independent assessment of the 2026-09-21/22 sessions

Reviewer: follow-up agent, 2026-09-22. Scope: everything the previous agent did on
"make the models actually load/run well on the RX 6600" — the Bonsai-2 config fixes (T1/T2),
the PTQ1_0 Vulkan shader fix, the HIP ladder, and the Kaggle golden pipeline.
Sources: `SESSION_CONTEXT.md` entries 2026-09-21/22, `data/tmp/t1_*/t2_*/final_probe*.json`,
`data/shader_sweep/*`, `data/golden/*`, `data/kaggle_runs/*`, `docs/HIP_PREBUILT_LADDER.md`,
`docs/LOCAL_VULKAN_BUILD.md`, and live rig state re-checked today (not trusting the log alone).

## TL;DR

Real, well-verified progress — but the headline goal was **not** reached, and the evidence
says more of the same work won't reach it. PTQ1_0 decode went 3.3 → **6.4–6.7 t/s (+95%)**,
correctness proven char-for-char against a CUDA T4 golden reference. Target was 20–24 t/s.
**Five independent matmul designs all land at 6.3–6.7 t/s** → the remaining bottleneck is
*outside* the trit matmul (scheduling / attention / other per-token ops) and nobody has
profiled it yet. TQ2_0 still does 12.2 t/s in the same binary, so it stays the daily driver.
The shader track closed at the right place; the next wins are elsewhere.

## What was accomplished (verified)

**A. Bonsai-2 launcher fixes (T1/T2, 9/21 evening) — DONE, partially adopted**
- T1 `--reasoning-effort medium`: PASS. Template default `xhigh` burned the whole token
  budget thinking (5m14s → empty answer); medium finishes the same task in 1m50s.
  Adopted in `scripts/start_bonsai2.ps1` and live in the running server (PID 59404,
  verified cmdline today).
- T2 `-ctk q4_0 -ctv q4_0 -c 32768`: measured but NOT promoted. `data/tmp/t2_mid.json`:
  16,221-token doc stuffed, prefill 69.9 t/s, decode **10.9 t/s** (bar was ≥8). Final
  launcher still ships 8K/q8; roster never got the 32K-usable line. Free win sitting unused.

**B. PTQ1_0 Vulkan shader fix (9/22) — DONE, hit a hard ceiling**
- Full local toolchain with zero installers: portable `C:/tools` (~1.6 GB) + isolated fork
  checkout `C:/src/llama.cpp` @ prism-b10709; `glslc` shim over glslang; build reproduces the
  official baseline exactly (601us/195 GFLOPS matvec; 39/39 correctness). See
  `docs/LOCAL_VULKAN_BUILD.md`.
- Kernel work: LUT matvec v2 = **247us / 473 GFLOPS** (from 601/195), 3/3 correct; MMVQ
  (vecq) port completed and correct; packed16 loads and `-O` tested and rejected;
  subgroup16/rm_kq pipeline config breaks correctness (documented why).
- End-to-end decode: 3.3 → 6.4–6.7 t/s. Golden verification: **7/8 prompts char-identical**
  to the CUDA T4 golden (`spec 25005c6c2ea1d69c`); the single divergence is a 0.007-nat
  top-2 coin flip, not a bug. This methodology is genuinely good — keep it.
- Decisive negative result: 5 matmul designs, same 6.3–6.7 t/s. The bottleneck is NOT the
  shader anymore. Note the shipped house runtime (`llama-prism-b10685-vulkan`, what :9103
  runs) does NOT contain any of this — it only exists in the local C:/src build.

**C. HIP/ROCm ladder — L1 closed with evidence**
- Win-HIP prebuilt FAILS: `ggml-hip.dll` won't load (system `amdhip64.dll` v10 too old),
  gfx1032 not in the Windows ROCm matrix even with `HSA_OVERRIDE_GFX_VERSION`. Do NOT
  install the HIP SDK on Windows — dead end, documented.
- L2 (Linux ROCm, the rung with real chance): untested. WSL2 has no distros; USB-boot
  Ubuntu is the more reliable route (consumer-card driver risk in WSL2).
- L3 (AMD cloud build gfx1032): runbook ready in `docs/AMD_HIP_BUILD_WORKFLOW.md`.

**D. Kaggle golden pipeline — DONE, reusable**
- Token in `~/.kaggle/access_token`; golden captured on T4 CUDA (PTQ1_0 ran 11.9–17 t/s
  there — the same model is 2-3x faster on a 2018 datacenter card than our best local).
  Quota used: 1.8/30 h. Shader-compile pipeline (`shader_build_kernel.py` + spv import
  shim) is reusable for any future shader experiment without installing the Vulkan SDK.

## Gaps — what "accomplished but not enough" concretely means

1. **PTQ1_0 plateau vs target**: 6.4–6.7 vs the 20–24 predicted. The prediction assumed the
   matvec WAS the bottleneck; it isn't anymore. No per-op profile exists — the missing 2x
   is unidentified, not unfixable-in-principle.
2. **TQ2_0 (the daily driver at 12.2 t/s) has never been quality-checked against the golden
   reference.** It's a requantization of PTQ1_0 (double-quant risk flagged 9/18, still open).
   If it diverges from golden materially, our fastest config is also our least trusted.
3. **Doc rot (minor)**: `MODEL_ROSTER.md` row 10 was stale (PTQ1_0 "3.3 broken dead end")
   and row 9 lacked the golden-check caveat. Both fixed today; T2/reasoning-effort were
   already in row 9, just not promoted to a selectable preset (see task 2).
4. **`gpu_sweep.py` has never produced data**: the only run (9/20) is all `load_failed` /
   `ram_floor`. mini/qwen35 presets are still guesses.
5. **C: at 99%** (standing rule): any further build work must watch disk; bare `ninja`
   fills it.
6. Some old comparisons ran with a model alive on the GPU (contended) — the agent flagged
   this itself (pp128: 77 exclusive vs 59 coexisting). Treat pre-9/22 numbers as ±20%.

## What the next person should do (ordered)

1. **Golden-check TQ2_0** — ✅ DONE 2026-09-22: **FAILS the bar: 4/8 prompts diverge**
   (live :9103, shipped b10685, GPU exclusive). Not coin flips: golden's top-2 gaps at the
   divergent steps were 0.13 / 0.45 / 1.34 / 0.62 nats and TQ2_0 always picked the golden's
   rank-2/3 token → real numeric drift from the double-quant. All four outputs stayed
   grammatical and correct in substance. Decode 10.5–12.6 t/s during capture.
   Caveat left open: TQ2_0 ran on shipped b10685 while the PTQ1_0 control ran on the fork,
   so runtime-vs-model isn't isolated. **Implication**: TQ2_0 = fast-but-drifting daily
   driver; PTQ1_0+LUT = fidelity path. If the drift ever matters, the likely fix is
   re-quantizing TQ2_0 from a higher-precision source (BF16/F16 + imatrix) instead of from
   PTQ1_0 — same fast kernel path, without stacking two quant error floors.
2. **Adopt the T2 result** — ✅ DONE 2026-09-22: bonsai2 `high` preset is now
   `-c 32768 -ctk q4_0 -ctv q4_0` in `scripts/local_models.py` + launcher + roster;
   29 tests pass. Also fixed on the way: `smol_server_args('bonsai2')` stripped
   `--reasoning-format` but orphaned its `deepseek` value as a stray positional in the
   Smol-slot argv (regression test added in `tests/test_smol.py`).
3. **Profile the non-matmul floor** (one focused session, needs the C:/src build):
   per-op timing on PTQ1_0 vs TQ2_0 graphs (same binary, everything else equal) to find
   which op eats the delta — candidates: attention path, RMS-norm/rope variants, or a
   fallback generic `mul_mat` shape still hitting a scalar ptq1_0 path. Only resume shader
   work if a specific op shows up; otherwise accept 6.4–6.7 as the rig ceiling.
4. **Ship the upstream PR** (material ready: kernel + vecq + env switches + golden
   methodology + numbers). Even at 1.4–2.6x kernel-level it helps every AMD user; and
   upstream review may hand us the pipeline-config answer for free.
5. **Run the real sweep once** (GPU idle, RAM free): `python scripts/gpu_sweep.py` —
   finally fill the mini/qwen35/bonsai2 -b/-ub × KV matrix with data.
6. **HIP L2 only if (3) finds nothing and PTQ1_0's VRAM headroom matters**: USB-boot Ubuntu
   + ROCm prebuilt (`docs/HIP_PREBUILT_LADDER.md`). Do not spend AMD cloud credits before
   L2 fails.

## Do NOT

- Reopen shader micro-optimization (5 designs, same plateau — that's a wall, not a bug).
- Install HIP SDK / WSL ROCm stack on Windows.
- Run bare `ninja` in C:/src (disk at 99%; named targets only).
- Trust any number measured while another model held VRAM.
- Edit `kaggle/golden_prompts.json` (frozen spec; editing forks the reference hash).

## Current truth table (RX 6600, GPU exclusive, measured on-rig)

| Config | Decode | Status |
|---|---|---|
| Bonsai-2 TQ2_0, 8K, q8 KV (daily driver) | 12.2–13 t/s | shipped; golden-check FAILS 4/8 (real drift, outputs still sound) |
| Bonsai-2 TQ2_0, 32K, q4 KV, 16K fill | 10.9 t/s | ✅ adopted as `high` preset 9/22 |
| Bonsai-2 PTQ1_0, new LUT build (C:/src only) | 6.4–6.7 t/s | golden-verified 7/8; not in house runtime |
| Bonsai-2 PTQ1_0, shipped b10685 runtime | 3.3 t/s | obsolete but still what's installed |
| Bonsai-2 PTQ1_0, Kaggle T4 CUDA | 11.9–17 t/s | reference point |

