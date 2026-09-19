Superseded by SOLO_CANDIDATE_RESULTS_2026-09-06.md. User approved pause/restore; solo trials complete, Qwen2.5 restored healthy.

# Candidate evaluation, 2026-09-06

User authorized new trials; prior budget pause no longer applies to this task.

## Gemma 4 12B coder Q3_K_M

- Download: 6,087,086,624 bytes; pinned revision and SHA256 verified in data/models/gemma4-coder-q3/verified.json.
- Runtime: existing Vulkan build 10516, b95502ba9; RX6600 = Vulkan1.
- 8K, all 49 layers offloaded, KV q8_0. First mmap load stopped at <1 GiB available RAM.
- Retry with --no-mmap -b 256 -ub 128 loaded successfully.
- Cross-file fixture PASS: rename shared conversion function in both files, preserve fractions, reject negative item values, empty receipt works. Host AST restrictions and tests; no real repository edits.
- 1.43 tok/s smoke and 1.40 tok/s edit are CONTAMINATED timings: pre-existing Qwen2.5 server PID 13324 (:8123) was also on RX6600. Windows counters showed shared GPU memory for both processes. Do not use these as solo model performance.
- Trial intentionally stopped after cross-file PASS. Long-context probe and native tool exercises remain incomplete.
- Raw: data/gemma-eval-20260906-163356/ and data/gemma-eval-20260906-163537/.

## New candidates

- Bonsai 27B Q1_0: 3,803,452,480 bytes, downloaded and SHA256 verified. This is NOT the previously installed/tested Bonsai 4B Q1_0. The prior 0/6 result does not apply to 27B.
- Prism current upstream status explicitly includes Vulkan Q1_0: https://github.com/PrismML-Eng/Bonsai-demo#upstream-status-for-binary
- Gemma E4B QAT selected file: gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf, 4,215,695,776 bytes. Drafter mtp-gemma-4-E4B-it.gguf: 59,678,016 bytes. Both downloaded and SHA256 verified.
- E4B official context is 128K, not the unverified 656K claim: https://huggingface.co/google/gemma-4-E4B-it
- QAT/MTP instructions: https://huggingface.co/unsloth/gemma-4-E4B-it-qat-GGUF
- No new trials of Ornith35B or Qwen27 IQ4. No default/profile/runtime changes.

## Pending execution

Awaiting user response to temporary stop/restore of their Qwen2.5 server, because concurrent VRAM use invalidates comparisons. It remains untouched. Task-owned Gemma stopped.

Existing server command observed:
Z:/ai/llama.cpp/llama-server.exe -m Z:/ai/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf -ngl 99 -c 32768 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --device Vulkan1 --host 127.0.0.1 --port 8123 --jinja

Python: E:/zengatrivi-drive-e/catts/.venv/Scripts/python.exe only.
Evaluators: scripts/eval_gemma_coder.py; scripts/eval_local_candidate.py --model PATH --label NAME [--draft PATH] [--smoke-only]. They use isolated data folders, port 9103, and stop their own server in finally.


