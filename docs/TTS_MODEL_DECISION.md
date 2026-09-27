# TTS model decision

Date: 2026-07-30 (updated)

## Decision

**Primary on AMD RX 6600:** `patientx/fish-speech-zluda` (Fish Speech 1.5 + ZLUDA `--half`).  
Kokoro stays the lightweight no-clone sanity check. Pocket stays optional. XTTS stays gated on Coqui CPML. No cloud neural TTS as the quality path.

CATTS engine id: `fish` → `services/fish_tts.py` → `CATTS_FISH_URL` (`http://127.0.0.1:8080`).

Full host steps: [FISH_ZLUDA_RX6600.md](FISH_ZLUDA_RX6600.md).

## Candidates

| Engine | Role | Fit |
|---|---|---|
| **fish-speech-zluda** | AMD GPU clone + quality TTS | **Pick.** RX 6600 validated upstream with `--half` ~3×. |
| Kokoro-FastAPI | Fast local no-clone | CPU sanity / fallback when Fish is down. |
| Pocket-TTS | Small in-process clone | Convenient but slow for long books. |
| XTTS v2 | Existing clone path | CPML gate; not the AMD default. |
| Chatterbox | Alt clone | No solid AMD GPU path here. |

## CATTS settings

```powershell
CATTS_TTS_ENGINE=fish
CATTS_FISH_URL=http://127.0.0.1:8080
CATTS_FISH_ROOT=E:\path\to\fish-speech-zluda
```

```powershell
.\scripts\setup_fish_zluda.ps1   # once (after HIP/Brknsoul prep)
.\scripts\start_fish_api.ps1     # leave running
# restart CATTS → /health tts_engine=fish tts_ready=true
```

Sources:

- fish-speech-zluda: https://github.com/patientx/fish-speech-zluda
- Kokoro-FastAPI: https://github.com/remsky/Kokoro-FastAPI
