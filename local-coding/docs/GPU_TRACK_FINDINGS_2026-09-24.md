# GPU track findings — review document (2026-09-24)

Purpose: single review-ready record of the RX 6600 LLM-speedup track. Every claim
carries its measurement. Written for a reviewer who has read nothing else. Decision
table at the end; artifact index at the bottom.

---

## 1. Executive summary

- The rig: Ryzen 5 PRO 4650G, RX 6600 8 GB (224 GB/s), 15.4 GB RAM (iGPU UMA takes
  ~5), models on Z: HDD, C: chronically ~97-99% full.
- Two production models: **TQ2_0** (daily driver, 12–13 t/s) and **PTQ1_0** (fidelity
  path, golden-verified, 3.3 → 6.4 → **7.4–7.9 t/s** after today).
- Today delivered: **PTQ1_0 −18% decode GPU time** (int8 LUT fix) + repair of a broken
  vecq shader file + a falsified layout hypothesis + a full findings trail.
- The verified, unexploited lever: **TQ2_0 has no integer-dot decode path** (q4_0 does,
  and q4_0 proves 217 GB/s = 97% of peak is reachable on this card). Porting it is the
  concrete 15–20 t/s candidate for the daily driver.
- Open decision: port TQ2_0 (one focused session), package the upstream PR, run the
  profiler (RGP), or close the track. Costs/payoffs in §6.

## 2. Hardware physics — why "graphics does it, why can't the LLM" is the wrong analogy

- Real-time graphics saturates the card because millions of pixels are independent.
- LLM decode is the opposite: **one token at a time; each token requires streaming ALL
  weights once (TQ2_0: 6.48 GB); the next token depends on this one.** No parallelism
  across tokens. Decode speed = memory bandwidth utilization, nothing else.
- **TQ2_0 ceiling: 6.48 GB ÷ 224 GB/s = 29 ms/token = 34.5 t/s at 100% bandwidth.**
  PTQ1_0: 5.95 GB → 37.6 t/s at 100%.
- Today: TQ2_0 = 12–13 t/s = **38% of bandwidth**; PTQ1_0 = 7.4–7.9 t/s = ~43% (was 24%).
- Proof the card can stream at peak: a single q4_0 matvec (715 MB, cold) measured
  **3300 µs = 217 GB/s = 97% of peak** on this card. Hardware is not the limit.

## 3. Wins (verified, with artifacts)

| Date | Change | Effect | Verification |
|---|---|---|---|
| 09-22 | PTQ1_0 LUT matvec kernel (op 601→247 µs) | PTQ1_0 3.3 → 6.4 t/s | golden 7/8 vs CUDA T4 |
| 09-24 | Repaired `mul_mat_vecq_funcs.glsl` — **it had never compiled since 09-22** (duplicate sections + stray fragment + unbalanced `#endif`); all PTQ1_0 MMVQ dispatches were silently falling back to the f32 path | vecq path exists for the first time | 68/68 suite |
| 09-24 | **int8 LUT** (shared LUT 5 KB float → 1.25 KB int8) in both f32 matvec and vecq paths | PTQ1_0 GPU-sum **157.8 → 129.2 ms/tok (−18%)**; gate/up 483→377 µs; down 470→376; lm_head 6683→5249; server decode timing **7.72 t/s** (`tg_tps`, count300 — headline metric); wall 7.44 t/s incl. prefill+HTTP | 68/68 suite + **golden 7/8** (`data/golden/confirm-20260924-195613.json`; retained suite log `data/provenance/suite-log-20260924.txt`) |

Key insight that produced the int8 win: even with the tensor **inside the 32 MB Infinity
Cache**, the old kernel delivered only 52 GB/s — issue-limited, not memory-limited. The
5 KB float LUT capped occupancy (~12 wavefronts/CU). Storing trit+1 as int8 cut LDS
5 KB → 1.25 KB.

