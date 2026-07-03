import time

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from api.deps import require_api_key
from api.schemas import HealthResponse, LiveTTSRequest
from config import OCR_ENGINE, TTS_ENGINE, WORKER_URL
from db import get_voice, voice_dir
from services.ocr_client import check_worker_health
from services.tts_client import engine_label, live_tts

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    worker_ok = await check_worker_health()
    return HealthResponse(
        status="ok",
        worker_reachable=worker_ok,
        worker_url=WORKER_URL or "(not set)",
        ocr_engine=OCR_ENGINE,
        tts_engine=engine_label(),
    )


@router.post("/tts/live")
async def tts_live(req: LiveTTSRequest, _: None = Depends(require_api_key)):
    words = req.text.split()
    if len(words) > 12:
        raise HTTPException(400, "Live TTS limited to 12 words")
    t0 = time.perf_counter()
    ref_audio = None
    voice = get_voice(req.voice_id)
    if voice and voice.get("artifact_path"):
        ref = Path(voice["artifact_path"])
        if ref.is_file():
            ref_audio = ref
        elif (ref / "reference.wav").exists():
            ref_audio = ref / "reference.wav"
    elif voice:
        vdir = voice_dir(req.voice_id)
        for name in ("reference.wav", "sample.wav"):
            p = vdir / name
            if p.exists():
                ref_audio = p
                break
    audio = await live_tts(req.text, req.voice_id, req.lang, ref_audio=ref_audio)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"X-TTS-Latency-Ms": str(elapsed_ms)},
    )
