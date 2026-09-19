# Solo candidate evaluation — 2026-09-06

User approved pausing and restoring the pre-existing Qwen2.5 :8123 server. All trials below ran sequentially, alone on RX6600. Qwen2.5 restored healthy, PID1480; all task-owned servers stopped.

## Results

| Model | Short decode tok/s | Cross-file edit | Read/write/test tools | ~6.5K input context probe |
| --- | ---: | --- | --- | --- |
| Gemma4 12B coder Q3_K_M | 18.4–18.5 | PASS | 0/3 | PASS; 149 prompt tok/s |
| Bonsai27B Q1_0 | 16.7 | Raw JSON FAIL; code PASS after removing Markdown fences | 3/3 | PASS; 94 prompt tok/s |
| Gemma4 E4B QAT UD-Q4_K_XL | 41.0–42.3 | PASS | 3/3 | PASS; 520 prompt tok/s |
| E4B QAT + MTP | 50.8 | Not tested | Not tested | Not tested |

E4B QAT is the strongest preliminary candidate for supervised work: fastest baseline decode and prompt processing, strict cross-file JSON accepted, native tool workflows passed. Bonsai27B is a viable alternate. Gemma12B generated correct small code but did not use tools in this serving configuration: it answered with prose/code instead of reading files or running tests.

MTP result is one short smoke, not a full quality/agent evaluation. Draft acceptance 88/120 (~73%). Baseline and MTP produced different-length completions (137 vs118 tokens); ~24% observed decode increase is not a fixed-output throughput benchmark. No 200 tok/s claim.

## Method and limits

- Existing llama.cpp Vulkan build10516, b95502ba9; RX6600 Vulkan1, all layers offloaded, 8192 context, one slot, KV q8_0, flash attention on, --no-mmap, batch256, ubatch128.
- Greedy standalone requests, thinking disabled. Tool exercises temperature0.2, thinking disabled, max10 turns/case; bounded read_file/write_file/run_tests, host-owned tests, AST restrictions and subprocess deadlines.
- Cross-file fixture: two small Python functions loaded into a shared namespace; rename conversion and its caller, retain fractional cents, reject negative individual items, support empty receipt. This is not a real repository/import/build integration trial.
- Three native tool exercises: mean/empty input, settings parser, stable unique list. E4B needed ~46.7s total vs Bonsai ~45.4s; decode speed alone does not predict complete tool-workflow time.
- Context probe used 6489–6494 new prompt tokens and recovered two markers. This confirms the bounded request works; it does NOT validate 128K/656K context, sustained use, difficult retrieval, multimodal operation or unattended project editing.
- Bonsai raw-format failure is preserved. Recheck removes only surrounding Markdown fences and applies the identical host AST/tests; no model retry or code repair.
- Initial 1.4 tok/s Gemma result was contaminated by concurrent Qwen2.5 GPU allocations; superseded by these solo results.
- Prior Bonsai0/6 evidence concerned 4B Q1_0, not this 27B.
- No profiles, defaults or runtime installations changed.

## Evidence

Relative to local-coding/:

- data/gemma12-solo-eval-20260906-180533/report.json
- data/bonsai27-solo-eval-20260906-180831/report.json
- data/bonsai27-solo-eval-20260906-180831/normalized-cross-file/validation.json
- data/e4b-solo-eval-20260906-181146/report.json
- data/e4b-mtp-solo-eval-20260906-181405/report.json
- Per-model tool-exercise/*/report.json contains all calls, answers, usage and host test outcomes.
- data/solo-sequence-20260906-180528/prior-server.json and restoration.json record the preserved server command and healthy restoration.

Weights and SHA256 manifests remain under data/models/. E4B main4,215,695,776 bytes; MTP59,678,016 bytes. Bonsai27B3,803,452,480 bytes. Gemma12B6,087,086,624 bytes.

Evaluator: scripts/eval_local_candidate.py --model PATH --label NAME [--draft PATH] [--smoke-only]. Python must be E:/zengatrivi-drive-e/catts/.venv/Scripts/python.exe. Run a single model at a time; do not overlap with :8123. Exact tested argv is recorded in each report. scripts/run_solo_candidates.ps1 performs the approved pause/trials/restore sequence; it must only be invoked when pausing that server is authorized.
