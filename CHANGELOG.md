# Changelog

## v0.7.3 — 2026-07-30

- **Fish Speech + ZLUDA** engine (`CATTS_TTS_ENGINE=fish`) for AMD GPUs (RX 6600)
- Client: `services/fish_tts.py` → local `POST /v1/tts`
- Scripts: `setup_fish_zluda.ps1`, `start_fish_api.ps1`
- Docs: `docs/FISH_ZLUDA_RX6600.md`, updated `TTS_MODEL_DECISION.md`
- `CATTS_TTS_SPEED` (default `0.9` ≈ 10% slower): Fish via ffmpeg atempo, Kokoro via API `speed`

## v0.7 — 2026-07-03

### UX
- Two clear flows: **(1) Audiobook** upload → process → play, **(2) Your voice** sample → script match → live interpreting
- Sticky **activity bar** (TTS / STT / books / voices background status)
- Subtle page background; primary panels open by default
- Book upload and voice save show status boxes (busy / ok / error)

### Voices
- Cards show **sample present**, size, duration, and a **script-match status bar**
- After save, **STT** (Whisper) scores how well the recording matches the training script (EN/ES)
- **Check script** button re-runs evaluation (`POST /voices/{id}/evaluate`)
- Quality stored in `data/voices/<id>/quality.json`

### Docs
- Updated `docs/CONTEXT.md`
- This changelog

## v0.6.2 — 2026-07-03

- Live TTS / Hear sample status boxes with elapsed timer
- Stop list refresh from wiping the player mid-play
- Health: `xtts_ready`, `xtts_message`

## v0.6 — 2026-07-03

- Local STT (faster-whisper), Argos EN↔ES translate, DOCX ingest
- No silent Edge fallback when a voice is selected

## v0.5.x — 2026-07-03

- Waveform player, XTTS persistent worker, default voice
