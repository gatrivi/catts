# CATTS overnight report — 2026-07-03

Read this when you're back. Honest status, no hype.

---

## What happened while you slept

1. **STT install partially failed** — `setup_stt.ps1` hit `MemoryError` during pip (16GB RAM + XTTS already in venv). **faster-whisper 1.2.1 is installed**; Argos was retried with `--no-cache-dir`.
2. **Fixed `setup_stt.ps1`** — installs packages one at a time, no cache; added `scripts/install_argos_packages.py`.
3. **v0.6 pushed** — STT API, translate API, DOCX ingest, honest TTS (no silent Edge when voice set).
4. **Server** — should still be on `:59200` (restart after STT finish).

---

## Your machine reality (Ryzen 5, RX 6600 8GB, 16GB RAM)

You are running **two heavy CPU models** in one `.venv`:

| Model | RAM (approx) | First use | After warm |
|-------|----------------|-----------|------------|
| Coqui XTTS v2 | ~2 GB | ~60s load | ~5–30s/phrase |
| faster-whisper `small` | ~1 GB | ~30s load | ~realtime–5s/min audio |

**16GB total** — Windows + browser + both models = swap risk. If things freeze:
- Set `CATTS_STT_MODEL=base` or `tiny` in `.env` (less accurate, less RAM)
- Don't run Live TTS + Transcribe at the same time
- Close other apps during book generation

The **22 seconds for 160KB** you saw was **not download** — it was reloading the 2GB XTTS model every request (fixed in v0.5.2 with persistent worker).

---

## MVP checklist (honest)

| Goal | Status | Notes |
|------|--------|-------|
| PDF/EPUB/DOCX → audiobook | ✅ | Scanned PDFs still fail without OCR |
| Text polish + chapters | ✅ | |
| Your voice TTS | ⚠️ | XTTS zero-shot — sounds *like* you, not studio clone |
| Live TTS | ⚠️ | Works if XTTS warm; first run slow |
| STT EN/ES | ⚠️ | Whisper `small` — good local quality, not Deepgram latency |
| Translate EN↔ES | ⚠️ | Argos offline — fine for drafts, not DeepL |
| Train voice | ✅ renamed | "Save voice sample" — no ML training, just reference wav |

---

## Morning commands

```powershell
cd e:\zengatrivi-drive-e\catts

# If STT/translate not ready:
.\.venv\Scripts\python.exe -c "import faster_whisper; print('whisper ok')"
.\.venv\Scripts\python.exe -c "import argostranslate; print('argos ok')"
# If argos missing:
powershell -ExecutionPolicy Bypass -File scripts\setup_stt.ps1

# Restart API
# Kill old process if port busy: netstat -ano | findstr :59200
py -3 -m uvicorn api.main:app --host 0.0.0.0 --port 59200
```

Open http://127.0.0.1:59200/ — header should show **v0.6** and `STT:whisper`.

**Quick tests:**
1. **Speech tools** → upload a short wav → Transcribe
2. Paste result → Translate EN↔ES
3. **Live TTS** → your voice (wait for warm worker)
4. **New book** → upload `.docx` or `.pdf` with your voice default-selected

---

## Hugging Face / Cerebras Gemma 4 blog — useful for us?

Source: [HF + Cerebras Gemma 4 voice AI](https://huggingface.co/blog/cerebras-gemma4-voice-ai)

**Short answer: not for your local box today.**

That stack is:
- **Parakeet** (NVIDIA STT) → **Gemma 4 31B on Cerebras wafer** → **Qwen3 TTS**
- Built for **cloud real-time** (milliseconds LLM), not AMD 8GB VRAM
- Repo: `huggingface/speech-to-speech` — great **architecture reference** (modular STT→LLM→TTS)

**What we could borrow later:**
- Same **cascade pattern** we already use (Whisper → text → XTTS)
- WebSocket live voice UI from their Space
- If you get cloud API keys: swap XTTS for Qwen3-TTS or ElevenLabs

**What doesn't fit:**
- Cerebras inference (custom hardware, not installable locally)
- Gemma 4 31B on 16GB RAM CPU (impractical for real-time)

---

## Known bugs still open

1. **Full book on CPU** — hours per novel; no ETA in UI
2. **Scanned PDF OCR** — needs NVIDIA worker or future Tesseract pass
3. **ffmpeg** — if missing, only first chapter kept in concat
4. **Old jobs** — tiny silent MP3s; use **Re-record book**
5. **Two duplicate "My main voice" entries** — pick one or delete folder
6. **RAM** — simultaneous XTTS + Whisper may OOM during pip or inference
7. **Translate subprocess** — first call ~60–90s (Argos/Stanza cold); fixed v0.6.1 to run in `.venv` not global Python

---

## File map (what was added tonight)

```
scripts/stt_worker.py       — persistent Whisper worker
scripts/setup_stt.ps1       — STT install (fixed)
scripts/install_argos_packages.py
services/stt_client.py
services/translate_client.py
api/routes/stt.py           — POST /stt/transcribe, /stt/translate
services/ingest.py          — docx_to_text()
docs/CONTEXT.md             — MVP summary
```

---

## Suggested next session (priority order)

1. Confirm Argos installed + run one transcribe + translate
2. Re-record one book with XTTS warm — verify it's your voice not Edge
3. Add job ETA rough estimate in UI ("~N chunks × 15s")
4. Optional: Tesseract OCR for scans (CPU, slow but local)
5. Optional: explore `huggingface/speech-to-speech` for live WebSocket UX only

---

## Version

**CATTS v0.6** — commit `08e4827` + overnight fixes on `setup_stt.ps1`

Sleep well. The hard part (honest local stack on AMD) is mostly wired — morning is verify + tune RAM/model sizes.
