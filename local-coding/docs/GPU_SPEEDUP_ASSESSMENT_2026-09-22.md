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
| Bonsai-2 PTQ1_0, Kaggle T4 CUDA | 11.9–17 t/s | reference point; measured at 16K-ctx config, ≤320-token greedy prompts — long-ctx T4 numbers are extrapolated |

## Peer-review addendum (2026-09-22 evening)

Corrections from evidence-checking after items 1–2 landed:

- **Double-quant confirmed by construction**: the quantize log shows TQ2_0 was made with
  `llama-quantize --allow-requantize --output-tensor-type TQ2_0` **from PTQ1_0, no
  imatrix**. The drift signature (0.13–1.34 nat top-2 gaps) matches.
- **But an alternative cause is untested: the Vulkan `tq2_0` kernel itself.** HF ships only
  F16 / PTQ1_0 / PQ2_0 — TQ2_0 is ours, so PTQ1_0 and TQ2_0 run different shader paths and
  only the PTQ1_0 one was golden-verified. **Decision gate (free, ~40 min CPU, no GPU/quota):
  golden-capture TQ2_0 with `-ngl 0`.** CPU clean → kernel-level bug → B won't fix it
  (becomes kernel/PR work in the C:/src build). CPU drifts 4/8 → B is the right fix.
  Run this BEFORE any cloud requant spend.
- **B cost correction**: source is `Ternary-Bonsai-2-27B-F16.gguf` = 53.8 GB; local free
  space (C 12.5 / E 4.0 / Z 18.3 GB) can't hold it → cloud quantize is mandatory, and the
  binding constraint is host DISK (~61 GB with output), not RAM (`llama-quantize` streams;
  the PTQ1_0→TQ2_0 run took 6 min). Kaggle working+tmp ≈40 GB is too small → **Colab is the
  realistic host**; imatrix is an extra calibration job on top.
- **PQ2_0 is a dead shortcut**: author-made PQ2_0 (7.2 GB) has no Vulkan kernel
  (`ggml-vulkan.dll` exposes dequant_ptq1_0/tq2_0 only; pq2_0 traits exist CPU-side only)
  → CPU-only ≈ unusable. Don't spend the transfer.
- **Item 3 reframed**: bounded (247 µs vs 94.6 µs matvec ⇒ best case ≈ TQ2_0's ~12 t/s —
  an inference, not a measurement) but NOT worthless: it's the only route to faithful+fast
  without a cloud requant, and it feeds the upstream PR. Priority depends on the CPU
  control above.
- **Path B is fully specified**: the Colab requant job — verified toolchain (Linux CPU
  tarball ships `llama-quantize` + `llama-imatrix`), exact positional-type command with
  both `--*-type TQ2_0` overrides, real sizes (TQ2_0 = 2.06 bpw, 6622 MiB, peak disk
  67.7 GB), the HF repo, and private-HF persistence — is in
  `docs/COLAB_TQ2_REQUANT_JOB.md`.


## CPU decision gate — RESULT: the drift is the QUANT, not the kernel (2026-09-22, late)

Ran the gate exactly as specced: shipped `llama-prism-b10685-vulkan` runtime, `-ngl 0` (CPU),
otherwise identical flags to the GPU capture, `:9103` and the GPU untouched.

- Dump: `data/tmp/tq2-cpu-20260922.json` (spec 25005c6c match, 8/8 prompts, top-logprobs).
- `golden_check` vs the CUDA golden: **4/8 divergent, exit 1** — code_summary (t18),
  toolcall (t1), es_mar (t6), fox_cont (t1). Same four prompts, same steps and the same
  replacement tokens as the Vulkan run (`.` / ` can` / ` la` / ` scene`).
- **CPU and Vulkan are byte-identical on 7/8 prompts**; fox_cont agrees through token 7 and
  only then continues differently. Two independent kernel implementations agree with each
  other and disagree with the PTQ1_0 CUDA golden ⇒ **the divergence lives in the TQ2_0
  weights** (double-stack), not in the tq2_0 shader.
- Cost for the record: 0.54–0.74 t/s decode, ~1.15 t/s prompt eval, count300 (320 tok) took
  462 s, whole capture ~16 min. RAM: 6.48 GB resident, free RAM fell to ~0.7 GB (the iGPU
  UMA carves ~5 GB out of the 15.4 GB total) — slow but stable, no thrash-kill.

**Verdict: Path B lives.** A requant from F16 (+ imatrix if affordable) is the correct fix;
do NOT spend shader effort on tq2_0 for fidelity. Gate cost ~30 min wall clock, zero quota.
## Discord recon addendum — ROCm on gfx1032, as of 2026-09 (AMD Developer server)

Scraped 2026-09-22. Revises section C (HIP ladder, L2):

- **Official line (ROCm AI Assistant, citing the compatibility matrix):** gfx1032 (RX 6600,
  Navi 23) still NOT in the official support matrix; `HSA_OVERRIDE_GFX_VERSION=10.3.0`
  remains the path. gfx1030 (6800/6900) is natively supported on Linux.
