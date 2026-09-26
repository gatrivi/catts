# Bonsai-2 reasoning-effort adaptation (from @sudoingX findings) — 2026-09-21

## Status: T1 + T2 DONE 2026-09-21 (see RESULTS below). T3 blocked on Windows HIP.

## RESULTS (2026-09-21, all greedy, max_tokens as noted, GPU exclusive)
- **T1 PASS.** Baseline stock: 5m14s, 4000/4000 completion tokens ALL reasoning
  (~9.5k chars), finish=length, answer EMPTY. `--reasoning-effort medium` same
  prompt: 1m50s, 1417 tokens (1240 chars think + 1782 chars HTML), finish=stop.
  65% less wall time. Quality probe find_dup @ medium: correct (answer 3),
  finish=stop. -> flag added to start_bonsai2.ps1. (`--reasoning-budget` variant
  not run; medium sufficed.)
  GOTCHA: do NOT put PS comment lines between a backtick continuation and the
  command tail — first edit did that and the flag was silently dropped
  (smoke test caught it: empty answer again). Comments go ABOVE the command.
- **T2 PASS with caveat.** TQ2_0, `-ctk q4_0 -ctv q4_0 -c 32768`:
  fresh decode 12.5 t/s (no penalty vs q8 8K baseline 12-13); with 16,221-token
  prompt in context decode 10.9 t/s (vs 3.2 t/s in the old 100K/q8 config —
  that one is dead, this one lives). Probe answered correctly.
  CAVEAT: prompt processing 69.9 t/s -> 232 s to ingest 16k. Fine for persistent
  sessions, painful for one-shot big prompts. Not made default; run ad hoc with
  the flags above.
- **T3 BLOCKED on Windows.** PrismML ships Windows HIP builds (b10709, 322 MB,
  tested) but `--list-devices` = none on our RX 6600: gfx1032 unsupported by
  Windows HIP SDK; HSA_OVERRIDE_GFX_VERSION is Linux-only. Only path = WSL2 +
  Ubuntu ROCm 7.2 build + override. Parked (big install). HIP build deleted.

## EXECUTION PLAN (original, in order, each ~20-30 min, GPU exclusive required)
Baseline before any change: stock start_bonsai2.ps1, decode 12-13 t/s @ 8K q8 KV.

**T1 — reasoning effort A/B** (highest confidence, do first)
- Start stock; send one known build-task prompt (the overnight plan-call prompt
  works) at max_tokens 4000, greedy. Record think tokens, wall time, finish_reason.
- Restart with `--reasoning-effort medium`; same prompt. Record same.
- Also try `--reasoning-budget 2048` variant.
- PASS if medium cuts think time >=40% with no answer-quality regression on a
  2nd probe (toCents or trace-find_dup). Then add winning flag(s) to
  start_bonsai2.ps1 + update roster row. ROLLBACK: remove flag.
- Check smol/e4b proxies: do they send reasoning_effort? If yes, note override.

**T2 — q4_0 KV @ 32k** (context win)
- Relaunch TQ2_0 with `-ctk q4_0 -ctv q4_0 -c 32768` (keep everything else).
- Measure: load OK, weights stay on GPU (ngl 99 effective), decode fresh AND with
  ~16k of doc stuffed in. Compare vs 8K q8 baseline.
- PASS if >=8 t/s mid-fill and probes still pass. If PASS: new roster line
  "32k usable via q4 KV"; if marginal (<8 t/s), keep 8K q8, close item.

**T3 — ROCm backend recon** (research only this round)
- Check PrismML releases/branches for a ROCm/HIP Windows (or WSL2) build of the
  fork compatible with gfx1032 + our GGUF quants.
- Only if a prebuilt exists: bench decode vs Vulkan b10685 on TQ2_0, same flags.
- PASS if >=20 t/s fresh. Otherwise record "no ROCm build, revisit <date>".

Order rationale: T1 is nearly free (template flag, corroborated by our own failure
logs), T2 needs a relaunch and could stall at load, T3 is blocked on upstream.
Total ~1.5 h GPU-exclusive. Stop-other-models rule applies (Spark/Qwen/MiniCPM off).


## The claim (their RTX 3060, CUDA PTQ1_0 + kernel)
- Bonsai-2's chat template defaults `reasoning_effort` to **xhigh** → huge thinking
  budgets. At 4K max_tokens, build tasks returned **empty answers** after ~108 s of
  thinking; `--reasoning-effort medium` made the same tasks finish in 45–58 s.
- Clients sending their own `reasoning_effort` override the server flag.
- At 4K even medium truncates long generations → use 16K max_tokens for big outputs.

