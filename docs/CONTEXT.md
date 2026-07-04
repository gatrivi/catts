# CATTS context (v0.7)

Local **audiobook + voice** tool for AMD/CPU (no NVIDIA required).

## Core flows

### 1. Audiobook
1. Upload PDF / EPUB / DOCX / TXT
2. Process (polish, chapters) in the background
3. TTS with default or selected voice → play in Library

### 2. Your voice (EN / ES)
1. Record or upload a sample (read the script)
2. STT checks **script match** (status bar on voice card)
3. Use for books and **Live interpreting** (XTTS clone)

## Engines

| Feature | Engine | Setup |
|---------|--------|-------|
| Voice clone TTS | Coqui XTTS v2 | `scripts/setup_xtts.ps1` |
| STT + script match | faster-whisper `small` | `scripts/setup_stt.ps1` |
| Translate EN↔ES | Argos | same STT setup |
| Books | pymupdf / ebooklib / python-docx | `requirements.txt` |

## Run

```powershell
cd e:\zengatrivi-drive-e\catts
py -3 -m uvicorn api.main:app --host 0.0.0.0 --port 59200
```

Open http://127.0.0.1:59200/ — activity bar shows TTS/STT/jobs/voices.

## API highlights

- `POST /jobs/audiobook` — upload book
- `POST /voices` — save sample (queues quality check)
- `POST /voices/{id}/evaluate?wait=true` — STT script match
- `POST /tts/live` — live interpreting phrase
- `POST /stt/transcribe`, `POST /stt/translate`
- `GET /health` — `xtts_ready`, `stt_engine`, `translate_ready`

## Limits

- CPU XTTS is slow for full books; Live TTS ~5–30s/phrase after warm
- Scanned PDFs need OCR (not local yet)
- Script match = token overlap vs training script, not a pro WER lab score

See [CHANGELOG.md](../CHANGELOG.md) and [NIGHT_REPORT.md](NIGHT_REPORT.md).
