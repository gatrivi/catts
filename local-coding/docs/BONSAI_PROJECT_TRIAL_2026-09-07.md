# Bonsai 27B project trial — 2026-09-07

FAIL: 7/12 original Node tests passed. One attempt; no repairs.

Fresh isolated copy of the three-module checkout fixture used for E4B. Small synthetic project, not a real application. Native API read_file/write_file harness, not OMP: writes enforced for three source paths only, read-before-write. Six-minute/16-turn bounds, 16K context, Vulkan1, full offload, Q8 KV, no MTP. Installed verified Bonsai27B Q1_0; size checked before loading.

Completed in 9 turns, 102.6 seconds of API requests. Read instructions, sources and tests; wrote all three sources. Protected tests/package/instructions/user-note hashes unchanged. Host reviewed generated sources before running node --test.

Five failing tests: decimal conversion, invalid monetary input, quantity-before-shipping example, empty cart, empty receipt. Float equality rejects valid 19.99; Number() accepts forbidden exponent strings; empty carts incur shipping. No corrections/retry. Different harness prevents a clean comparison with E4B/OMP.

Evidence: data/bonsai-project-20260907-114842/report.json and validation.json; fixture data/e4b-project-trials/20260907-114851/ and sibling baseline manifest. Runner: scripts/bonsai_project_trial.py.

No prior model server was active at startup; no Qwen pause/restoration needed (early commentary incorrectly said paused). Bonsai stopped; final process list empty and ports 8123/9103 unreachable. Original applications untouched; no downloads/default changes.