**Timings note (reconciled):** 7.72 t/s = the server's own decode-only timing
(`tg_tps` in the capture JSON) — the headline metric. 7.44 t/s = wall clock
(tokens ÷ total request time, includes prefill + HTTP). Both from the same capture.
**Run-to-run variance:** 129.19 / 128.44 ms/tok across captures = <1%.

**Golden gate rule (explicit, replaces the informal override):** the single divergent
prompt (`toolcall`) diverges at token 0. Three facts make it a numeric coin-flip, not a
harness fault: (1) the golden spec's toolcall prompt is **plain text with no tools
array** — T4 and our capture sent byte-identical payloads, ruling out environmental
mismatch; (2) the 09-22 capture (`bonsai2-ptq10-lut-vulkan-20260922-131535.json`)
retained the top-logprobs showing a 0.007-nat top-2 gap at the divergence step;
(3) two independent kernel builds (pre- and post-int8) reproduce the identical
92/81-char divergence profile. Rule: `toolcall` is reported separately and the numeric
bar is ≥7/8 of the remaining prompts; any NEW divergence outside toolcall = hard fail.

Also today: day-1 baseline harness first run; per-op capture script
(`scripts/d1_perop_profile.py`) using the fork's built-in `GGML_VK_PERF_LOGGER`
(timestamp queries — no rebuild); production decode shapes added to `test-backend-ops`.

## 4. Refuted hypotheses (each closed with a measurement)

| Hypothesis | Test | Result |
|---|---|---|
| 5 matmul kernel designs differ | all measured | tie at 6.3–6.7 t/s (09-22) |
| Workgroup width matters | `GGML_PTQ1_0_WG` 32/64/128 | 64 = exact tie; 128 = −18% lm_head but 1 batched-case correctness fail → parked; ceiling ~5–7% E2E anyway |
| Load redundancy limits speed (V-C cooperative LDS staging) | kills all redundant loads, no layout change | **−5% (regressed)** → redundancy disproven → **E3 repack skipped** |
| LDS serialization limits speed (zero-LDS closed form) | arithmetic vs LUT | tie; parked (LDS now 1.25 KB) |
| Element-major layout would fix it | V-C gate refuted its premise | skipped (saved ~half day) |
| ROCm/HIP on gfx1032 Windows | L1: amdhip64.dll too old; gfx1032 not in Windows matrix | closed 09-21 |
| ROCmFPX fork helps gfx1032 | validated on gfx1151 only; no Windows prebuilts verified; no ternary support | closed 09-24 |
| Sub-32 MB suite numbers are honest | **Infinity-Cache confound found**: suite re-reads the same tensor → IC-inflated (tq2_0 161 GB/s in-suite vs 102 cold). The 280 MB lm_head shape is IC-immune and matches production | all future A/Bs use lm_head; pre-09-24 suite numbers distrust |
| test-backend-ops covers production shapes | test mode silently culls large shapes | production correctness only via golden gate |

## 5. The verified structural gap (the unexploited lever)

- **TQ2_0 has no integer-dot vecq path** — grep-verified: no `DATA_A_TQ2_0` branch in
  `mul_mat_vecq_funcs.glsl`, no `mul_mat_vec_tq2_0_q8_1` pipeline. It decodes via the
  float-FMA specialized matvec with per-element unpacking.
