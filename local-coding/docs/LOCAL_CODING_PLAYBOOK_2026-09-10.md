# Local coding playbook — every lever, assessed (2026-09-10)

Question asked: "what can be done at every conceivable level to make local coding work."
Scope: research + doc only. No installs, downloads, runtime or profile changes.
Rig: Ryzen5 PRO 4650G (6C/12T), RX 6600 8GB, 16GB RAM (~8GB free cap), Windows, llama.cpp
Vulkan build 10516 (b95502ba9), OMP harness + SMOL launcher.

## 0. Ground truth — what actually fails (from our 6 trials)

Every model ≥2B passes native tool calls. Failures are behavioral/quality, never capability:

| Model | Tests | Agent behavior | Failure mode |
| --- | --- | --- | --- |
| Qwen3.5-4B Q8 | 4/12 | BEST: 5 parallel reads, clean stop, 33s | patch quality: decimals/edge cases |
| MiniCPM5-2B Q8 | 5/12 | 214 calls, 21 malformed, 5/12 repeat-loop | malformed calls + loops |
| Gemma E4B QAT | 6/12 | tools 3/3, 41-42 tok/s | earlier project trial: wrote nothing |
| Bonsai27B Q1 | 7/12 | 9 turns, 103s, Markdown-fences bug | format + speed |
| Gemma12B Q3 | — | 0/3 tools: prose instead of calls | tool usage |

External anchor: FrogNano report — same Qwen3.5-4B went 8.3% → 37.2% from HARNESS alone;
mini-SWE-agent hits 65% on Verified with 100 lines of Python; SWE-agent: ACI design moves
scores as much as model swaps. Conclusion: our headroom is harness + verification first,
model second, training third. Budget note: E4B ~42 tok/s ≈ ~2-3s per 100-token edit;
Qwen4B ~33s/task API time — iteration loops are affordable, 27B loops are not.

## 1. Runtime level (server/runtime, per-request cost: none)
- **Update Vulkan build to b10828+**: single highest-leverage infra move. Already the queued
  Spark blocker; also buys MTP fixes (upstream merged MTP PRs + draft-head fixes Sept 2026),
  #28495-style PP regressions, Kimi-K3-style recurrent rollback machinery for future models.
  Official Windows Vulkan release exists — needs explicit user OK (runtime addition rule).
- mmap over --no-mmap: already applied (15s vs stalled load on 4.6GB Q8). Keep.
- KV q8_0 + flash attention: already on. q4_0 KV exists but prefill time (79 tok/s → ~5min
  to fill 24K) makes >32K pointless on this rig regardless of KV savings. Memory is NOT our
  limit; prefill is.
- --cache-reuse (KV shifting): unconventional and relevant — OMP compaction currently
  summarizes then re-prefills; KV-shift reuse could extend effective context without full
  re-prefill. Low risk, test after build update.
- One slot, no -np 2 (upstream: PP drops 42-54% on later requests with unified KV).
- Sampling: keep greedy/temp 0.2 for tools. min_p only for chat. No XTC/mirostat case for code.

## 2. Decoding level (make bad output impossible)
- **GBNF / json_schema-constrained tool calls** (llama-server native, ~any model): forces
  valid typed JSON args. Directly attacks MiniCPM's 21 malformed / 9 self-repaired calls.
  Cost: small token-time overhead; risk: over-tight grammar degrades a model that was
  going to succeed. Ship behind a per-model flag, default off, A/B in next trial.
- Grammar-shaped edit format: constrain edits to {anchor, replacement} JSON — combines the
  aider SEARCH/REPLACE lesson (below) with guaranteed parseability.
- MTP/speculative: PROVEN on this rig (E4B MTP smoke: 73% acceptance, +24% decode).
  Untested: agent-flow quality with MTP on. Cheap trial once build updated.

## 3. Harness level (biggest lever; matches FrogNano 8.3→37.2 evidence)
- **Repeat-loop detection**: already specced in SESSION_CONTEXT (MiniCPM died 5/12 in
  identical-call loops; replays same call on same error string). Detect ≥2 identical
  (tool,args) → vary-hint or ask-user. Highest value-per-line of code available.
- **Flexible patch-apply layer** (aider lesson: weak models need forgiving appliers):
  strip Markdown fences (we did this manually for Bonsai — it passed), tolerant whitespace/
  indentation matching, anchor by unique substring instead of exact block. Never silently
  accept: apply + show diff.
- **Lint/AST-check on every edit before acceptance** (SWE-agent guardrail lesson): reject
  syntactically-broken edits AT THE TOOL BOUNDARY with the error as tool feedback — turns
  silent corruption into a correctable loop. Cheap: Python ast.parse already in trial scripts.
- **Edit-format per model**: whole-file for ≤2B; SEARCH/REPLACE for 4B; unified diffs only
  with strong models. Aider measured naive-diff collapse + udiff 3x laziness fix — pick
  per-model, don't assume.
- Retrieval discipline: repo map (tree-sitter symbols) + search tool instead of raw reads;
  already have read caps (120 lines) + 8KB spill caps. Add symbol-level "outline" tool.
- Compaction: validated (FrogNano recovers full perf at 64K with compaction; ours at 16K/32K).
  Keep recent-tokens 3000/6000 setting; consider testing compaction keep-window sizes.

