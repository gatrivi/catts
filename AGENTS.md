# AGENTS.md

## Cursor Cloud specific instructions

CATTS is a single Python 3.12 FastAPI app (local audiobook + voice TTS/STT tool). CPU-only dev mode is the target here; the GPU worker + docker-compose (`docker/`) profile is NOT used.

### Environment
- Dependencies live in a project-local `.venv` (created by the update script). This is required, not optional: `services/stt_client.py` and `services/translate_client.py` spawn subprocesses via `.venv/bin/python`, so STT/translate silently degrade if `.venv` is missing.
- Installed sets: `requirements.txt` (core API + Kokoro TTS), `requirements-stt.txt` (faster-whisper + Argos), plus `pytest`. `requirements-tts.txt` (XTTS/Coqui `torch`+`transformers`) is intentionally NOT installed — it's heavy and gated by Coqui CPML terms; live TTS uses Kokoro instead, so `xtts_ready:false` in `/health` is expected/fine.
- System `ffmpeg` and `python3.12-venv` are already provisioned in the VM image.

### Running (see README for the canonical commands)
- API + UI: `.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 59200` → UI at `http://127.0.0.1:59200/`, Swagger at `/docs`.
- Kokoro TTS server (default engine, must be running for TTS): `.venv/bin/python scripts/kokoro_server.py` (port 8880). Start it BEFORE relying on `/tts/live` or audiobook audio; `/health` shows `tts_ready`.
- Config is `.env` (copy of `.env.example`); default engine is `CATTS_TTS_ENGINE=kokoro`. `.env`, `.venv/`, and `data/` are gitignored.

### Non-obvious caveats
- First run of the Kokoro server (~300MB), faster-whisper `small` model, and Argos packages download from the network. Kokoro + Whisper download automatically; **Argos EN↔ES must be installed once** via `.venv/bin/python scripts/install_argos_packages.py` (into `data/argos_runtime/`, idempotent) or the translate flow returns errors. This is deliberately kept out of the startup update script (network/brittle).
- Tests: run `.venv/bin/python -m pytest tests/` (scope to `tests/`). A plain `pytest` from the repo root fails collection because `scripts/_kokoro_direct_test.py` matches the `*_test.py` pattern and makes a live HTTP call at import.
- Smoke test needs the repo root on `PYTHONPATH`: `PYTHONPATH=/workspace .venv/bin/python scripts/_smoke_test.py` (checks health + translate + STT + voice + audiobook + live TTS end to end; requires API + Kokoro running).
- Setup `.ps1` scripts under `scripts/` are Windows-only; ignore them on Linux and use the venv + pip flow above.
