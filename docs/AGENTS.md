# Agent notes (CATTS)

## Always read first
1. `docs/SESSION_CONTEXT.md` (cheap truth)
2. `docs/HEAVY_PROCESSES.md` (RAM / workers)
3. Remote/web agents: `docs/CLOUD_AGENTS.md`
4. User query only — do not re-crawl whole repo

## Constraints
- 16 GB RAM: Cursor ~4 GB; leave room for user work. Kill heavy Python after batch.
- Tight disk: warn before big downloads; HIP SDK needs ~30 GB free.
- Prefer `.venv\Scripts\python.exe`. PATH may point at Hermes/other Pythons.
- No PR unless asked. Document context in MD to save tokens.
- Warn before spending ~500k+ tokens.

## Voice clone (binding)
Read `docs/VOICE_CLONE_PREFERENCE.md`. User does **not** want zero-shot “instant clone.” Days of training OK. Prefer GPT-SoVITS-class. Do not burn tokens on more XTTS zero-shot demos.

## Engines
- Interim narration: **kokoro**.
- Target clone: **GPT-SoVITS** (train-once). XTTS deprioritized (CPML + quality).
- Fish only after HIP **5.7.1** (not 6.4); check license before commercial use.
- See `docs/TTS_MODEL_DECISION.md`.