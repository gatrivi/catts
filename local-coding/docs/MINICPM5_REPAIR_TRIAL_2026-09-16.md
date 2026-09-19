# MiniCPM5-2B repair-loop trial — 2026-09-16

User task: "considering making it code able" (MiniCPM in SMOL). Approved scope:
tool probes + repair-loop trial, gate decision, no promotion without evidence.

## Results

| Test | Result |
| --- | --- |
| OMP tool probes (4 configs: 16K/32K × default/xml) | **4/4 PASS** — real `read` toolCall + successful toolResult each; xml template NOT needed |
| Checkout trial 1 (test-feedback, 3 runs, 2 repairs) | **3/12** (tests-3.log) |
| Checkout trial 2 (fresh fixture, identical protocol) | **4/12** (tests-3.log) |
| Baseline checkout tests before edits | 12/12 by construction (host-generated fixture) |
| Host unit tests after work | 32/32 (31 prior + 1 new parser test) |

## Evidence

- Probe run: `data/smol/probes/20260916-211401/` (rows.jsonl re-summarized from raw
  logs after a parser bug; raw agent.jsonl files are untouched; hash-verified in
  `tests/test_minicpm_tool_probe.py`).
- Repair trial 1: `data/minicpm5-repair-project-20260916-202711/report.json`.
- Repair trial 2: `data/minicpm5-final-checkout-project-20260916-212654/report.json`.
- Runner: existing `scripts/bonsai_project_trial.py --probe-tools --test-feedback`
  (isolated fixture, SHA256-guarded tests, 3 test runs max, temperature 0).

## Tool mechanics vs code quality

MiniCPM's tool mechanics are fine: native tool probe PASS, 5 reads in turn 1,
3 writes per repair round, correct run_tests usage, no loops, ~50-60 tok/s.
The failures are code quality, not tooling:

- `toCents` rejects required string inputs or accepts invalid ones (`1e2`, `1.001`).
- `formatCents` returns whole dollars (`1.00` for input 1 instead of `0.01`).
- `cart.cjs` shipping math references an out-of-scope `item` variable
  (ReferenceError) and ignores the 5000-cent free-shipping threshold.
- `receipt.cjs` calls `formatCents` without importing it; omits `$` on shipping.
- Repairs changed only `money.cjs` (both trials); cart/receipt bugs persisted
  through two feedback rounds with exact failing output supplied.

## Gate decision (per approved scope)

**FAIL — MiniCPM5-2B is not promoted as a coding editor.** Qwen3.5-9B remains the
SMOL project editor. MiniCPM stays chat/fast-chat; no further MiniCPM coding
trials without new evidence (e.g., mainline runtime + GBNF-constrained tool
calls, or a fine-tuned checkpoint).

## Notes

- Two consecutive trials run to characterize variance, not to retry after failure;
  the second was authorized within the approved "repair-loop trial" scope.
- An assistant-written correction pass on a separate fixture copy reached 5/12
  and is recorded as host-side context, NOT as a model result.
- SMOL defaults, profiles, and runtime were not modified; trial-only scripts:
  `scripts/minicpm_tool_probe.py` (+ parser test). The `minicpm_trial_guard.mjs`
  hook was drafted but NOT validated or wired into any launcher; treat as
  unvalidated scratch.
- All model servers stopped; protected fixture files unchanged (hash-verified in
  both trial reports: `protected_intact: true`).
