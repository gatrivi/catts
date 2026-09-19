# Split completed — 2026-09-06

Canonical local-coding source: Z:/catts/local-coding.
34 selected source/config/test/help files copied;23 E: scripts replaced with forwarding shims.
E: npm commands and command files still work. Desktop Taller local shortcut now targets Z:.
E: remains the TTS workspace. Its runtime, API and existing Z:/catts legacy TTS files were preserved.

Verification:19 existing host tests pass in Z: and through E: shims; Taller CheckOnly passes
via both paths; editor dependency check passes through E:; Python CLI help and PowerShell
syntax checks pass. No live inference, downloads, installations or benchmark runs.

Explicit shared dependencies (intentional, not a standalone installation):
- Python: E:/zengatrivi-drive-e/catts/.venv/Scripts/python.exe.
- Private OMP profile/history: E:/zengatrivi-drive-e/catts/data/local-omp; not copied/reset.
- Bonsai existing asset fallback on E:, then Z:/models/external/Bonsai-demo.
- Model weights and llama runtime retain existing Z: paths.
- Old benchmark reads the existing E: services/tts_runtime.py fixture; never ran during migration.
- Shared OmniRoute/translation/TTS integration remains on E:.

New model logs/task journals/advisory notes are rooted on Z:. Existing historical journals,
trial snapshots and raw evidence remain on E: and can still be addressed by absolute path.
The original E: coding tests remain for compatibility verification. No history or databases deleted.

Rollback originals and previous desktop shortcut:
E:/zengatrivi-drive-e/catts/data/local-coding-migration-20260906/.
MIGRATION_MANIFEST.json records original and final source hashes.
Restore the listed originals and backed-up shortcut to roll back; preserve newer task data.

Local-model reliability experiments remain PAUSED. Moving the tools does not resolve
their demonstrated editing failures. Use remaining budget for concrete project work.
