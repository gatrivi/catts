# Qwen3.5-4B project trial, 2026-09-08

Motivation: FrogNano technical report (Microsoft Froggy, `Z:/catts/frognano_technical_report.pdf`,
extract at `%TEMP%/opencode/frognano-utf8.txt`). FrogNano weights are NOT released (checked
debug-gym page + all 538 microsoft HF repos; only FrogBoss-32B/FrogMini-14B exist). The report
states base Qwen3.5-4B + Leaf-style harness = 43.0% SWE-bench Verified (131K ctx, 150 turns),
FrogNano = 61.5%. This trial measures the base model's agent behavior under our existing
bounded protocol, which is the closest available proxy.

## Setup
- Model: `bartowski/Qwen_Qwen3.5-4B-GGUF` Q8_0, 4,622,131,168 bytes, revision
  4168f45a16a1290d65a4ec0fa312ae917a4c15d6, SHA256
  5c74c0ede371924357dff0cb6ba145bd67208b9b2389ded681adfff3f7608db7, VERIFIED.
  `data/models/qwen35-4b/` + manifest + verified.json.
- Harness: existing `scripts/bonsai_project_trial.py --probe-tools` unchanged (isolated checkout
  fixture, native llama.cpp API, 16K ctx, read/write_file only, 16 turns / 6 min, hash-protected).
- One protocol deviation: removed `--no-mmap` from the trial server args. With 4.6GB weights and
  ~5GB free RAM the no-mmap load stalled past the 180s timeout (first run data/qwen35-4b-project-
  20260908-212341, load timeout, no session). Default mmap load: 15s. GGML deprecation notice
  confirms the flag is legacy. No other changes.
- Server: existing Vulkan runtime, Vulkan1, all layers offloaded, Q8 KV, flash attention, greedy.

## Results
- Native tool probe: PASS (typed tool call, exact JSON args).
- Trajectory: 5 turns, 33.0s API. Turn 1: FIVE parallel read_file calls (AGENTS.md, 3 src, tests).
  Turns 2-4: write_file. Turn 5: natural termination, finished=True. No turn-limit or overflow.
- Decode ~27-32 tok/s (567-2522 prefill per turn, 143-388 decode tokens/turn).
- Changed files: exactly the 3 allowed src files; protected files intact; no extra files.
- Host evaluation (original 12-test suite in another copy, verified hashes): **4/12 PASS**
  (tests/checkout: pass 4, fail 8).
- Failure characterization from diff: receipt format broken
  (`$${totalCents/100}.00` renders `$5.3.00`; shipping `/100 + '.00'` only correct for whole
  dollars), empty-cart shipping not zeroed (empty receipt `Total: $5.00 (shipping $5.00)`),
  decimal/float-exactness and validation edge cases wrong. Cart core (integer cents, quantities,
  invalid rejection) correct.
- Report + raw turn JSON: `data/qwen35-4b-project-20260908-212811/`; diff/test:
  `data/e4b-project-trials/20260908-212818-review/`.

## Comparison with prior trials (same fixture)
| Model | Tests | Turns | API s | Behavior |
| --- | --- | --- | --- | --- |
| Qwen3.5-4B Q8 (base) | 4/12 | 5 | 33.0 | tools PASS, 5 parallel calls, natural stop |
| MiniCPM5-2B Q8 | 5/12 | 3 | 19.75 | multiple basic bugs |
| Gemma E4B QAT | 6/12 | - | - | best preliminary candidate |
| Bonsai27B Q1 | 7/12 | 9 | ~103 | code PASS after stripping Markdown |

Output quality at/below the prior 4B/2B class; agent discipline (parallel tool calls, clean
termination, protected-file respect, fast: 33s vs 103s for 27B) is the best observed on this rig.
This matches the FrogNano report's claim that harness compatibility, not raw ability, was the
4B bottleneck (8.3% -> 37.2% from harness alone).

## Verdict
As a "circular hand saw with hands": the workflow behavior is now good enough to use
interactively, but the base 4B patch quality is not. The upgrade path is exactly the model we
cannot yet get: FrogNano (+18.5 pts over this same base on Verified). When a FrogNano GGUF
appears, re-run this identical trial before any promotion decision. No promotion of the base
model. All trial servers stopped; no runtime/profile/default changes beyond the noted flag.
