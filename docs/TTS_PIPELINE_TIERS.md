# NEVER feed hard-wrapped lines to TTS — unwrap soft breaks first or you get mid-sentence pauses that sound like echo. (`scripts/tts_text_prep.py` · motto candidate: NoLineBreakPauses)

# TTS pipeline tiers (Ryzen / Win10)

**Locked 2026-07-30.** Topic crib for agents. Full session: `SESSION_CONTEXT.md`.

| Tier | Engine | Use |
|------|--------|-----|
| **Bulk books** | **Pocket** (CPU) | Full chapters/albums while PC sits idle. `overnight_books_pocket.py` → `KEEP_*_Pocket` |
| **Permanent local short** | **Kokoro** (`:8880`) | Live / offline clips when Pocket not loaded |
| **Showcase only** | **VibeVoice** | Prayers, intros — **not** whole books |
| **Banned for books** | **Edge** | Cloud robotic. Do **not** bake albums with Edge. |

## Text prep (binding)

Before **any** engine: `from scripts.tts_text_prep import prep_for_tts` → `prep_for_tts(raw)`.

## Defaults

- Book bake / CatReader albums → **Pocket** (`bake_book_pocket_resume.py` / `overnight_books_pocket.py`)
- API default `.env` → `CATTS_TTS_ENGINE=pocket` (not edge)
- Rosario Liber prayer WAVs → VV Carter (showcase)
- **Do not** restart `build_vv_album.py` library queue
- **Do not** run `overnight_books_edge.py` / `bake_book_edge_resume.py` unless user explicitly says Edge

## Anti-Edge (so we don't slip)

1. `.env` + `.env.example`: `CATTS_TTS_ENGINE=pocket`
2. Docs here + `SESSION_CONTEXT` say Edge banned for books
3. `overnight_books_edge.py` refuses unless `CATTS_ALLOW_EDGE_BOOKS=1`
4. Pocket albums use `KEEP_*_Pocket` — promote over Edge KEEP when ready

## Bake

```text
.\.venv\Scripts\python.exe scripts\overnight_books_pocket.py
.\.venv\Scripts\python.exe scripts\bake_book_pocket_resume.py --keep KEEP_Cassian_Pocket --chapters-dir data/books/vv_chapters/cassian
```

Log: `data/tts_tests/overnight_books_pocket.log`

## Related

- `ENGINE_TIMES.md` · `TTS_RX6600_RESEARCH.md` (Pocket RTF)
- `HEAVY_PROCESSES.md` — kill Kokoro after short-clip work; Pocket bake is in-process CPU
