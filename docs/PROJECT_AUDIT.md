# CATTS project audit

Date: 2026-07-05

## What this project is

CATTS is a local FastAPI + static HTML app for turning books into audio and for experimenting with local voice workflows on a CPU/AMD Windows machine.

The core user flows are:

1. Upload a PDF, EPUB, DOCX, TXT, or Markdown file.
2. Extract text, detect/split chapters, and write manuscript artifacts.
3. Optionally render chapter audio with a selected voice.
4. Save voice samples for XTTS reference audio.
5. Run local STT with faster-whisper.
6. Translate English/Spanish offline with Argos Translate.
7. Generate short live voice-cloned TTS snippets with XTTS.

The main web app is `api.main:app`. The UI is `static/index.html`.

## Runtime shape

Important paths:

- `api/main.py` creates the FastAPI app, mounts the static UI, includes routes, initializes the DB, and starts warmup threads for XTTS and STT.
- `api/routes/jobs.py` handles audiobook jobs, manuscript downloads, chapter audio, retries, regeneration, cleanup, and folder reveal actions.
- `api/routes/voices.py` handles saving voice samples, evaluating samples, renaming voices, and exposing sample files.
- `api/routes/stt.py` handles transcription and translation endpoints.
- `api/routes/diagnostics.py` exposes an in-app smoke check.
- `services/job_runner.py` is the async queue for audiobook and voice jobs.
- `services/ingest.py` extracts text from PDF, EPUB, DOCX, TXT, and Markdown.
- `services/tts_client.py` chooses XTTS, Chatterbox, GPT-SoVITS, Edge TTS, or a silent placeholder fallback.
- `services/xtts_tts.py` starts a persistent XTTS worker from `.venv`.
- `services/stt_client.py` starts a persistent faster-whisper worker from `.venv`.
- `services/translate_client.py` runs Argos translation through `.venv`.
- `db.py` stores jobs and voices in SQLite under `data/catts.db`.

Data layout:

- `data/jobs/<job_id>/` contains uploaded source files, extracted text, chapter metadata, manuscript files, chapter audio, and packaged audiobook output.
- `data/voices/<voice_id>/` contains saved voice samples and reference audio.
- `chapters/` is used by the older CLI path in `main.py`, separate from the web job pipeline.

## How it is supposed to run

The intended command is:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 59200
```

Open:

```text
http://127.0.0.1:59200/
```

Use the explicit `.venv` Python. This keeps the web API and local model workers in the same project-local Python environment.

## Current confirmed problems

### 1. Python environment mismatch was the first blocker

There are two relevant Python environments:

- Repo `.venv`: has the AI/audio packages such as `argostranslate`, `coqui-tts`, `torch`, and faster-whisper-related packages.
- Default `python`: points to `C:\Users\DevTrivi\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe` and can import FastAPI, but does not have the local model stack.

Repair pass update: `requirements.txt` has now been installed into `.venv`, and `scripts/check_env.py` reports PASS for API, book, voice, and STT/translate module groups. Use `.venv` as the runtime from this point forward.

Before repair, the repo `.venv` could not start the API because it was missing base web packages:

- `fastapi`
- `uvicorn`
- `python-multipart`
- likely other packages from `requirements.txt`

Observed checks:

```powershell
.\.venv\Scripts\python.exe -c "import fastapi"
# ModuleNotFoundError: No module named 'fastapi'

.\.venv\Scripts\python.exe -c "import uvicorn"
# ModuleNotFoundError: No module named 'uvicorn'

