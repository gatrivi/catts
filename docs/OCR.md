# OCR (token-cheap)

**Read this, not the plan / ocr_client crawl.**

| Mode | Endpoint | Engine | Out |
|---|---|---|---|
| Fast (now) | `POST /ocr/fast` | Tesseract | `data/ocr/<stamp>-fast.md` |
| Batch (books) | `POST /ocr/batch` | OmniRoute vision → fallback Tesseract; or `unlimited` | `data/ocr/<stamp>-batch.md` |

**Env:** `CATTS_OCR_FAST=tesseract` · `CATTS_OCR_BATCH=omniroute|tesseract|unlimited` · `CATTS_OMNIROUTE_URL=http://127.0.0.1:20128/v1` · optional `CATTS_OCR_FAST_POLISH=1` · legacy `CATTS_OCR_ENGINE=unlimited` + `CATTS_WORKER_URL`.

**Batch form:** PDF alone, or N images; optional `titles` (`a|b|c` or JSON list) → `## title` between pages. Legacy `/ocr/image` `/ocr/pdf` → batch.

**Jobs:** scanned PDF → OCR page 1 first → `manuscript_partial.md` + `ocr_buffer.txt` → rest pages → `process_book` → TTS. Need `batch_configured()`.

**Code:** `services/ocr_client.py` · `api/routes/ocr.py` · job path in `services/job_runner.py`.

**RAM:** Tesseract stays light. Do not leave Unlimited/OmniRoute/TTS hot after batch (`docs/HEAVY_PROCESSES.md`).

**Quality note:** Tesseract weak on poem screenshots; use batch+OmniRoute when hub is up.

## Candidate: OvisOCR2 (not wired)
- https://huggingface.co/ATH-MaaS/OvisOCR2 — 0.8B page→Markdown (OmniDocBench SOTA).
- Needs **vLLM + CUDA** (their snip: `vllm==0.22.1`). **Not for this AMD Win box** (no CUDA; 16 GB RAM too tight with Cursor).
- Revisit on **NVIDIA cloud** or when we have a remote GPU worker. Until then: batch=`omniroute` / tesseract.
