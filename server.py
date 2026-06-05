"""CatIntAssist local TTS server — Piper on CPU, port 59125."""

from __future__ import annotations

import io
import logging
import os
import time
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from piper import PiperVoice

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("TTS_PORT", "59125"))
MODELS_DIR = Path(os.environ.get("TTS_MODELS_DIR", Path(__file__).parent / "models"))
ENGINE = "piper"
DEVICE = "cpu"

# lang code -> Piper voice id (medium quality, CPU-friendly)
VOICES: dict[str, str] = {
    "en": os.environ.get("TTS_VOICE_EN", "en_US-lessac-medium"),
    "es": os.environ.get("TTS_VOICE_ES", "es_MX-ald-medium"),
}

_loaded: dict[str, PiperVoice] = {}


def _voice_paths(voice_id: str) -> tuple[Path, Path]:
    onnx = MODELS_DIR / f"{voice_id}.onnx"
    config = MODELS_DIR / f"{voice_id}.onnx.json"
    return onnx, config


def _load_voice(voice_id: str) -> PiperVoice:
    if voice_id in _loaded:
        return _loaded[voice_id]

    onnx, config = _voice_paths(voice_id)
    if not onnx.is_file() or not config.is_file():
        raise FileNotFoundError(
            f"Voice '{voice_id}' not found in {MODELS_DIR}. "
            f"Run: python scripts/download_voices.py"
        )

    t0 = time.perf_counter()
    voice = PiperVoice.load(str(onnx))
    _loaded[voice_id] = voice
    logger.info("Loaded voice %s in %.2fs", voice_id, time.perf_counter() - t0)
    return voice


def _synthesize_wav(voice: PiperVoice, text: str) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        voice.synthesize_wav(text.strip(), wav_file)
    return buf.getvalue()


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    lang: Literal["en", "es"] = "en"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for lang, voice_id in VOICES.items():
        try:
            _load_voice(voice_id)
            logger.info("Preloaded %s -> %s", lang, voice_id)
        except FileNotFoundError as exc:
            logger.warning("Skip preload %s: %s", lang, exc)
    yield


app = FastAPI(title="CatIntAssist TTS", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
def health():
    voices = {}
    for lang, voice_id in VOICES.items():
        onnx, _ = _voice_paths(voice_id)
        voices[lang] = {
            "voice": voice_id,
            "loaded": voice_id in _loaded,
            "onnx_exists": onnx.is_file(),
        }
    return {
        "ok": all(v["onnx_exists"] for v in voices.values()),
        "model": ENGINE,
        "device": DEVICE,
        "port": PORT,
        "voices": voices,
    }


@app.post("/tts")
def tts(req: TTSRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    voice_id = VOICES.get(req.lang)
    if not voice_id:
        raise HTTPException(status_code=400, detail=f"unsupported lang: {req.lang}")

    try:
        voice = _load_voice(voice_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    t0 = time.perf_counter()
    try:
        audio = _synthesize_wav(voice, text)
    except Exception as exc:
        logger.exception("synthesis failed")
        raise HTTPException(status_code=500, detail=f"synthesis failed: {exc}") from exc

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "TTS lang=%s chars=%d latency_ms=%.0f voice=%s",
        req.lang,
        len(text),
        elapsed_ms,
        voice_id,
    )

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={
            "X-TTS-Latency-Ms": f"{elapsed_ms:.0f}",
            "X-TTS-Voice": voice_id,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=PORT, reload=False)
