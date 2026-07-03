# CATTS context (v0.6) — MVP

## Local stack (AMD / CPU, no NVIDIA)
| Feature | Engine | Setup |
|---------|--------|-------|
| Audiobook | PDF, EPUB, **DOCX**, TXT | built-in |
| Voice clone TTS | Coqui XTTS v2 | `scripts/setup_xtts.ps1` |
| STT transcribe | faster-whisper `small` | `scripts/setup_stt.ps1` |
| Translate EN↔ES | Argos Translate | same STT setup |
| OCR scans | not local | needs GPU worker |

## Install (once)
```powershell
cd e:\zengatrivi-drive-e\catts
powershell -ExecutionPolicy Bypass -File scripts\setup_xtts.ps1
powershell -ExecutionPolicy Bypass -File scripts\setup_stt.ps1
py -3 -m pip install python-docx
py -3 -m uvicorn api.main:app --host 0.0.0.0 --port 59200
```

## API
- POST /jobs/audiobook — pdf, epub, docx
- POST /stt/transcribe — audio file, lang=en|es optional
- POST /stt/translate — `{text, from_lang, to_lang}`
- POST /tts/live, POST /voices

## Env
- CATTS_DEFAULT_VOICE_ID — auto voice for books/live
- CATTS_STT_MODEL — whisper size (default `small`)

## Honest limits
- XTTS + Whisper each load ~1–2GB RAM; first request slow
- Full book on CPU = hours
- Argos translation is good not DeepL-grade
- Whisper `small` ≈ solid local STT, not quite Deepgram cloud