.\.venv\Scripts\python.exe -c "import multipart"
# ModuleNotFoundError: No module named 'multipart'
```

The documented command also fails:

```powershell
py -3 --version
# No installed Python found!
```

This was the first issue to fix before deeper debugging.

### 2. Setup scripts previously used a broken launcher

Earlier setup docs and scripts used:

```powershell
py -3 -m pip install -r requirements.txt
```

On this machine that command cannot work because `py -3` is unavailable. Active setup scripts have been updated to use:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. XTTS/STT worker readiness is separate from API import

The API can import under the default Python, and an in-process `/health` request returned HTTP 200. However, that does not mean the full app is ready.

The health payload reported:

```json
{
  "status": "ok",
  "worker_reachable": false,
  "worker_url": "(not set)",
  "ocr_engine": "none",
  "tts_engine": "xtts",
  "stt_engine": "whisper",
  "translate_ready": true,
  "xtts_installed": true,
  "xtts_ready": false
}
```

Interpretation:

- API code can load.
- OCR worker is not configured.
- Translate appears installed in `.venv`.
- STT appears installed enough for the health check.
- XTTS appears installed but the persistent model worker was not hot/ready during the check.

### 4. Cleanup endpoint import bug is fixed

`api/routes/jobs.py` now imports `cleanup_job_artifacts(...)` from `services/job_cleanup.py`. This was a real blocker for cleanup endpoints before the repair pass.

### 5. `rg` is broken in this shell

`rg --files` failed with:

```text
No application is associated with the specified file for this operation
```

Use PowerShell `Get-ChildItem`, `Select-String`, or fix the local ripgrep installation before relying on `rg`.

## Known constraints

- Full audiobook generation on CPU can be slow.
- XTTS first load can take around a minute and uses significant memory.
- faster-whisper also uses significant memory.
- Running XTTS and Whisper together on a 16 GB RAM system can cause swapping or failures.
- Scanned PDFs need OCR; local embedded-text PDF extraction will reject scanned PDFs with little text.
- ffmpeg is now available through `imageio-ffmpeg` in `.venv`; system `ffmpeg` is still not installed.
- `CATTS_API_KEY` is optional. If set, UI and smoke tests must send `X-API-Key`.

## Short architecture advice

`.venv` is the project-local Python install. It is not an extra API or service. The FastAPI server, upload handlers, OCR client, TTS workers, and STT workers all import Python packages at runtime, so the same environment needs the web dependencies and the model dependencies.

External APIs can handle OCR or TTS only after the local API server is running and has code/configuration for those external services. They do not remove the need for a working local Python environment.

Baidu OCR should not be cloned blindly. First identify the exact repo and whether it exposes one of these useful interfaces:

1. A Python package we can import from `services/ocr_client.py`.
2. A local HTTP server we can call like the current `CATTS_WORKER_URL` pattern.
3. A CLI that accepts images/PDFs and returns text reliably.

If it needs cloud credentials, document the credentials and cost/latency tradeoff before wiring it into the MVP.

Follow-up: the likely repo is `https://github.com/baidu/Unlimited-OCR`. It targets NVIDIA CUDA through Transformers/vLLM/SGLang. CATTS now has `/ocr/image` and `/ocr/pdf` endpoints that can call an Unlimited-OCR/SGLang-style worker through `CATTS_WORKER_URL`, but this is not a local RX 6600/CPU solution.

## Suggested next repair order

1. Start the API from `.venv`.
2. Run `/health` and the diagnostics smoke check.
3. Verify one cheap browser flow first: upload a TXT file with `generate_audio=false`.
4. Verify voice sample save in the UI.
5. Verify STT with real microphone/user audio.
6. Decide OCR architecture: remote Unlimited-OCR/SGLang worker, cloud OCR, or lighter local fallback.
7. Decide whether to accept Coqui CPML/commercial terms before any XTTS model download/load.
8. Verify XTTS/live TTS last, because it is slowest and most memory-sensitive.

## Recommended agent workflow

Use a lighter model for mapping, documentation, and low-risk bug discovery. Use a stronger model for edits that require judgment across the app, especially:

- dependency/environment repair,
- async job behavior,
- audio fallback behavior,
- UI state correctness,
- diagnosing model worker failures,
- anything involving generated audio correctness.

Keep the current lightweight pass focused on making the project legible: document what exists, what fails, and the order of operations. Then hand the stronger model a short, concrete repair list rather than asking it to rediscover the repo from scratch.
