# CATTS context (v0.5)

## What works on AMD / CPU (no NVIDIA)
- Ingest PDF/EPUB → polished manuscript + chapter audiobook
- **Voice clone:** Coqui **XTTS v2** in `.venv` (subprocess) — `scripts/setup_xtts.ps1`
- Fallback: **edge-tts** (generic voice) if XTTS not installed
- GUI: http://127.0.0.1:59200/ — header `tts_engine=xtts` when clone ready

## Install voice clone (once, ~2GB download on first synth)
```powershell
cd e:\zengatrivi-drive-e\catts
powershell -ExecutionPolicy Bypass -File scripts\setup_xtts.ps1
# restart API
```

## Env
| Var | Default |
|-----|---------|
| CATTS_TTS_ENGINE | xtts |
| CATTS_WORKER_URL | (empty) |
| CATTS_OCR_ENGINE | none |

## API highlights
- POST /jobs/audiobook, POST /jobs/{id}/regenerate
- GET /jobs/{id}/chapters/{n}/audio
- POST /voices, POST /tts/live
- DELETE /jobs/{id}

## NVIDIA-only (optional worker)
- GPT-SoVITS training, Unlimited-OCR — set CATTS_WORKER_URL
