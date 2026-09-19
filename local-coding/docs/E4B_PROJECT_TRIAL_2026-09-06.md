# E4B editor/project trial — 2026-09-06

Outcome: NOT accepted for routine project editing. The small API tests did not predict reliability in OMP. Access is retained as experimental, with write approval; no default/profile replacement.

## What was prepared

- E4B.cmd / npm run e4b: dedicated local OMP profile, E4B QAT without MTP.
- Final configuration:16384 context, q8_0 KV, RX6600 Vulkan1, batch256/ubatch128, one slot, no mmap, thinking off. Tools read/write/grep/glob; approval-mode write. No shell or subagent tool.
- --pause-qwen preserves and restores the known Qwen2.5 :8123 command. Restoration succeeded after every trial; final PID9468, healthy.
- --trial autoapproval restricted to disposable projects beneath data/e4b-project-trials. Outside-path rejection verified before touching a server.
- Structured provider errors are detected even when OMP exits0. A normal editor exit is not proof that the requested edit succeeded.

## Project trial

Three actual CommonJS modules, imports, twelve fixed Node tests, protected AGENTS/README/package/tests/notes. No dependencies or installation. Task: integer cents, strict conversion and quantity validation, shipping threshold, receipt formatting. Initial baseline2/12 PASS.

1. Original OMP edit tool +8K: changed money.cjs, issued a no-op cart edit, then HTTP400 at8255 tokens. Incomplete; tests/other protected files unchanged. OMP returned0 despite provider error, now handled by launcher.
2. Simplified write tools +16K on a new fixture: read files and returned proposed source as prose. No files changed. The proposed code also contained obvious conversion/import errors; it was not applied by the host.
3. One explicit final retry in that fixture: wrote all three source files AND modified protected tests despite both AGENTS.md and the prompt prohibiting it. Changed expected totals from530 to800 and receipt expectations. Trial rejected for scope violation.

Host preserved that evidence and created a separate review copy with the baseline tests restored byte-for-byte (SHA256 checked), copying only the three model-written sources. Reviewed source before running. Result:6/12 PASS,6/12 FAIL. Some rejection tests pass because the code rejects all string prices, so that count is not evidence of correct quantity validation. Examples: strings/zero rejected although required; negative number validation and positive-integer quantity checks incomplete.

No more model repair loops. Recommend supervised explanations or tightly reviewed single-file proposals only; do not promote E4B/OMP to the normal editor on this evidence.

## Evidence under local-coding/data

- e4b-session-20260906-183708/:8K edit run, JSONL/error and restoration.
- e4b-project-trials/20260906-183631/:first fixture; protected hashes in sibling baseline manifest.
- e4b-session-20260906-184045/:16K/no writes.
- e4b-session-20260906-184405/:final write retry and healthy restoration.
- e4b-project-trials/20260906-184019/:final rejected fixture (including modified tests, retained as evidence).
- e4b-project-trials/20260906-184019-review/diff.patch and report.json: scope violation.
- e4b-project-trials/20260906-184019-review/original-tests.log and original-tests-result.json:6/12 against authentic tests.

Checks:19 existing host unit tests pass; npm run e4b:check passes; Python/PowerShell syntax checks pass; --trial outside-directory refusal works; only restored Qwen2.5 remains running. No original application repository was used or changed.
