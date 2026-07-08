# TTS model decision

Date: 2026-07-07

## Decision

Use Kokoro-FastAPI first as the no-auth local TTS sanity check. Keep XTTS disabled unless its Coqui CPML/commercial terms are explicitly accepted. Evaluate `patientx/fish-speech-zluda` second for AMD/ZLUDA voice cloning.

For live interpreting “ttw”, we will keep CATTS’ `/tts/live` endpoint stable and, when we implement live cloning for it, use `patientx/fish-speech-zluda` as the next voice-cloning engine.

## Candidates

| Engine | Role | Fit |
|---|---|---|
| Kokoro-FastAPI | Fast local TTS API | Best first test. OpenAI-compatible `/v1/audio/speech`, no voice cloning, simple latency check. |
| fish-speech-zluda | AMD/ZLUDA voice cloning | Best next clone candidate, but heavier setup and needs separate validation. |
| XTTS v2 | Existing clone path | Installed but blocked by explicit Coqui terms; not the low-friction default. |
| Edge TTS | Fallback | Works as generic cloud TTS, but violates the “less external dependency” goal. |

## CATTS settings

```powershell
CATTS_TTS_ENGINE=kokoro
CATTS_KOKORO_URL=http://127.0.0.1:8880
CATTS_KOKORO_VOICE=af_bella
```

Start Kokoro-FastAPI separately, then restart CATTS. `/health` should show `tts_engine=kokoro` and `tts_ready=true`.

Sources:

- Kokoro-FastAPI: https://github.com/remsky/Kokoro-FastAPI
- fish-speech-zluda: https://github.com/patientx/fish-speech-zluda
