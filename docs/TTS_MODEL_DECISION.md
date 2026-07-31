# TTS model decision

Date: 2026-07-07 · Updated: 2026-07-08

## User preference (binding)
See [VOICE_CLONE_PREFERENCE.md](VOICE_CLONE_PREFERENCE.md).

**Train-once quality > zero-shot speed.** Days of training OK. Audiobooks + interpreter (train day X, use day Y).

## Current decision (revised)

| Priority | Engine | Role |
|---|---|---|
| 1 | **GPT-SoVITS-class** (few-shot train) | Target for real voice clone (EN/ES, Córdoba) — MIT, quality-first |
| 2 | Chatterbox (MIT) | Commercial-friendly fallback if SoVITS won’t run on AMD Win |
| 3 | Fish-speech-zluda | Only if HIP 5.7.1 works; check NC license before selling |
| — | Kokoro | Non-clone narration / sanity TTS |
| — | XTTS | **Deprioritize** — CPML non-commercial + poor accent/quality here |

Do **not** burn tokens on more XTTS zero-shot tuning.

## CATTS settings (interim)

```powershell
CATTS_TTS_ENGINE=kokoro   # or xtts only for private experiments
CATTS_KOKORO_URL=http://127.0.0.1:8880
```

## Sources
- GPT-SoVITS: https://github.com/RVC-Boss/GPT-SoVITS
- fish-speech-zluda: https://github.com/patientx/fish-speech-zluda
- Chatterbox: https://github.com/resemble-ai/chatterbox
- HIP 5.7.1 hub: https://www.amd.com/en/developer/resources/rocm-hub/hip-sdk.html