- q4_0 (which HAS the int-dot vecq path) streams at 217 GB/s (97% of peak) on this card.
- Port = same pattern as the PTQ1_0 vecq branch (Q2_K's repack4 + int-dot, adapted to
  tq2_0's 2-bit layout and the sumq−sumb ternary identity). In-tree templates exist.
- Expected payoff if it behaves like q4_0: **TQ2_0 12–13 → est. 15–20 t/s** — the daily
  driver, i.e. the model catintassist serving actually uses.
- Risk: other "should be faster" variants tied; only the measurement decides. Cost if it
  ties: the session itself, and the track closes with a complete negative map.

## 6. Decision table (what remains, with costs)

| Option | Token cost | Payoff | Risk |
|---|---|---|---|
| **TQ2_0 int-dot vecq port** | ~1 focused session (spec can be pre-written) | daily driver 12–13 → est. 15–20 t/s (58% BW) | medium — may tie; golden gate decides |
| Upstream PR (int8 LUT + vecq repair + golden methodology + numbers) | ~1 session, or patch-only (KB) | community value; upstream review may answer pipeline-config questions | low |
| RGP profiler capture | 1–2 GB C: for installer + captures (C: at ~3 GB — cleanup needed first); 1 analysis session | per-instruction ground truth | disk risk; only if the port disappoints |
| Close track now | 0 | PTQ1_0 +18% and full map banked; TQ2_0 keeps working at 12–13 | none |

**Cloud assessment:** no cloud path exists for this work. Kernel tuning is
Vulkan-on-RDNA2 — measurement requires this rig. Kaggle T4 = CUDA (its job — the CUDA
golden reference — is done and banked); AMD cloud = gfx942/HIP (wrong ISA, wrong API).
Cloud also cannot run the golden-fidelity gate for a Vulkan kernel change. The build +
test + measure loop itself is local scripts and costs **zero tokens**; tokens only pay
for agent judgment.

## 7. Token-efficiency rules for any continuation

- Measurements are already automated and free: `CATTS-NightJobs` (02:30, clean baseline
  + first gpu_sweep data → `data/night/<date>/MORNING_REPORT.md`) and `CATTS-GPUConfirm`
  (10:00–22:00 polling → perop + golden gate → `data/confirm/<date>/`). Both are
  scripts-only (no LLM). Delete the Confirm task on video-call days — it cannot see
  dGPU video decode.
- Shader iteration = local loop (edit → `ninja test-backend-ops` → perf lm_head →
  suite) — zero tokens; agents only read the 5-line verdicts.
- Any agent session starts from this document + the runbook, never from history
  re-derivation. Spec-first: pre-write implementations before the session that runs them.
- Batch decisions at session end; no open-ended "what else" exploration.

## 8. Artifact index

- Baselines: `data/profile/d1_20260924-{150704,191300,193411}.json` (9.36 @2.5 GB /
  9.28 @4.3 GB / 10.05 @7.3 GB — RAM curve; roster 12–13 re-examined at 02:30)
- Per-op captures: `data/profile/d1_perop_20260924-{151504,152010,195142,195503}.json`
  (TQ2_0 81.8 ms/tok op-sum; PTQ1_0 157.8 → 129.2 with int8)
- Golden: `data/kaggle_runs/gold-20260921/golden.json` (CUDA T4 reference);
  `data/golden/confirm-20260924-{183714,195613}.json` (7/8 both)
- Shader backups: `data/shader_baks/mul_mat_vec_ptq1_0.comp.bak-{e2,e2a}`
- Scripts: `scripts/profile_day1.ps1`, `scripts/d1_perop_profile.py`,
  `scripts/night_jobs.ps1`, `scripts/wait_gpu_confirm.ps1`
- Deeper docs: `GPU_SPEEDUP_ASSESSMENT_2026-09-22.md` (D1/D2 sections),
  `D2_ROUND2_RUNBOOK_2026-09-24.md`, `GPU_CRAWL_2026-09-24.md`,
  `docs/HIP_PREBUILT_LADDER.md`, `docs/AMD_HIP_BUILD_WORKFLOW.md`,
  `docs/COLAB_TQ2_REQUANT_JOB.md`
- Tasks: `CATTS-NightJobs` (daily 02:30, first run 25/09), `CATTS-GPUConfirm` (daily
  10:00, first run 25/09); legacy openclaw one-shots `CATTS-GPU-Crawl/-2/-3` +
  `CATTS-Morning-Ready` are inert (the "lost crawl agent" — found)
