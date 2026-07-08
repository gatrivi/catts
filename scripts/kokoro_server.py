"""Minimal Kokoro OpenAI-compatible TTS server for CATTS (CPU, no Docker)."""

from __future__ import annotations

import io
import logging
import os
import sys
import threading
from pathlib import Path

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._local_cache import configure_project_cache

configure_project_cache()

logger = logging.getLogger("kokoro_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HOST = os.getenv("KOKORO_HOST", "127.0.0.1")
PORT = int(os.getenv("KOKORO_PORT", "8880"))

VOICES = [
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore",
    "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael",
    "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
]

_pipeline = None
_pipeline_lock = threading.Lock()


def _get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline
        logger.info("Loading Kokoro pipeline (first run may download ~300MB model)")
        from kokoro import KPipeline

        _pipeline = KPipeline(lang_code="a")
        logger.info("Kokoro ready")
        return _pipeline


class SpeechRequest(BaseModel):
    model: str = "kokoro"
    input: str = Field(..., min_length=1)
    voice: str = "af_bella"
    response_format: str = "wav"
    speed: float = 1.0


app = FastAPI(title="CATTS Kokoro", version="1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/audio/voices")
def list_voices():
    return {"voices": [{"id": voice, "name": voice} for voice in VOICES]}


@app.post("/v1/audio/speech")
def create_speech(req: SpeechRequest):
    text = req.input.strip()
    if not text:
        raise HTTPException(400, "empty input")

    voice = (req.voice or "af_bella").strip()
    try:
        pipeline = _get_pipeline()
        chunks: list[np.ndarray] = []
        for _i, (_gs, _ps, audio) in enumerate(
            pipeline(text, voice=voice, speed=max(0.5, min(req.speed, 2.0)))
        ):
            chunks.append(np.asarray(audio, dtype=np.float32))
        if not chunks:
            raise RuntimeError("no audio generated")
        merged = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
        buf = io.BytesIO()
        sf.write(buf, merged, 24000, format="WAV", subtype="PCM_16")
        return Response(content=buf.getvalue(), media_type="audio/wav")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("speech failed")
        raise HTTPException(500, str(exc)[:400]) from exc


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
