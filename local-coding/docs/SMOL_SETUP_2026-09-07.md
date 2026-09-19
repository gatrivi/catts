# Smol personal setup ? 2026-09-07

User-authorized personal access, not a new coding evaluation.
Entry: Desktop Smol local shortcut -> local-coding/SMOL.cmd -> scripts/smol.py.
OMP18.0.6 and existing Vulkan runtime/models reused. No downloads, installs,
or replacement of previous profiles. Five generated model profiles live in data/smol.

Chat: no tools. Project: read/write/edit/grep/glob/bash, approval-mode always-ask.
Git Bash pinned to installed path. Sessions retained in per-model OMP profiles;
continue/resume is scoped by OMP to the selected project. Exit returns to menu.
Launch with Enter for MiniCPM fast chat, or select numbered model to configure.
No trial deadline or8192response cutoff. Server n_predict=-1 and request max_tokens=-1,
16K context,no context shift. OMP compaction enabled at65%. Physical context still
limits each response. Thinking selection applied through chat_template_kwargs;
Nanbeige uses preserved reasoning and the existing legacy metadata overrides.

Windows job object stops the owned backend if the launcher disappears.
Single-launch lock prevents GPU overlap. Only recognized Qwen8123 may be paused;
normal shutdown restores its exact saved arguments. Abrupt close cannot guarantee
Qwen restoration. Other model servers are not stopped automatically.

Validation:24host tests passed,including profile/session preservation,
tool approval configuration,unrecognized-server refusal and kill-on-close.
All5models returned a visible marker through OMP and shut down.
MiniCPM project mode read a disposable marker using OMP's read tool.
Git Bash ran node --version successfully. Desktop target and menu exit verified.
Evidence:data/smol/setup-validation.json and individual runs/* logs.
These were integration checks,not model coding reliability tests.
Final no model servers active.