## Why we believe it applies to us (independent corroboration in OUR logs)
- MODEL_ROSTER.md bonsai2 row: "verbose: max_tokens 2500+, json_object truncates".
- SESSION_CONTEXT.md overnight run: all 6 tasks MODEL FAIL at max_tokens 1200
  (finish_reason=length, verbose reasoning); "8192 reasoning tokens hit response
  limit at ~389 s".
- Our fork (llama-prism-b10685-vulkan) exposes `--reasoning-effort LEVEL` AND
  `--reasoning-budget N` (verified via --help). Start script passes neither, so the
  template default (xhigh) applies to us too.

## Plan (when picked up)
1. Test first, A/B: start bonsai2 on :9103 twice — stock vs `--reasoning-effort medium`
   (and try `--reasoning-budget 2048` as an alternative knob). Same greedy prompt,
   compare think-token count, wall time, answer completeness. Budget ~20 min.
2. If confirmed: add the winning flag(s) to `scripts/start_bonsai2.ps1`
   (TQ2_0, our everyday file — weights untouched, flag only affects the chat template).
3. Update MODEL_ROSTER.md bonsai2 row (max_tokens guidance may relax from 2500+).
4. Note: our smol/e4b proxies that call :9103 may send their own reasoning_effort —
   check whether the client override path bites us (tweet says client wins).

## From the X/Grok "rig tuning" threads (2026-09-21) — 2 testable, rest is known
1. **q4_0 KV for longer context** (TESTABLE): our 100K test failed because q8 KV
   pushed weights off the 8 GB card (3.2 t/s). Bonsai-2 is hybrid-attention
   (~16/64 layers full KV), so q4_0 KV halves the KV and may make 32–64k usable.
   Test: `-ctk q4_0 -ctv q4_0 -c 32768` on TQ2_0, measure t/s fresh + mid-fill.
   Caveat: quality hit "measurable but often acceptable"; our 8K q8 setup stays
   default if gain is marginal (8K KV is tiny anyway — only pays at long ctx).
2. **ROCm/TheRock instead of Vulkan** (TESTABLE, bigger potential win): RDNA2 gfx1032
   via `HSA_OVERRIDE_GFX_VERSION=10.3.0`; community claims ROCm beats Vulkan on RX
   6600-class. Would need a Prism fork ROCm/HIP Windows build (or WSL) — our
   b10685 is Vulkan-only. Check PrismML releases for a ROCm build before investing.
   If decode jumps 12-13 -> 20+ t/s, roster lines change broadly.
- Not new to us: flash attention on, ngl 99, single slot, -b/-ub tuned, reasoning
  budget (section above), "avoid CPU offload on 16 GB RAM" (already enforced),
  model picks (Spark/MiniCPM5/NeoHorse already in roster; "Spark-X2.5-4B" thread
  model doesn't match our spark — verify before trusting that ranking).
- The Grok VRAM tables (12 GB floor for 20-30 tps @ 100k) describe NVIDIA-class
  cards; on our 8 GB the practical ceiling stays 8K (or maybe 32-64k w/ q4 KV, item 1).

## NOT applicable to us (separate findings, same author)
- CUDA matvec kernel + Qwen3.8 MTP head graft: RTX 30/40 only, we are AMD/Vulkan.
  PTQ1_0 Vulkan kernel still broken here (195 GFLOPS); we stay on TQ2_0.
- Watch PrismML-Eng/llama.cpp PRs #217/#218 — a Vulkan port would change the
  roster's "dead end on AMD" line.

## Addendum 2026-09-23 - author's evals ran at extra-high effort + 131k thinking
Barron's 2026-09-22 thread (full capture: BONSAI2_AUTHOR_EVAL_THREAD_2026-09-22.md) states the
published Bonsai-2 results ("95% of full-precision Qwen3.8 27B on IMO 2026") were taken at
**extra-high reasoning, 131k thinking budget, stock llama.cpp, no tools**. Consequences for T1:
- Score the effort A/B against the golden top-10 logprobs, not think-time alone: lowering effort
  may spend part of that advertised 5% gap.
- Our max_tokens 1200/2500 failures are a config mismatch vs their harness, not a model limit:
  hard tasks need max_tokens >= 16k (sundoingX's 4K/medium truncation note agrees).

### Independent confirmation of the template default (2026-09-23)
A third-party re-upload of the same PTQ1_0 weights (`dealignai/Bonsai-2-27B-1bit-CRACK-GGUF`,
recon in BONSAI2_CRACK_GGUF_RECON_2026-09-23.md) publishes the model's Jinja template:
`reasoning_effort|default('xhigh')` and it `raise_exception`s for anything outside
`('xhigh','medium','low')`. So: default really is xhigh, **"high" is not a legal level**, and the
T1 A/B must use `xhigh` / `medium` / `low` (or `--reasoning-budget N`).

