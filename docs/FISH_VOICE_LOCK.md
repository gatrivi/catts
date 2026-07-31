# Fish voice lock (audiobooks) — 2026-07-31

## Bug
Fish with **no reference** samples a **random speaker every chunk** → accents flip, unusable books.

## Fix
- `services/fish_tts.resolve_fish_ref()` picks **one** wav and every synth reuses it.
- Refuse to synthesize without a ref (hard error, not random).
- Same `seed=42`, `temperature=0.5`, `use_memory_cache=on`.
- Chunk defaults **400–800** chars (fewer Fish round-trips).

## Setup (EN focus)
1. Put a **10–30s clean EN** clip at:
   `data/voices/<id>/fish_ref_en_15s.wav`
2. `.env`:
   ```
   CATTS_TTS_ENGINE=fish
   CATTS_DEFAULT_VOICE_ID=<id>
   CATTS_FISH_REF_EN=E:\...\data\voices\<id>\fish_ref_en_15s.wav
   CATTS_TTS_CHUNK_MIN=400
   CATTS_TTS_CHUNK_MAX=800
   ```
3. Optional: `fish_ref_en_15s.txt` with the exact words spoken in the clip (helps Fish).

## Speed / VRAM (RX 6600 8 GB)
- Warm Fish ≈ **~3 GB VRAM**. Closing Cursor/STT/Kokoro frees **RAM**, not a magic “intensity” dial.
- Keep Fish API hot for the whole book; kill after (`npm run stop:heavy`).
- First boot still ~9 min compile once.
- Larger chunks help wall time more than “running harder.”

## ES
Same pattern with `fish_ref_es_15s.wav` / `CATTS_FISH_REF_ES`. EN-first until ES is stable.
