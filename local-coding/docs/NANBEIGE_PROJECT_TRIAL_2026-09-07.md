# Nanbeige4.2-3B Q8 thinking trial — 2026-09-07

Outcome: compatibility PASS; bounded checkout task FAILED/INCOMPLETE.
Six-minute coding deadline expired during self-review after writing all three
source files. No host repair prompt, source correction, or second attempt.

Original test suite could not load: generated money.cjs uses invalid JavaScript
regex flag /n. Zero individual cases ran; do not report this as 0/12 executed.
Review also found incorrect currency formatting, duplicated dollar symbols,
and numeric inputs rounded without rejecting excess decimal places.
Protected instructions, tests, README, package and user note hashes unchanged.

Q8 source: Tdamre/Nanbeige4.2-3B-GGUF (community conversion), revision
128d8e87d69f9c1a30c37e40530c69deda96475d;4,434,787,104 bytes.
SHA256 32b60cd0fb3da4d8a3c01d0ca7d0461818c29c81ffb42f8fc71a94141bd803c6
verified. Retained in data/models/nanbeige42-q8/.

Existing Vulkan runtime b95502ba9; no runtime change. This older GGUF stores
logical block_count44 and loop_count2; current runtime expects physical
block_count22 and num_loops2. Tensor headers verified physical blocks0..21.
Used launch-only overrides nanbeige.block_count=int:22,nanbeige.num_loops=int:2;
weights/file untouched. Source and template preflight saved in
data/nanbeige42-preflight/. Embedded vs current official template differs only
by trailing-newline trimming after reasoning extraction.

16K context,Q8 KV,full GPU offload,RX6600 Vulkan1,flash attention,no MTP.
Thinking enabled,preserve_thinking=true,XML tool calls,temperature1,top_p0.95,
top_k20. 8192 max new tokens/request (bounded below publisher recommendation),
16-turn/six-minute overall editing limits. Reasoning-format deepseek; returned
reasoning_content passed back unchanged. /apply-template sentinel check proved
reasoning preservation; native read_file probe passed.

Three completed coding requests: five reads,three writes,three review reads.
Completed requests321.94s; next request timed out at overall360s limit.
Observed decode~21–25tok/s. Fresh same three-module checkout fixture; native
API harness,not OMP. No shell/test tool exposed. Small synthetic project,
not a real app or a controlled thinking-on/off comparison.

Host reviewed final sources then ran node --test with original hashed tests.
No prior server active; task server stopped, verified outside sandbox.
No original applications touched. Do not promote to routine editor on this result.

Evidence: data/nanbeige42-project-20260907-133437/report.json,validation.json,
original-tests.log,cleanup.json,server.log. Fixture:
data/e4b-project-trials/20260907-133443/ and sibling baseline manifest.
Runner: scripts/bonsai_project_trial.py --nanbeige-thinking --probe-tools
with corresponding --model and --label nanbeige42.
