import time



from pathlib import Path



from fastapi import APIRouter, Depends, HTTPException

from fastapi.responses import Response



from api.deps import require_api_key

from api.schemas import HealthResponse, LiveTTSRequest

from config import OCR_ENGINE, WORKER_URL

from db import get_voice, voice_dir

from services.ocr_client import check_worker_health

from services import stt_client, translate_client
from services.tts_client import engine_label, live_tts

from services.voice_default import resolve_default_voice_id

from services.voice_ref import prepare_xtts_reference



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
        stt_engine="whisper" if stt_client.available() else "none",
        translate_ready=translate_client.available(),
        default_voice_id=resolve_default_voice_id(),

    )





def _resolve_ref_audio(voice_id: str) -> Path | None:

    voice = get_voice(voice_id)

    if not voice:

        return None

    if voice.get("artifact_path"):

        ref = Path(voice["artifact_path"])

        if ref.is_file():

            return prepare_xtts_reference(ref)

        nested = ref / "reference.wav"

        if nested.is_file():

            return prepare_xtts_reference(nested)

    vdir = voice_dir(voice_id)

    for name in ("reference.wav", "sample.wav"):

        p = vdir / name

        if p.is_file():

            return prepare_xtts_reference(p)

    return None





@router.post("/tts/live")

async def tts_live(req: LiveTTSRequest, _: None = Depends(require_api_key)):

    words = req.text.split()

    if len(words) > 12:

        raise HTTPException(400, "Live TTS limited to 12 words")

    voice_id = req.voice_id or resolve_default_voice_id()

    if not voice_id:

        raise HTTPException(400, "No voice — train one first or set CATTS_DEFAULT_VOICE_ID")

    t0 = time.perf_counter()

    ref_audio = _resolve_ref_audio(voice_id)

    try:

        audio, engine_used = await live_tts(req.text, voice_id, req.lang, ref_audio=ref_audio)

    except RuntimeError as exc:

        raise HTTPException(503, str(exc)) from exc

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return Response(

        content=audio,

        media_type="audio/wav",

        headers={

            "X-TTS-Latency-Ms": str(elapsed_ms),

            "X-TTS-Engine": engine_used,

        },

    )

