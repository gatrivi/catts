# MiniCPM5-2B Q8 trial — 2026-09-07

Outcome: runtime/tool compatibility PASS; checkout task FAIL, 5/12 original tests.
One attempt, no repairs. Native API harness, not OMP. Small synthetic project;
no claim about real application reliability or maximum useful context.

Official openbmb/MiniCPM5-2B-GGUF, revision
8ffce18336801a527a4385b318e70822fc0f876c; Q8_0 2,679,710,688 bytes.
SHA256 c5415f8989bf88a8288f1b55a3cc371af53c07b0faa220a63bd7a990cfaba078 verified.
Retained under data/models/minicpm5-2b-q8/. No runtime installation/change.

Existing llama.cpp Vulkan runtime loaded it successfully: RX6600 Vulkan1,
all layers offloaded,16K context,Q8 KV,flash attention,no MTP.
One native read_file probe passed without a custom parser. Fresh checkout fixture,
same task as Bonsai; only three source files writable, read-before-write enforced.
Completed five reads and three writes in three turns,19.75s API time;
observed decode ~48–60tok/s. No test feedback/retry.

Host reviewed source then ran node --test against SHA256-verified original tests.
Seven failures: decimal conversion, cents formatting, small-cart totals,
quantity-before-shipping example, shipping threshold, populated/empty receipt.
Sources reject required string prices, accept fractional-cent numeric inputs,
format cents as whole dollars, omit quantity validation, miscompute shipping,
and omit the formatCents import. Some rejection tests pass for the wrong reason
(all string prices rejected), so even5/12 overstates correct behavior.

Tests, instructions, package, README and user note unchanged. Original apps untouched.
No prior model server active; owned server stopped. Unsandboxed final process check
found no llama-server.exe and trial endpoint unreachable.

Evidence: data/minicpm5-2b-project-20260907-131651/report.json,
validation.json,original-tests.log,server.log. Fixture:
data/e4b-project-trials/20260907-131658/ and sibling baseline manifest.
Runner: scripts/bonsai_project_trial.py with --model, --label and --probe-tools.

Recommendation: no promotion to project editor; stop here per agreed trial scope.
