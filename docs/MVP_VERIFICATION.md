# MVP verification

Date: 2026-07-05

Source checklist: `docs/TARGET.MD`

Follow-up repair pass started after this verification:

- Setup scripts now use `.\.venv\Scripts\python.exe` instead of the broken `py -3` launcher.
- `scripts/setup_api.ps1` was added for API/book dependencies.
- `scripts/check_env.py` was added for repeatable local environment checks.
- `api/routes/jobs.py` now imports `cleanup_job_artifacts`.
- `requirements.txt` was installed into `.venv`.
- Argos config/cache/data was moved into `data/argos_runtime`, and `/stt/translate` now returns `Hola mundo` for `Hello world`.
- `imageio-ffmpeg` was added and the app now finds bundled ffmpeg from `.venv`.
- Audiobook chapter conversion now transcodes single WAV chunks to real MP3 instead of copying WAV bytes to an `.mp3` filename.
- `.env` is now loaded by `config.py`.
- `POST /ocr/image` and `POST /ocr/pdf` were added for configured Unlimited-OCR/SGLang workers.
- XTTS now reports the Coqui CPML/commercial terms requirement through health instead of failing with EOF.
- `POST /stt/transcribe` loads faster-whisper-small and returns 200 for a generated WAV.

## Bottom line

The MVP is not currently verified as working end to end, but the non-TTS base is now much stronger:

- Local API modules, book parsing modules, STT/translation modules, voice modules, database access, and ffmpeg all pass `scripts/check_env.py`.
- The automated test suite passes: `14 passed`.
- Upload/extraction tests cover TXT, DOCX, embedded-text PDF, and EPUB with audio generation disabled.
- `/stt/translate` works locally for EN->ES and returns `Hola mundo` for `Hello world`.
- `/ocr/image` and `/ocr/pdf` exist and fail cleanly with 503 until an OCR worker is configured.

The repo contains a substantial scaffold for the audiobook and voice flows, and the Python dependency split has been repaired. The current local setup still does not meet the full target:

- OCR is not local or Baidu-based; it depends on `CATTS_WORKER_URL` and is currently disabled.
- XTTS is configured as zero-shot voice cloning from a reference sample, not real local user voice training.
- "Virtually indistinguishable from user voice" is not supported by the current docs, code, or model choice.
- Live conversational performance is not verified and is unlikely on this PC with CPU-only XTTS.
- English/Spanish translation now works through the API; only English voice samples are currently present.

## Verification status

Legend:

- PASS: locally checked and working for a narrow case.
- PARTIAL: code path exists, but current setup or feature scope is incomplete.
- FAIL: current repo/setup does not support the requirement.
- UNKNOWN: requires a heavy runtime test or subjective/audio evaluation not completed in this pass.

## I. Book to audiobook

| Requirement | Status | Evidence |
|---|---:|---|
| App can take PDF, DOCX, EPUB, TXT, Markdown | PASS | Automated API tests cover TXT, DOCX, embedded-text PDF, and EPUB with `generate_audio=false`; upload route accepts Markdown too. |
| App can OCR books | PARTIAL | `POST /ocr/pdf` exists and `services/ocr_client.py` supports Unlimited-OCR/SGLang-style workers, but `CATTS_WORKER_URL` is not configured, so OCR returns 503 locally. |
| App can process books ready for audiobook | PASS | `text_processor.process_book(...)` was run locally and produced chapters/chunks from sample chaptered text. |
| App can TTS books into audiobooks | PARTIAL | Job pipeline exists in `services/job_runner.py`, TTS routing exists in `services/tts_client.py`, and packaging exists in `services/audiobook_mux.py`. ffmpeg is available through `imageio-ffmpeg`, and single-chunk chapter MP3 conversion was fixed. Not end-to-end verified because XTTS terms/model readiness are still blocked. |

## II. User voice and live TTS

| Requirement | Status | Evidence |
|---|---:|---|
| App can be trained on user voice | PARTIAL | `api/routes/voices.py` saves voice samples. `services/voice_trainer.py` does not do local model training when `CATTS_WORKER_URL` is unset; it copies the sample to `reference.wav` for XTTS zero-shot cloning. |
| App can take strings and return TTS | PARTIAL | `POST /tts/live` exists and returns audio bytes when TTS is ready. It requires a ready voice reference and working TTS engine. Current health reports XTTS installed but blocked by Coqui terms/model readiness. |
| App can do this performantly like a normal conversation | FAIL | Docs estimate CPU XTTS at about 5-30 seconds per phrase after warmup, with first load around 60 seconds. That is not normal conversational latency. |
| App TTS is virtually indistinguishable from user voice | FAIL | Current docs explicitly describe XTTS zero-shot as sounding like the user, not a studio clone. There is no speaker-similarity benchmark or listening-test evidence in the repo. |
| App can do this via API | PARTIAL | API endpoints exist: `/voices`, `/tts/live`, `/stt/transcribe`, `/stt/translate`, `/jobs/audiobook`. `/health` and `/stt/translate` work in-process from `.venv`; live TTS still has not been verified. |
| App can do English and Spanish | PARTIAL | `lang` is wired through voice, STT, translate, and TTS paths. EN->ES translation works through `/stt/translate`; STT route returns 200 with `lang=en`; XTTS worker allows `en` and `es`. Current saved voice profiles are English only, and Spanish TTS audio is not verified. |

## Bonus

