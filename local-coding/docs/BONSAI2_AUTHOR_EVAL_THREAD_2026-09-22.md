# Bonsai-2 author eval thread (Barron @barronnotbaron, 2026-09-22) — captured for agents

Status: REFERENCE (no local runs needed). Source: X thread by the model author, 2026-09-22,
plus repo https://github.com/barronprism/Bonsai2-Demos (full solutions + reproducibility).
Captured 2026-09-23 so any agent sees the vendor's own quality/behaviour claims without re-fetching X.

## 1. Verbatim claims (do not restate as our measurements)

- "Ternary Bonsai 2 27B: **5.9 GB of weights for a 27B model**" — matches our PTQ1_0 file
  (5.95 GB). The author's headline artifact IS the PTQ1_0 quant we hold, not TQ2_0.
- Eval conditions: **no internet, no tools, minimal harness** for coding problems;
  **llama.cpp default serving config** unless stated; **all reasoning at extra-high**
  (Gemma 4 has a single effort level); **131k thinking context** then forced answer.
- IMO 2026 (released after all three models' training cutoff), vs **full-precision
  Qwen3.8 27B (54 GB)** and **Gemma 4 12B QAT (~7 GB)**:
  - Bonsai and Qwen land in the **upper human-bronze range (16–22)**.
  - Bonsai kept **95% of Qwen-FP's IMO score**, finished in **~70% of the wall time**,
    but used **~22% MORE thinking tokens**.
- Side-by-side of Problem 4 published; also: Caltech 3rd-year info-theory/ECC exam
  (class average 48%) given as PDF — models must extract the problems; Bonsai solved an
  easier first-year Caltech RLC-circuit physics problem **faster than Gemma 4**.
- Upstream facts: extra-high reasoning + long thinking budget are the *stock* regime;
  the author benchmarks a 27B ternary against FP27B and finds ~5% loss.

## 2. What this confirms for our rig (already measured locally)

- **27B-class quality at 6 GB is real, not PR**: independent of our runs, the author's
  IMO comparison says ternary compression costs ~5% score. Our roster's choice of
  Bonsai-2 as the "smartest local" tier is validated.
- **PTQ1_0 is the reference quant**; TQ2_0 (our 12 t/s workhorse) is a *double-quantized*
  derivative the author never benchmarked. Our 2026-09-22 CPU-vs-Vulkan gate concluded the
  4/8 golden divergence lives in TQ2_0's double quantization, not in the shader. This
  thread raises the stakes on that verdict: fidelity-critical work should run **PTQ1_0**
  (now 6.4–6.7 t/s after the 601→247 µs LUT matvec fix), accepting ~2x slower decode.
- **The "verbose reasoning" signature is the author's own config, not a bug in our setup**:
  extra-high effort + 131k thinking window is how the published numbers were obtained.

## 3. Insights that change our plan

1. **Quality-critical tasks are being crippled by our max_tokens caps, not the model.**
   The author's harness lets the model think up to 131k, then forces an answer. Our
   overnight run failed 6/6 at max_tokens 1200 (finish_reason=length). Rule: hard tasks
   need **max_tokens >= 16k** (sundoingX's independent note: medium effort truncates long
   generations at 4K) and the largest ctx we can afford. Cheap config fix, big effect.
2. **Reducing reasoning effort is a trade, not a free speedup.** "95% of FP27B" was
   measured at extra-high. Our `--reasoning-effort medium` / `--reasoning-budget` fix
   (BONSAI2_REASONING_EFFORT.md, T1) still earns its keep for latency/truncation, but its
   quality cost is now measurable against `gold-20260921` top-10 logprobs on the frozen
   8-prompt set — run the effort A/B *through* `golden_check.py`, not just on wall time.
3. **The author's "~70% wall time" is hardware-relative and does NOT transfer to us.**
   5.9 GB vs 54 GB is ~9.2x less memory traffic, but +22% tokens offsets it; observed 1.4x
   time advantage implies their FP27B baseline ran on far more bandwidth than our 224 GB/s.
   Our ceiling stays the local physics: ~34–37 t/s (TQ2_0/PTQ1_0 traffic) at short ctx.
4. **Their eval regime (no tools, no internet, stock llama.cpp) is stricter than our agentic
   usage** — where we add tools/retrieval, part of that 5% gap can be recovered by harness
   design rather than by quant wars. Corollary: our 4/8 golden drift was measured on a
   *text-continuation* fidelity test, and drift lands on rank-2/3 tokens whose text stays
   correct — i.e. an IMO-style eval may not even register it.
5. **We cannot reproduce the FP27B reference locally at all** (54 GB weights, 8/16 GB
   hardware). Any local quality comparison must anchor to published figures or to
   `data/golden/` CUDA captures, never to an on-rig "Qwen3.8-27B FP" claim.

## 4. Actions (none require GPU-exclusive time beyond what T1 already needs)

- [ ] Fold into the T1 effort A/B: score `--reasoning-effort medium` and `budget 2048`
      against the golden top-10 logprobs, not only think-time. PASS = >=40% think-time cut
      AND golden_check unchanged vs high effort.
- [ ] Update MODEL_ROSTER bonsai2 rows: PTQ1_0 = fidelity-critical path (author's quant,
      95% of FP27B on IMO 2026, 6.4–6.7 t/s); TQ2_0 = speed path with known double-quant drift.
- [ ] Raise per-task max_tokens guidance from 2500 to >=16k for hard/thinking-heavy tasks;
      keep 131k-thinking behaviour in mind when budgeting ctx (local 8–16K ctx is far below
      the author's eval regime — expect score gaps on hard problems and route those to cloud).
- [ ] Optional recon: repro artifacts in barronprism/Bonsai2-Demos (harness, prompts,
      IMO solutions) — could become our next frozen scoring set alongside the 8-prompt golden.

## 5. Cross-refs

- `BONSAI2_REASONING_EFFORT.md` — effort flags; claim "client override wins" still untested.
- `BONSAI2_RX6600_BEST_SETUP_2026-09-18.md` — bandwidth ceiling math (34 t/s @8-16K).
- `BONSAI2_PTQ1_0_VULKAN_PERF_2026-09-18.md` — PTQ1_0 shader fix, 3.3 -> 6.4–6.7 t/s.
- `MODEL_ROSTER.md`, `SESSION_CONTEXT.md` (2026-09-22 night: TQ2_0 drift = quantization).
- `GPU_SPEEDUP_ASSESSMENT_2026-09-22.md` — cloud-vs-local task ranking.