## 4. Verification level (turn "hope" into "checked")
- **Tests-as-oracle best-of-N**: generate N candidate patches, run host tests, keep first
  pass. At 33s/attempt (Qwen4B), 3 attempts ≈ 100s/task — the rig's best cost:quality trade.
  Guard: cap N=3, dedupe identical candidates, always log all attempts (trial protocol).
- Test-driven feedback loop: on failure, feed the failing test output back once (SWE-agent
  lesson: models can't self-debug without the error text). One retry, then stop.
- Keep the existing protections: isolated copies, hash-protected fixtures, AST restrictions,
  subprocess deadlines. These are why failures were cheap.

## 5. Model level
- **Spark-X2.5-4B**: authorized plan exists, blocked only on build update. SWE Pro 44.4 >
  9B class; Q8 fits VRAM; SWA keeps KV small; expect 40-50 tok/s. Try thinking-on AND off.
- **FrogNano watch**: the one model proven +18.5 pts over our best base — re-run identical
  Qwen trial if a GGUF ships.
- Ornith9B installed but untested — cheapest unexplored candidate (no download).
- E4B QAT remains best preliminary; pair with MTP after build update.
- Skip: >8GB VRAM models (Bonsai 27B lesson: 103s/task, 2 failures), Bonsai ternary
  (no Vulkan kernels), K3-in-C (REJECTED 2026-09-09, see assessment).

## 6. Training level (unconventional; expectations LOW, verify first)
- Unsloth desktop now ships a Vulkan llama.cpp backend (inference confirmed via README);
  whether TRAINING runs on RX 6600/Windows is UNVERIFIED (docs unreachable today). Cheap
  check before any commitment: install app, look for train tab with Vulkan backend. No trial
  without user OK.
- If it works: LoRA on our OWN recorded trajectories (runs/ + trial JSONs = free SFT data
  in the exact format we need: tool calls, stop discipline) — SWE-smith showed synthetic
  SE-task training data works; our fixtures could generate it. Worst case, training stays
  out of reach on this rig — the harness levers above don't depend on it.

## 7. Workflow level (costs nothing, already partially in place)
- One bounded task per session, /new between tasks, relay doc on compaction (SMOL.md).
- Chat with manual fragments for context control when Project over-reads.
- Supervised posture stays: no trial established unattended reliability; FrogNano-class
  result is the bar to revisit that.

## 8. Dead ends (assessed, do not revisit)
- K3-in-C / CPU disk-streaming (no GPU path, ~1.45TB/token disk reads) — see assessment.
- 131K context on 8GB: prefill-bound (~5min/fill at 24K already); announced context ≠ fit.
- Bigger dense models as the fix: 27B slower + failed 2x; small + harness beats big + slow.
- Any new runtime/model trial without explicit user OK (budget + rules).

## 9. Prioritized roadmap (effort / risk / payoff)
| # | Action | Effort | Risk | Payoff |
| --- | --- | --- | --- | --- |
| 1 | Repeat-loop detection in harness | hours | none (OMP-side) | stops 5/12 death mode |
| 2 | Update Vulkan runtime b10828+ | 1 install (user OK) | low | unblocks Spark + MTP fixes |
| 3 | Flexible patch-apply + fences strip | hours | none | converts Bonsai-class fails |
| 4 | Lint-on-edit guardrail | hours | none | silent corruption → feedback |
| 5 | Best-of-3 with tests-as-oracle | hours | 100s/task cost | quality without new model |
| 6 | GBNF-constrained tool calls, A/B | 1 trial | over-tight grammar | kills malformed calls |
| 7 | Spark-X2.5-4B trial (thinking on/off) | 1 trial | runtime version | possible new daily driver |
| 8 | E4B+MTP agent-flow retest | 1 trial | none | +24% decode if quality holds |
| 9 | Ornith9B eval | 1 trial | none | cheapest unexplored option |
| 10 | Unsloth Vulkan-training feasibility | 1 check | unknown | only path to SFT on rig |
| 11 | FrogNano GGUF watch | passive | none | +18.5 pts if it ships |

Do 1→4 BEFORE any new model trial: harness fixes apply to every current AND future
candidate (that is the FrogNano report's whole point). Every action = explicit user
authorization at run time; trials protocol unchanged.

## Evidence index
Local: QWEN35_4B_PROJECT_TRIAL_2026-09-08.md; SOLO_CANDIDATE_RESULTS_2026-09-06.md;
MINICPM5_PROJECT_TRIAL_2026-09-07.md; BONSAI_PROJECT_TRIAL_2026-09-07.md; SMOL.md
(32K report, limits.json); SESSION_CONTEXT.md (Spark queued plan, MiniCPM observations).
External: swebench.com (mini-SWE-agent 65% in 100 lines, Jul 2025); arxiv 2405.15793
(SWE-agent ACI); aider.chat/docs/unified-diffs.html; llama.cpp server README + grammars
README (GBNF/json_schema, --cache-reuse, kv quant); llama.cpp issue tracker Sept 2026
(MTP/Vulkan activity, #28495 -np2 PP drop); FrogNano report via Qwen trial doc.



