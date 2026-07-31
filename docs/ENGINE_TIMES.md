# Engine times (honest, this machine)

Ryzen 5 + RX 6600 XT + 16 GB RAM. Updated 2026-07-08.

| Engine | Train time | 1 sentence (~12 words) | 1 page (~400 words) | Book (~80k words / ~10h audio) | Notes |
|---|---|---|---|---|---|
| Edge | 0 | 1–3 s | ~1–2 min | ~20–40 min | no clone |
| Kokoro | 0 | 2–8 s | ~3–10 min | ~1–3 h | no clone |
| Chatterbox CPU | 0 (zero-shot) | **30–90 s** (first load 5–15 min) | **~20–60 min** | **~15–40 h wall** | books OK if overnight/weekend |
| XTTS CPU | 0 | 10–40 s | ~15–40 min | ~10–25 h | quality poor here |
| Fish/ZLUDA | 0 | warm ~60–90 s (14w); cold first ~7+ min | unknown | unknown | cold+warmup ~9 min; ~7.6 tok/s after (2026-07-31) |
| GPT-SoVITS **local AMD** | **~48–156 h** attempt (often fails / thrash) | if it ever works: 5–30 s? | — | — | not recommended |
| GPT-SoVITS **4090 rent** | **2–8 h (~$1–5)** | **1–5 s** | **~5–15 min** | **~$3–10** | best clone path |
| Chatterbox **4090 rent** | 0 | **1–3 s** | **~3–8 min** | **~$2–8** | fast zero-shot |

## What to do when leaving the house

- **Fish first boot:** start `.\scripts\start_fish_zluda.ps1`, walk **60–90 min**, then check `:8080` health. If still compiling at 2 h, kill it.
- **Chatterbox book:** leave job running overnight (expect **many hours** on CPU).
- **Real Fausto train:** rent 4090, GPT-SoVITS **2–8 h**, don’t stare at local AMD.

## UI live word caps
- Chatterbox / Kokoro / Edge / Fish: **80 words**
- XTTS / Pocket: **12 words**