| Requirement | Status | Evidence |
|---|---:|---|
| App can OCR images | PARTIAL | `POST /ocr/image` exists and can call an Unlimited-OCR/SGLang-style worker. It returns 503 until `CATTS_WORKER_URL` is configured. |
| App breaks books into chapters for playback | PASS | `text_processor.split_into_chapters(...)` and `process_book(...)` exist and were locally verified with sample chapter text. UI exposes `chapter_mode`. |

## Assets and local model status

| Asset requirement | Status | Evidence |
|---|---:|---|
| Downloaded TTS that can use user voice | PARTIAL | `coqui-tts`, `torch`, `torchaudio`, and `TTS` are installed in `.venv`; `xtts_tts.available()` returns `True`. The XTTS model cache is not verified and model loading is gated behind explicit Coqui CPML/commercial terms acceptance. |
| TTS virtually indistinguishable from user | FAIL | No evidence. Current implementation uses XTTS zero-shot reference audio, not verified high-fidelity training. |
| TTS runs performantly on Ryzen 5 / RX 6600 / 16 GB RAM | FAIL | `scripts/setup_xtts.ps1` installs CPU-only PyTorch. RX 6600 is not used by this stack. Docs already warn about RAM pressure and 5-30 seconds per phrase after warmup. |
| App stays under 50-60% system CPU/RAM while another platform uses 30-40% | UNKNOWN/LIKELY FAIL | No resource limiter or benchmark exists. CPU-only XTTS inference will likely spike CPU during generation. Needs measured testing after XTTS is actually hot. |
| OCR asset, possibly Baidu OCR | PARTIAL | The likely repo is `baidu/Unlimited-OCR`. It targets NVIDIA CUDA/vLLM/SGLang, not local RX 6600 CPU/AMD inference. CATTS now exposes worker-backed `/ocr/image` and `/ocr/pdf` endpoints compatible with that style of worker. |
| Text processing | PASS | Local `process_book` check passed and the code supports OCR cleanup, chapter detection, language detection fallback, TTS chunking, Markdown output, and plain text output. |

## Commands and checks run

Latest repair-pass validation:

```text
pytest: 14 passed
GET /health: 200
POST /stt/translate Hello world en->es: Hola mundo
POST /stt/transcribe generated WAV: 200, empty transcript expected for tone-only audio
POST /ocr/image without worker: 503 with clear message
POST /ocr/pdf without worker: 503 with clear message
ffmpeg smoke: generated one.mp3, non-silent peak 0.2457
scripts/check_env.py: PASS for API, book modules, voice modules, STT/translate modules, ffmpeg, usable voice, database
scripts/check_env.py: FAIL for OCR and XTTS terms, PARTIAL for XTTS cache
```

Package availability in `.venv` after repair:

```text
fastapi=True
uvicorn=True
multipart=True
fitz=True
ebooklib=True
docx=True
edge_tts=True
argostranslate=True
faster_whisper=True
TTS=True
torch=True
torchaudio=True
```

Package availability in default `python`:

```text
fastapi=True
uvicorn=True
multipart=True
fitz=False
ebooklib=False
docx=False
edge_tts=True
argostranslate=False
faster_whisper=False
TTS=False
torch=False
torchaudio=False
```

Service probes from `.venv`:

```text
stt_available=True
xtts_available=True
translate_available=True
xtts_status={'installed': True, 'ready': False, 'message': 'XTTS installed - model loading (first start ~1 min) or idle'}
```

In-process API health check with default `python`:

```json
{
  "status": "ok",
  "worker_reachable": false,
  "worker_url": "(not set)",
  "ocr_engine": "none",
  "tts_engine": "xtts",
  "stt_engine": "whisper",
  "translate_ready": true,
  "default_voice_id": "1bac924450bc401a",
  "xtts_installed": true,
  "xtts_ready": false
}
```

Text processing smoke check:

```text
Input with two chapter headers produced 2 chapters.
First title: Capitulo 1
First chapter chunks: 1
```

Argos translation smoke check after repair:

```json
{"ok": true, "text": "Hola mundo"}
```

Local model/cache checks:

```text
faster-whisper-small cache exists with about 486 MB of blob files.
XTTS cache directory exists but appears empty.
ffmpeg is available through `imageio-ffmpeg` inside `.venv`.
```

Voice data:

```text
Two voice records exist.
Default voice 1bac924450bc401a has real sample/reference WAV files around 4.3 MB and quality score 93.5.
Voice 94a09c093e2948d7 has 44-byte sample/reference WAV files and appears unusable.
No Spanish voice profile was found.
No audiobook jobs currently exist in the DB.
```

## Required fixes before a real MVP test

1. Start the API from `.venv`.
2. Run `/health` and the diagnostics smoke check.
3. Configure OCR worker if using `baidu/Unlimited-OCR`, or choose a lighter OCR fallback for this PC.
4. Accept or reject Coqui XTTS v2 CPML/commercial terms; set `CATTS_ACCEPT_COQUI_CPML=1` only if accepted.
5. Decide whether "virtually indistinguishable" is a hard requirement. If yes, XTTS zero-shot on CPU is not enough.
6. Benchmark warm and cold `/tts/live` latency on this PC with the interpreting platform running.

## Links currently found in repo docs

Only one external source link was found in the project docs:

- Hugging Face / Cerebras voice AI blog: `https://huggingface.co/blog/cerebras-gemma4-voice-ai`
- Baidu Unlimited-OCR repo: `https://github.com/baidu/Unlimited-OCR`

I did not find a target local TTS model that claims indistinguishable cloning or a benchmark for the Ryzen 5 / RX 6600 / 16 GB RAM target.
