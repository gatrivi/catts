"""GPU worker HTTP service — OCR (Unlimited-OCR) + TTS (GPT-SoVITS) + voice training."""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CATTS GPU Worker", version="0.1.0")

VOICES_ROOT = Path(os.getenv("WORKER_VOICES_DIR", "/data/voices"))
GPT_SOVITS_ROOT = Path(os.getenv("GPT_SOVITS_ROOT", "/opt/GPT-SoVITS"))
OCR_MODE = os.getenv("WORKER_OCR_MODE", "sglang")  # sglang | stub
TTS_MODE = os.getenv("WORKER_TTS_MODE", "stub")  # gptsovits | stub
SGLANG_URL = os.getenv("SGLANG_URL", "http://127.0.0.1:10000")


class LiveTTSBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)
    voice_id: str
    lang: str = "en"


class SynthesizeBody(BaseModel):
    text: str
    text_lang: str = "en"
    voice_id: str = ""
    ref_audio_path: str = ""
    prompt_text: str = ""
    prompt_lang: str = "en"


@app.get("/health")
def health():
    return {
        "status": "ok",
        "ocr_mode": OCR_MODE,
        "tts_mode": TTS_MODE,
        "sglang_url": SGLANG_URL,
    }


@app.post("/ocr/pdf")
async def ocr_pdf_endpoint(
    file: UploadFile = File(...),
    dpi: int = Form(300),
):
    if OCR_MODE == "stub":
        content = await file.read()
        return {
            "text": "[OCR stub] Configure SGLang + Unlimited-OCR for real extraction.",
            "pages": 1,
            "bytes": len(content),
        }

    from services.ocr_client import ocr_pdf

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)
    try:
        text = await ocr_pdf(tmp_path)
        pages = text.count("\n\n") + 1
        return {"text": text, "pages": pages}
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/tts/synthesize")
async def tts_synthesize(body: SynthesizeBody):
    out = Path(tempfile.mktemp(suffix=".wav"))
    if TTS_MODE == "stub":
        from services.tts_client import _stub_wav

        _stub_wav(out, duration_sec=min(0.5 + len(body.text) * 0.02, 8.0))
        return FileResponse(out, media_type="audio/wav", filename="out.wav")

    ref = body.ref_audio_path
    voice_dir = VOICES_ROOT / body.voice_id
    if not ref and voice_dir.exists():
        for name in ("reference.wav", "sample.wav"):
            if (voice_dir / name).exists():
                ref = str(voice_dir / name)
                break

    script = GPT_SOVITS_ROOT / "api_v2.py"
    if not script.exists():
        raise HTTPException(500, "GPT-SoVITS api_v2.py not found on worker")

    # Invoke GPT-SoVITS HTTP if running, else subprocess inference
    import httpx

    gpt_url = os.getenv("GPT_SOVITS_API_URL", "http://127.0.0.1:9880")
    payload = {
        "text": body.text,
        "text_lang": body.text_lang,
        "ref_audio_path": ref,
        "prompt_text": body.prompt_text,
        "prompt_lang": body.prompt_lang,
    }
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(f"{gpt_url}/tts", json=payload)
        if r.status_code == 404:
            raise HTTPException(500, "Start GPT-SoVITS api_v2 on port 9880")
        r.raise_for_status()
        out.write_bytes(r.content)
    return FileResponse(out, media_type="audio/wav", filename="out.wav")


@app.post("/tts/live")
async def tts_live(body: LiveTTSBody):
    if len(body.text.split()) > 12:
        raise HTTPException(400, "Max 12 words for live TTS")
    out = Path(tempfile.mktemp(suffix=".wav"))
    if TTS_MODE == "stub":
        from services.tts_client import _stub_wav

        _stub_wav(out, duration_sec=min(0.3 + len(body.text.split()) * 0.08, 3.0))
        return Response(content=out.read_bytes(), media_type="audio/wav")

    import httpx

    gpt_url = os.getenv("GPT_SOVITS_API_URL", "http://127.0.0.1:9880")
    voice_dir = VOICES_ROOT / body.voice_id
    ref = ""
    for name in ("reference.wav", "sample.wav"):
        if (voice_dir / name).exists():
            ref = str(voice_dir / name)
            break
    payload = {
        "text": body.text,
        "text_lang": body.lang,
        "ref_audio_path": ref,
        "prompt_text": "",
        "prompt_lang": body.lang,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{gpt_url}/tts", json=payload)
        r.raise_for_status()
        return Response(content=r.content, media_type="audio/wav")


@app.post("/voices/train")
async def train_voice(
    sample: UploadFile = File(...),
    voice_id: str = Form(...),
):
    vdir = VOICES_ROOT / voice_id
    vdir.mkdir(parents=True, exist_ok=True)
    dest = vdir / f"sample{Path(sample.filename or '.wav').suffix}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(sample.file, f)

    if TTS_MODE == "stub" or not (GPT_SOVITS_ROOT / "webui.py").exists():
        shutil.copy(dest, vdir / "reference.wav")
        return {"voice_id": voice_id, "status": "ready", "mode": "stub"}

    # Run GPT-SoVITS training pipeline (simplified — full train is long-running)
    train_script = Path(__file__).parent / "scripts" / "train_gptsovits.sh"
    if train_script.exists():
        subprocess.Popen(
            ["bash", str(train_script), voice_id, str(dest)],
            cwd=str(GPT_SOVITS_ROOT),
            env={**os.environ, "VOICE_ID": voice_id, "SAMPLE_PATH": str(dest)},
        )
        return {"voice_id": voice_id, "status": "training", "message": "Training started in background"}

    shutil.copy(dest, vdir / "reference.wav")
    return {"voice_id": voice_id, "status": "ready", "mode": "reference_only"}


def run():
    import uvicorn

    host = os.getenv("WORKER_HOST", "0.0.0.0")
    port = int(os.getenv("WORKER_PORT", "59201"))
    uvicorn.run("worker.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