- **NEW — TheRock PR #5719 (2026-06):** gfx103X-dgpu **Linux nightly wheel builds
  re-enabled**, gfx1032 marked **"Sanity Tested" on Linux** (83/87 ctest; 4 failures are a
  missing RDC artifact, not GPU). Windows stays disabled. → prebuilt ROCm/PyTorch gfx1032
  wheels exist as nightlies; L2 build risk is lower than when L2 was shelved.
- **Community confirmations:** TheRock PR #1629 thread — works on RX 6800 / **6600** /
  6750 XT (2026-02); soulafein83 (2026-07): "RX 6600 … performing very well on CachyOS
  with ROCm 7.13".
- **WSL2 correction to the original L2 note:** AMD's own blog (2026-03) documents RX 6600
  on WSL2 (Adrenalin ≥25.6.1, `amdgpu-install --usecase=wsl,rocm`, Ubuntu 22.04/24.04) —
  so WSL2 is *documented*, not merely rumored. Still second choice here: the VHDX lands on
  C: (99% full — relocatable but friction), and native external-SSD install avoids both the
  disk problem and the translation layer. WSL2 is now a legitimate **cheap probe** (hours,
  no repartition) before committing the external SSD.
- **AMD staff (Guo Hongwei, 2026-08):** ROCm vs Vulkan has no universal winner — test both
  on the same device/model; cites an RX 6600 lemonade issue where ROCm OOM'd on 8 GB while
  Vulkan ran. Our 8 GB budget is the standing risk for PTQ1_0 (7.5 GB file + KV) — favors
  TQ2_0 (6.6 GB) for the first HIP probe.

**Net:** L2 upgraded from "untested, risky" to "community-verified, nightlies available".
Recommended probe order: (1) WSL2 quick test if C: can be freed or VHDX relocated,
else (2) Ubuntu/CachyOS on external USB3 SSD, ROCm 7.x + override, build prism fork
`-DGGML_HIP=ON`, PTQ1_0 vs golden_check. The CUDA ternary kernels (proven 11.9–17 t/s on
T4) carry to HIP via hipify, so PTQ1_0 ≈ 8–12 t/s faithful is a plausible outcome.

### Second pass — live Discord search (2026-09-22, same day)

Independent agent drove the AMD Developer server search box directly and read messages.
Corrections/additions to the addendum above:

- **Headline negative:** NO gfx1032 + llama.cpp HIP success report exists in that server
  (`gfx1032 llama`, `6600 llama.cpp`, `gfx1032 prebuilt` all empty as actually read;
  multi-term counts were flaky, so only read messages count). The gfx1032 validation that
  DOES exist lives in **TheRock PR #5719** — CI `-- Test targets:` include gfx1032/1030/
  1031; independent RX 6800 Linux validation posted to complement "gfx1032 results already
  shared on this PR". **Next read: that PR thread.**
- **rocBLAS gap is real and dated:** `TensileLibrary_lazy_gfx1032.dat not found, failed to
  verify manifest` while building TheRock with `gfx103x-dgpu` (nym, 2025-05). Mitigation
  stands: build the fork with `AMDGPU_TARGETS=gfx1032` — ggml's own kernels compile
  natively; the override/prebuilt-blob risk concentrates in the *math libraries*
  (rocBLAS/hipBLASLt), which llama.cpp barely uses on the hot path.
- **Cheapest probe identified:** `lemonade-sdk/llamacpp-rocm` publishes nightly llama.cpp
  ROCm-7 builds on TheRock — IF gfx1032 math-libs are in them, that's a free stack smoke
  test. **Caveat: those are STOCK llama.cpp — no ternary kernels.** Useful to validate
  ROCm+override+bench a standard quant on the 6600 *before* spending effort on the prism
  fork HIP build; it can never run Bonsai-2 itself.
- **L1 verdict reinforced:** AMD's Windows HIP SDK page lists gfx1032 ❌; the
  `win-rocm-7.14-x64` upstream prebuilt has `ggml-hip.dll` missing-import on `hipblas.dll`
  (issue #26996) — same err=126 class as our L1 failure. Windows HIP dead end now backed by
  AMD's own docs AND a packaging bug independent of arch.
- **Expectation correction (important):** Phoronix ROCm 7.1 vs RADV + community reports put
  **Vulkan ahead for decode, ROCm ahead for prefill** on RDNA2. My "PTQ1_0 ≈ 8–12 t/s
  decode on HIP" estimate above is UNVERIFIED (T4 confound: 320 GB/s + mature CUDA path).
  Honest position: HIP probe is more likely a **prefill / quality-path** win than the
  missing decode 2×. Test both directions; don't pre-commit to decode.
- **WSL2 hedge:** one fresh report of llama.cpp ROCm failing entirely on WSL2/Windows
  (AJO, 2026-09-19 — but an RDNA4 card, not Navi 23). WSL2-first probe order kept, with
  the C: 99% disk constraint still the practical blocker.
- **Navi 23 memory faults:** no corroborating report (`gfx1032 fault` empty) — treat as
  open question, not established.
